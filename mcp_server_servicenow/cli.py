"""
ServiceNow MCP Server CLI

This module provides the command-line interface for the ServiceNow MCP server.
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from mcp_server_servicenow.server import ServiceNowMCP, create_basic_auth


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default

def main():
    """Run the ServiceNow MCP server from the command line"""
    # Load environment variables from .env file if it exists.
    # First try current working directory, then fall back to repository root.
    loaded = load_dotenv()
    if not loaded:
        repo_env = Path(__file__).resolve().parents[1] / ".env"
        if repo_env.exists():
            load_dotenv(dotenv_path=repo_env)
    
    parser = argparse.ArgumentParser(description="ServiceNow MCP Server")
    parser.add_argument("--url", help="ServiceNow instance URL", default=os.environ.get("SERVICENOW_INSTANCE_URL"))
    parser.add_argument("--transport", help="Transport protocol (stdio or sse)", default="stdio", choices=["stdio", "sse"])
    
    # Authentication options
    auth_group = parser.add_argument_group("Authentication")
    auth_group.add_argument("--username", help="ServiceNow username", default=os.environ.get("SERVICENOW_USERNAME"))
    auth_group.add_argument("--password", help="ServiceNow password", default=os.environ.get("SERVICENOW_PASSWORD"))
    auth_group.add_argument("--token", help="ServiceNow token", default=os.environ.get("SERVICENOW_TOKEN"))
    auth_group.add_argument("--client-id", help="OAuth client ID", default=os.environ.get("SERVICENOW_CLIENT_ID"))
    auth_group.add_argument("--client-secret", help="OAuth client secret", default=os.environ.get("SERVICENOW_CLIENT_SECRET"))
    auth_group.add_argument("--obo-tenant-id", help="Entra tenant ID for OBO", default=os.environ.get("SERVICENOW_OBO_TENANT_ID"))
    auth_group.add_argument("--obo-client-id", help="Entra app client ID for OBO", default=os.environ.get("SERVICENOW_OBO_CLIENT_ID"))
    auth_group.add_argument("--obo-client-secret", help="Entra app client secret for OBO", default=os.environ.get("SERVICENOW_OBO_CLIENT_SECRET"))
    auth_group.add_argument("--obo-user-assertion", help="Static fallback user token for local testing only", default=os.environ.get("SERVICENOW_OBO_USER_ASSERTION"))
    auth_group.add_argument("--obo-scope", help="Downstream scope for OBO exchange", default=os.environ.get("SERVICENOW_OBO_SCOPE"))
    auth_group.add_argument("--obo-token-endpoint", help="Optional custom token endpoint for OBO", default=os.environ.get("SERVICENOW_OBO_TOKEN_ENDPOINT"))
    auth_group.add_argument("--obo-expected-audience", help="Comma-separated expected incoming token audiences (defaults to OBO client ID)", default=os.environ.get("SERVICENOW_OBO_EXPECTED_AUDIENCE"))
    auth_group.add_argument("--obo-expected-issuer", help="Comma-separated allowed incoming token issuers (defaults to Entra tenant issuers)", default=os.environ.get("SERVICENOW_OBO_EXPECTED_ISSUER"))
    auth_group.add_argument(
        "--obo-allow-static-assertion",
        help="Allow static OBO assertion fallback (local testing only)",
        action="store_true",
        default=(os.environ.get("SERVICENOW_OBO_ALLOW_STATIC_ASSERTION", "").lower() in {"1", "true", "yes"}),
    )
    auth_group.add_argument("--sn-jwt-tenant-id", help="Entra tenant ID for incoming user token validation", default=os.environ.get("SERVICENOW_SN_JWT_TENANT_ID"))
    auth_group.add_argument("--sn-jwt-upstream-client-id", help="Expected incoming token audience/client ID", default=os.environ.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID"))
    auth_group.add_argument("--sn-jwt-client-id", help="ServiceNow OAuth JWT bearer client ID", default=os.environ.get("SERVICENOW_SN_JWT_CLIENT_ID"))
    auth_group.add_argument("--sn-jwt-private-key", help="PEM private key content for ServiceNow JWT assertion signing", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY"))
    auth_group.add_argument("--sn-jwt-private-key-path", help="Path to PEM private key file for ServiceNow JWT assertion signing", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PATH"))
    auth_group.add_argument("--sn-jwt-private-key-passphrase", help="Optional passphrase for encrypted private key", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PASSPHRASE"))
    auth_group.add_argument("--sn-jwt-client-secret", help="Optional ServiceNow OAuth client secret", default=os.environ.get("SERVICENOW_SN_JWT_CLIENT_SECRET"))
    auth_group.add_argument("--sn-jwt-scope", help="Optional scope for ServiceNow JWT bearer exchange", default=os.environ.get("SERVICENOW_SN_JWT_SCOPE"))
    auth_group.add_argument("--sn-jwt-kid", help="Optional key ID header for JWT assertion signing", default=os.environ.get("SERVICENOW_SN_JWT_KID"))
    auth_group.add_argument("--sn-jwt-token-endpoint", help="ServiceNow OAuth token endpoint (defaults to <instance>/oauth_token.do)", default=os.environ.get("SERVICENOW_SN_JWT_TOKEN_ENDPOINT"))
    auth_group.add_argument("--sn-jwt-user-claim-source", help="Preferred user claim to map to ServiceNow JWT subject", default=os.environ.get("SERVICENOW_SN_JWT_USER_CLAIM_SOURCE", "preferred_username"))
    auth_group.add_argument("--sn-jwt-user-assertion", help="Static fallback incoming user token for local testing only", default=os.environ.get("SERVICENOW_SN_JWT_USER_ASSERTION"))
    auth_group.add_argument("--sn-jwt-expected-audience", help="Comma-separated expected incoming token audiences", default=os.environ.get("SERVICENOW_SN_JWT_EXPECTED_AUDIENCE"))
    auth_group.add_argument("--sn-jwt-expected-issuer", help="Comma-separated allowed incoming token issuers", default=os.environ.get("SERVICENOW_SN_JWT_EXPECTED_ISSUER"))
    auth_group.add_argument("--sn-jwt-assertion-ttl", help="JWT assertion lifetime in seconds", type=int, default=_env_int("SERVICENOW_SN_JWT_ASSERTION_TTL", 300))
    auth_group.add_argument("--sn-jwt-cache-safety-buffer", help="Token refresh safety buffer in seconds", type=int, default=_env_int("SERVICENOW_SN_JWT_CACHE_SAFETY_BUFFER", 60))
    auth_group.add_argument(
        "--sn-jwt-allow-static-assertion",
        help="Allow static incoming user assertion fallback (local testing only)",
        action="store_true",
        default=(os.environ.get("SERVICENOW_SN_JWT_ALLOW_STATIC_ASSERTION", "").lower() in {"1", "true", "yes"}),
    )
    
    args = parser.parse_args()
    
    # Check required parameters
    if not args.url:
        print("Error: ServiceNow instance URL is required")
        print("Set SERVICENOW_INSTANCE_URL environment variable or use --url")
        sys.exit(1)

    # Catch common placeholder values from .env.example early.
    if "your-instance.service-now.com" in args.url:
        print("Error: SERVICENOW_INSTANCE_URL is still a placeholder value")
        print("Set it to your real instance URL, e.g. https://dev123456.service-now.com/")
        sys.exit(1)

    if args.username == "your-username" or args.password == "your-password":
        print("Error: ServiceNow credentials are still placeholder values")
        print("Update SERVICENOW_USERNAME and SERVICENOW_PASSWORD in your .env file")
        sys.exit(1)
    
    # Determine authentication method
    auth = None
    sn_jwt_required_fields = {
        "--sn-jwt-tenant-id": args.sn_jwt_tenant_id,
        "--sn-jwt-upstream-client-id": args.sn_jwt_upstream_client_id,
        "--sn-jwt-client-id": args.sn_jwt_client_id,
    }
    sn_jwt_key_configured = bool(args.sn_jwt_private_key or args.sn_jwt_private_key_path)
    any_sn_jwt_config = (
        any(sn_jwt_required_fields.values())
        or sn_jwt_key_configured
        or bool(args.sn_jwt_token_endpoint)
    )
    all_sn_jwt_required = all(sn_jwt_required_fields.values()) and sn_jwt_key_configured

    if any_sn_jwt_config and not all_sn_jwt_required:
        missing = [key for key, value in sn_jwt_required_fields.items() if not value]
        if not sn_jwt_key_configured:
            missing.append("--sn-jwt-private-key or --sn-jwt-private-key-path")
        print("Error: Incomplete ServiceNow JWT bearer configuration")
        print("Missing required values: " + ", ".join(missing))
        sys.exit(1)

    obo_fields = {
        "--obo-tenant-id": args.obo_tenant_id,
        "--obo-client-id": args.obo_client_id,
        "--obo-client-secret": args.obo_client_secret,
        "--obo-scope": args.obo_scope,
    }
    any_obo_config = any(obo_fields.values()) or bool(args.obo_token_endpoint)
    all_obo_required = all(obo_fields.values())

    if any_obo_config and not all_obo_required:
        missing = [key for key, value in obo_fields.items() if not value]
        print("Error: Incomplete OBO configuration")
        print("Missing required OBO values: " + ", ".join(missing))
        sys.exit(1)

    if all_sn_jwt_required:
        from mcp_server_servicenow.server import create_servicenow_jwt_bearer_user_auth
        auth = create_servicenow_jwt_bearer_user_auth(
            tenant_id=args.sn_jwt_tenant_id,
            upstream_client_id=args.sn_jwt_upstream_client_id,
            jwt_client_id=args.sn_jwt_client_id,
            token_endpoint=args.sn_jwt_token_endpoint,
            instance_url=args.url,
            jwt_private_key=args.sn_jwt_private_key,
            jwt_private_key_path=args.sn_jwt_private_key_path,
            jwt_private_key_passphrase=args.sn_jwt_private_key_passphrase,
            jwt_client_secret=args.sn_jwt_client_secret,
            jwt_scope=args.sn_jwt_scope,
            jwt_kid=args.sn_jwt_kid,
            user_claim_source=args.sn_jwt_user_claim_source,
            user_assertion=args.sn_jwt_user_assertion,
            allow_static_assertion=args.sn_jwt_allow_static_assertion,
            expected_audiences=args.sn_jwt_expected_audience,
            expected_issuers=args.sn_jwt_expected_issuer,
            assertion_ttl_seconds=args.sn_jwt_assertion_ttl,
            cache_safety_buffer_seconds=args.sn_jwt_cache_safety_buffer,
        )
    elif all_obo_required:
        from mcp_server_servicenow.server import create_obo_auth
        auth = create_obo_auth(
            tenant_id=args.obo_tenant_id,
            client_id=args.obo_client_id,
            client_secret=args.obo_client_secret,
            user_assertion=args.obo_user_assertion,
            scope=args.obo_scope,
            token_endpoint=args.obo_token_endpoint,
            allow_static_assertion=args.obo_allow_static_assertion,
            expected_audiences=args.obo_expected_audience,
            expected_issuers=args.obo_expected_issuer,
        )
    elif args.token:
        from mcp_server_servicenow.server import create_token_auth
        auth = create_token_auth(args.token)
    elif args.client_id and args.client_secret and args.username and args.password:
        from mcp_server_servicenow.server import create_oauth_auth
        auth = create_oauth_auth(args.client_id, args.client_secret, args.username, args.password, args.url)
    elif args.username and args.password:
        auth = create_basic_auth(args.username, args.password)
    else:
        print("Error: Authentication credentials required")
        print("Provide one of: ServiceNow JWT bearer, Entra OBO, token, OAuth, or username/password")
        sys.exit(1)
    
    # Create and run the server
    server = ServiceNowMCP(instance_url=args.url, auth=auth)
    if args.transport == "stdio":
        print(
            "ServiceNow MCP server started (stdio). Waiting for MCP client input...",
            file=sys.stderr,
        )
    else:
        print("ServiceNow MCP server starting with sse transport...", file=sys.stderr)
    server.run(transport=args.transport)

if __name__ == "__main__":
    main()
