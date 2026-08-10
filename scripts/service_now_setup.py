"""One-command ServiceNow setup for the MCP OBO / JWT bearer integration.

This is the "do everything for me" entry point. Point it at a fresh ServiceNow
Personal Developer Instance (PDI) with admin credentials and it will run the
whole ServiceNow-side setup in order:

    1. Activate the required ServiceNow plugin (via the CI/CD API).
    2. Generate local RSA key material and certificate (if not already present).
    3. Generate the public JWKS document from that key material.
    4. Build the ServiceNow OAuth/JWT provisioning payload templates.
    5. Create/update the ServiceNow ``oauth_jwt`` client record (JWT bearer).
    6. Update ``.env`` in place with the resulting values (the UI-only client secret is
       left as a placeholder and never overwritten).

It reads connection details from your environment / ``.env`` file:

    SERVICENOW_INSTANCE_URL   e.g. https://dev123456.service-now.com/
    SERVICENOW_USERNAME       admin username
    SERVICENOW_PASSWORD       admin password
    (or SERVICENOW_TOKEN for a bearer token instead of username/password)

Every step is idempotent and individually skippable, so re-running is safe.

Example:

    python scripts/service_now_setup.py \
        --jwks-url "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/.servicenow-jwt/jwks.json"

The one thing this script cannot do for you is host the public JWKS document at
a URL ServiceNow can reach. Publish ``.servicenow-jwt/jwks.json`` somewhere
public (for example the raw GitHub URL of this repo) and pass it via
``--jwks-url`` (or ``SERVICENOW_SN_JWT_JWKS_URL``).
"""

from __future__ import annotations

import argparse
import os
import sys
from argparse import Namespace
from pathlib import Path

# Both scripts live in the same folder, so a direct import works when this file
# is run as ``python scripts/service_now_setup.py``.
import bootstrap_servicenow_jwt as bootstrap

REPO_ROOT = bootstrap.REPO_ROOT
KEY_DIR = REPO_ROOT / ".servicenow-jwt"
KEY_BASENAME = "servicenow-jwt"
PRIVATE_KEY_PATH = KEY_DIR / f"{KEY_BASENAME}-private.pem"
PUBLIC_KEY_PATH = KEY_DIR / f"{KEY_BASENAME}-public.pem"
CERTIFICATE_PATH = KEY_DIR / f"{KEY_BASENAME}-certificate.pem"
JWKS_PATH = KEY_DIR / "jwks.json"
PAYLOAD_DIR = KEY_DIR / "payloads"
OAUTH_JWT_PAYLOAD_PATH = PAYLOAD_DIR / "oauth_jwt.payload.json"
ENV_PATH = REPO_ROOT / ".env"

DEFAULT_PLUGIN_ID = "com.snc.integration.sso.multi.installer"


def _banner(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def _require_connection(args: argparse.Namespace) -> None:
    if not args.url:
        raise SystemExit(
            "SERVICENOW_INSTANCE_URL is not set. Set it in .env or pass --url "
            "(e.g. https://dev123456.service-now.com/)."
        )
    if not args.token and not (args.username and args.password):
        raise SystemExit(
            "ServiceNow admin credentials are required. Set SERVICENOW_USERNAME "
            "and SERVICENOW_PASSWORD (or SERVICENOW_TOKEN) in .env or pass them as flags."
        )


def _keys_present() -> bool:
    return PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists() and CERTIFICATE_PATH.exists()


def _check_auth(args: argparse.Namespace) -> int:
    """Verify admin basic-auth (or token) access to the ServiceNow REST API.

    Returns 0 when the credentials in ``.env`` authenticate successfully, and a
    non-zero exit code otherwise. This is the preflight the README points at so
    users can confirm ``admin`` is not locked out before running full setup.
    """
    _banner("Verify admin REST authentication")
    client = bootstrap.ServiceNowAdminClient(
        instance_url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
    )
    try:
        rows = client.query_table(
            "sys_user",
            query=f"user_name={args.username}" if args.username else "",
            fields=["user_name", "sys_id"],
            limit=1,
        )
    except Exception as exc:  # noqa: BLE001 - surface any auth/connectivity failure to the user
        print(f"Authentication FAILED for {args.url}")
        print(f"  {exc}")
        print(
            "\nA 401 means the credentials in .env do not match the instance, or the\n"
            "Multiple Provider SSO Account Recovery lockout is enabled (see README Step 3).\n"
            "Update SERVICENOW_INSTANCE_URL / SERVICENOW_USERNAME / SERVICENOW_PASSWORD in .env\n"
            "to match the current instance and try again."
        )
        return 1
    identity = rows[0]["user_name"] if rows else (args.username or "(bearer token)")
    print(f"Authentication OK. Connected to {args.url} as {identity}.")
    return 0


def _activate_plugin(args: argparse.Namespace) -> None:
    _banner(f"Activate plugin {args.plugin_id}")
    if args.skip_plugin:
        print("Skipped (--skip-plugin).")
        return
    ns = Namespace(
        url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
        plugin_id=args.plugin_id,
        poll_interval=args.poll_interval,
        max_wait=args.max_wait,
    )
    code = bootstrap._activate_plugin(ns)
    if code == 2:
        print("Plugin activation is still running server-side; continuing with the rest of setup.")
    elif code != 0:
        raise SystemExit(f"Plugin activation failed (exit {code}). See output above.")


def _ensure_key_material(args: argparse.Namespace) -> None:
    _banner("Generate RSA key material and certificate")
    if _keys_present() and not args.overwrite_keys:
        print(f"Key material already present in {KEY_DIR}. Reusing (pass --overwrite-keys to regenerate).")
        return
    ns = Namespace(
        output_dir=str(KEY_DIR),
        basename=KEY_BASENAME,
        key_size=2048,
        years=2,
        subject_common_name="ServiceNow JWT Delegated Auth",
        subject_organization="ServiceNow MCP",
        passphrase=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PASSPHRASE"),
        overwrite=True,
    )
    if bootstrap._generate_key_material(ns) != 0:
        raise SystemExit("Key material generation failed.")


def _generate_jwks(args: argparse.Namespace) -> None:
    _banner("Generate public JWKS document")
    ns = Namespace(
        certificate_path=str(CERTIFICATE_PATH),
        public_key_path=str(PUBLIC_KEY_PATH),
        kid=os.environ.get("SERVICENOW_SN_JWT_KID"),
        output_file=str(JWKS_PATH),
    )
    if bootstrap._generate_jwks(ns) != 0:
        raise SystemExit("JWKS generation failed.")


def _build_payloads(args: argparse.Namespace) -> None:
    _banner("Build ServiceNow OAuth/JWT payload templates")
    ns = Namespace(
        output_dir=str(PAYLOAD_DIR),
        client_id="",
        jwt_provider_name="",
        entity_name="MCP Entra to ServiceNow OBO",
        profile_name="",
        jwks_url=args.jwks_url,
        user_field=args.user_field,
        sub_claim="sys_id",
        jti_claim="jti",
        clock_skew=60,
        enable_jti_verification=True,
        token_format="opaque",
        scope_restriction_status="useraccount",
        client_type="integration_as_a_user",
        comments="Provisioned for ServiceNow MCP delegated JWT bearer integration.",
        scope_name="",
        scope_value="",
    )
    if bootstrap._build_payload_templates(ns) != 0:
        raise SystemExit("Payload template generation failed.")


def _provision_oauth_jwt(args: argparse.Namespace) -> dict:
    _banner("Create/update the ServiceNow oauth_jwt client record")
    client = bootstrap.ServiceNowAdminClient(
        instance_url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
    )
    payload = bootstrap._read_json_file(str(OAUTH_JWT_PAYLOAD_PATH))
    existing = client.query_table(
        "oauth_jwt",
        query=f"jwks_url={payload['jwks_url']}",
        fields=["sys_id", "client_id", "jwks_url"],
        limit=2,
    )
    if existing:
        record = client.update_record("oauth_jwt", existing[0]["sys_id"], payload)
        print(f"Updated existing oauth_jwt record (sys_id {record.get('sys_id')}).")
    else:
        record = client.create_record("oauth_jwt", payload)
        print(f"Created oauth_jwt record (sys_id {record.get('sys_id')}).")
    print(f"  client_id: {record.get('client_id')}")
    return record


CLIENT_SECRET_PLACEHOLDER = "__SET_FROM_SERVICENOW_UI__"


def _update_env_file(args: argparse.Namespace, record: dict) -> None:
    _banner("Update .env with provisioned values")
    token_endpoint = os.environ.get("SERVICENOW_SN_JWT_TOKEN_ENDPOINT")
    if not token_endpoint and args.url:
        token_endpoint = args.url.rstrip("/") + "/oauth_token.do"

    updates = {
        "SERVICENOW_SN_JWT_TENANT_ID": os.environ.get("SERVICENOW_SN_JWT_TENANT_ID"),
        "SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID": os.environ.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID"),
        "SERVICENOW_SN_JWT_CLIENT_ID": record.get("client_id"),
        "SERVICENOW_SN_JWT_PRIVATE_KEY_PATH": f".servicenow-jwt/{KEY_BASENAME}-private.pem",
        "SERVICENOW_SN_JWT_TOKEN_ENDPOINT": token_endpoint,
        "SERVICENOW_SN_JWT_USER_CLAIM_SOURCE": os.environ.get(
            "SERVICENOW_SN_JWT_USER_CLAIM_SOURCE", "preferred_username"
        ),
        "SERVICENOW_SN_JWT_JWKS_URL": args.jwks_url,
    }
    # Only write keys that have a concrete value.
    updates = {key: value for key, value in updates.items() if value}

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []

    def _key_of(line: str) -> str:
        if not line.lstrip().startswith("#") and "=" in line:
            return line.split("=", 1)[0].strip()
        return ""

    changed: list[str] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        key = _key_of(line)
        if key in updates:
            new_line = f"{key}={updates[key]}"
            if new_line != line:
                lines[index] = new_line
                changed.append(key)
            seen.add(key)

    appended: list[str] = []
    missing = [key for key in updates if key not in seen]
    if missing and lines and lines[-1].strip():
        lines.append("")
    for key in missing:
        lines.append(f"{key}={updates[key]}")
        appended.append(key)

    # The client secret is only visible in the ServiceNow UI. Never overwrite an
    # existing value; add a placeholder only if the key is missing entirely.
    secret_key = "SERVICENOW_SN_JWT_CLIENT_SECRET"
    if not any(_key_of(line) == secret_key for line in lines):
        lines.append(f"{secret_key}={CLIENT_SECRET_PLACEHOLDER}")
        appended.append(secret_key)

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if changed:
        print("Updated in .env: " + ", ".join(changed))
    if appended:
        print("Added to .env:   " + ", ".join(appended))
    if not changed and not appended:
        print(".env already up to date.")

    secret_value = os.environ.get("SERVICENOW_SN_JWT_CLIENT_SECRET")
    if not secret_value or secret_value == CLIENT_SECRET_PLACEHOLDER:
        print(
            f"\nStill required (human-only): set {secret_key} in .env with the client secret "
            "revealed in the ServiceNow Application Registry. The REST API does not expose it."
        )


def _print_next_steps(record: dict) -> None:
    _banner("ServiceNow-side setup complete")
    if record.get("sys_id"):
        print(f"oauth_jwt client_id: {record.get('client_id')}")
        print(f"oauth_jwt sys_id:    {record.get('sys_id')}")
        print("Next: finish the remaining manual steps in the README Getting Started guide.")
    else:
        print("ServiceNow records were not provisioned in this run.")
        print("Next: publish .servicenow-jwt/jwks.json and re-run with --jwks-url <url>.")
        print("See the README Getting Started guide for the full step-by-step.")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-command ServiceNow setup for the MCP OBO / JWT bearer integration.",
    )
    parser.add_argument("--url", default=os.environ.get("SERVICENOW_INSTANCE_URL"), help="ServiceNow instance URL")
    parser.add_argument("--username", default=os.environ.get("SERVICENOW_USERNAME"), help="ServiceNow admin username")
    parser.add_argument("--password", default=os.environ.get("SERVICENOW_PASSWORD"), help="ServiceNow admin password")
    parser.add_argument("--token", default=os.environ.get("SERVICENOW_TOKEN"), help="ServiceNow bearer token (alternative to username/password)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")

    parser.add_argument("--plugin-id", default=DEFAULT_PLUGIN_ID, help="Plugin to activate in Step 1")
    parser.add_argument("--skip-plugin", action="store_true", help="Skip plugin activation")
    parser.add_argument("--poll-interval", type=float, default=5.0, help="Seconds between plugin activation progress polls")
    parser.add_argument("--max-wait", type=float, default=600.0, help="Maximum seconds to wait for plugin activation")

    parser.add_argument("--overwrite-keys", action="store_true", help="Regenerate key material even if it already exists")

    parser.add_argument(
        "--jwks-url",
        default=os.environ.get("SERVICENOW_SN_JWT_JWKS_URL"),
        help="Public URL where ServiceNow can fetch the JWKS document (required to provision the oauth_jwt record)",
    )
    parser.add_argument("--user-field", default=os.environ.get("SERVICENOW_SN_JWT_USER_FIELD", "email"), help="ServiceNow user field used to resolve the JWT subject")
    parser.add_argument("--skip-records", action="store_true", help="Skip ServiceNow record provisioning (Steps 4-5)")
    parser.add_argument("--check-auth", action="store_true", help="Only verify admin REST authentication against the instance, then exit")

    return parser


def main() -> int:
    bootstrap._load_env()
    args = _build_parser().parse_args()
    _require_connection(args)

    print(f"ServiceNow instance: {args.url}")
    print(f"Admin identity:      {args.username or '(bearer token)'}")

    if args.check_auth:
        return _check_auth(args)

    _activate_plugin(args)
    _ensure_key_material(args)
    _generate_jwks(args)

    record: dict = {}
    if args.skip_records:
        _banner("ServiceNow record provisioning")
        print("Skipped (--skip-records).")
    elif not args.jwks_url:
        _banner("ServiceNow record provisioning")
        print(
            "Skipped: no JWKS URL provided. Publish .servicenow-jwt/jwks.json at a public URL\n"
            "ServiceNow can reach, then re-run with --jwks-url <url> (or set SERVICENOW_SN_JWT_JWKS_URL)."
        )
    else:
        _build_payloads(args)
        record = _provision_oauth_jwt(args)
        _update_env_file(args, record)

    _print_next_steps(record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
