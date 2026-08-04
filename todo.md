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

### MCP Server Tools

- [x] Register `list_incidents` as an MCP tool (was resource-only) so it appears in the Inspector Tools tab and returns most-recent incidents for the delegated user. (2026-08-04)
- [x] Remove the `servicenow://incidents` resource registration (resource reads lack the request Authorization header, so delegated OBO fails); expose `list_incidents` as a tool only. (2026-08-04)
- [x] Update README Features list (drop `servicenow://incidents` resource, add `list_incidents` tool, note delegated identity flows through tools) and add Step 11 documenting interactive MCP Inspector testing over SSE with a device-code Bearer header. (2026-08-04)

### Consumer Setup Tooling

- [x] Add scripted plugin activation (`activate-plugin` via CI/CD API) to the bootstrap helper so consumers can enable ServiceNow plugins without the UI. (2026-07-31)
- [x] Add a one-command `scripts/service_now_setup.py` orchestrator that runs the full ServiceNow-side setup (plugin, keys, JWKS, `oauth_jwt` record, env) against a consumer's own instance. (2026-07-31)
- [x] Rewrite the README Getting Started section in plain English (bring-your-own PDI, admin login, run the setup script). (2026-07-31)
- [x] Add a manual "enable account recovery" step to the README Getting Started runbook and renumber the following steps. (2026-07-31)
- [x] Clarify README Step 3 to keep `admin` basic auth working alongside Multiple Provider SSO by designating `admin` as the Account Recovery (ACR) user (SSO for other users, basic auth preserved for the setup script and MCP server). (2026-07-31)
- [x] Correct README Step 3 after testing disproved the ACR claim: the setup script enables multi-SSO (which alone does not block basic auth), Account Recovery is a UI-only feature the script never enables, and ACR designation only restores UI login not REST basic auth. Removed the manual account-recovery/authenticator enrollment step; documented `login.do?sysparm_prevent_sso=true` / `side_door.do` lockout recovery. (2026-07-31)
- [x] Reorder README Getting Started steps: Step 3 is now the `.env` PDI-details update (clone/install folded in); account-recovery note moved into the setup step; remaining steps renumbered and cross-references fixed. (2026-07-31)
- [x] Fix README Step 4 JWKS chicken-and-egg: split into 4a generate keys/JWKS (`--skip-records`), 4b publish `.servicenow-jwt/jwks.json` at a public URL, 4c re-run with `--jwks-url` to provision the `oauth_jwt` record. (2026-08-03)
- [x] Convert the README JWKS sub-steps (4a/4b/4c) into whole-numbered steps 4/5/6 and renumber the rest to 7-10. (2026-08-03)
- [x] Simplify `service_now_setup.py` final output to defer manual-step explanation to the README and reflect whether `oauth_jwt` provisioning ran or was skipped. (2026-08-03)
- [x] Add a README Step 4 blurb explaining why a JWKS is needed (OAuth 2.0 JWT bearer flow, private-key signing, public-key verification via JWKS, passwordless/rotatable/delegated access). (2026-08-03)
- [x] Correct the README Step 4 JWKS-purpose blurb to match `server.py`: server signs a JWT *assertion* carrying the delegated user (`sub`) to obtain a ServiceNow access token that is cached/reused per user, not a JWT per request; JWKS lets ServiceNow trust the server's signed user claim. (2026-08-03)
- [x] Correct README Step 5/6: publish JWKS URL into `.env` as `SERVICENOW_SN_JWT_JWKS_URL`, make Step 6 read it from `.env` (flag becomes an override), and replace the hardcoded `main` raw-GitHub example with a `<branch>` placeholder. (2026-08-03)
- [x] Make `service_now_setup.py` write provisioned `SERVICENOW_SN_JWT_*` values into `.env` automatically (upsert existing keys, append missing, never clobber the UI-only client secret) so consumers do not hand-edit `.env`; document as README Step 7. (2026-08-03)
- [x] Document `SERVICENOW_SN_JWT_JWKS_URL` in `.env.example` so the template matches README Step 5 and the setup script's provisioning input. (2026-08-03)
- [x] Realign numbering: drop numeric "Step N" prefixes from `service_now_setup.py` banners (descriptive phase labels) so they no longer clash with the README's Getting Started step numbers; README owns step numbering. (2026-08-03)
- [x] Rewrite README Step 7 with beginner-friendly, click-by-click ServiceNow navigation for revealing the client secret and ensuring a matching user (no assumed ServiceNow experience). (2026-08-03)
- [x] Set a `name` on the provisioned `oauth_jwt` record so it is no longer "(empty)" in the ServiceNow Application Registry and is easy to find. (2026-08-03)
- [x] Rename the provisioned entity to "MCP Entra to ServiceNow OBO" to reflect the integration intent (Entra→ServiceNow OBO via MCP) rather than the JWT-bearer mechanism. (2026-08-03)
- [x] Document the missing step: the smoke test must be run as an Entra user whose `preferred_username` maps to a ServiceNow user's email (Step 7b rewrite + Step 9 note) to avoid `invalid_grant`/`User not found`. (2026-08-03)
- [x] Warn in README Step 7b + troubleshooting that mapping to the `admin` user is rejected with `Grant access token to admin is not allowed`; require a dedicated non-admin user. (2026-08-03)
- [x] Document in the README how the three Entra OBO app registrations are scripted for new users (`bootstrap-entra-obo.ps1`): roles, env-var mapping, prerequisites, what it configures, parameters, secret handling. (2026-08-03)
- [x] Add optional claims (`preferred_username`, `email`, `upn`) to the broker app in `bootstrap-entra-obo.ps1` so the access token the MCP server validates explicitly carries the delegated user's identity; document in README Step 8. (2026-08-04)
- [x] Add a Token claims reference subsection to README Step 8 (claims table + how the subject claim maps to the ServiceNow user_field). (2026-08-04)
- [x] Change the interactive MCP test client to prefer the Entra device-code flow (print URL + code for any browser) instead of MSAL launching the system browser, which crashes on some hosts; add `--use-device-code`/`--no-device-code` flags. (2026-08-04)
- [x] Update the README Interactive CLI Helper section to document the device-code default sign-in and the `--use-device-code`/`--no-device-code` flags. (2026-08-04)
- [x] Add README Step 5 reset guidance (update instance URL/username/password after an instance reset) and a `--check-auth` preflight in `scripts/service_now_setup.py` to verify admin REST auth before setup. (2026-07-31)
- [ ] When scripting Multiple Provider SSO property configuration in `service_now_setup.py`, keep `admin` basic auth working: enable multisso/auto-import but do NOT enable the Account Recovery lockout (it blocks REST basic auth even for the ACR user). Confirm exact `sys_properties` names against a live instance before hardcoding.

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
- [ ] Decide whether to deprecate or remove the legacy direct OBO path after ServiceNow JWT bearer flow is proven in your tenant.

## Done

- [x] Fixed delegated `list_incidents` visibility gap by switching to ServiceNow-native ORDERBY query encoding and applying deterministic newest-first incident ordering for the default list path. (2026-07-08)
- [x] Fixed remaining helper/smoke-test scope coupling by introducing dedicated ServiceNow JWT user-assertion acquisition scope support (`SERVICENOW_SN_JWT_USER_SCOPE`) instead of reusing OBO scope settings. (2026-07-08)
- [x] Fixed the interactive helper to acquire only the selected auth mode instead of fetching both JWT and OBO user assertions in the same run, eliminating mixed-identity local test behavior. (2026-07-08)
- [x] Re-aligned the interactive helper toward production-like delegated identity behavior by removing runtime username prompting, forcing Entra account selection, and printing the actual signed-in token identity returned by the login flow. (2026-07-08)
- [x] Updated the interactive helper to prompt for the Entra user at runtime for local OBO/JWT delegated testing, removing the need to store per-user login hints in `.env` for multi-user test runs. (2026-07-08)
- [x] Added a dedicated ServiceNow JWT interactive login-hint setting so local helper sign-in can be forced to the intended Entra user instead of reusing a cached admin session. (2026-07-08)
- [x] Fixed interactive helper local test flow so ServiceNow JWT mode auto-acquires and binds an incoming user assertion token (static local fallback) instead of failing with missing request-bound Authorization context. (2026-07-08)
- [x] Added a prominent README section clarifying the production MCP + OBO runtime path, including explicit distinction between `_start_mcp_server.bat` (production server) and `_start_obo.bat` (interactive test helper). (2026-07-08)
- [x] Reworked README onboarding with a complete Getting Started runbook covering prerequisites, auth pattern selection, bootstrap/merge steps, ServiceNow JWT setup sequence, end-to-end smoke testing, and first-run troubleshooting checks. (2026-07-08)
- [x] Added a repeatable ServiceNow JWT delegated-flow smoke test script and documented one-command usage for ongoing validation. (2026-07-08)
- [x] Added full OBO flow options documentation with architecture breakdown, Mermaid diagrams, and comparative analysis for direct OBO versus ServiceNow JWT bearer bridge patterns. (2026-07-08)
- [x] Updated README with validated ServiceNow JWT bearer runbook details and references to the new OBO options architecture document. (2026-07-08)
- [x] Validated ServiceNow JWT bearer delegated auth end-to-end (token exchange 200 + incident table API 200) after aligning ServiceNow JWT client selection, assertion audience semantics, and ServiceNow user mapping. (2026-07-08)
- [x] Fixed ServiceNow JWT env automation so generated client-secret and additional `SERVICENOW_SN_JWT_*` settings are included in env merge operations. (2026-07-08)
- [x] Updated ignore rules so the public JWKS document can be committed while private key material and generated payload files remain excluded. (2026-07-08)
- [x] Added JWKS generation and ServiceNow OAuth/JWT payload template generation to the bootstrap helper so key material can flow directly into oauth_jwt, oauth_entity, and oauth_entity_profile provisioning. (2026-07-08)
- [x] Fixed Azure bootstrap Graph PATCH body handling and made delegated scope configuration idempotent so reruns no longer fail on malformed JSON or enabled-scope replacement. (2026-07-08)
- [x] Extended Azure bootstrap output and env-merge automation to emit/carry ServiceNow JWT delegated-auth Azure values, and added a ServiceNow bootstrap helper for table discovery, key generation, registry upsert/validation, and env emission. (2026-07-08)
- [x] Implemented ServiceNow OAuth JWT bearer delegated-user auth mode (incoming Entra token validation + signed JWT assertion exchange + user-scoped token cache) and wired CLI/interactive helper/env template configuration for local and MCP runtime use. (2026-07-08)
- [x] Removed unintended broker delegated permission/grant to a SAML-based ServiceNow enterprise app to restore intended OBO app-permission scope. (2026-07-07)
- [x] Reverted local OBO scope to OAuth-capable app resource after confirming tenant `ServiceNow` app is SAML-only (AADSTS399274), and documented required non-SAML OBO audience guidance for end-to-end delegated access. (2026-07-07)
- [x] Granted broker app delegated `user_impersonation` permission to the tenant ServiceNow resource app and switched `SERVICENOW_OBO_SCOPE` to ServiceNow audience (`https://<your-instance>.service-now.com/.default`) for direct API OBO token acceptance. (2026-07-07)
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
