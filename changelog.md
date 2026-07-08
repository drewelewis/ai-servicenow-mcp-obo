## 2026-07-08

### Added
- Added a new ServiceNow delegated-user authentication mode that validates incoming Entra bearer tokens and performs ServiceNow OAuth JWT bearer exchange using signed assertions: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Added a new ServiceNow JWT bootstrap helper that can discover OAuth-related tables, generate key material, upsert or validate registry records, and emit the remaining `SERVICENOW_SN_JWT_*` env values: [scripts/bootstrap_servicenow_jwt.py](scripts/bootstrap_servicenow_jwt.py).
- Added JWKS generation and ServiceNow payload-template generation to the bootstrap helper so oauth_jwt, oauth_entity, and oauth_entity_profile provisioning files can be produced from local key material: [scripts/bootstrap_servicenow_jwt.py](scripts/bootstrap_servicenow_jwt.py).
- Added a full OBO flow architecture document with side-by-side pattern breakdown, troubleshooting guidance, and Mermaid diagrams for direct OBO versus ServiceNow JWT bearer bridge approaches: [obo-flow-options.md](obo-flow-options.md).
- Added a repeatable delegated JWT bearer smoke-test script that performs device-code sign-in, ServiceNow token exchange, and incident query verification in one run: [scripts/smoke_test_sn_jwt.py](scripts/smoke_test_sn_jwt.py).

### Changed
- Expanded CLI authentication selection and environment-driven flags to support ServiceNow JWT bearer delegated auth alongside existing OBO/token/OAuth/basic modes: [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py).
- Expanded the interactive helper auth parser and mode selection to run the ServiceNow JWT bearer delegated flow for local validation: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Documented full ServiceNow JWT bearer delegated auth environment configuration, including key material, issuer/audience checks, and local static-assertion fallback controls: [.env.example](.env.example).
- Extended Azure bootstrap output and env-merge automation to carry the new JWT delegated-auth Azure values into local env configuration: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1), [scripts/apply-obo-env.ps1](scripts/apply-obo-env.ps1).
- Updated ignore rules so [.servicenow-jwt/jwks.json](.servicenow-jwt/jwks.json) can be committed as public key material while private PEM files and generated payload templates remain ignored: [.gitignore](.gitignore).
- Updated ServiceNow JWT assertion construction to use the ServiceNow JWT client identifier as the assertion audience, matching the validated token endpoint semantics for this tenant: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Expanded env-merge key coverage to include additional ServiceNow JWT bearer settings (`SERVICENOW_SN_JWT_CLIENT_SECRET`, token endpoint, scope, kid, expected issuer/audience, TTL/cache tuning, and static assertion toggles): [scripts/apply-obo-env.ps1](scripts/apply-obo-env.ps1).
- Updated README with validated ServiceNow JWT bearer tenant runbook details, new smoke-test usage, and reference to complete OBO pattern comparison documentation: [README.md](README.md).
- Reworked README onboarding with a complete Getting Started runbook so first-time setup covers prerequisites, auth-path choices, identity bootstrap, ServiceNow JWT configuration, smoke-test validation, and first-run troubleshooting instead of clone-only guidance: [README.md](README.md).
- Added a prominent README production-path section that clarifies the MCP + OBO runtime flow and explicitly distinguishes `_start_mcp_server.bat` (production MCP server entrypoint) from `_start_obo.bat` (interactive local test helper): [README.md](README.md).

### Fixed
- Unified request-scoped bearer-token extraction/binding for both Entra OBO and ServiceNow JWT bearer delegated auth paths so incoming identity context is consistently required for delegated calls: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Fixed the env merge helper so dry-run mode no longer creates backups and the conditional logic parses correctly in PowerShell: [scripts/apply-obo-env.ps1](scripts/apply-obo-env.ps1).
- Fixed Azure bootstrap Graph PATCH body handling for PowerShell and made delegated scope configuration idempotent so rerunning the bootstrap no longer fails on enabled existing scopes: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1).
- Fixed ServiceNow JWT bearer live-token failures by aligning runtime to the correct ServiceNow JWT client entity, rotating known client secret values, and provisioning a ServiceNow user record that matches the incoming Entra `preferred_username` claim used for delegated user resolution: [.env](.env).
- Validated end-to-end delegated flow success after remediation (ServiceNow `/oauth_token.do` 200 and `/api/now/table/incident` 200) during live tenant test run.
- Fixed interactive helper auth bootstrap for ServiceNow JWT mode by auto-acquiring and binding a local test assertion token when request transport context is absent, preventing `Missing incoming user token for delegated ServiceNow JWT exchange` failures in `_start_obo.bat`: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Fixed interactive helper Entra user selection for ServiceNow JWT mode by adding a dedicated JWT login-hint option, so local testing can target a specific Entra user instead of unintentionally reusing a cached admin session: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Fixed interactive helper multi-user local testing by prompting for the Entra user login hint at runtime when no explicit hint is supplied, removing the need to store per-user values in `.env`: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Adjusted interactive helper delegated sign-in behavior to more closely mirror production by relying on the Entra account-selection flow, then printing the actual returned token identity instead of depending on a local prompt as the source of truth: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Fixed interactive helper local delegated testing so it now acquires only the assertion for the selected auth mode instead of fetching both JWT and OBO assertions in one run, preventing mixed-identity results when both configurations are present: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Fixed residual local auth scope coupling by introducing dedicated ServiceNow JWT user-assertion acquisition scope support (`SERVICENOW_SN_JWT_USER_SCOPE`) in both interactive and smoke-test utilities instead of reusing OBO scope settings: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py), [scripts/smoke_test_sn_jwt.py](scripts/smoke_test_sn_jwt.py), [.env.example](.env.example).

## 2026-07-07

### Added
- Added a root server launcher script to start the MCP server directly via Python module entrypoint: [_start_mcp_server.bat](_start_mcp_server.bat).
- Added a top-level OBO architecture diagram and layered component overview to explain the identity plane, MCP runtime plane, and ServiceNow-facing integration path: [README.md](README.md).
- Added an interactive Python helper for menu-driven ServiceNow MCP operations for local validation workflows: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Added a root helper launcher to start the interactive OBO client from repository root with optional passthrough args: [_start_obo.bat](_start_obo.bat).

### Changed
- Removed the unintended broker delegated permission and OAuth2 permission grant that targeted the SAML-based ServiceNow enterprise app (`65f131b1-2cf1-42b9-b700-ee1485da296b`) to restore intended OBO permission boundaries.
- Reverted local OBO scope from ServiceNow SAML-only audience to OAuth-capable app audience after validating AADSTS399274 (`SAML SSO app cannot be used for non-SAML token issuance`): [.env](.env).
- Added troubleshooting guidance for AADSTS399274 and clarified that OBO downstream scopes must target OAuth/OIDC-capable resource apps, not SAML-only enterprise apps: [README.md](README.md).
- Updated OBO downstream audience configuration to target the tenant ServiceNow resource app (`https://dev397814.service-now.com/.default`) and aligned broker delegated permission grant to ServiceNow `user_impersonation` for direct ServiceNow API token acceptance: [.env](.env).
- Corrected local ServiceNow base URL configuration from a page URL (`/login.do`) to the instance root URL so API calls no longer target `.../login.do/api/...` and trigger login redirects: [.env](.env).
- Updated Entra OBO bootstrap automation so the interactive client app is configured with localhost public-client redirect URI (`http://localhost`) alongside public-client fallback, preventing AADSTS500113 during local interactive assertion acquisition: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1).
- Added missing local interactive OBO env keys so helper sign-in uses the interactive client ID and broker `user_impersonation` scope, resolving broker self-resource sign-in failures in `_start_obo.bat`: [.env](.env).
- Removed the obsolete `# OBO auth credentials` heading from local environment configuration to keep auth comments consistent with current flow documentation: [.env](.env).
- Added local OBO test-mode behavior in the interactive helper to auto-acquire an Entra user assertion token (when `SERVICENOW_OBO_USER_ASSERTION` is unset/placeholder) using interactive Entra sign-in (browser popup with MFA, plus optional device-code fallback), then apply it as static assertion input for downstream OBO exchange: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py), [README.md](README.md), [.env.example](.env.example).
- Updated interactive OBO user-assertion scope defaults/documentation to use GUID-based resource notation (`<client-id>/.default`) to avoid Entra self-token scope failures like AADSTS90009: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py), [README.md](README.md), [.env.example](.env.example).
- Extended Entra OBO bootstrap automation to provision and configure an interactive public-client app, expose broker API delegated scope, and grant interactive-to-broker delegated permission so local MFA assertion acquisition aligns with OBO expectations: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1), [README.md](README.md).
- Updated generated/merge env-key handling so bootstrap output and apply helper include `SERVICENOW_OBO_PUBLIC_CLIENT_ID` and `SERVICENOW_OBO_USER_SCOPE`: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1), [scripts/apply-obo-env.ps1](scripts/apply-obo-env.ps1), [README.md](README.md).
- Added compatibility fallback in the interactive helper so `SERVICENOW_OBO_USERNAME` and `SERVICENOW_OBO_PASSWORD` are accepted as defaults for OAuth username/password resolution when `SERVICENOW_USERNAME` and `SERVICENOW_PASSWORD` are not set: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Removed basic-auth login flow from the interactive helper and aligned it to non-basic auth modes via `.env`/CLI args (OBO, bearer token, or ServiceNow OAuth): [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py), [README.md](README.md).
- Added CLI startup status messages to stderr so running the MCP server manually makes the waiting-for-client state explicit for stdio and sse transports: [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py).
- Documented usage for the interactive MCP helper script in README, including list-commands mode: [README.md](README.md).
- Added inline authentication-purpose comments in local environment configuration to clarify each auth-related setting and runtime assertion usage: [.env](.env).
- Added explicit ServiceNow OAuth and bearer-token variable placeholders/comments in local environment configuration to clarify non-OBO auth setup paths: [.env](.env).
- Reworked the authentication documentation so each supported auth mode now has its own usage section and scenario guidance: [README.md](README.md).
- Clarified the usage section to separate basic-auth examples from Entra OBO examples and document CLI auth-selection precedence: [README.md](README.md).
- Corrected the installation section to document this repository as source-only and to use the current fork URL instead of inherited upstream/PyPI guidance: [README.md](README.md).
- Added architecture guidance for the OBO path, including major components, design boundaries, and authentication alternatives: [README.md](README.md).
- Updated the OBO flow documentation to reflect implemented incoming-token validation and user-scoped delegated-token caching, while clarifying downstream audience requirements: [README.md](README.md).
- Replaced the runtime OBO flowchart with a Mermaid sequence diagram to improve step-by-step readability: [README.md](README.md).
- Simplified the Entra registration diagram to focus on registration and tenant object relationships, separate from runtime flow: [README.md](README.md).

### Fixed
- Added incoming Entra bearer token validation for issuer, audience, signature, and expiry on the OBO downstream request path: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py), [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py).
- Added request-scoped auth binding and user-scoped delegated token caching for OBO exchanges, with configurable expected audience and issuer controls: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py), [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py), [.env.example](.env.example), [requirements.txt](requirements.txt), [pyproject.toml](pyproject.toml).
- Added `msal` as a runtime dependency so interactive Entra MFA sign-in works for local OBO assertion acquisition in the helper script: [requirements.txt](requirements.txt), [pyproject.toml](pyproject.toml).
- Added explicit troubleshooting guidance in the interactive helper error path when Entra returns AADSTS90009 during user-assertion acquisition: [scripts/interactive_mcp_client.py](scripts/interactive_mcp_client.py).
- Updated Mermaid syntax in the Entra registration relationship diagram to improve GitHub renderer compatibility (removed multiline node syntax and normalized edge labels): [README.md](README.md).

## 2026-07-06

### Changed
- Added an MCP OBO flow diagram and flow summary to documentation for delegated token exchange visibility: [README.md](README.md).
- Added ignore rules for generated OBO env output and backup secret files to prevent accidental secret commits: [.gitignore](.gitignore).
- Added explicit documentation of the purpose of Entra app registrations used in OBO setup: [README.md](README.md).
- Added a quick visual diagram for Broker and Downstream Entra registration roles in OBO setup: [README.md](README.md).

## 2026-07-02

### Added
- Added MCP Explorer helper scripts for local workflow control: [_start_mcp_explorer.bat](_start_mcp_explorer.bat), [_stop_mcp_explorer.bat](_stop_mcp_explorer.bat).
- Added Entra OBO bootstrap automation script to create app registrations, scope, permissions, admin consent attempt, and generated env output: [scripts/bootstrap-entra-obo.ps1](scripts/bootstrap-entra-obo.ps1).
- Added env merge helper script to apply generated OBO settings into local env with backup support: [scripts/apply-obo-env.ps1](scripts/apply-obo-env.ps1).
- Added repository skill for changelog discipline and change tracking enforcement: [.github/skills/changelog-enforcer/SKILL.md](.github/skills/changelog-enforcer/SKILL.md).
- Added repository task tracker file for planning and execution status: [todo.md](todo.md).
- Added repository skill for TODO tracking enforcement: [.github/skills/todo-enforcer/SKILL.md](.github/skills/todo-enforcer/SKILL.md).

### Changed
- Updated MCP startup path to launch CLI module for consistent env loading and stdio transport handling: [_start_mcp_explorer.bat](_start_mcp_explorer.bat).
- Expanded runtime auth options to include Entra OBO configuration in CLI argument and env handling: [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py).
- Replaced OBO guidance draft with a normative, implementation-independent security specification and validation runbook: [obo_guide.md](obo_guide.md).
- Expanded setup documentation with MCP Explorer, OBO bootstrap, and env merge workflows: [README.md](README.md).
- Expanded repository agent instructions to require todo.md maintenance alongside changelog updates: [.github/copilot-instructions.md](.github/copilot-instructions.md).
- Seeded a spec-driven OBO remediation execution plan (P0/P1/P2) in repository task tracker: [todo.md](todo.md).
- Promoted OBO spec verification and gap-capture task to top priority in tracker: [todo.md](todo.md).
- Clarified governance policy that todo.md tracks planned/in-progress work while changelog.md tracks completed changes only: [.github/copilot-instructions.md](.github/copilot-instructions.md), [.github/skills/changelog-enforcer/SKILL.md](.github/skills/changelog-enforcer/SKILL.md), [.github/skills/todo-enforcer/SKILL.md](.github/skills/todo-enforcer/SKILL.md).
- Removed duplicate task-state ambiguity in priority section by keeping active verification tracking in In Progress: [todo.md](todo.md).
- Refined task-tracking policy during governance iteration to evaluate general-vs-feature tracker handling before settling on single-tracker workflow: [todo.md](todo.md), [.github/skills/todo-enforcer/SKILL.md](.github/skills/todo-enforcer/SKILL.md), [.github/copilot-instructions.md](.github/copilot-instructions.md).
- Cleaned repository instruction wording to remove duplicate tracking-policy statement before OBO kickoff: [.github/copilot-instructions.md](.github/copilot-instructions.md).
- Reverted tracker split and restored single-tracker policy so all planned/in-progress work (including OBO) is tracked in [todo.md](todo.md): [todo.md](todo.md), [.github/skills/todo-enforcer/SKILL.md](.github/skills/todo-enforcer/SKILL.md), [.github/copilot-instructions.md](.github/copilot-instructions.md).
- Expanded OBO delivery tracking with an ongoing testing and verification cadence (per-change checks, weekly reviews, and release gate criteria): [todo.md](todo.md).
- Implemented request-context OBO assertion capture and fail-closed behavior for missing delegated identity, including context propagation through ServiceNow client calls and updated OBO CLI fallback controls: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py), [mcp_server_servicenow/cli.py](mcp_server_servicenow/cli.py).
- Updated OBO configuration docs to describe request-bound assertions and local-only static fallback toggle: [.env.example](.env.example), [README.md](README.md).
- Removed natural language positioning and examples from project docs, and clarified explicit MCP tool usage: [README.md](README.md).
- Updated package metadata to remove NLP references and reflect MCP tool-based behavior: [pyproject.toml](pyproject.toml).

### Fixed
- Removed NLP tool registration and handlers so the server exposes only explicit MCP tools/resources: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Removed NLP implementation and its dedicated tests to eliminate error-prone natural language parsing path: [mcp_server_servicenow/nlp.py](mcp_server_servicenow/nlp.py), [tests/test_nlp.py](tests/test_nlp.py).

- Improved ServiceNow API error diagnostics to clearly surface redirect-to-login and auth failure conditions without leaking secrets: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Fixed OAuth token expiry handling to use consistent epoch-based refresh logic: [mcp_server_servicenow/server.py](mcp_server_servicenow/server.py).
- Updated stop script process matching to terminate both legacy and CLI-launched server sessions reliably: [_stop_mcp_explorer.bat](_stop_mcp_explorer.bat).
