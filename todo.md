# Project TODO

This file tracks planned and in-progress work for general repository development.

## Conventions

- Keep items concise and action-oriented.
- Move items between sections as status changes.
- Link related files or PRs when relevant.
- Mark completed items with completion date.

## Backlog

- [ ] Keep shared project automation and contributor workflow docs up to date.
- [ ] Review and improve test coverage for non-OBO modules.
- [ ] Track cross-feature technical debt items.

### OBO Compliance Plan (Spec-Driven)

#### P0 (Must - Blockers for Spec Conformance)

- [x] Implement authenticated transport token capture from request/session boundary and reject missing identity context. (2026-07-02)
- [x] Add incoming user token validation (issuer, audience, signature, expiry) on the OBO request path before delegated downstream execution. (2026-07-07)
- [x] Bind validated identity to request-scoped security context for OBO execution. (2026-07-07)
- [ ] Refactor OBO exchange to resolve subject token from active request context at call time.
- [x] Implement user-scoped delegated token cache keyed by identity + audience/scope tuple. (2026-07-07)
- [ ] Add token refresh safety buffer (30-60 seconds) and deterministic fail-closed behavior on refresh errors.
- [ ] Remove or guard legacy entrypoints that bypass OBO enforcement path.
- [ ] Add structured correlation IDs propagated across tool invocation, token exchange, and downstream API call.

#### P1 (Should - Security and Reliability Hardening)

- [ ] Enforce least-privilege scope policy per tool operation (deny over-broad requested scopes).
- [ ] Add bounded retry policy for token exchange transient failures with explicit retryable vs non-retryable classes.
- [ ] Add preflight auth checks for write tools to avoid partial side effects.
- [ ] Add sanitized auth error taxonomy (invalid incoming token, exchange failure, downstream deny, downstream transient).
- [ ] Add audit event schema mapping delegated user identity to tool action and downstream resource.
- [ ] Add secure secret source abstraction (env/dev vs managed secret store/prod) and rotation runbook references.

#### P2 (Operational Excellence and Release Gates)

- [ ] Build conformance test suite mapped to obo_guide.md MUST/SHOULD requirements.
- [ ] Add automated regression tests covering incoming token validation, request-scoped auth binding, and user-scoped OBO token cache behavior.
- [ ] Add negative security tests (expired token, tampered signature, wrong audience, missing scope).
- [ ] Add concurrency/isolation tests validating no cross-session token leakage under load.
- [ ] Add observability checks ensuring no tokens/secrets are emitted in logs.
- [ ] Add deployment readiness checklist execution report (security review, conformance pass, incident playbook).

#### Delivery Tracking Notes

- [ ] Produce implementation matrix linking each OBO spec requirement to code locations and test coverage.
- [ ] Track unresolved blockers and decisions in this file until all P0 items are completed.

### Ongoing Testing and Verification (Continuous)

- [ ] For every OBO code change, run auth-path unit tests and capture pass/fail in PR notes.
- [ ] For every OBO code change, run negative token tests (expired, bad signature, wrong audience, missing scope).
- [ ] For every OBO code change, run concurrency isolation checks for cross-session token leakage.
- [ ] For every OBO code change, verify token refresh buffer behavior under near-expiry conditions.
- [ ] For every OBO code change, verify structured logs include correlation IDs and exclude token/secret material.
- [ ] Weekly: review open OBO tasks and re-prioritize P0/P1/P2 based on latest findings.
- [ ] Weekly: re-run spec-to-code gap review against obo_guide.md and update backlog tasks.
- [ ] Release gate: require OBO conformance checklist and negative suite pass before tagging release.

## In Progress

- [ ] Verify obo_guide.md requirements against current implementation and capture all missing gaps as actionable tasks.
- [ ] Run manual regression testing for OBO auth hardening and architecture/documentation updates.
- [ ] Validate ServiceNow JWT bearer delegated auth end-to-end against the target instance and update README with verified setup/usage guidance.
- [ ] Decide whether to deprecate or remove the legacy direct OBO path after ServiceNow JWT bearer flow is proven in your tenant.

## Done

- [x] Fixed Azure bootstrap Graph PATCH body handling and made delegated scope configuration idempotent so reruns no longer fail on malformed JSON or enabled-scope replacement. (2026-07-08)
- [x] Extended Azure bootstrap output and env-merge automation to emit/carry ServiceNow JWT delegated-auth Azure values, and added a ServiceNow bootstrap helper for table discovery, key generation, registry upsert/validation, and env emission. (2026-07-08)
- [x] Implemented ServiceNow OAuth JWT bearer delegated-user auth mode (incoming Entra token validation + signed JWT assertion exchange + user-scoped token cache) and wired CLI/interactive helper/env template configuration for local and MCP runtime use. (2026-07-08)
- [x] Removed unintended broker delegated permission/grant to the SAML-based ServiceNow enterprise app (`65f131b1-2cf1-42b9-b700-ee1485da296b`) to restore intended OBO app-permission scope. (2026-07-07)
- [x] Reverted local OBO scope to OAuth-capable app resource after confirming tenant `ServiceNow` app is SAML-only (AADSTS399274), and documented required non-SAML OBO audience guidance for end-to-end delegated access. (2026-07-07)
- [x] Granted broker app delegated `user_impersonation` permission to the tenant ServiceNow resource app and switched `SERVICENOW_OBO_SCOPE` to ServiceNow audience (`https://dev397814.service-now.com/.default`) for direct API OBO token acceptance. (2026-07-07)
- [x] Corrected local ServiceNow instance URL in `.env` from `/login.do` page URL to root instance URL so API requests resolve to `/api/now/...` and do not redirect to session timeout. (2026-07-07)
- [x] Fixed Entra interactive sign-in failure AADSTS500113 by configuring localhost public-client redirect URI on the interactive app registration and updating bootstrap automation to set it by default. (2026-07-07)
- [x] Added missing local interactive OBO settings (`SERVICENOW_OBO_PUBLIC_CLIENT_ID`, `SERVICENOW_OBO_USER_SCOPE`) to `.env` so `_start_obo.bat` acquires a broker-audience user token instead of self-resource requests. (2026-07-07)
- [x] Added root launcher script `_start_mcp_server.bat` to start the MCP server with `python -m mcp_server_servicenow.cli`. (2026-07-07)
- [x] Extended OBO bootstrap automation to provision an interactive public-client app, expose broker delegated scope, grant interactive-to-broker delegated permission, and emit `SERVICENOW_OBO_PUBLIC_CLIENT_ID` plus `SERVICENOW_OBO_USER_SCOPE` for local MFA assertion acquisition. (2026-07-07)
- [x] Fixed interactive OBO assertion acquisition default scope to GUID-based format (`<client-id>/.default`) and added targeted AADSTS90009 troubleshooting hint for Entra self-token errors. (2026-07-07)
- [x] Added root launcher script `_start_obo.bat` to run the interactive OBO helper from repository root without path typing. (2026-07-07)
- [x] Removed the obsolete `# OBO auth credentials` heading from local `.env` to keep auth comments aligned with current OBO flow expectations. (2026-07-07)
- [x] Added local-test OBO user-token auto acquisition in the interactive helper using interactive Entra sign-in (browser popup with MFA, with optional device-code fallback) when a runtime assertion is not provided, simulating Teams-like inbound bearer behavior. (2026-07-07)
- [x] Updated interactive helper env parsing to accept `SERVICENOW_OBO_USERNAME`/`SERVICENOW_OBO_PASSWORD` as fallback defaults for OAuth username/password resolution to avoid manual prompting/renaming in local OBO test env files. (2026-07-07)
- [x] Updated interactive Python helper script to remove basic-auth login and use .env/args-based non-basic auth modes (OBO, token, OAuth), and documented usage in README. (2026-07-07)
- [x] Added explicit CLI startup status messaging so stdio server startup is visible as waiting-for-client instead of appearing frozen. (2026-07-07)
- [x] Added explicit ServiceNow OAuth and bearer-token variable guidance comments in local .env auth configuration. (2026-07-07)
- [x] Added inline authentication-setting comments to local .env so each auth variable purpose is explicit. (2026-07-07)
- [x] Restructured README so each authentication mode has its own usage section and clearer decision guidance. (2026-07-07)
- [x] Clarified README usage examples to separate basic auth from Entra OBO and documented CLI auth precedence. (2026-07-07)
- [x] Corrected README installation guidance to remove inherited PyPI and upstream-source instructions and document this repository as source-only. (2026-07-07)
- [x] Added top-level OBO architecture diagram plus component placement and alternative auth patterns in README. (2026-07-07)
- [x] Implemented incoming Entra token validation and request-scoped auth binding for OBO downstream calls. (2026-07-07)
- [x] Implemented user-scoped delegated token caching and configurable expected audience/issuer controls for OBO. (2026-07-07)
- [x] Documented the main OBO architecture components, design boundaries, and authentication alternatives in README. (2026-07-07)
- [x] Converted OBO runtime flow to Mermaid sequence diagram and separated registration/object relationships for readability. (2026-07-07)
- [x] Fixed README Mermaid syntax for GitHub-safe rendering in the Entra registration relationship diagram. (2026-07-07)
- [x] Added a mini Mermaid diagram showing Broker vs Downstream Entra registration responsibilities in README. (2026-07-06)
- [x] Documented the purpose of Entra app registrations in README OBO setup guidance. (2026-07-06)
- [x] Added ignore rules for generated OBO secret artifacts to prevent accidental commits and blocked pushes. (2026-07-06)
- [x] Added MCP OBO flow diagram to README for delegated auth visualization. (2026-07-06)
- [x] Added changelog enforcement skill and repository instruction guardrails. (2026-07-02)
- [x] Added scriptable Entra OBO bootstrap and env-merge automation scripts. (2026-07-02)
- [x] Rewrote obo_guide.md as implementation-independent MCP OBO security specification. (2026-07-02)
- [x] Removed natural-language processing path and NLP tools to make server MCP-tool-only. (2026-07-02)
