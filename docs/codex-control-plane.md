# GitHub Codex Control Plane

This repository uses GitHub as the shared control plane between a controller and a Codex implementation worker.

## One-time setup

The GitHub-hosted V1 uses the official `openai/codex-action@v1`. It requires an OpenAI API key stored as a repository Actions secret named `OPENAI_API_KEY`.

In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**, set the name to `OPENAI_API_KEY`, and paste a project API key with the intended API budget/limits. This execution path uses **API billing**; it is separate from ChatGPT subscription usage.

The connected ChatGPT GitHub tool cannot create or read repository secrets, so this one secret is intentionally a one-time external setup step.

Optional: define a repository variable such as `CODEX_MODEL` only if you later choose to pin a specific supported Codex model. V1 intentionally lets the action choose its supported default.

## State machine

The workflow bootstraps these labels when the control-plane workflow first lands on `main`:

- `agent:planned`
- `agent:ready`
- `agent:running`
- `agent:review`
- `agent:fix-required`
- `agent:verified`
- `agent:done`
- `agent:blocked`

The controller creates a complete task Issue and leaves it at `agent:planned` while requirements are being finalized. Applying `agent:ready` dispatches the worker.

## Initial implementation turn

1. Controller creates an Issue with Goal, Scope, Constraints, Acceptance criteria, Verification, and Out of scope.
2. Controller applies `agent:ready`.
3. GitHub Actions verifies that the triggering actor has write/maintain/admin permission.
4. The workflow creates `codex/issue-<issue>-<run-id>` from `main` and changes state to `agent:running`.
5. Dependencies are installed before Codex starts.
6. Codex receives a credential-free checkout, `AGENTS.md`, and a local copy of the Issue context. It runs with the `:workspace` permission profile.
7. The workflow runs `bash scripts/codex/verify.sh` after the Codex turn.
8. Only after verification passes does a trusted step authenticate Git, commit, push the feature branch, and run `gh pr create`.
9. The Issue moves to `agent:review` and receives the PR URL plus the Codex handoff.

Codex does not get persisted Git credentials and does not merge.

## Controller review and retry

The controller reviews the PR diff and CI. If changes are required, post a top-level PR comment beginning exactly with:

`/codex fix`

Put the blocking review instructions after that command. The repair workflow checks the actor's repository permission, verifies that the PR branch belongs to this repository and begins with `codex/issue-`, checks out that branch without persisted credentials, gives Codex the PR/review context, reruns deterministic verification, then pushes a new commit to the same PR branch.

The controller can mark the PR `agent:fix-required` before the command if desired. A successful repair returns it to `agent:review`; a failed authorized turn is marked `agent:blocked`.

## Merge policy

No Codex workflow auto-merges `main`. The controller owns final acceptance and merge.

Repository **branch protection** is strongly recommended for `main`: require pull requests, require the normal CI checks, and disallow force pushes. The current repository may not yet have branch protection enabled, so the controller must enforce the same rule operationally until a ruleset is configured.

After CI is green and review passes, the controller can mark `agent:verified`, merge, verify deployment/runtime behavior, then mark `agent:done` and close the Issue.

## Security model

- `OPENAI_API_KEY` is provided only to `openai/codex-action`.
- `actions/checkout` uses `persist-credentials: false` in worker jobs.
- GitHub authentication occurs only after Codex and deterministic verification complete.
- `:workspace` gives Codex workspace file access without granting general network access.
- Only repository write/maintain/admin actors can dispatch implementation or repair turns.
- Ordinary tasks may not modify control-plane files unless their Issue explicitly authorizes it.
- A failed worker turn never pushes `main`.

## Recovery

If a task becomes `agent:blocked`, inspect the workflow logs and the blocking comment. Fix infrastructure/authentication issues outside the worker if necessary, then return the task to `agent:ready` for a fresh implementation turn or use `/codex fix` on an existing Codex PR.

If `OPENAI_API_KEY` is absent, the worker deliberately fails before Codex starts. Do not treat that as a Codex execution.
