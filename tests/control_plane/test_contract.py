from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = ROOT / relative
    assert path.exists(), f"required control-plane file is missing: {relative}"
    return path.read_text(encoding="utf-8")


def test_codex_workflow_has_safe_dispatch_and_handoff_contract() -> None:
    workflow = _read(".github/workflows/codex-control-plane.yml")

    required = (
        "issues:",
        "issue_comment:",
        "agent:ready",
        "/codex fix",
        "openai/codex-action@v1",
        'permission-profile: ":workspace"',
        "openai-api-key: ${{ secrets.OPENAI_API_KEY }}",
        "persist-credentials: false",
        "scripts/codex/bootstrap.sh",
        "scripts/codex/verify.sh",
        "gh pr create",
        "agent:running",
        "agent:review",
        "agent:blocked",
    )
    for marker in required:
        assert marker in workflow, f"workflow contract missing: {marker}"

    assert "git push origin main" not in workflow
    assert "git push origin HEAD:main" not in workflow


def test_governance_reserves_controller_and_worker_responsibilities() -> None:
    agents = _read("AGENTS.md")

    required = (
        "ChatGPT Controller",
        "Codex Worker",
        "Never push or merge `main`",
        "TDD",
        ".github/workflows/codex-control-plane.yml",
        "scripts/codex/",
        "Do not weaken tests",
        "Do not expose secrets",
    )
    for marker in required:
        assert marker in agents, f"AGENTS.md governance missing: {marker}"


def test_worker_scripts_define_bootstrap_and_deterministic_verification() -> None:
    bootstrap = _read("scripts/codex/bootstrap.sh")
    verify = _read("scripts/codex/verify.sh")

    assert 'python -m pip install -e ".[dev]"' in bootstrap
    assert "projects/cot-radar/web" in bootstrap

    required_verify = (
        "projects/cot-radar/pipeline/tests",
        "ruff check",
        "mypy projects/cot-radar/pipeline/src",
        "npm test -- --run",
        "npm run build",
        "tests/control_plane",
        "git diff --check",
    )
    for marker in required_verify:
        assert marker in verify, f"verification gate missing: {marker}"


def test_bootstrap_does_not_create_false_implementation_diffs() -> None:
    bootstrap = _read("scripts/codex/bootstrap.sh")
    gitignore = _read(".gitignore")

    assert "npm install --package-lock=false" in bootstrap
    assert "*.egg-info/" in gitignore
    assert "*.tsbuildinfo" in gitignore


def test_issue_template_captures_machine_actionable_task_contract() -> None:
    template = _read(".github/ISSUE_TEMPLATE/codex-task.yml")
    for marker in (
        "Goal",
        "Scope",
        "Constraints",
        "Acceptance criteria",
        "Verification",
        "Out of scope",
        "agent:planned",
    ):
        assert marker in template, f"issue task contract missing: {marker}"


def test_operations_guide_documents_secret_and_controller_retry_flow() -> None:
    guide = _read("docs/codex-control-plane.md")
    for marker in (
        "OPENAI_API_KEY",
        "agent:ready",
        "/codex fix",
        "API billing",
        "branch protection",
        "controller",
    ):
        assert marker in guide, f"operations guide missing: {marker}"
