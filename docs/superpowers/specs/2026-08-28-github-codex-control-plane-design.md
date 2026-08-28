# GitHub Codex Control Plane Design

## Goal

Make GitHub the durable control plane between a ChatGPT controller and a Codex coding worker. The controller owns requirements, task state, review, acceptance, merge, and deployment verification. Codex owns implementation code, tests, refactors, and build fixes after this bootstrap is merged.

## Bootstrap exception

The control plane cannot use itself before it exists. This branch is therefore a one-time controller-authored bootstrap. After merge, normal production-code tasks must be dispatched to Codex through GitHub unless the bridge is unavailable or the task explicitly changes the control plane itself.

## Roles

### ChatGPT Controller
- Research and clarify requirements.
- Write design/spec and implementation plan when appropriate.
- Create and update GitHub Issues.
- Move tasks through GitHub state labels.
- Review PR diffs, CI, security, and acceptance evidence.
- Request fixes through PR comments.
- Merge only after required checks are green.
- Verify deployment and close the issue.

### Codex Worker
- Read `AGENTS.md`, the GitHub task, referenced specs/plans, and repository context.
- Work only on a feature branch.
- Use TDD for behavior changes.
- Modify implementation code and tests.
- Run the repository verification script before handoff.
- Never push or merge `main` directly.
- Never weaken tests, CI, security controls, or secrets handling to obtain a green result.

### GitHub
GitHub is the shared state store, audit log, dispatcher, CI system, and review surface. No direct ChatGPT-to-Codex session channel is required.

## Task lifecycle

Canonical labels:

1. `agent:planned`
2. `agent:ready`
3. `agent:running`
4. `agent:review`
5. `agent:fix-required`
6. `agent:verified`
7. `agent:done`
8. `agent:blocked`

A controller-created Issue contains the goal, scope, constraints, acceptance criteria, verification commands, and explicit out-of-scope items. Applying `agent:ready` dispatches Codex. Codex changes are committed to a `codex/issue-<number>-<run-id>` branch and opened as a PR. A controller can request another Codex turn by posting a PR comment beginning with `/codex fix` followed by blocking instructions.

## Worker execution

The worker runs on GitHub-hosted Ubuntu with `openai/codex-action@v1`.

- `actions/checkout` uses `persist-credentials: false`.
- Dependencies are installed before Codex starts.
- Codex receives `permission-profile: ":workspace"` and the action's default `drop-sudo` safety strategy.
- Codex does not receive `GITHUB_TOKEN` in its environment and cannot push by itself.
- The workflow passes the task text through a generated local prompt file.
- After Codex exits, a separate shell step runs `scripts/codex/verify.sh`.
- Only after verification succeeds does the workflow authenticate Git, commit, push the feature branch, and create/update the PR.

## Security boundaries

- `OPENAI_API_KEY` is a GitHub Actions secret and is only passed to `openai/codex-action`.
- Git credentials are not persisted in the checkout visible to Codex.
- Codex has workspace write access but no general network access under the built-in workspace permission profile.
- Dispatch/fix commands are accepted only from actors with repository write/maintain/admin permission.
- Control-plane files are controller-owned and must not be modified by ordinary Codex tasks unless the Issue explicitly authorizes a control-plane change.
- No workflow auto-merges `main`.

## Verification

Repository CI validates the control-plane contract without requiring an OpenAI secret. Contract tests assert the dispatcher triggers, permission boundary, non-persistent credentials, state labels, PR handoff, verification script, and governance policy. Runtime Codex execution is validated separately after `OPENAI_API_KEY` is configured.

## Failure behavior

If authorization, secret preflight, Codex execution, verification, commit, push, or PR creation fails, the Issue/PR is moved to `agent:blocked` and receives a diagnostic comment. Existing `main` is never modified by the worker workflow.

## Required external configuration

`OPENAI_API_KEY` must be added as a repository Actions secret before the first Codex task can run. The current GitHub connector cannot create or read repository secrets, so this is intentionally an external one-time configuration.

`main` branch protection is recommended but is not required for bootstrap. The controller must not merge until CI is green. If repository rules are later enabled, required checks should include the normal CI workflow.

## V1 non-goals

- Persistent Codex SDK thread/session state.
- A custom database, queue, Redis, daemon, or tmux orchestrator.
- Multi-agent routing.
- Automatic merging.
- Runtime LLM decisions inside the market applications.
