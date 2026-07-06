---
name: changelog-enforcer
description: Ensure every implementation change is captured in changelog.md before finalizing responses or pull requests.
---

# Changelog Enforcer Skill

## Purpose

This skill ensures project updates are consistently recorded in changelog.md.

Changelog scope:
- Record only completed, implementation-backed changes that have landed.
- Do not record planned, proposed, or in-progress work items.

## When To Use

Use this skill whenever any code, script, configuration, documentation, or behavior change is introduced.

Trigger phrases include:
- update changelog
- add release notes
- log this change
- keep track of changes
- before finalizing, update changelog

## Required Workflow

1. Read changelog.md.
2. Summarize the completed changes in concise bullets grouped by category.
3. Add a new dated section in changelog.md.
4. Include at minimum:
   - Added
   - Changed
   - Fixed
   - Security (if applicable)
5. Include impacted files for each bullet where practical.
6. Do not close the task until changelog.md has been updated.

## Entry Format

Use this format:

## YYYY-MM-DD

### Added
- item

### Changed
- item

### Fixed
- item

### Security
- item

If a section has no items, omit that section.

## Quality Bar

- Entries must be factual and implementation-backed.
- No placeholder text.
- No duplicate bullets.
- Keep bullets short and action-oriented.
- Use one entry per logical delivery batch.

## Guardrails

- Never claim deployment status unless verified.
- Never include secrets, tokens, passwords, or private data.
- If a change failed or was partial, record that explicitly under Changed or Fixed.
- Never move future work tracking into changelog.md; keep future work in todo.md.
