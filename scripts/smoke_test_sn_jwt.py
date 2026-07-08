#!/usr/bin/env python
"""Repeatable smoke test for ServiceNow JWT bearer delegated auth.

Flow:
1) Acquire Entra user token using device code.
2) Build ServiceNow JWT bearer auth using local env values.
3) Call incident list endpoint through ServiceNowMCP.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import jwt
import msal
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_servicenow.server import ServiceNowMCP, create_servicenow_jwt_bearer_user_auth


def _require(cfg: Dict[str, str], key: str) -> str:
    value = (cfg.get(key) or "").strip()
    if not value:
        raise SystemExit(f"Missing required setting: {key}")
    return value


def _acquire_device_token(tenant_id: str, public_client_id: str, scope: str) -> str:
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(client_id=public_client_id, authority=authority)

    flow = app.initiate_device_flow(scopes=[scope])
    if "user_code" not in flow:
        raise SystemExit(f"Failed to start device flow: {flow}")

    print(flow.get("message", "Open device auth URL and enter the shown code."))

    interval = int(flow.get("interval", 5))
    expires_at = int(flow.get("expires_at", int(time.time()) + 900))
    result: Dict[str, Any] = {}

    while int(time.time()) < expires_at:
        result = app.acquire_token_by_device_flow(flow)
        token = result.get("access_token")
        if token:
            return str(token)

        if result.get("error") in ("authorization_pending", "slow_down"):
            time.sleep(interval)
            continue

        raise SystemExit(f"Failed to acquire user token: {result}")

    raise SystemExit(f"Device flow timed out before completion: {result}")


def _dump_claims(access_token: str) -> None:
    claims = jwt.decode(
        access_token,
        options={
            "verify_signature": False,
            "verify_aud": False,
            "verify_iss": False,
        },
    )
    keys = ["preferred_username", "email", "upn", "oid", "sub", "name", "tid", "aud"]
    print("User token claims:")
    for key in keys:
        print(f"  {key}: {claims.get(key)}")


async def _run_smoke(cfg: Dict[str, str], access_token: str) -> int:
    instance_url = _require(cfg, "SERVICENOW_INSTANCE_URL")
    token_endpoint = (cfg.get("SERVICENOW_SN_JWT_TOKEN_ENDPOINT") or "").strip() or f"{instance_url.rstrip('/')}/oauth_token.do"

    auth = create_servicenow_jwt_bearer_user_auth(
        tenant_id=_require(cfg, "SERVICENOW_SN_JWT_TENANT_ID"),
        upstream_client_id=_require(cfg, "SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID"),
        jwt_client_id=_require(cfg, "SERVICENOW_SN_JWT_CLIENT_ID"),
        jwt_client_secret=(cfg.get("SERVICENOW_SN_JWT_CLIENT_SECRET") or "").strip() or None,
        token_endpoint=token_endpoint,
        instance_url=instance_url,
        jwt_private_key_path=(cfg.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PATH") or "").strip() or None,
        jwt_private_key=(cfg.get("SERVICENOW_SN_JWT_PRIVATE_KEY") or "").strip() or None,
        jwt_private_key_passphrase=(cfg.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PASSPHRASE") or "").strip() or None,
        jwt_scope=(cfg.get("SERVICENOW_SN_JWT_SCOPE") or "").strip() or None,
        jwt_kid=(cfg.get("SERVICENOW_SN_JWT_KID") or "").strip() or None,
        user_claim_source=(cfg.get("SERVICENOW_SN_JWT_USER_CLAIM_SOURCE") or "preferred_username").strip(),
        user_assertion=access_token,
        allow_static_assertion=True,
    )

    client = ServiceNowMCP(instance_url=instance_url, auth=auth)
    try:
        result = await client.list_incidents()
        print("ServiceNow list_incidents response:")
        try:
            parsed = json.loads(result)
            print(json.dumps(parsed, indent=2))
        except Exception:
            print(result)
        return 0
    finally:
        await client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test ServiceNow JWT bearer delegated flow")
    parser.add_argument("--env-file", default=".env", help="Path to env file")
    parser.add_argument("--show-claims", action="store_true", help="Print selected user-token claims")
    args = parser.parse_args()

    cfg = {k: (v or "") for k, v in dotenv_values(args.env_file).items()}
    tenant_id = _require(cfg, "SERVICENOW_SN_JWT_TENANT_ID")
    public_client_id = (cfg.get("SERVICENOW_OBO_PUBLIC_CLIENT_ID") or cfg.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID") or "").strip()
    scope = (cfg.get("SERVICENOW_OBO_USER_SCOPE") or f"{_require(cfg, 'SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID')}/.default").strip()

    if not public_client_id:
        raise SystemExit("Missing SERVICENOW_OBO_PUBLIC_CLIENT_ID or SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID")

    access_token = _acquire_device_token(tenant_id=tenant_id, public_client_id=public_client_id, scope=scope)
    if args.show_claims:
        _dump_claims(access_token)

    return int(asyncio.run(_run_smoke(cfg, access_token)))


if __name__ == "__main__":
    raise SystemExit(main())
