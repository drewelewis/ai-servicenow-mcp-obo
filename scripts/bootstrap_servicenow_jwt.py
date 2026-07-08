"""Bootstrap helper for ServiceNow JWT bearer delegated auth setup.

This script avoids hardcoding instance-specific ServiceNow security table names.
It gives you four safe operations:

1. discover: find OAuth-related tables and dictionary fields.
2. generate-key-material: create RSA private/public/certificate PEM files.
3. upsert-registry: create or update a chosen ServiceNow registry/security record.
4. emit-env: write the remaining SERVICENOW_SN_JWT_* values to an env file.

Use discover first, then upsert-registry once you know the correct registry table
and required field names in your instance.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    loaded = load_dotenv()
    if not loaded:
        repo_env = REPO_ROOT / ".env"
        if repo_env.exists():
            load_dotenv(dotenv_path=repo_env)


def _normalize_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        raise ValueError("ServiceNow instance URL is required")
    return value.rstrip("/")


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _read_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON payload file must contain an object: {path}")
    return data


class ServiceNowAdminClient:
    def __init__(
        self,
        instance_url: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.instance_url = _normalize_url(instance_url)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        elif username and password:
            self.session.auth = (username, password)
        else:
            raise ValueError(
                "ServiceNow admin authentication is required. Provide SERVICENOW_TOKEN or SERVICENOW_USERNAME/SERVICENOW_PASSWORD."
            )

    def _table_url(self, table: str) -> str:
        return f"{self.instance_url}/api/now/table/{table}"

    def query_table(
        self,
        table: str,
        query: str,
        fields: Optional[Iterable[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        params = {
            "sysparm_query": query,
            "sysparm_limit": str(limit),
        }
        if fields:
            params["sysparm_fields"] = ",".join(fields)

        response = self.session.get(self._table_url(table), params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        return payload.get("result", [])

    def create_record(self, table: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(self._table_url(table), data=json.dumps(payload), timeout=self.timeout)
        response.raise_for_status()
        return response.json().get("result", {})

    def update_record(self, table: str, sys_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.patch(
            f"{self._table_url(table)}/{sys_id}",
            data=json.dumps(payload),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("result", {})


def _discover(args: argparse.Namespace) -> int:
    client = ServiceNowAdminClient(
        instance_url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
    )
    query = f"nameLIKE{args.query}^ORlabelLIKE{args.query}"
    tables = client.query_table(
        "sys_db_object",
        query=query,
        fields=["name", "label", "super_class", "sys_scope"],
        limit=args.limit,
    )

    results: List[Dict[str, Any]] = []
    for item in tables:
        entry = {
            "name": item.get("name"),
            "label": item.get("label"),
            "super_class": item.get("super_class"),
            "sys_scope": item.get("sys_scope"),
        }
        if args.include_fields and entry["name"]:
            fields = client.query_table(
                "sys_dictionary",
                query=f"name={entry['name']}",
                fields=["element", "column_label", "internal_type", "mandatory", "max_length"],
                limit=args.field_limit,
            )
            entry["fields"] = fields
        results.append(entry)

    print(json.dumps({"result_count": len(results), "tables": results}, indent=2))
    return 0


def _generate_key_material(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    private_key_path = output_dir / f"{args.basename}-private.pem"
    public_key_path = output_dir / f"{args.basename}-public.pem"
    certificate_path = output_dir / f"{args.basename}-certificate.pem"

    for path in (private_key_path, public_key_path, certificate_path):
        if path.exists() and not args.overwrite:
            raise ValueError(f"Refusing to overwrite existing file without --overwrite: {path}")

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=args.key_size)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, args.subject_common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, args.subject_organization),
        ]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=365 * args.years))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key, hashes.SHA256())
    )

    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=(
            serialization.BestAvailableEncryption(args.passphrase.encode("utf-8"))
            if args.passphrase
            else serialization.NoEncryption()
        ),
    )
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    certificate_bytes = certificate.public_bytes(serialization.Encoding.PEM)

    private_key_path.write_bytes(private_key_bytes)
    public_key_path.write_bytes(public_key_bytes)
    certificate_path.write_bytes(certificate_bytes)

    result = {
        "private_key_path": str(private_key_path),
        "public_key_path": str(public_key_path),
        "certificate_path": str(certificate_path),
        "subject_common_name": args.subject_common_name,
        "subject_organization": args.subject_organization,
    }
    print(json.dumps(result, indent=2))
    return 0


def _upsert_registry(args: argparse.Namespace) -> int:
    client = ServiceNowAdminClient(
        instance_url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
    )
    payload = _read_json_file(args.payload_file)
    records = client.query_table(
        args.table,
        query=f"{args.lookup_field}={args.lookup_value}",
        fields=["sys_id", args.lookup_field],
        limit=2,
    )

    if args.dry_run:
        print(
            json.dumps(
                {
                    "table": args.table,
                    "lookup_field": args.lookup_field,
                    "lookup_value": args.lookup_value,
                    "existing_matches": records,
                    "payload": payload,
                },
                indent=2,
            )
        )
        return 0

    if records:
        updated = client.update_record(args.table, records[0]["sys_id"], payload)
        print(json.dumps({"action": "updated", "record": updated}, indent=2))
        return 0

    created = client.create_record(args.table, payload)
    print(json.dumps({"action": "created", "record": created}, indent=2))
    return 0


def _validate_registry(args: argparse.Namespace) -> int:
    client = ServiceNowAdminClient(
        instance_url=args.url,
        username=args.username,
        password=args.password,
        token=args.token,
        timeout=args.timeout,
    )
    fields = _split_csv(args.fields) if args.fields else ["sys_id", args.lookup_field]
    records = client.query_table(
        args.table,
        query=f"{args.lookup_field}={args.lookup_value}",
        fields=fields,
        limit=args.limit,
    )
    print(json.dumps({"match_count": len(records), "records": records}, indent=2))
    return 0 if records else 2


def _emit_env(args: argparse.Namespace) -> int:
    tenant_id = args.tenant_id or os.environ.get("SERVICENOW_SN_JWT_TENANT_ID") or os.environ.get("SERVICENOW_OBO_TENANT_ID", "")
    upstream_client_id = (
        args.upstream_client_id
        or os.environ.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID")
        or os.environ.get("SERVICENOW_OBO_CLIENT_ID", "")
    )
    token_endpoint = args.token_endpoint or f"{_normalize_url(args.url)}/oauth_token.do"

    lines = [
        "# Generated by scripts/bootstrap_servicenow_jwt.py",
        f"SERVICENOW_SN_JWT_TENANT_ID={tenant_id}",
        f"SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID={upstream_client_id}",
        f"SERVICENOW_SN_JWT_CLIENT_ID={args.client_id}",
        f"SERVICENOW_SN_JWT_PRIVATE_KEY_PATH={args.private_key_path}",
        f"SERVICENOW_SN_JWT_TOKEN_ENDPOINT={token_endpoint}",
        f"SERVICENOW_SN_JWT_USER_CLAIM_SOURCE={args.user_claim_source}",
    ]
    if args.client_secret:
        lines.append(f"SERVICENOW_SN_JWT_CLIENT_SECRET={args.client_secret}")
    if args.scope:
        lines.append(f"SERVICENOW_SN_JWT_SCOPE={args.scope}")
    if args.kid:
        lines.append(f"SERVICENOW_SN_JWT_KID={args.kid}")

    content = "\n".join(lines) + "\n"
    if args.output_file:
        Path(args.output_file).write_text(content, encoding="utf-8")
    print(content, end="")
    return 0


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", default=os.environ.get("SERVICENOW_INSTANCE_URL"), help="ServiceNow instance URL")
    parser.add_argument("--username", default=os.environ.get("SERVICENOW_USERNAME"), help="ServiceNow admin username")
    parser.add_argument("--password", default=os.environ.get("SERVICENOW_PASSWORD"), help="ServiceNow admin password")
    parser.add_argument("--token", default=os.environ.get("SERVICENOW_TOKEN"), help="ServiceNow bearer token")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ServiceNow JWT bootstrap helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="Discover OAuth-related ServiceNow tables and fields")
    _add_connection_args(discover)
    discover.add_argument("--query", default="oauth", help="Substring to search in table names/labels")
    discover.add_argument("--limit", type=int, default=25, help="Maximum candidate tables to return")
    discover.add_argument("--include-fields", action="store_true", help="Also list dictionary fields for each candidate table")
    discover.add_argument("--field-limit", type=int, default=200, help="Maximum dictionary fields per table")
    discover.set_defaults(func=_discover)

    keygen = subparsers.add_parser("generate-key-material", help="Generate RSA key pair and certificate PEM files")
    keygen.add_argument("--output-dir", default=str(REPO_ROOT / ".servicenow-jwt"), help="Output directory for generated PEM files")
    keygen.add_argument("--basename", default="servicenow-jwt", help="Base file name prefix")
    keygen.add_argument("--key-size", type=int, default=2048, help="RSA key size")
    keygen.add_argument("--years", type=int, default=2, help="Certificate validity period in years")
    keygen.add_argument("--subject-common-name", default="ServiceNow JWT Delegated Auth", help="Certificate subject common name")
    keygen.add_argument("--subject-organization", default="ServiceNow MCP", help="Certificate subject organization")
    keygen.add_argument("--passphrase", default=os.environ.get("SERVICENOW_SN_JWT_PRIVATE_KEY_PASSPHRASE"), help="Optional private key passphrase")
    keygen.add_argument("--overwrite", action="store_true", help="Allow overwriting existing output files")
    keygen.set_defaults(func=_generate_key_material)

    upsert = subparsers.add_parser("upsert-registry", help="Create or update a ServiceNow registry/security record")
    _add_connection_args(upsert)
    upsert.add_argument("--table", required=True, help="ServiceNow table name for the registry/security record")
    upsert.add_argument("--lookup-field", required=True, help="Field used to locate an existing record")
    upsert.add_argument("--lookup-value", required=True, help="Value used to locate an existing record")
    upsert.add_argument("--payload-file", required=True, help="Path to JSON object payload for the target record")
    upsert.add_argument("--dry-run", action="store_true", help="Print the target operation without writing changes")
    upsert.set_defaults(func=_upsert_registry)

    validate = subparsers.add_parser("validate-registry", help="Validate that a ServiceNow registry/security record exists")
    _add_connection_args(validate)
    validate.add_argument("--table", required=True, help="ServiceNow table name for the registry/security record")
    validate.add_argument("--lookup-field", required=True, help="Field used to locate the record")
    validate.add_argument("--lookup-value", required=True, help="Value used to locate the record")
    validate.add_argument("--fields", default="sys_id", help="Comma-separated fields to return")
    validate.add_argument("--limit", type=int, default=5, help="Maximum matching records to return")
    validate.set_defaults(func=_validate_registry)

    emit_env = subparsers.add_parser("emit-env", help="Emit remaining SERVICENOW_SN_JWT_* env values")
    emit_env.add_argument("--url", default=os.environ.get("SERVICENOW_INSTANCE_URL"), help="ServiceNow instance URL")
    emit_env.add_argument("--tenant-id", default=os.environ.get("SERVICENOW_SN_JWT_TENANT_ID"), help="Entra tenant ID")
    emit_env.add_argument("--upstream-client-id", default=os.environ.get("SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID"), help="Expected incoming token audience/client ID")
    emit_env.add_argument("--client-id", required=True, help="ServiceNow OAuth client ID")
    emit_env.add_argument("--private-key-path", required=True, help="Path to generated private key PEM file")
    emit_env.add_argument("--token-endpoint", default=os.environ.get("SERVICENOW_SN_JWT_TOKEN_ENDPOINT"), help="ServiceNow OAuth token endpoint")
    emit_env.add_argument("--user-claim-source", default=os.environ.get("SERVICENOW_SN_JWT_USER_CLAIM_SOURCE", "preferred_username"), help="User claim mapped to the ServiceNow subject")
    emit_env.add_argument("--client-secret", default=os.environ.get("SERVICENOW_SN_JWT_CLIENT_SECRET"), help="Optional ServiceNow OAuth client secret")
    emit_env.add_argument("--scope", default=os.environ.get("SERVICENOW_SN_JWT_SCOPE"), help="Optional ServiceNow OAuth scope")
    emit_env.add_argument("--kid", default=os.environ.get("SERVICENOW_SN_JWT_KID"), help="Optional JWT key ID header")
    emit_env.add_argument("--output-file", default=str(REPO_ROOT / "servicenow-jwt-bootstrap.env"), help="Optional output env file path")
    emit_env.set_defaults(func=_emit_env)

    return parser


def main() -> int:
    _load_env()
    parser = _build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except requests.HTTPError as exc:
        response = exc.response
        detail = response.text if response is not None else str(exc)
        print(f"HTTP error: {detail}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())