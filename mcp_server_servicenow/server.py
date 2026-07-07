"""
ServiceNow MCP Server

This module provides a Model Context Protocol (MCP) server that interfaces with ServiceNow.
It allows AI agents to access and manipulate ServiceNow data through a secure API.
"""

import os
import json
import asyncio
import logging
import re
import time
import hashlib
import contextvars
from urllib.parse import urlparse
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Literal, Tuple

import requests
import httpx
import jwt
from pydantic import BaseModel, Field, field_validator
from jwt import PyJWKClient

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

# Request-scoped assertion used by OBO exchange. This prevents cross-request leakage.
_request_user_assertion_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_user_assertion",
    default=None,
)
_request_auth_state_var: contextvars.ContextVar[Optional["RequestAuthState"]] = contextvars.ContextVar(
    "request_auth_state",
    default=None,
)


@dataclass(frozen=True)
class RequestAuthState:
    """Validated request-scoped auth state for delegated OBO flows."""

    user_assertion: str
    claims: Dict[str, Any]


def _get_request_user_assertion() -> Optional[str]:
    """Read the current request-scoped user assertion token, if available."""
    return _request_user_assertion_var.get()


def _get_request_auth_state() -> Optional[RequestAuthState]:
    """Read the current request-scoped validated auth state, if available."""
    return _request_auth_state_var.get()


def _extract_user_assertion_from_ctx(ctx: Optional[Context]) -> Optional[str]:
    """Extract bearer token from MCP request context transport metadata.

    Priority:
    1) Authorization header from the active request context.
    2) Auth middleware context token (if FastMCP auth middleware is enabled).
    """
    if ctx is not None:
        try:
            request = ctx.request_context.request
            if request is not None:
                headers = getattr(request, "headers", None)
                if headers is not None and hasattr(headers, "get"):
                    auth_header = headers.get("authorization")
                    if auth_header and isinstance(auth_header, str) and auth_header.lower().startswith("bearer "):
                        return auth_header.split(" ", 1)[1].strip()
        except Exception:
            # Fall through to middleware-backed token lookup.
            pass

    try:
        from mcp.server.auth.middleware.auth_context import get_access_token

        access_token = get_access_token()
        if access_token and access_token.token:
            return str(access_token.token).strip()
    except Exception:
        pass

    return None


def _split_csv_values(raw_value: Optional[str]) -> List[str]:
    """Parse a comma-separated config string into a normalized list."""
    if not raw_value:
        return []

    return [value.strip() for value in raw_value.split(",") if value.strip()]


class IncomingTokenValidationError(RuntimeError):
    """Raised when an incoming OBO assertion token is missing or invalid."""


class EntraTokenValidator:
    """Validate incoming Entra access tokens for issuer, audience, signature, and expiry."""

    def __init__(
        self,
        tenant_id: str,
        expected_audiences: List[str],
        expected_issuers: Optional[List[str]] = None,
        jwks_uri: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.expected_audiences = expected_audiences
        normalized_tenant = tenant_id.strip("/")
        self.expected_issuers = expected_issuers or [
            f"https://login.microsoftonline.com/{normalized_tenant}/v2.0",
            f"https://sts.windows.net/{normalized_tenant}/",
        ]
        self.jwks_client = PyJWKClient(
            jwks_uri or f"https://login.microsoftonline.com/{normalized_tenant}/discovery/v2.0/keys"
        )

    def validate(self, token: str) -> Dict[str, Any]:
        """Validate token signature and core claims, returning decoded claims on success."""
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=self.expected_audiences,
                options={
                    "require": ["exp", "iss", "aud"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise IncomingTokenValidationError(
                "Incoming user token validation failed. Verify issuer, audience, signature, and expiry."
            ) from exc
        except Exception as exc:
            raise IncomingTokenValidationError(
                "Unable to validate incoming user token against Entra signing keys."
            ) from exc

        issuer = str(claims.get("iss", "")).strip()
        if issuer not in self.expected_issuers:
            raise IncomingTokenValidationError(
                "Incoming user token issuer is not allowed for this tenant configuration."
            )

        token_tenant = str(claims.get("tid", "")).strip()
        if token_tenant and token_tenant != self.tenant_id:
            raise IncomingTokenValidationError(
                "Incoming user token tenant does not match configured OBO tenant."
            )

        if not claims.get("oid") and not claims.get("sub"):
            raise IncomingTokenValidationError(
                "Incoming user token is missing subject identity required for delegated access."
            )

        return claims

# ServiceNow API models
class IncidentState(int, Enum):
    NEW = 1
    IN_PROGRESS = 2 
    ON_HOLD = 3
    RESOLVED = 6
    CLOSED = 7
    CANCELED = 8

class IncidentPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MODERATE = 3
    LOW = 4
    PLANNING = 5

class IncidentUrgency(int, Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

class IncidentImpact(int, Enum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3

class IncidentCreate(BaseModel):
    """Model for creating a new incident"""
    short_description: str = Field(..., description="A brief description of the incident")
    description: str = Field(..., description="A detailed description of the incident")
    caller_id: Optional[str] = Field(None, description="The sys_id or name of the caller")
    category: Optional[str] = Field(None, description="The incident category")
    subcategory: Optional[str] = Field(None, description="The incident subcategory")
    urgency: Optional[IncidentUrgency] = Field(IncidentUrgency.MEDIUM, description="The urgency of the incident")
    impact: Optional[IncidentImpact] = Field(IncidentImpact.MEDIUM, description="The impact of the incident")
    assignment_group: Optional[str] = Field(None, description="The sys_id or name of the assignment group")
    assigned_to: Optional[str] = Field(None, description="The sys_id or name of the assignee")

class IncidentUpdate(BaseModel):
    """Model for updating an existing incident"""
    short_description: Optional[str] = Field(None, description="A brief description of the incident")
    description: Optional[str] = Field(None, description="A detailed description of the incident")
    caller_id: Optional[str] = Field(None, description="The sys_id or name of the caller")
    category: Optional[str] = Field(None, description="The incident category")
    subcategory: Optional[str] = Field(None, description="The incident subcategory")
    urgency: Optional[IncidentUrgency] = Field(None, description="The urgency of the incident")
    impact: Optional[IncidentImpact] = Field(None, description="The impact of the incident")
    state: Optional[IncidentState] = Field(None, description="The state of the incident")
    assignment_group: Optional[str] = Field(None, description="The sys_id or name of the assignment group")
    assigned_to: Optional[str] = Field(None, description="The sys_id or name of the assignee")
    work_notes: Optional[str] = Field(None, description="Work notes to add to the incident (internal)")
    comments: Optional[str] = Field(None, description="Customer visible comments to add to the incident")
    
    @field_validator('work_notes', 'comments')
    @classmethod
    def validate_not_empty(cls, v):
        if v is not None and v.strip() == '':
            raise ValueError("Cannot be an empty string")
        return v

    class Config:
        use_enum_values = True
        
class QueryOptions(BaseModel):
    """Options for querying ServiceNow records"""
    limit: int = Field(10, description="Maximum number of records to return", ge=1, le=1000)
    offset: int = Field(0, description="Number of records to skip", ge=0)
    fields: Optional[List[str]] = Field(None, description="List of fields to return")
    query: Optional[str] = Field(None, description="ServiceNow encoded query string")
    order_by: Optional[str] = Field(None, description="Field to order results by")
    order_direction: Optional[Literal["asc", "desc"]] = Field("desc", description="Order direction")

class Authentication:
    """Base class for ServiceNow authentication methods"""
    
    async def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for ServiceNow API requests"""
        raise NotImplementedError("Subclasses must implement this method")

class BasicAuth(Authentication):
    """Basic authentication for ServiceNow"""
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        
    async def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for ServiceNow API requests"""
        return {}
    
    def get_auth(self) -> tuple:
        """Get authentication tuple for requests"""
        return (self.username, self.password)

class TokenAuth(Authentication):
    """Token authentication for ServiceNow"""
    
    def __init__(self, token: str):
        self.token = token
        
    async def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for ServiceNow API requests"""
        return {"Authorization": f"Bearer {self.token}"}
    
    def get_auth(self) -> None:
        """Get authentication tuple for requests"""
        return None

class OAuthAuth(Authentication):
    """OAuth authentication for ServiceNow"""
    
    def __init__(self, client_id: str, client_secret: str, username: str, password: str, 
                 instance_url: str, token: Optional[str] = None, refresh_token: Optional[str] = None,
                 token_expiry: Optional[float] = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.instance_url = instance_url
        self.token = token
        self.refresh_token = refresh_token
        self.token_expiry = token_expiry
        
    async def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for ServiceNow API requests"""
        if self.token is None or (self.token_expiry and time.time() > self.token_expiry):
            await self.refresh()
            
        return {"Authorization": f"Bearer {self.token}"}
    
    def get_auth(self) -> None:
        """Get authentication tuple for requests"""
        return None
        
    async def refresh(self):
        """Refresh the OAuth token"""
        if self.refresh_token:
            # Try refresh flow first
            data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token
            }
        else:
            # Fall back to password flow
            data = {
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password
            }
            
        token_url = f"{self.instance_url}/oauth_token.do"
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            result = response.json()
            
            self.token = result["access_token"]
            self.refresh_token = result.get("refresh_token")
            expires_in = result.get("expires_in", 1800)  # Default 30 minutes
            self.token_expiry = time.time() + float(expires_in)


class EntraOBOAuth(Authentication):
    """Microsoft Entra OAuth On-Behalf-Of authentication for downstream APIs."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user_assertion: Optional[str],
        scope: str,
        token_endpoint: Optional[str] = None,
        allow_static_assertion: bool = False,
        expected_audiences: Optional[List[str]] = None,
        expected_issuers: Optional[List[str]] = None,
        cache_safety_buffer_seconds: int = 60,
        token: Optional[str] = None,
        token_expiry: Optional[float] = None,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_assertion = user_assertion
        self.scope = scope
        self.token_endpoint = token_endpoint or f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.allow_static_assertion = allow_static_assertion
        self.cache_safety_buffer_seconds = cache_safety_buffer_seconds
        self.token = token
        self.token_expiry = token_expiry
        self._token_cache: Dict[str, Tuple[str, float]] = {}
        self._validator = EntraTokenValidator(
            tenant_id=tenant_id,
            expected_audiences=expected_audiences or [client_id],
            expected_issuers=expected_issuers,
        )

    def validate_user_assertion(self, user_assertion: str) -> Dict[str, Any]:
        """Validate the incoming user assertion before any downstream token exchange."""
        return self._validator.validate(user_assertion)

    def bind_request_auth(self, user_assertion: Optional[str]) -> Tuple[Optional[contextvars.Token], Optional[contextvars.Token]]:
        """Validate and bind request-scoped auth state for the current downstream call path."""
        assertion_value = user_assertion
        claims = None

        if assertion_value:
            claims = self.validate_user_assertion(assertion_value)
        elif self.allow_static_assertion and self.user_assertion:
            assertion_value = self.user_assertion
            claims = self.validate_user_assertion(assertion_value)
        else:
            raise IncomingTokenValidationError(
                "Missing incoming user token for OBO exchange. Provide an Authorization bearer token on the MCP request."
            )

        assertion_token = _request_user_assertion_var.set(assertion_value)
        auth_state_token = _request_auth_state_var.set(RequestAuthState(assertion_value, claims))
        return assertion_token, auth_state_token

    def reset_request_auth(
        self,
        assertion_token: Optional[contextvars.Token],
        auth_state_token: Optional[contextvars.Token],
    ) -> None:
        """Clear request-scoped auth state after downstream call completion."""
        if auth_state_token is not None:
            _request_auth_state_var.reset(auth_state_token)
        if assertion_token is not None:
            _request_user_assertion_var.reset(assertion_token)

    def _build_cache_key(self, claims: Dict[str, Any]) -> str:
        """Create a non-reversible cache key scoped to user identity and downstream audience tuple."""
        subject = str(claims.get("oid") or claims.get("sub") or "")
        tenant = str(claims.get("tid") or self.tenant_id)
        cache_material = f"{tenant}|{subject}|{self.scope}|{self.token_endpoint}"
        return hashlib.sha256(cache_material.encode("utf-8")).hexdigest()

    def _get_cached_token(self, cache_key: str) -> Optional[Tuple[str, float]]:
        """Return a cached token only when it remains outside the safety buffer."""
        cached = self._token_cache.get(cache_key)
        if not cached:
            return None

        token_value, expiry = cached
        if time.time() >= (expiry - self.cache_safety_buffer_seconds):
            self._token_cache.pop(cache_key, None)
            return None

        return token_value, expiry

    async def get_headers(self) -> Dict[str, str]:
        """Get bearer token headers for ServiceNow API requests via OBO exchange."""
        auth_state = _get_request_auth_state()

        if auth_state is not None:
            cache_key = self._build_cache_key(auth_state.claims)
            cached = self._get_cached_token(cache_key)
            if cached is not None:
                token_value, expiry = cached
                return {"Authorization": f"Bearer {token_value}"}

            await self.refresh(auth_state=auth_state)
            cached = self._get_cached_token(cache_key)
            if cached is None:
                raise RuntimeError("OBO token acquisition failed to populate the delegated token cache")

            token_value, expiry = cached
            self.token = token_value
            self.token_expiry = expiry
            return {"Authorization": f"Bearer {token_value}"}

        if self.token is None or (self.token_expiry and time.time() >= (self.token_expiry - self.cache_safety_buffer_seconds)):
            await self.refresh()

        return {"Authorization": f"Bearer {self.token}"}

    def get_auth(self) -> None:
        """Get authentication tuple for requests."""
        return None

    async def refresh(self, auth_state: Optional[RequestAuthState] = None):
        """Exchange incoming user assertion for downstream access token using OBO flow."""
        active_auth_state = auth_state or _get_request_auth_state()
        user_assertion = active_auth_state.user_assertion if active_auth_state else _get_request_user_assertion()
        cache_key = self._build_cache_key(active_auth_state.claims) if active_auth_state else None

        if cache_key:
            cached = self._get_cached_token(cache_key)
            if cached is not None:
                self.token, self.token_expiry = cached
                return

        if not user_assertion and self.allow_static_assertion:
            user_assertion = self.user_assertion
            if user_assertion:
                self.validate_user_assertion(user_assertion)

        if not user_assertion:
            raise RuntimeError(
                "Missing user assertion in active request context for OBO exchange. "
                "Provide Authorization: Bearer token on transport request, or explicitly enable static assertion mode for local testing."
            )

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "requested_token_use": "on_behalf_of",
            "assertion": user_assertion,
            "scope": self.scope,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.token_endpoint, data=data)
            response.raise_for_status()
            result = response.json()

            access_token = result.get("access_token")
            if not access_token:
                raise RuntimeError("OBO token exchange succeeded but no access_token was returned")

            expires_in = result.get("expires_in", 3600)
            expiry = time.time() + float(expires_in)
            self.token = access_token
            self.token_expiry = expiry

            if cache_key:
                self._token_cache[cache_key] = (access_token, expiry)

class ServiceNowClient:
    """Client for interacting with ServiceNow API"""
    
    def __init__(self, instance_url: str, auth: Authentication):
        self.instance_url = instance_url.rstrip('/')
        self.auth = auth
        self.client = httpx.AsyncClient()

    def _safe_host(self) -> str:
        """Return host only for diagnostics without exposing secrets."""
        try:
            return urlparse(self.instance_url).netloc or self.instance_url
        except Exception:
            return self.instance_url

    def _http_error_detail(self, e: httpx.HTTPStatusError) -> str:
        """Build a user-friendly HTTP error message for common ServiceNow failures."""
        response = e.response
        status = response.status_code
        location = response.headers.get("Location", "")
        body_preview = (response.text or "").strip().replace("\n", " ")[:300]
        host = self._safe_host()

        if status in (301, 302, 303, 307, 308):
            if "login.do" in location or "session_timeout.do" in location:
                return (
                    f"ServiceNow redirected to login/session timeout (HTTP {status}) on host '{host}'. "
                    "This usually means authentication failed or credentials are missing. "
                    f"Redirect target: {location}"
                )
            return (
                f"Unexpected redirect from ServiceNow (HTTP {status}) on host '{host}'. "
                f"Redirect target: {location}"
            )

        if status in (401, 403):
            return (
                f"ServiceNow authentication/authorization failed (HTTP {status}) on host '{host}'. "
                "Verify SERVICENOW_USERNAME/SERVICENOW_PASSWORD or token permissions."
            )

        return (
            f"ServiceNow API error (HTTP {status}) on host '{host}'. "
            f"Response preview: {body_preview}"
        )
        
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        
    async def request(self, method: str, path: str, 
                    params: Optional[Dict[str, Any]] = None,
                    json_data: Optional[Dict[str, Any]] = None,
                    ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Make a request to the ServiceNow API"""
        url = f"{self.instance_url}{path}"
        assertion_token = None
        auth_state_token = None

        if isinstance(self.auth, EntraOBOAuth):
            assertion = _extract_user_assertion_from_ctx(ctx)
            assertion_token, auth_state_token = self.auth.bind_request_auth(assertion)

        try:
            headers = await self.auth.get_headers()
            headers["Accept"] = "application/json"
        
            if isinstance(self.auth, BasicAuth):
                auth = self.auth.get_auth()
            else:
                auth = None
            
            response = await self.client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                auth=auth
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            detail = self._http_error_detail(e)
            logger.error(detail)
            raise RuntimeError(detail) from e
        except httpx.RequestError as e:
            host = self._safe_host()
            detail = (
                f"Network error connecting to ServiceNow host '{host}': {str(e)}. "
                "Check SERVICENOW_INSTANCE_URL, DNS/VPN connectivity, and proxy settings."
            )
            logger.error(detail)
            raise RuntimeError(detail) from e
        except IncomingTokenValidationError as e:
            detail = str(e)
            logger.error(detail)
            raise RuntimeError(detail) from e
        finally:
            if isinstance(self.auth, EntraOBOAuth):
                self.auth.reset_request_auth(assertion_token, auth_state_token)
            
    async def get_record(self, table: str, sys_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Get a record by sys_id"""
        if table == "incident" and sys_id.startswith("INC"):
            # This is an incident number, not a sys_id
            logger.warning(f"Attempted to use get_record with incident number instead of sys_id: {sys_id}")
            logger.warning("Redirecting to get_incident_by_number method")
            result = await self.get_incident_by_number(sys_id, ctx=ctx)
            if result:
                return {"result": result}
            else:
                raise ValueError(f"Incident not found: {sys_id}")
        return await self.request("GET", f"/api/now/table/{table}/{sys_id}", ctx=ctx)
        
    async def get_records(self, table: str, options: QueryOptions = None, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Get records with query options"""
        if options is None:
            options = QueryOptions()
            
        params = {
            "sysparm_limit": options.limit,
            "sysparm_offset": options.offset
        }
        
        if options.fields:
            params["sysparm_fields"] = ",".join(options.fields)
            
        if options.query:
            params["sysparm_query"] = options.query
            
        if options.order_by:
            direction = "desc" if options.order_direction == "desc" else "asc"
            params["sysparm_order_by"] = f"{options.order_by}^{direction}"
            
        return await self.request("GET", f"/api/now/table/{table}", params=params, ctx=ctx)
    
    async def create_record(self, table: str, data: Dict[str, Any], ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Create a new record"""
        return await self.request("POST", f"/api/now/table/{table}", json_data=data, ctx=ctx)
        
    async def update_record(self, table: str, sys_id: str, data: Dict[str, Any], ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Update an existing record"""
        return await self.request("PUT", f"/api/now/table/{table}/{sys_id}", json_data=data, ctx=ctx)
        
    async def delete_record(self, table: str, sys_id: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Delete a record"""
        return await self.request("DELETE", f"/api/now/table/{table}/{sys_id}", ctx=ctx)
        
    async def get_incident_by_number(self, number: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Get an incident by its number"""
        result = await self.request("GET", f"/api/now/table/incident", 
                                  params={"sysparm_query": f"number={number}", "sysparm_limit": 1},
                                  ctx=ctx)
        if result.get("result") and len(result["result"]) > 0:
            return result["result"][0]
        return None
        
    async def search(self, query: str, table: str = "incident", limit: int = 10, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Search for records using text query"""
        return await self.request("GET", f"/api/now/table/{table}", 
                                params={"sysparm_query": f"123TEXTQUERY321={query}", "sysparm_limit": limit},
                                ctx=ctx)
                                
    async def get_available_tables(self, ctx: Optional[Context] = None) -> List[str]:
        """Get a list of available tables"""
        result = await self.request("GET", "/api/now/table/sys_db_object", 
                                  params={"sysparm_fields": "name,label", "sysparm_limit": 100},
                                  ctx=ctx)
        return result.get("result", [])
        
    async def get_table_schema(self, table: str, ctx: Optional[Context] = None) -> Dict[str, Any]:
        """Get the schema for a table"""
        result = await self.request("GET", f"/api/now/ui/meta/{table}", ctx=ctx)
        return result


class ScriptUpdateModel(BaseModel):
    """Model for updating a ServiceNow script"""
    name: str = Field(..., description="The name of the script")
    script: str = Field(..., description="The script content")
    type: str = Field(..., description="The type of script (e.g., sys_script_include)")
    description: Optional[str] = Field(None, description="Description of the script")

class ServiceNowMCP:
    """ServiceNow MCP Server"""
    
    def __init__(self, 
                instance_url: str,
                auth: Authentication,
                name: str = "ServiceNow MCP"):
        self.client = ServiceNowClient(instance_url, auth)
        self.mcp = FastMCP(name, dependencies=[
            "requests",
            "httpx", 
            "pydantic"
        ])
        
        # Register resources
        self.mcp.resource("servicenow://incidents")(self.list_incidents)
        self.mcp.resource("servicenow://incidents/{number}")(self.get_incident)
        self.mcp.resource("servicenow://users")(self.list_users)
        self.mcp.resource("servicenow://knowledge")(self.list_knowledge)
        self.mcp.resource("servicenow://tables")(self.get_tables)
        self.mcp.resource("servicenow://tables/{table}")(self.get_table_records)
        self.mcp.resource("servicenow://schema/{table}")(self.get_table_schema)
        
        # Register tools
        self.mcp.tool(name="create_incident")(self.create_incident)
        self.mcp.tool(name="update_incident")(self.update_incident)
        self.mcp.tool(name="search_records")(self.search_records)
        self.mcp.tool(name="get_record")(self.get_record)
        self.mcp.tool(name="perform_query")(self.perform_query)
        self.mcp.tool(name="add_comment")(self.add_comment)
        self.mcp.tool(name="add_work_notes")(self.add_work_notes)
        self.mcp.tool(name="update_script")(self.update_script)
        
        # Register prompts
        self.mcp.prompt(name="analyze_incident")(self.incident_analysis_prompt)
        self.mcp.prompt(name="create_incident_prompt")(self.create_incident_prompt)
    
    async def close(self):
        """Close the ServiceNow client"""
        await self.client.close()
        
    def run(self, transport: str = "stdio"):
        """Run the ServiceNow MCP server"""
        try:
            self.mcp.run(transport=transport)
        finally:
            asyncio.run(self.close())
        
    # Resource handlers
    async def list_incidents(self, ctx: Context = None) -> str:
        """List recent incidents in ServiceNow"""
        options = QueryOptions(limit=10)
        result = await self.client.get_records("incident", options, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def get_incident(self, number: str, ctx: Context = None) -> str:
        """Get a specific incident by number"""
        try:
            # Always use get_incident_by_number to query by incident number, not get_record
            incident = await self.client.get_incident_by_number(number, ctx=ctx)
            if incident:
                return json.dumps({"result": incident}, indent=2)
            else:
                logger.error(f"No incident found with number: {number}")
                return json.dumps({"error":{"message":"No Record found","detail":"Record doesn't exist or ACL restricts the record retrieval"},"status":"failure"})
        except Exception as e:
            logger.error(f"Error getting incident {number}: {str(e)}")
            return json.dumps({"error":{"message":str(e),"detail":"Error occurred while retrieving the record"},"status":"failure"})
        
    async def list_users(self, ctx: Context = None) -> str:
        """List users in ServiceNow"""
        options = QueryOptions(limit=10)
        result = await self.client.get_records("sys_user", options, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def list_knowledge(self, ctx: Context = None) -> str:
        """List knowledge articles in ServiceNow"""
        options = QueryOptions(limit=10)
        result = await self.client.get_records("kb_knowledge", options, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def get_tables(self, ctx: Context = None) -> str:
        """Get a list of available tables"""
        result = await self.client.get_available_tables(ctx=ctx)
        return json.dumps({"result": result}, indent=2)
        
    async def get_table_records(self, table: str, ctx: Context = None) -> str:
        """Get records from a specific table"""
        options = QueryOptions(limit=10)
        result = await self.client.get_records(table, options, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def get_table_schema(self, table: str, ctx: Context = None) -> str:
        """Get the schema for a table"""
        result = await self.client.get_table_schema(table, ctx=ctx)
        return json.dumps(result, indent=2)
    
    # Tool handlers
    async def create_incident(self, 
                     incident,
                     ctx: Context = None) -> str:
        """
        Create a new incident in ServiceNow
        
        Args:
            incident: The incident details to create - can be either an IncidentCreate object,
                      a dictionary containing incident fields, or a string with the description
            ctx: Optional context object for progress reporting
        
        Returns:
            JSON response from ServiceNow
        """
        # Handle different input types
        if isinstance(incident, str):
            # If a string was provided, treat it as the description and generate a short description
            short_desc = incident[:50] + ('...' if len(incident) > 50 else '')
            incident_data = {
                "short_description": short_desc,
                "description": incident
            }
            logger.info(f"Creating incident from string description: {short_desc}")
        elif isinstance(incident, dict):
            # Dictionary provided
            incident_data = incident
            logger.info(f"Creating incident from dictionary: {incident.get('short_description', 'No short description')}")
        elif isinstance(incident, IncidentCreate):
            # IncidentCreate model provided
            incident_data = incident.dict(exclude_none=True)
            logger.info(f"Creating incident from IncidentCreate: {incident.short_description}")
        else:
            error_message = f"Invalid incident type: {type(incident)}. Expected IncidentCreate, dict, or str."
            logger.error(error_message)
            return json.dumps({"error": error_message})

        # Validate that required fields are present
        if "short_description" not in incident_data and isinstance(incident, dict):
            if "description" in incident_data:
                # Auto-generate short description from description
                desc = incident_data["description"]
                incident_data["short_description"] = desc[:50] + ('...' if len(desc) > 50 else '')
            else:
                incident_data["short_description"] = "Incident created through API"
        
        if "description" not in incident_data and isinstance(incident, dict):
            if "short_description" in incident_data:
                incident_data["description"] = incident_data["short_description"]
            else:
                incident_data["description"] = "No description provided"
    
        # Log and create the incident
        if ctx:
            await ctx.info(f"Creating incident: {incident_data.get('short_description', 'No short description')}")
        
        try:
            result = await self.client.create_record("incident", incident_data, ctx=ctx)
            
            if ctx:
                await ctx.info(f"Created incident: {result['result']['number']}")
                
            return json.dumps(result, indent=2)
        except Exception as e:
            error_message = f"Error creating incident: {str(e)}"
            logger.error(error_message)
            if ctx:
                await ctx.error(error_message)
            return json.dumps({"error": error_message})
        
    async def update_incident(self,
                     number: str,
                     updates: IncidentUpdate,
                     ctx: Context = None) -> str:
        """
        Update an existing incident in ServiceNow
        
        Args:
            number: The incident number (INC0010001)
            updates: The fields to update
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response from ServiceNow
        """
        # First, get the sys_id for the incident number
        if ctx:
            await ctx.info(f"Looking up incident: {number}")
            
        incident = await self.client.get_incident_by_number(number, ctx=ctx)
        
        if not incident:
            error_message = f"Incident {number} not found"
            if ctx:
                await ctx.error(error_message)
            return json.dumps({"error": error_message})
            
        sys_id = incident['sys_id']
        
        # Now update the incident
        if ctx:
            await ctx.info(f"Updating incident: {number}")
            
        data = updates.dict(exclude_none=True)
        result = await self.client.update_record("incident", sys_id, data, ctx=ctx)
        
        return json.dumps(result, indent=2)
        
    async def search_records(self, 
                    query: str, 
                    table: str = "incident",
                    limit: int = 10,
                    ctx: Context = None) -> str:
        """
        Search for records in ServiceNow using text query
        
        Args:
            query: Text to search for
            table: Table to search in
            limit: Maximum number of results to return
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response containing matching records
        """
        if ctx:
            await ctx.info(f"Searching {table} for: {query}")
            
        result = await self.client.search(query, table, limit, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def get_record(self,
                table: str,
                sys_id: str,
                ctx: Context = None) -> str:
        """
        Get a specific record by sys_id
        
        Args:
            table: Table to query
            sys_id: System ID of the record
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response containing the record
        """
        if ctx:
            await ctx.info(f"Getting {table} record: {sys_id}")
            
        result = await self.client.get_record(table, sys_id, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def perform_query(self,
                   table: str,
                   query: str = "",
                   limit: int = 10,
                   offset: int = 0,
                   fields: Optional[List[str]] = None,
                   ctx: Context = None) -> str:
        """
        Perform a query against ServiceNow
        
        Args:
            table: Table to query
            query: Encoded query string (ServiceNow syntax)
            limit: Maximum number of results to return
            offset: Number of records to skip
            fields: List of fields to return (or all fields if None)
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response containing query results
        """
        if ctx:
            await ctx.info(f"Querying {table} with: {query}")
            
        options = QueryOptions(
            limit=limit,
            offset=offset,
            fields=fields,
            query=query
        )
        
        result = await self.client.get_records(table, options, ctx=ctx)
        return json.dumps(result, indent=2)
        
    async def add_comment(self,
                 number: str,
                 comment: str,
                 ctx: Context = None) -> str:
        """
        Add a comment to an incident (customer visible)
        
        Args:
            number: Incident number
            comment: Comment to add
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response from ServiceNow
        """
        if ctx:
            await ctx.info(f"Adding comment to incident: {number}")
            
        incident = await self.client.get_incident_by_number(number, ctx=ctx)
        
        if not incident:
            error_message = f"Incident {number} not found"
            if ctx:
                await ctx.error(error_message)
            return json.dumps({"error": error_message})
            
        sys_id = incident['sys_id']
        
        # Add the comment
        update = {"comments": comment}
        result = await self.client.update_record("incident", sys_id, update, ctx=ctx)
        
        return json.dumps(result, indent=2)
        
    async def add_work_notes(self,
                    number: str,
                    work_notes: str,
                    ctx: Context = None) -> str:
        """
        Add work notes to an incident (internal)
        
        Args:
            number: Incident number
            work_notes: Work notes to add
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response from ServiceNow
        """
        if ctx:
            await ctx.info(f"Adding work notes to incident: {number}")
            
        incident = await self.client.get_incident_by_number(number, ctx=ctx)
        
        if not incident:
            error_message = f"Incident {number} not found"
            if ctx:
                await ctx.error(error_message)
            return json.dumps({"error": error_message})
            
        sys_id = incident['sys_id']
        
        # Add the work notes
        update = {"work_notes": work_notes}
        result = await self.client.update_record("incident", sys_id, update, ctx=ctx)
        
        return json.dumps(result, indent=2)
    
    async def update_script(self,
                   script_update: ScriptUpdateModel,
                   ctx: Context = None) -> str:
        """
        Update a ServiceNow script
        
        Args:
            script_update: The script update details
            ctx: Optional context object for progress reporting
            
        Returns:
            JSON response from ServiceNow
        """
        if ctx:
            await ctx.info(f"Updating script: {script_update.name}")
            
        # Search for the script by name
        table = script_update.type
        query = f"name={script_update.name}"
        
        options = QueryOptions(
            limit=1,
            query=query
        )
        
        result = await self.client.get_records(table, options, ctx=ctx)
        
        if not result.get("result") or len(result["result"]) == 0:
            # Script doesn't exist, create it
            if ctx:
                await ctx.info(f"Script not found, creating new script: {script_update.name}")
                
            data = {
                "name": script_update.name,
                "script": script_update.script
            }
            
            if script_update.description:
                data["description"] = script_update.description
                
            result = await self.client.create_record(table, data, ctx=ctx)
        else:
            # Script exists, update it
            script = result["result"][0]
            sys_id = script["sys_id"]
            
            if ctx:
                await ctx.info(f"Updating existing script: {script_update.name} ({sys_id})")
                
            data = {
                "script": script_update.script
            }
            
            if script_update.description:
                data["description"] = script_update.description
                
            result = await self.client.update_record(table, sys_id, data, ctx=ctx)
            
        return json.dumps(result, indent=2)
    
    # Prompt templates
    def incident_analysis_prompt(self, incident_number: str) -> str:
        """Create a prompt to analyze a ServiceNow incident
        
        Args:
            incident_number: The incident number to analyze (e.g., INC0010001)
            
        Returns:
            Prompt text for analyzing the incident
        """
        return f"""
        Please analyze the following ServiceNow incident {incident_number}.
        
        First, call the appropriate tool to fetch the incident details using get_incident.
        
        Then, provide a comprehensive analysis with the following sections:
        
        1. Summary: A brief overview of the incident
        2. Impact Assessment: Analysis of the impact based on the severity, priority, and affected users
        3. Root Cause Analysis: Potential causes based on available information
        4. Resolution Recommendations: Suggested next steps to resolve the incident
        5. SLA Status: Whether the incident is at risk of breaching SLAs
        
        Use a professional and clear tone appropriate for IT service management.
        """
        
    def create_incident_prompt(self) -> str:
        """Create a prompt for incident creation guidance
        
        Returns:
            Prompt text for helping users create an incident
        """
        return """
        I'll help you create a new ServiceNow incident. Please provide the following information:
        
        1. Short Description: A brief title for the incident (required)
        2. Detailed Description: A thorough explanation of the issue (required)
        3. Caller: The person reporting the issue (optional)
        4. Category and Subcategory: The type of issue (optional)
        5. Impact (1-High, 2-Medium, 3-Low): How broadly this affects users (optional)
        6. Urgency (1-High, 2-Medium, 3-Low): How time-sensitive this issue is (optional)
        
        After collecting this information, I'll use the create_incident tool to submit the incident to ServiceNow.
        """


# Factory functions for creating authentication objects
def create_basic_auth(username: str, password: str) -> BasicAuth:
    """Create BasicAuth object for ServiceNow authentication"""
    return BasicAuth(username, password)

def create_token_auth(token: str) -> TokenAuth:
    """Create TokenAuth object for ServiceNow authentication"""
    return TokenAuth(token)

def create_oauth_auth(client_id: str, client_secret: str, 
                     username: str, password: str,
                     instance_url: str) -> OAuthAuth:
    """Create OAuthAuth object for ServiceNow authentication"""
    return OAuthAuth(client_id, client_secret, username, password, instance_url)


def create_obo_auth(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    user_assertion: Optional[str],
    scope: str,
    token_endpoint: Optional[str] = None,
    allow_static_assertion: bool = False,
    expected_audiences: Optional[Union[str, List[str]]] = None,
    expected_issuers: Optional[Union[str, List[str]]] = None,
) -> EntraOBOAuth:
    """Create Entra OBO authentication object for downstream bearer token acquisition."""
    parsed_audiences = (
        _split_csv_values(expected_audiences)
        if isinstance(expected_audiences, str)
        else (expected_audiences or [client_id])
    )
    parsed_issuers = (
        _split_csv_values(expected_issuers)
        if isinstance(expected_issuers, str)
        else expected_issuers
    )

    return EntraOBOAuth(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        user_assertion=user_assertion,
        scope=scope,
        token_endpoint=token_endpoint,
        allow_static_assertion=allow_static_assertion,
        expected_audiences=parsed_audiences,
        expected_issuers=parsed_issuers,
    )
