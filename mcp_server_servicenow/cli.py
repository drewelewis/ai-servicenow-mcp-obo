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
    auth_group.add_argument(
        "--obo-allow-static-assertion",
        help="Allow static OBO assertion fallback (local testing only)",
        action="store_true",
        default=(os.environ.get("SERVICENOW_OBO_ALLOW_STATIC_ASSERTION", "").lower() in {"1", "true", "yes"}),
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

    if all_obo_required:
        from mcp_server_servicenow.server import create_obo_auth
        auth = create_obo_auth(
            tenant_id=args.obo_tenant_id,
            client_id=args.obo_client_id,
            client_secret=args.obo_client_secret,
            user_assertion=args.obo_user_assertion,
            scope=args.obo_scope,
            token_endpoint=args.obo_token_endpoint,
            allow_static_assertion=args.obo_allow_static_assertion,
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
        print("Either provide username/password, token, or OAuth credentials")
        sys.exit(1)
    
    # Create and run the server
    server = ServiceNowMCP(instance_url=args.url, auth=auth)
    server.run(transport=args.transport)

if __name__ == "__main__":
    main()
