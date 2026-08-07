# Azure Deployment Plan — ServiceNow MCP (OBO)

Status: Validated

## 1. Overview

Deploy the ServiceNow MCP server (delegated Entra OBO / JWT-bearer) to Azure as a
remotely reachable HTTP (SSE) endpoint.

- Deployment tool: Azure Developer CLI (`azd`)
- Infrastructure as Code: Bicep
- Hosting target: Azure Container Apps
- Secrets: Azure Key Vault (referenced via user-assigned managed identity)

## 2. Mode

- [ ] NEW
- [x] MODIFY (add Azure deployment to an existing repository)
- [ ] MODERNIZE

## 3. Application Facts (to confirm)

- Language/runtime: Python (>= 3.10 required by `mcp`; container will use 3.11)
- Framework: FastMCP (`mcp` package)
- Entrypoint (remote): `python -m mcp_server_servicenow.cli --transport sse`
- Transport: SSE (HTTP) — required for remote hosting; stdio is local-only
- Listen binding: must bind `0.0.0.0` and platform port via `FASTMCP_HOST` / `FASTMCP_PORT`
- Dependencies: `mcp`, `httpx`, `requests`, `PyJWT[crypto]`, `pydantic`, `python-dotenv`, `msal`
- Public dependency: JWKS already published (GitHub raw) — no change

## 4. Architecture (proposed)

| Component | Azure service | Notes |
|-----------|---------------|-------|
| MCP server (SSE) | Azure Container Apps | External HTTPS ingress on the app port |
| Container image | Azure Container Registry | Built and pushed by `azd` |
| Secrets | Azure Key Vault | ServiceNow creds, Entra broker secret, SN JWT client secret, RSA private key (PEM) |
| Identity | User-assigned managed identity | ACR pull + Key Vault secret get |
| Observability | Log Analytics + Container Apps env | Container console logs |

## 5. Configuration & Secrets Mapping (to finalize)

Non-secret app settings (env):
- `SERVICENOW_INSTANCE_URL`, `SERVICENOW_SN_JWT_TENANT_ID`, `SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID`,
  `SERVICENOW_SN_JWT_CLIENT_ID`, `SERVICENOW_SN_JWT_TOKEN_ENDPOINT`, `SERVICENOW_SN_JWT_JWKS_URL`,
  `SERVICENOW_SN_JWT_USER_CLAIM_SOURCE`, `FASTMCP_HOST=0.0.0.0`, `FASTMCP_PORT=<port>`

Secrets (Key Vault → Container App secret refs):
- `SERVICENOW_SN_JWT_PRIVATE_KEY` (PEM content — stored in Key Vault, injected as env, not a file path)
- `SERVICENOW_SN_JWT_CLIENT_SECRET` (if the ServiceNow OAuth client requires one)

> **Decision (resolved): JWT-bearer only.** The deployed server runs the delegated
> ServiceNow JWT-bearer path only. No ServiceNow admin `SERVICENOW_PASSWORD` and no
> OBO broker secret are deployed. Incoming Entra user tokens are validated by the
> server; per-user ServiceNow tokens are minted via the signed JWT assertion.

## 6. Resolved Decisions

- **Auth mode:** JWT-bearer only (no basic-auth fallback in Azure).
- **Ingress:** External (public) HTTPS ingress. Tool calls require a valid Entra bearer
  token (validated server-side). Note: unauthenticated `tools/list` is possible; endpoint
  hardening (e.g., network restriction / front door) is a follow-up option.
- **RSA private key:** Stored as a Key Vault secret (PEM), injected via managed identity.
- **Subscription & region:** Confirmed at execution time (azure-validate / azure-deploy).

## 7. Artifacts To Generate

- `Dockerfile` (Python 3.11 slim, non-root, runs SSE entrypoint)
- `azure.yaml` (azd service definition)
- `infra/` Bicep: Container Apps env, Container App, ACR, Key Vault, managed identity, Log Analytics
- `.dockerignore`

## 8. Workflow

`azure-prepare` (this plan + artifacts) → `azure-validate` → `azure-deploy`

## 9. Generated Artifacts (complete)

- `Dockerfile` — Python 3.11-slim, non-root (uid 10001), binds `0.0.0.0:8000`, runs SSE entrypoint
- `.dockerignore` — excludes `.env`, `.servicenow-jwt/`, `*.pem`, caches, tests
- `azure.yaml` — azd service `mcp` (host: containerapp, Docker build)
- `infra/main.bicep` — subscription-scope: resource group + resources module + outputs
- `infra/resources.bicep` — UAMI, Log Analytics, ACR (admin off), Key Vault (RBAC), KV secrets, Container Apps env, Container App (external ingress, KV secret refs via UAMI)
- `infra/main.parameters.json` — maps azd env values to Bicep params

Bicep validated with `az bicep build` (BICEP_BUILD_OK).

## 10. Required azd Environment Values (set before deploy)

Non-secret (`azd env set <NAME> <value>`):
- `SERVICENOW_INSTANCE_URL`, `SERVICENOW_SN_JWT_TENANT_ID`, `SERVICENOW_SN_JWT_UPSTREAM_CLIENT_ID`,
  `SERVICENOW_SN_JWT_CLIENT_ID`, `SERVICENOW_SN_JWT_TOKEN_ENDPOINT`, `SERVICENOW_SN_JWT_JWKS_URL`,
  `SERVICENOW_SN_JWT_USER_CLAIM_SOURCE` (optional; defaults to `preferred_username`)

Secrets (stored in Key Vault by the deployment):
- `SERVICENOW_SN_JWT_PRIVATE_KEY_BASE64` — base64 of the PEM private key
  (PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes('.servicenow-jwt/servicenow-jwt-private.pem'))`)
- `SERVICENOW_SN_JWT_CLIENT_SECRET` — optional; only if the ServiceNow client requires it

## 11. Validation Proof

Recipe: azd (Bicep). Validated 2026-08-05.

| Check | Command | Result |
|-------|---------|--------|
| azd installed | `azd version` | PASS (1.24.2) |
| Authenticated | `azd auth login --check-status` | PASS (logged in) |
| Environment | `azd env new servicenow-mcp --subscription d201ebeb-… --location eastus2` | PASS (default env set) |
| Subscription/location | `azd env get-values` | PASS (ME-MngEnvMCAP623732-drlewis-1 / East US 2) |
| Bicep build | `az bicep build --file infra/main.bicep` | PASS (BICEP_BUILD_OK) |
| Provision preview | `azd provision --preview --no-prompt` | PASS (exit 0; plans rg + Container App + ACA env + ACR + Key Vault + Log Analytics) |
| Package | `azd package --no-prompt` | PASS (exit 0; image build offloaded to ACR via `remoteBuild: true`) |

Static role verification: `infra/resources.bicep` assigns **AcrPull** (7f951dda-…) and
**Key Vault Secrets User** (4633458b-…) to the user-assigned managed identity used by the
Container App — sufficient for image pull and Key Vault secret retrieval.

Note: local Docker build failed with an SSL handshake error to PyPI (corporate TLS-inspection
proxy not trusted inside the build container); resolved by enabling ACR remote build
(`remoteBuild: true` in `azure.yaml`), so the image is built in Azure.
