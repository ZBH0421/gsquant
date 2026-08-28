# Agent Governance

This repository uses GitHub as the control plane between a **ChatGPT Controller** and a **Codex Worker**.

## ChatGPT Controller

The controller owns research, requirements, architecture, specs, task decomposition, GitHub Issues, review comments, acceptance, merge decisions, and deployment verification.

After the control-plane bootstrap is merged, the controller should not directly implement ordinary production-code changes when the Codex bridge is available. The controller dispatches those changes through a GitHub task instead.

## Codex Worker

The Codex Worker owns implementation code, tests, refactors, migrations, and build fixes for an approved GitHub task.

Before changing code:

1. Read this file.
2. Read the complete GitHub Issue and any referenced spec/plan.
3. Inspect existing repository patterns before editing.
4. Use TDD for behavior changes: establish RED, implement the minimum correct change, then prove GREEN.

Worker rules:

- Work only in the checked-out feature branch.
- **Never push or merge `main`**.
- Do not create or manage GitHub credentials; the trusted workflow owns commit/push/PR handoff.
- Do not weaken tests, delete assertions, disable CI, or relax type/lint checks merely to make a task pass.
- Do not expose secrets in files, logs, prompts, test fixtures, or generated artifacts.
- Do not assume network access from the Codex sandbox.
- Run `scripts/codex/verify.sh` before finishing and fix failures caused by the task.
- Keep facts, formulas, inference, confirmation, and invalidation separate in market-research applications.

## Controller-owned control-plane paths

Ordinary implementation tasks must not modify these paths unless the GitHub Issue explicitly authorizes a control-plane change:

- `.github/workflows/codex-control-plane.yml`
- `.github/ISSUE_TEMPLATE/codex-task.yml`
- `AGENTS.md`
- `scripts/codex/`
- `tests/control_plane/`
- `docs/codex-control-plane.md`

If a normal task appears to require changing one of these paths, stop and report the conflict instead of bypassing the boundary.

## Completion contract

A Codex turn is not complete because code was generated. It is complete only when the requested behavior is implemented, deterministic verification is green, the diff is scoped to the task, and the worker gives a concise handoff describing what changed and any residual limitation.
