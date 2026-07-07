# ServiceNow MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server that interfaces with ServiceNow, allowing AI agents to access and manipulate ServiceNow data through a secure API using explicit MCP tools and resources.

## Features

### Resources

- `servicenow://incidents`: List recent incidents
- `servicenow://incidents/{number}`: Get a specific incident by number
- `servicenow://users`: List users
- `servicenow://knowledge`: List knowledge articles
- `servicenow://tables`: List available tables
- `servicenow://tables/{table}`: Get records from a specific table
- `servicenow://schema/{table}`: Get the schema for a table

### Tools

#### Basic Tools
- `create_incident`: Create a new incident
- `update_incident`: Update an existing incident
- `search_records`: Search for records using text query
- `get_record`: Get a specific record by sys_id
- `perform_query`: Perform a query against ServiceNow
- `add_comment`: Add a comment to an incident (customer visible)
- `add_work_notes`: Add work notes to an incident (internal)

#### Script Management Tool
- `update_script`: Update ServiceNow script files (script includes, business rules, etc.)

## Installation

This repository is currently supported as a source checkout only.

### From Source

```bash
git clone https://github.com/drewelewis/ai-servicenow-mcp-obo.git
cd ai-servicenow-mcp-obo
pip install -e .
```

Notes:

1. Do not use the original upstream repository URL for this fork's OBO-specific changes.
2. Do not rely on a PyPI package for this repo's current feature set.
3. On Windows, you can also use the provided helper scripts for local setup: `_env_create.bat`, `_env_activate.bat`, and `_install.bat`.

## Usage

### Command Line

Run the server using the Python module.

#### Example Using Basic Auth

```bash
python -m mcp_server_servicenow.cli --url "https://your-instance.service-now.com/" --username "your-username" --password "your-password"
```

Or use environment variables:

```bash
export SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
export SERVICENOW_USERNAME="your-username"
export SERVICENOW_PASSWORD="your-password"
python -m mcp_server_servicenow.cli
```

On Windows PowerShell:

```powershell
$env:SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
$env:SERVICENOW_USERNAME="your-username"
$env:SERVICENOW_PASSWORD="your-password"
python -m mcp_server_servicenow.cli
```

#### Example Using Entra OBO

Use OBO when your upstream caller provides a user bearer token and you want delegated downstream access.

```bash
python -m mcp_server_servicenow.cli \
  --url "https://your-instance.service-now.com/" \
  --obo-tenant-id "<tenant-guid>" \
  --obo-client-id "<broker-app-client-id>" \
  --obo-client-secret "<broker-app-client-secret>" \
  --obo-scope "api://<downstream-app-id>/.default"
```

Or use environment variables:

```bash
export SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
export SERVICENOW_OBO_TENANT_ID="<tenant-guid>"
export SERVICENOW_OBO_CLIENT_ID="<broker-app-client-id>"
export SERVICENOW_OBO_CLIENT_SECRET="<broker-app-client-secret>"
export SERVICENOW_OBO_SCOPE="api://<downstream-app-id>/.default"
python -m mcp_server_servicenow.cli
```

On Windows PowerShell:

```powershell
$env:SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
$env:SERVICENOW_OBO_TENANT_ID="<tenant-guid>"
$env:SERVICENOW_OBO_CLIENT_ID="<broker-app-client-id>"
$env:SERVICENOW_OBO_CLIENT_SECRET="<broker-app-client-secret>"
$env:SERVICENOW_OBO_SCOPE="api://<downstream-app-id>/.default"
python -m mcp_server_servicenow.cli
```

Auth selection rules:

1. OBO and basic auth are both supported, but they are separate auth modes.
2. If complete OBO settings are present, the CLI selects OBO.
3. If OBO is not configured, the CLI can fall back to token auth, OAuth, or basic username/password.
4. Do not assume `--username` and `--password` are combined with OBO; they are used for the non-OBO auth paths.

### MCP Explorer (Inspector) Quick Start

If you are using this repository scripts on Windows:

1. Create and activate the virtual environment.
2. Copy `.env.example` to `.env` and fill in your ServiceNow credentials.
3. Install dependencies.
4. Start MCP Explorer.

```bat
_env_create.bat
_env_activate.bat
copy .env.example .env
_install.bat
_start_mcp_explorer.bat
```

Stop MCP Explorer when done:

```bat
_stop_mcp_explorer.bat
```

Why this matters: `_start_mcp_explorer.bat` launches `python -m mcp_server_servicenow.cli`, which loads values from `.env` automatically.

### Configuration in Cline

To use this MCP server with Cline, add the following to your MCP settings file:

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "/path/to/your/python/executable",
      "args": [
        "-m",
        "mcp_server_servicenow.cli",
        "--url", "https://your-instance.service-now.com/",
        "--username", "your-username",
        "--password", "your-password"
      ],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

**Note:** Make sure to use the full path to the Python executable that has the `mcp-server-servicenow` package installed.

## Troubleshooting Startup

- `Error: ServiceNow instance URL is required`
  - Set `SERVICENOW_INSTANCE_URL` in your environment, or create `.env` from `.env.example`.
- `Error: Authentication credentials required`
  - Provide one supported auth method in `.env` (basic auth, token, or OAuth values).
- `npx was not found`
  - Install Node.js so `npx` is available in `PATH`.

## Tool Usage Examples

Use explicit tool inputs for all operations. For searching and updates, call `search_records`, `perform_query`, `update_incident`, `add_comment`, and `add_work_notes` directly with structured arguments.

### Managing Scripts

You can update ServiceNow scripts from local files:

```
Update the ServiceNow script include "HelloWorld" with the contents of hello_world.js
Upload utils.js to ServiceNow as a script include named "UtilityFunctions"
Update @form_validation.js, it's a client script called "FormValidation"
```

## Authentication Methods

The server supports multiple authentication methods:

1. **Basic Authentication**: Username and password
2. **Token Authentication**: OAuth token
3. **OAuth Authentication**: Client ID, Client Secret, Username, and Password
4. **Entra OBO Authentication**: Exchange incoming user token for downstream API token

### Entra OBO Setup

Use OBO when you want per-user delegated access instead of storing static ServiceNow credentials.

#### Architecture Overview

```mermaid
flowchart LR
  subgraph ID[Identity Plane]
    B[Broker App Registration]
    E[Entra Token Endpoint]
    D[Downstream API App Registration]
  end

  subgraph RT[MCP Runtime Plane]
    U[User or Upstream MCP Host]
    I[MCP Server Ingress]
    C[Validated Request Auth Context]
    T[Tool Handlers]
    K[User-scoped OBO Token Cache]
  end

  subgraph BS[Business System Plane]
    G[Protected Gateway or API Facade]
    S[ServiceNow Instance]
  end

  U -->|Bearer token| I
  I --> C
  C --> T
  C -->|OBO exchange| E
  B -. broker client identity .-> E
  D -. audience and delegated scope .-> E
  E -->|Scoped downstream token| K
  K --> T
  T -->|Delegated call| G
  G --> S
  T -. alternative direct integration path .-> S
```

Read this diagram in three layers:

1. Identity plane defines who can mint and accept delegated tokens.
2. MCP runtime plane validates the incoming user, performs OBO, and executes tools.
3. Business system plane is where ServiceNow is ultimately reached, either directly or through a protected facade.

#### Design Check

This repository currently models an Entra-based delegated access pattern with these important boundaries:

1. The MCP server acts as the broker confidential client.
2. The incoming user token is captured from the active MCP request context and used for OBO exchange.
3. The exchanged token is meant for the configured downstream audience, not automatically for every HTTP endpoint.
4. A direct ServiceNow call only works with this pattern if the downstream target can validate the Entra-issued bearer token or is fronted by a gateway that can.

Practical implication:

- If you call ServiceNow through an Entra-protected API or gateway, the broker/downstream app-registration model fits well.
- If you call ServiceNow directly and it is not validating your Entra token as a resource audience, use one of the alternatives below instead of assuming raw OBO is enough by itself.

#### Main Components And Why They Exist

1. MCP client or upstream host:
  - Originates the request on behalf of a signed-in user.
  - Supplies the user assertion token that anchors delegated identity.
2. MCP server ingress:
  - Receives the MCP request and extracts transport auth metadata.
  - Prevents tool execution from running without an authenticated caller context.
3. Request auth context:
  - Holds the current request's user assertion in request-scoped state.
  - Prevents one user's delegated token flow from being sourced from another request.
4. Broker app registration:
  - Represents this MCP server as a confidential Entra client.
  - Is required so the server can perform the OBO token exchange.
5. Entra token endpoint:
  - Exchanges the upstream user assertion for a scoped downstream access token.
  - Enforces tenant, consent, and delegated-permission policy.
6. Downstream API app registration:
  - Represents the resource audience the broker is requesting access to.
  - Exposes the delegated scope that the broker asks for during OBO.
7. Service principals:
  - Materialize both app registrations inside the tenant.
  - Are required for consent, policy enforcement, and enterprise administration.
8. Downstream connector target:
  - Is the actual HTTP target that receives the delegated bearer token.
  - In this design, that target should be an Entra-protected API, gateway, or another resource that trusts the issued token.
9. ServiceNow instance:
  - Remains the system of record for incidents, tables, scripts, and user-facing operations.
  - May be reached directly, or indirectly through a gateway or facade depending on the auth pattern you choose.

#### Where Each Component Sits In The Design

- Identity plane:
  - Broker app registration, downstream app registration, service principals, Entra token endpoint.
- MCP runtime plane:
  - MCP client, MCP server ingress, request auth context, tool handlers.
- Business system plane:
  - Downstream connector target and the ServiceNow instance.

Production note:

- The current implementation validates incoming Entra bearer tokens for signature, issuer, audience, and expiry before OBO exchange.
- The current implementation also keeps delegated tokens in a user-scoped in-memory cache keyed by validated identity plus downstream scope and token endpoint.
- Broader production hardening remains tracked in [todo.md](todo.md), including policy refinement, retry behavior, and full conformance coverage.

#### MCP OBO Flow

```mermaid
sequenceDiagram
  autonumber
  participant U as User / MCP Client
  participant I as MCP Server Ingress
  participant C as Session Auth Context
  participant O as OBO Token Exchange
  participant E as Entra ID Token Endpoint
  participant K as User-scoped Delegated Token Cache
  participant S as Downstream API or ServiceNow Path

  U->>I: MCP request with user bearer token
  I->>C: Validate issuer, audience, signature, expiry
  C->>O: Tool call needs downstream access
  O->>E: Exchange user assertion for delegated token
  E-->>O: Short-lived scoped token
  O->>K: Cache token by user identity and scope
  K->>S: Attach bearer token to API call
  S-->>I: Response
  I-->>U: Tool result + audit metadata
```

Flow summary:

1. The MCP request carries the user assertion.
2. The server validates identity and binds it to a session context.
3. The server performs OBO exchange for downstream scoped access.
4. The delegated token is cached per user and downstream scope until near expiry.
5. Result metadata is returned to the caller.

#### Fully Scriptable Entra Bootstrap

This repository now includes a script that creates everything needed in Entra for OBO and prints the exact `.env` values for this server.

Purpose of the Entra registrations:

1. Broker app registration:
  - Represents this MCP server as a confidential client.
  - Accepts the incoming user assertion and performs OBO token exchange.
2. Downstream API app registration:
  - Represents the resource API audience for delegated access.
  - Exposes the delegated scope (for example, `user_impersonation`) that the broker requests.
3. Service principals:
  - Materialize both app registrations in your tenant so permissions and consent can be enforced.
4. Delegated permission + admin consent:
  - Grants the broker app permission to request downstream delegated tokens for signed-in users.
  - Ensures OBO calls are authorized by policy instead of static shared credentials.

Registration relationship (quick view):

```mermaid
flowchart LR
  B[Broker App Registration - MCP confidential client]
  D[Downstream API App Registration]
  SC[user_impersonation delegated scope]
  B -. "represented in tenant" .-> SB[Broker Service Principal]
  D -. "represented in tenant" .-> SD[Downstream Service Principal]
  B -->|Delegated permission plus admin consent| D
  D -->|Exposes| SC
```

#### When This Design Is The Right Fit

Use this brokered OBO design when all of the following are true:

1. Your upstream caller already authenticates users with Entra ID.
2. You need per-user delegated authorization, not a shared integration identity.
3. Your downstream API can validate the Entra token directly, or is fronted by a gateway that can.

Optional validation configuration:

- `SERVICENOW_OBO_EXPECTED_AUDIENCE`: comma-separated allowed audiences for incoming bearer tokens. Defaults to the broker app client ID.
- `SERVICENOW_OBO_EXPECTED_ISSUER`: comma-separated allowed issuers for incoming bearer tokens. Defaults to Entra tenant issuers for the configured tenant.

#### Potential Alternatives

1. Direct ServiceNow basic auth:
  - Simplest setup.
  - Uses a shared integration identity, so it does not preserve end-user authorization boundaries.
2. Direct ServiceNow OAuth with a shared service account:
  - Better secret hygiene than basic auth.
  - Still behaves like app-owned access unless you build separate per-user token handling.
3. ServiceNow-native per-user OAuth:
  - Best fit when ServiceNow itself is the true resource server and must authorize each user directly.
  - More operationally complex because you manage ServiceNow OAuth trust and user-consent flows instead of Entra OBO alone.
4. Entra-protected gateway or facade in front of ServiceNow:
  - Best fit for this repository's current broker/downstream app-registration shape.
  - Lets the gateway validate Entra tokens, enforce policy, and then call ServiceNow with its own trusted backend mechanism.
5. App-only or client-credentials integration:
  - Useful for unattended automation or batch operations.
  - Not appropriate when you must preserve the initiating user's security boundary.

Recommended decision rule:

- If the goal is true per-user delegation into a resource that trusts Entra tokens, keep the brokered OBO design.
- If the goal is direct ServiceNow access and ServiceNow is the real authorization authority, prefer ServiceNow-native OAuth or a gateway pattern.

Script path:

- `scripts/bootstrap-entra-obo.ps1`

What the script does:

1. Creates or reuses a broker app registration (the MCP server confidential client).
2. Creates or reuses a downstream API app registration.
3. Creates service principals for both apps.
4. Configures an exposed delegated scope on the downstream API.
5. Adds delegated permission from broker app to downstream API.
6. Attempts tenant-wide admin consent.
7. Creates/rotates a broker app client secret.
8. Writes and prints a generated env block with all required `SERVICENOW_OBO_*` values.

Prerequisites:

1. Azure CLI installed (`az`).
2. Signed in to Azure CLI (`az login`).
3. Permission to create app registrations and grant admin consent (or have an admin run consent step).

Run in PowerShell from repo root:

```powershell
# Optional: allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# Sign in if needed
az login

# Run with defaults
.\scripts\bootstrap-entra-obo.ps1

# Or run with explicit names/tenant
.\scripts\bootstrap-entra-obo.ps1 `
  -TenantId "<tenant-guid>" `
  -BrokerAppName "servicenow-mcp-obo-broker" `
  -DownstreamApiAppName "servicenow-mcp-obo-downstream-api" `
  -DownstreamScopeName "user_impersonation" `
  -SecretYears 1 `
  -OutputEnvFile ".env.obo.generated"
```

Expected output artifacts:

1. Console output with the generated env values.
2. A file (default `.env.obo.generated`) containing:
   - `SERVICENOW_OBO_TENANT_ID`
   - `SERVICENOW_OBO_CLIENT_ID`
   - `SERVICENOW_OBO_CLIENT_SECRET`
   - `SERVICENOW_OBO_SCOPE`
   - `SERVICENOW_OBO_TOKEN_ENDPOINT`
   - `SERVICENOW_OBO_USER_ASSERTION` placeholder

Then apply those values to your `.env` used by this MCP server.

#### Merge Generated OBO Values Into .env

Use the helper script to merge generated OBO settings into your existing `.env` while preserving unrelated keys.

Script path:

- `scripts/apply-obo-env.ps1`

Run:

```powershell
# Dry run (shows which keys will be applied)
.\scripts\apply-obo-env.ps1 -SourceEnvFile ".env.obo.generated" -TargetEnvFile ".env" -WhatIfOnly

# Apply changes and create backup of .env
.\scripts\apply-obo-env.ps1 -SourceEnvFile ".env.obo.generated" -TargetEnvFile ".env"
```

Behavior:

1. Reads OBO values from the generated file.
2. Updates these keys in `.env`:
  - `SERVICENOW_OBO_TENANT_ID`
  - `SERVICENOW_OBO_CLIENT_ID`
  - `SERVICENOW_OBO_CLIENT_SECRET`
  - `SERVICENOW_OBO_SCOPE`
  - `SERVICENOW_OBO_TOKEN_ENDPOINT`
  - `SERVICENOW_OBO_USER_ASSERTION`
3. Creates timestamped backup file by default: `.env.bak-YYYYMMDD-HHMMSS`.

Important runtime note:

- `SERVICENOW_OBO_USER_ASSERTION` is an incoming user token and should be supplied at runtime by your upstream caller/session, not hardcoded as a long-lived secret.

Set these environment variables:

```bash
SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com/"
SERVICENOW_OBO_TENANT_ID="<tenant-id-guid>"
SERVICENOW_OBO_CLIENT_ID="<app-client-id>"
SERVICENOW_OBO_CLIENT_SECRET="<app-client-secret>"
SERVICENOW_OBO_SCOPE="api://<downstream-app-id>/.default"
# Optional override
# SERVICENOW_OBO_TOKEN_ENDPOINT="https://login.microsoftonline.com/<tenant-id>/oauth2/v2.0/token"
# Optional local-only fallback if request transport cannot provide assertion
# SERVICENOW_OBO_ALLOW_STATIC_ASSERTION="false"
# SERVICENOW_OBO_USER_ASSERTION="<incoming-user-access-token>"
```

Then run:

```bash
python -m mcp_server_servicenow.cli --transport stdio
```

Notes:

- OBO mode is selected automatically when all required `SERVICENOW_OBO_*` values are present.
- OBO takes precedence over static token/basic auth.
- OBO uses request-bound bearer assertions by default and fails closed when assertion is missing.
- `SERVICENOW_OBO_ALLOW_STATIC_ASSERTION=true` is intended for local testing only.
- The downstream API represented by `SERVICENOW_OBO_SCOPE` must trust your Entra app and accept delegated tokens.

## Development

### Prerequisites

- Python 3.8+
- ServiceNow instance with API access

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/michaelbuckner/servicenow-mcp.git
cd servicenow-mcp

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
