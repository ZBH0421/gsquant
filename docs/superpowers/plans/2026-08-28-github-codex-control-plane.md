# GitHub Codex Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub-native bridge where controller-created Issues dispatch an isolated Codex worker that implements code on a feature branch, verifies it, opens/updates a PR, and returns control to the controller for review and merge.

**Architecture:** GitHub Issues/labels are the durable task state. `openai/codex-action@v1` edits a credential-free checkout under the `:workspace` permission profile, while separate trusted workflow steps own Git authentication, commits, pushes, PR creation, and state transitions. A `/codex fix` PR comment dispatches a repair turn on the existing PR branch.

**Tech Stack:** GitHub Actions, GitHub CLI, OpenAI Codex GitHub Action, Bash, Python/pytest contract tests.

**Spec:** `docs/superpowers/specs/2026-08-28-github-codex-control-plane-design.md`

## Global Constraints

- Bootstrap is the only controller-authored implementation exception.
- Codex must never receive persisted Git credentials or push/merge `main`.
- Codex uses `permission-profile: ":workspace"` and `openai/codex-action@v1`.
- `OPENAI_API_KEY` is read only from GitHub Actions secrets.
- Every normal implementation task is feature-branch + PR + CI gated.
- Existing COT Radar CI must remain green.

---

### Task 1: Establish RED control-plane contract

**Files:**
- Create: `tests/control_plane/test_contract.py`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: repository filesystem.
- Produces: executable contract tests defining required workflow, scripts, template, and governance files.

- [ ] Add tests that require the Codex workflow, `AGENTS.md`, bootstrap/verify scripts, issue template, safe checkout, workspace permission profile, secret reference, state labels, PR creation, and `/codex fix` support.
- [ ] Add `python -m pytest tests/control_plane -q` to CI.
- [ ] Push and confirm CI fails because the control-plane implementation does not exist yet.

### Task 2: Add worker governance and repository commands

**Files:**
- Create: `AGENTS.md`
- Create: `scripts/codex/bootstrap.sh`
- Create: `scripts/codex/verify.sh`

**Interfaces:**
- `bootstrap.sh`: prepares local dependencies before Codex runs.
- `verify.sh`: deterministic repository gate invoked after every Codex turn.

- [ ] Document controller/worker ownership, protected control-plane paths, TDD, branch rules, and no-secret/no-CI-bypass rules.
- [ ] Make bootstrap install the repository Python dev dependencies and COT web dependencies when present.
- [ ] Make verify run COT pytest/Ruff/mypy, COT web test/build, control-plane tests, and `git diff --check`.

### Task 3: Implement dispatcher and repair workflows

**Files:**
- Create: `.github/workflows/codex-control-plane.yml`

**Interfaces:**
- Consumes: `agent:ready` Issue labels and `/codex fix` PR comments.
- Produces: `codex/issue-*` branch, commits, PR, state-label transitions, diagnostic comments.

- [ ] Bootstrap the canonical agent labels on merge to `main` or manual dispatch.
- [ ] Authorize trigger actors using repository permission lookup.
- [ ] Fetch task/PR context into a local prompt file without exposing GitHub credentials to Codex.
- [ ] Run `openai/codex-action@v1` with `OPENAI_API_KEY`, `:workspace`, and `persist-credentials: false` checkout.
- [ ] Run `scripts/codex/verify.sh` after Codex.
- [ ] On success, authenticate after Codex, commit, push feature branch, create/update PR, and move state to review.
- [ ] On failure, move state to blocked and post diagnostics.

### Task 4: Add controller-facing task template and operations guide

**Files:**
- Create: `.github/ISSUE_TEMPLATE/codex-task.yml`
- Create: `docs/codex-control-plane.md`

**Interfaces:**
- Issue template produces controller-readable task contracts.
- Operations guide documents setup, state transitions, controller commands, and recovery.

- [ ] Include goal, scope, constraints, acceptance, verification, and out-of-scope fields.
- [ ] Document the one-time `OPENAI_API_KEY` secret setup and API-billing implication.
- [ ] Document `agent:ready` dispatch and `/codex fix` repair flow.
- [ ] Document recommended `main` branch protection and that merge remains controller-owned.

### Task 5: GREEN verification and bootstrap PR

**Files:**
- Modify only files required by test/CI findings.

- [ ] Run/observe control-plane contract tests until green.
- [ ] Confirm existing COT Python and web jobs remain green.
- [ ] Confirm `git diff --check` is clean.
- [ ] Open a PR from `feat/github-codex-control-plane` to `main`.
- [ ] Review the diff against the spec and security boundary.
- [ ] Merge only after CI is green.

### Task 6: Post-merge runtime readiness

**Files:** None unless runtime verification reveals a control-plane defect.

- [ ] Confirm the main-branch bootstrap workflow creates canonical labels.
- [ ] Confirm the control-plane workflow is present and enabled.
- [ ] If `OPENAI_API_KEY` is already configured, create a harmless pilot Issue and prove Codex opens a PR.
- [ ] If the secret is absent, stop at `READY / secret required`; do not fake a Codex execution.
