## 2026-07-06

### Changed
- Added an MCP OBO flow diagram and flow summary to documentation for delegated token exchange visibility: [README.md](README.md).
- Added ignore rules for generated OBO env output and backup secret files to prevent accidental secret commits: [.gitignore](.gitignore).

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
