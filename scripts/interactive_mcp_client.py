"""Interactive helper for calling ServiceNow MCP tool handlers directly.

This script is useful for local/manual validation when you want a simple
menu-driven interface instead of wiring an MCP client first.

Authentication is loaded from .env or command-line args and supports:
- Entra OBO
- ServiceNow bearer token
- ServiceNow OAuth
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

# Allow running the script directly from scripts/ without requiring editable install.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server_servicenow.server import (
    IncidentUpdate,
    ServiceNowMCP,
    create_obo_auth,
    create_oauth_auth,
    create_servicenow_jwt_bearer_user_auth,
    create_token_auth,
)


MENU_TEXT = """
Available commands:
  1) list_incidents
  2) get_incident
  3) search_records
  4) perform_query
  5) get_record
  6) create_incident
  7) update_incident
  8) add_comment
  9) add_work_notes
 10) get_tables
 11) get_table_records
 12) get_table_schema
 13) show_command_list
  0) exit
""".strip()


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _prompt_json(prompt: str) -> Dict[str, Any]:
    raw = input(prompt).strip()
    if not raw:
        return {}
    return json.loads(raw)


def _safe_print_result(raw: str) -> None:
    try:
        parsed = json.loads(raw)
        print(json.dumps(parsed, indent=2))
    except Exception:
        print(raw)


async def _run_menu(client: ServiceNowMCP) -> None:
    print(MENU_TEXT)
    while True:
        choice = input("\nSelect command (0-13): ").strip()

        try:
            if choice == "0":
                print("Exiting.")
                return

            if choice == "1":
                _safe_print_result(await client.list_incidents())
            elif choice == "2":
                number = input("Incident number (e.g., INC0010001): ").strip()
                _safe_print_result(await client.get_incident(number=number))
            elif choice == "3":
                query = input("Search text: ").strip()
                table = input("Table [incident]: ").strip() or "incident"
                limit = int(input("Limit [10]: ").strip() or "10")
                _safe_print_result(await client.search_records(query=query, table=table, limit=limit))
            elif choice == "4":
                table = input("Table: ").strip()
                query = input("Encoded query (optional): ").strip()
                limit = int(input("Limit [10]: ").strip() or "10")
                offset = int(input("Offset [0]: ").strip() or "0")
                fields_raw = input("Fields comma-separated (optional): ").strip()
                fields = [f.strip() for f in fields_raw.split(",") if f.strip()] if fields_raw else None
                _safe_print_result(
                    await client.perform_query(
                        table=table,
                        query=query,
                        limit=limit,
                        offset=offset,
                        fields=fields,
                    )
                )
            elif choice == "5":
                table = input("Table: ").strip()
                sys_id = input("sys_id: ").strip()
                _safe_print_result(await client.get_record(table=table, sys_id=sys_id))
            elif choice == "6":
                print("Provide incident JSON payload. Example:")
                print('{"short_description":"API test","description":"Created from interactive client"}')
                payload = _prompt_json("Incident JSON: ")
                _safe_print_result(await client.create_incident(incident=payload))
            elif choice == "7":
                number = input("Incident number: ").strip()
                print("Provide update JSON payload. Example:")
                print('{"state":2,"work_notes":"Updated via interactive client"}')
                payload = _prompt_json("Update JSON: ")
                update_model = IncidentUpdate(**payload)
                _safe_print_result(await client.update_incident(number=number, updates=update_model))
            elif choice == "8":
                number = input("Incident number: ").strip()
                comment = input("Comment: ").strip()
                _safe_print_result(await client.add_comment(number=number, comment=comment))
            elif choice == "9":
                number = input("Incident number: ").strip()
                notes = input("Work notes: ").strip()
                _safe_print_result(await client.add_work_notes(number=number, work_notes=notes))
            elif choice == "10":
                _safe_print_result(await client.get_tables())
            elif choice == "11":
                table = input("Table: ").strip()
                _safe_print_result(await client.get_table_records(table=table))
            elif choice == "12":
                table = input("Table: ").strip()
                _safe_print_result(await client.get_table_schema(table=table))
            elif choice == "13":
                print(MENU_TEXT)
            else:
                print("Unknown command. Choose a value between 0 and 13.")
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON input: {exc}")
        except Exception as exc:
            print(f"Command failed: {exc}")


def _validate_url(url: str) -> None:
    if not url:
        raise ValueError("ServiceNow instance URL is required")
    if "your-instance.service-now.com" in url:
        raise ValueError("SERVICENOW_INSTANCE_URL is still a placeholder value")


def _build_auth(args: argparse.Namespace):
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
        raise ValueError("Incomplete ServiceNow JWT bearer configuration. Missing: " + ", ".join(missing))

    if all_sn_jwt_required:
        return create_servicenow_jwt_bearer_user_auth(
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
        raise ValueError("Incomplete OBO configuration. Missing: " + ", ".join(missing))

    if all_obo_required:
        return create_obo_auth(
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

    if args.token:
        return create_token_auth(args.token)

    if args.client_id and args.client_secret and args.username and args.password:
        return create_oauth_auth(
            client_id=args.client_id,
            client_secret=args.client_secret,
            username=args.username,
            password=args.password,
            instance_url=args.url,
        )

    raise ValueError(
        "Authentication required. Configure one of: complete OBO, token, or complete ServiceNow OAuth."
    )


def _is_placeholder_assertion(value: str) -> bool:
    return value.strip() in {"", "__SET_AT_RUNTIME__", "<set-at-runtime>", "placeholder"}


async def _maybe_acquire_obo_user_assertion(args: argparse.Namespace) -> None:
    """Acquire an Entra user token for local OBO testing when no assertion is provided.

    This simulates the incoming bearer token a Teams-like client would normally pass.
    """
    obo_fields = [args.obo_tenant_id, args.obo_client_id, args.obo_client_secret, args.obo_scope]
    if not all(obo_fields):
        return

    existing_assertion = (args.obo_user_assertion or "").strip()
    if existing_assertion and not _is_placeholder_assertion(existing_assertion):
        return

    authority = f"https://login.microsoftonline.com/{args.obo_tenant_id}"
    # For self-token scenarios, Entra expects GUID-based resource notation.
    upstream_scope = args.obo_user_scope or f"{args.obo_client_id}/.default"
    public_client_id = args.obo_public_client_id or args.obo_client_id

    try:
        import msal  # type: ignore
    except Exception as exc:
        raise ValueError(
            "Interactive OBO assertion acquisition requires the 'msal' package. "
            "Install dependencies and retry."
        ) from exc

    app = msal.PublicClientApplication(client_id=public_client_id, authority=authority)

    result = app.acquire_token_interactive(
        scopes=[upstream_scope],
        login_hint=(args.obo_username or None),
        prompt="select_account",
    )

    access_token = result.get("access_token")
    if not access_token and args.obo_allow_device_code_fallback:
        device_flow = app.initiate_device_flow(scopes=[upstream_scope])
        if "user_code" not in device_flow:
            raise ValueError(
                "Failed to initialize device-code fallback flow for OBO assertion token acquisition"
            )

        message = device_flow.get("message", "Open the verification URL and enter the device code.")
        print(message)
        result = app.acquire_token_by_device_flow(device_flow)
        access_token = result.get("access_token")

    if not access_token:
        error = result.get("error")
        description = result.get("error_description") or "No access token returned"
        hint = ""
        if "AADSTS90009" in description:
            hint = (
                " Hint: set SERVICENOW_OBO_USER_SCOPE to '<resource-app-client-id>/.default' "
                "(GUID-based) instead of 'api://<id>/.default'."
            )
        raise ValueError(
            "Failed to auto-acquire OBO user assertion token via interactive auth. "
            f"{error or 'unknown_error'}: {description}{hint}"
        )

    args.obo_user_assertion = access_token
    args.obo_allow_static_assertion = True
    print("Auto-acquired OBO user assertion token via interactive Entra auth for local test mode.")


async def _async_main(args: argparse.Namespace) -> int:
    if args.list_commands:
        print(MENU_TEXT)
        return 0

    _validate_url(args.url)
    await _maybe_acquire_obo_user_assertion(args)
    auth = _build_auth(args)
    client = ServiceNowMCP(instance_url=args.url, auth=auth)

    try:
        await _run_menu(client)
        return 0
    finally:
        await client.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive ServiceNow MCP helper")
    parser.add_argument(
        "--url",
        default=os.environ.get("SERVICENOW_INSTANCE_URL"),
        help="ServiceNow instance URL",
    )
    parser.add_argument(
        "--username",
        default=(os.environ.get("SERVICENOW_USERNAME") or os.environ.get("SERVICENOW_OBO_USERNAME")),
        help="ServiceNow username (OAuth only)",
    )
    parser.add_argument(
        "--password",
        default=(os.environ.get("SERVICENOW_PASSWORD") or os.environ.get("SERVICENOW_OBO_PASSWORD")),
        help="ServiceNow password (OAuth only)",
    )
    parser.add_argument("--token", default=os.environ.get("SERVICENOW_TOKEN"), help="ServiceNow bearer token")
    parser.add_argument("--client-id", default=os.environ.get("SERVICENOW_CLIENT_ID"), help="ServiceNow OAuth client ID")
    parser.add_argument("--client-secret", default=os.environ.get("SERVICENOW_CLIENT_SECRET"), help="ServiceNow OAuth client secret")
    parser.add_argument("--obo-tenant-id", default=os.environ.get("SERVICENOW_OBO_TENANT_ID"), help="Entra tenant ID for OBO")
    parser.add_argument("--obo-client-id", default=os.environ.get("SERVICENOW_OBO_CLIENT_ID"), help="Entra app client ID for OBO")
    parser.add_argument("--obo-client-secret", default=os.environ.get("SERVICENOW_OBO_CLIENT_SECRET"), help="Entra app client secret for OBO")
    parser.add_argument("--obo-user-assertion", default=os.environ.get("SERVICENOW_OBO_USER_ASSERTION"), help="Static fallback user token for local testing only")
    parser.add_argument("--obo-username", default=os.environ.get("SERVICENOW_OBO_USERNAME"), help="Entra username used to auto-acquire OBO user assertion for local testing")
    parser.add_argument("--obo-public-client-id", default=os.environ.get("SERVICENOW_OBO_PUBLIC_CLIENT_ID"), help="Public client ID used for interactive Entra sign-in (defaults to SERVICENOW_OBO_CLIENT_ID)")
    parser.add_argument(
        "--obo-allow-device-code-fallback",
        action="store_true",
        default=(os.environ.get("SERVICENOW_OBO_ALLOW_DEVICE_CODE_FALLBACK", "").lower() in {"1", "true", "yes"}),
        help="Allow device-code fallback when browser interactive sign-in is unavailable",
    )
    parser.add_argument("--obo-user-scope", default=os.environ.get("SERVICENOW_OBO_USER_SCOPE"), help="Optional scope used when acquiring local OBO user assertion token")
    parser.add_argument("--obo-scope", default=os.environ.get("SERVICENOW_OBO_SCOPE"), help="Downstream scope for OBO exchange")
    parser.add_argument("--obo-token-endpoint", default=os.environ.get("SERVICENOW_OBO_TOKEN_ENDPOINT"), help="Optional custom token endpoint for OBO")
    parser.add_argument("--obo-expected-audience", default=os.environ.get("SERVICENOW_OBO_EXPECTED_AUDIENCE"), help="Comma-separated expected incoming token audiences")
    parser.add_argument("--obo-expected-issuer", default=os.environ.get("SERVICENOW_OBO_EXPECTED_ISSUER"), help="Comma-separated allowed incoming token issuers")
    parser.add_argument(
        "--obo-allow-static-assertion",
        action="store_true",
        default=(os.environ.get("SERVICENOW_OBO_ALLOW_STATIC_ASSERTION", "").lower() in {"1", "true", "yes"}),
        help="Allow static OBO assertion fallback (local testing only)",
    )
    parser.add_argument("--sn-jwt-tenant-id", default=os.environ.get("SERVICENOW_SN_JWT_TENANT_ID"), help="Entra tenant ID for incoming user token validation")
    parser.add_argument("--sn-jwt-upstream-client-id", default=os.environ.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID"), help="Expected incoming token audience/client ID")
    parser.add_argument("--sn-jwt-client-id", default=os.environ.get("SERVICENOW_SN_JWT_CLIENT_ID"), help="ServiceNow OAuth JWT bearer client ID")
    parser.add_argument("--sn-jwt-private-key", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY"), help="PEM private key content for ServiceNow JWT assertion signing")
    parser.add_argument("--sn-jwt-private-key-path", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PATH"), help="Path to PEM private key file for ServiceNow JWT assertion signing")
    parser.add_argument("--sn-jwt-private-key-passphrase", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PASSPHRASE"), help="Optional passphrase for encrypted private key")
    parser.add_argument("--sn-jwt-client-secret", default=os.environ.get("SERVICENOW_SN_JWT_CLIENT_SECRET"), help="Optional ServiceNow OAuth client secret")
    parser.add_argument("--sn-jwt-scope", default=os.environ.get("SERVICENOW_SN_JWT_SCOPE"), help="Optional scope for ServiceNow JWT bearer exchange")
    parser.add_argument("--sn-jwt-kid", default=os.environ.get("SERVICENOW_SN_JWT_KID"), help="Optional key ID header for JWT assertion signing")
    parser.add_argument("--sn-jwt-token-endpoint", default=os.environ.get("SERVICENOW_SN_JWT_TOKEN_ENDPOINT"), help="ServiceNow OAuth token endpoint (defaults to <instance>/oauth_token.do)")
    parser.add_argument("--sn-jwt-user-claim-source", default=os.environ.get("SERVICENOW_SN_JWT_USER_CLAIM_SOURCE", "preferred_username"), help="Preferred user claim to map to ServiceNow JWT subject")
    parser.add_argument("--sn-jwt-user-assertion", default=os.environ.get("SERVICENOW_SN_JWT_USER_ASSERTION"), help="Static fallback incoming user token for local testing only")
    parser.add_argument("--sn-jwt-expected-audience", default=os.environ.get("SERVICENOW_SN_JWT_EXPECTED_AUDIENCE"), help="Comma-separated expected incoming token audiences")
    parser.add_argument("--sn-jwt-expected-issuer", default=os.environ.get("SERVICENOW_SN_JWT_EXPECTED_ISSUER"), help="Comma-separated allowed incoming token issuers")
    parser.add_argument("--sn-jwt-assertion-ttl", type=int, default=_env_int("SERVICENOW_SN_JWT_ASSERTION_TTL", 300), help="JWT assertion lifetime in seconds")
    parser.add_argument("--sn-jwt-cache-safety-buffer", type=int, default=_env_int("SERVICENOW_SN_JWT_CACHE_SAFETY_BUFFER", 60), help="Token refresh safety buffer in seconds")
    parser.add_argument(
        "--sn-jwt-allow-static-assertion",
        action="store_true",
        default=(os.environ.get("SERVICENOW_SN_JWT_ALLOW_STATIC_ASSERTION", "").lower() in {"1", "true", "yes"}),
        help="Allow static incoming user assertion fallback (local testing only)",
    )
    parser.add_argument(
        "--list-commands",
        action="store_true",
        help="Print supported command list and exit",
    )
    return parser


def main() -> int:
    # Load environment variables from .env file if present.
    loaded = load_dotenv()
    if not loaded:
        repo_env = Path(__file__).resolve().parents[1] / ".env"
        if repo_env.exists():
            load_dotenv(dotenv_path=repo_env)

    parser = _build_parser()
    args = parser.parse_args()
    try:
        return asyncio.run(_async_main(args))
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
