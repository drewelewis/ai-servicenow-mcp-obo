---
name: todo-enforcer
description: Ensure implementation tasks are tracked in todo.md and status is maintained throughout delivery.
---

# TODO Enforcer Skill

## Purpose

This skill ensures work planning and execution status are tracked in todo.md.

TODO scope:
- Track planned and in-progress work items.
- Keep implementation backlog visible and current.
- Do not use changelog.md for planned work.

## When To Use

Use this skill whenever implementation work is requested, started, or completed.

Trigger phrases include:
- update todo
- track tasks
- keep task list current
- mark item complete
- add backlog items

## Required Workflow

1. Read todo.md before starting implementation.
2. Add new tasks to Backlog if they are not already tracked.
3. Move active tasks to In Progress when work starts.
4. Move completed tasks to Done with date.
5. Ensure task wording remains action-oriented and outcome-focused.
6. Do not finalize implementation responses with stale task states.

## Status Rules

- Backlog: planned but not started.
- In Progress: currently being implemented.
- Done: completed and verified.

## Quality Bar

- Avoid duplicate tasks.
- Keep tasks scoped and specific.
- Prefer file-linked or outcome-linked wording where practical.
- Keep the list readable and current.

## Guardrails

- Do not mark tasks Done unless implementation has actually landed.
- If work is blocked, keep in In Progress and add blocker note.
- If work is canceled, remove from In Progress and add a brief note in Done or Backlog as appropriate.
- When a task moves to Done, ensure the completed implementation is reflected in changelog.md.
