# Credit Stress / Reversal Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deployable Credit Stress / Reversal Radar beside COT Radar using public credit, volatility, and equity-proxy data.

**Architecture:** A standalone `credit_radar` Python package fetches and validates FRED/Stooq inputs, calculates prior-only analytics/state transitions/backtests, and exports immutable derived artifacts. A separate React/Vite app renders those artifacts. Root packaging, CI, and Pages workflows are extended without changing COT Radar semantics.

**Tech Stack:** Python 3.11, pandas, gs-quant 2.1.6, httpx, PyYAML, pytest, Ruff, mypy, React 19, TypeScript, Vite, Vitest, GitHub Actions/Pages.

**Spec:** `docs/superpowers/specs/2026-08-28-credit-stress-radar-design.md`

## Global Constraints
- Use FRED `BAMLH0A0HYM2`, `BAMLC0A0CM`, and `VIXCLS`.
- Use SPY/QQQ only as clearly labeled ES/NQ price proxies.
- Default prior-only percentile lookback is 756 trading observations with minimum 252.
- Default state thresholds: 70 / 85 / 95 percentile, SMA50, 5D/20D spread changes, 10W price SMA, 4W price momentum.
- No look-ahead, no runtime LLM, no direct buy/sell advice, no secrets.
- Frontend renders Python output; it never recreates state rules.

---

### Task 1: Packaging and RED contract tests
**Files:** modify `pyproject.toml`, `.github/workflows/ci.yml`; create `projects/credit-radar/pipeline/tests/*` and `projects/credit-radar/config/settings.yaml`.
**Produces:** failing tests that define configuration, prior-only analytics, provider validation, state machine, backtest, export contract, and frontend contract.
- [ ] Add Credit package/source/test paths and `credit-radar` CLI to root packaging.
- [ ] Add Credit Python and web jobs to CI.
- [ ] Write tests before production code.
- [ ] Push RED commit and verify GitHub Actions fails because `credit_radar` / frontend are not implemented.

### Task 2: Public providers and config
**Files:** create `credit_radar/config.py`, `models.py`, `providers/http.py`, `providers/fred.py`, `providers/prices.py`.
**Interfaces:** `RadarSettings.load(path)`, `FredProvider.fetch(series_id) -> DataFrame`, `StooqPriceProvider.fetch(symbol) -> DataFrame`.
- [ ] Implement strict numeric/date normalization and source metadata.
- [ ] Reject missing/duplicate/invalid observations deterministically.
- [ ] Run provider/config tests to GREEN.

### Task 3: Prior-only credit analytics
**Files:** create `analytics.py`.
**Interfaces:** `compute_credit_features(frame, settings) -> DataFrame`, `compute_price_features(frame, settings) -> DataFrame`.
- [ ] Implement shifted rolling percentile using only prior observations.
- [ ] Add SMA50, 5D/20D spread change, 20D high, VIX/IG percentiles.
- [ ] Add 4W momentum and 10W SMA for SPY/QQQ.
- [ ] Run analytics tests to GREEN.

### Task 4: State machine and cross-asset interpretation
**Files:** create `signals.py`.
**Interfaces:** `classify_credit_states(frame, settings) -> DataFrame`, `build_cross_asset_evidence(latest, settings) -> dict`.
- [ ] Implement deterministic precedence and 60-trading-day stress memory.
- [ ] Implement HY-specific/systemic and credit-vs-vol divergence labels.
- [ ] Export formula, evidence, and falsification text/data.
- [ ] Run signal tests to GREEN.

### Task 5: Backtest and event study
**Files:** create `backtest.py`.
**Interfaces:** `build_event_study(states, prices, settings) -> list[dict]`.
- [ ] Detect state-entry transitions only.
- [ ] Compute 1/4/8/13/26W return, MAE, MFE, period and sample size.
- [ ] Suppress positive-return rate below minimum sample size.
- [ ] Run backtest tests to GREEN.

### Task 6: Pipeline, export, freshness
**Files:** create `pipeline.py`, `export.py`, `cli.py`, `__init__.py`.
**Interfaces:** `run_pipeline(...)`, `write_artifacts(...)`.
- [ ] Align daily credit/VIX calendar safely and weekly proxy prices without timezone shifting.
- [ ] Export dashboard/history/backtest/state CSV/status JSON and copy web public data.
- [ ] Mark stale/incomplete input and preserve provenance/history windows.
- [ ] Run export/pipeline tests to GREEN.

### Task 7: Credit Radar frontend
**Files:** create `projects/credit-radar/web` Vite app and tests.
- [ ] Write Vitest contract tests first for regime, freshness, evidence, confirmation, backtest small-sample warning, sources, and Asia/Taipei-safe dates.
- [ ] Implement dark Traditional Chinese responsive UI.
- [ ] Show explicit `SPY/QQQ proxy—not ES/NQ settlement` wording.
- [ ] Run `npm test -- --run`, `npx tsc -b --pretty false`, and `npx vite build`.

### Task 8: CI, refresh, and Pages integration
**Files:** modify `.github/workflows/ci.yml`, `.github/workflows/deploy-pages.yml`, `README.md`.
- [ ] CI runs COT and Credit Python/web checks plus diff-check.
- [ ] Scheduled/manual deployment refreshes both projects; a Credit refresh failure keeps last validated Credit artifacts and displays a warning.
- [ ] Pages artifact contains `/cot-radar/` and `/credit-radar/`.
- [ ] Document FRED's current three-year ICE history limitation and longer-history extension point.

### Task 9: Verification and merge
- [ ] Run full GitHub CI; require pytest, Ruff, mypy, Vitest, TypeScript, Vite, and `git diff --check` success.
- [ ] Review branch diff against this spec.
- [ ] Open PR, require green PR CI, merge to `main` using a merge commit.
- [ ] Require main CI and Pages deployment success.
- [ ] Verify live `/credit-radar/` and `/credit-radar/data/status.json` show the new assets, source/proxy labels, and consistent current status.
