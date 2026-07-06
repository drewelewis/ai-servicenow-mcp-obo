# Repository Instructions

## Changelog Requirement

Whenever implementation changes are made (code, scripts, docs, config, tests), the agent must update changelog.md before finalizing the response.

## TODO Requirement

Whenever implementation work is planned, started, or completed, the agent must update todo.md before finalizing the response.

## Tracking Policy

- `todo.md` is for general planned and in-progress work.
- `changelog.md` is for completed changes only.
- Do not add planned work to `changelog.md`.

## Required Process

1. Read changelog.md.
2. Follow the changelog-enforcer skill workflow in .github/skills/changelog-enforcer/SKILL.md.
3. Add a dated entry with relevant sections (Added, Changed, Fixed, Security as applicable).
4. Include impacted file paths in changelog bullets where practical.
5. Read todo.md.
6. Follow the todo-enforcer skill workflow in .github/skills/todo-enforcer/SKILL.md.
7. Ensure task state reflects delivered work (Backlog, In Progress, Done).
8. Do not finalize if changelog.md or todo.md is not updated for the delivered changes.

## Guardrails

- Entries must be factual and implementation-backed.
- Do not include secrets, tokens, passwords, or private data.
- If work is partial or failed, record that clearly.
