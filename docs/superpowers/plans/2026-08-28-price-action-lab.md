# Price Action Research Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible ES/NQ 5-minute Wedge Bull Flag research platform that separates deterministic features, broad candidates, human Brooks-style labels, outcome statistics, and out-of-sample experiment decisions.

**Architecture:** Python under `projects/price-action-lab/src/price_action` owns ingestion, causal market-structure features, candidate generation, labels, outcomes, experiments, and static chart payloads. A lightweight browser UI reads local/static candidate payloads and writes label records through a narrow local persistence boundary. Raw licensed data stays local and out of Git; only fixtures, code, metadata, and derived non-restricted artifacts are versioned.

**Tech Stack:** Python 3.11+, pandas, NumPy, PyYAML, Pydantic 2, pytest, Ruff, mypy; React 19, TypeScript, Vite, lightweight-charts or Plotly, Vitest, Testing Library. Use project-local dependencies where possible and avoid changing root shared files unless a task explicitly requires it.

**Spec:** `docs/superpowers/specs/2026-08-28-price-action-lab-design.md`

## Global Constraints

- MVP markets are ES and NQ only.
- Timeframe is 5-minute bars only.
- RTH is 09:30–16:00 America/New_York using bar-start timestamps, 09:30 inclusive and 16:00 exclusive.
- Candidate classification must use only data available at or before the decision bar; lookahead is forbidden.
- The machine emits `WEDGE_BULL_FLAG_CANDIDATE`, never a machine-asserted confirmed Brooks pattern.
- Raw licensed market data must not be committed to Git.
- Futures roll/continuous-series policy must be explicit in dataset metadata and must not be silently mixed across experiments.
- Human labels remain separate from deterministic features and are never overwritten by recalculation.
- Pattern-labeling mode must not reveal future outcome bars before label commitment.
- Research experiment IDs use `EXP-xxx`; engineering task IDs use `PAL-xxx`.
- COT Radar source files under `projects/cot-radar/` must not be modified by any Price Action task.
- Root dependency files and `.github/workflows/` are shared collision points and must be avoided unless the task explicitly authorizes a minimal shared change.
- Codex is the source/test implementation writer. ChatGPT controls architecture, task contracts, evidence review, and final audit.

---

### PAL-001: Project foundation, canonical bars, CSV ingestion, RTH normalization

**Files:**
- Create: `projects/price-action-lab/pyproject.toml`
- Create: `projects/price-action-lab/.gitignore`
- Create: `projects/price-action-lab/config/markets.yaml`
- Create: `projects/price-action-lab/src/price_action/__init__.py`
- Create: `projects/price-action-lab/src/price_action/models.py`
- Create: `projects/price-action-lab/src/price_action/ingestion.py`
- Create: `projects/price-action-lab/tests/test_models.py`
- Create: `projects/price-action-lab/tests/test_ingestion.py`
- Create: `projects/price-action-lab/data/fixtures/es_small.csv`
- Create: `projects/price-action-lab/data/fixtures/nq_small.csv`

**Interfaces:**
- Produces `Bar`, `DatasetMetadata`, `Dataset`, `CsvBarLoader.load(path, metadata) -> Dataset`, and `filter_rth(frame) -> pd.DataFrame`.
- `Bar` fields: `timestamp`, `symbol`, `contract`, `open`, `high`, `low`, `close`, `volume`, `session`, `source`.
- `DatasetMetadata` records `dataset_version`, `source`, `timezone`, `bar_interval`, `roll_policy`, `symbols`, and source date range.

- [ ] **Step 1: Write model tests first**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from price_action.models import Bar, DatasetMetadata


def test_bar_rejects_negative_price():
    with pytest.raises(ValidationError):
        Bar(
            timestamp=datetime(2026, 1, 2, 9, 30, tzinfo=ZoneInfo("America/New_York")),
            symbol="ES",
            contract="ESH26",
            open=-1,
            high=2,
            low=1,
            close=1.5,
            volume=100,
            session="RTH",
            source="fixture",
        )


def test_dataset_metadata_requires_explicit_roll_policy():
    with pytest.raises(ValidationError):
        DatasetMetadata(
            dataset_version="fixture-v1",
            source="fixture",
            timezone="America/New_York",
            bar_interval="5m",
            roll_policy="",
            symbols=["ES", "NQ"],
            start_date="2026-01-02",
            end_date="2026-01-05",
        )
```

- [ ] **Step 2: Run focused model tests and verify a genuine RED**

Run: `cd projects/price-action-lab && python -m pytest tests/test_models.py -q`  
Expected: tests collect; assertions fail because required production API is absent or incomplete. Import/collection errors do not satisfy the RED gate.

- [ ] **Step 3: Implement typed models minimally**

Implement strict Pydantic models with `extra="forbid"`, positive OHLC values, non-negative volume, `high >= max(open, close, low)`, `low <= min(open, close, high)`, ES/NQ symbol validation, timezone-aware timestamps, and non-empty roll policy.

- [ ] **Step 4: Write ingestion tests**

```python
from pathlib import Path

import pandas as pd
import pytest

from price_action.ingestion import CsvBarLoader, DuplicateBarError, filter_rth
from price_action.models import DatasetMetadata


def test_loader_normalizes_to_new_york_and_sorts(es_csv: Path, metadata: DatasetMetadata):
    dataset = CsvBarLoader().load(es_csv, metadata)
    assert str(dataset.frame["timestamp"].dt.tz) == "America/New_York"
    assert dataset.frame["timestamp"].is_monotonic_increasing


def test_rth_uses_0930_inclusive_1600_exclusive(sample_frame: pd.DataFrame):
    result = filter_rth(sample_frame)
    local_times = result["timestamp"].dt.strftime("%H:%M").tolist()
    assert "09:30" in local_times
    assert "15:55" in local_times
    assert "16:00" not in local_times


def test_duplicate_timestamp_symbol_is_rejected(duplicate_csv: Path, metadata: DatasetMetadata):
    with pytest.raises(DuplicateBarError):
        CsvBarLoader().load(duplicate_csv, metadata)
```

- [ ] **Step 5: Run ingestion tests and verify RED**

Run: `cd projects/price-action-lab && python -m pytest tests/test_ingestion.py -q`  
Expected: focused tests fail on missing ingestion behavior, not collection.

- [ ] **Step 6: Implement CSV ingestion and RTH normalization**

Accept configurable CSV column aliases, normalize timestamps to `America/New_York`, sort chronologically, reject duplicate `(timestamp, symbol)` rows, validate five-minute spacing where present, preserve missing-bar gaps as data-quality facts rather than filling them, and mark RTH deterministically.

- [ ] **Step 7: Verify PAL-001**

Run:
`cd projects/price-action-lab && python -m pytest tests/test_models.py tests/test_ingestion.py -q`
`cd projects/price-action-lab && python -m ruff check src tests`
`cd projects/price-action-lab && python -m mypy src`
Expected: all exit 0.

- [ ] **Step 8: Commit**

Commit message: `feat: add Price Action Lab data foundation`

---

### PAL-002: Bar geometry, EMA20, ATR, and causal context primitives

**Files:**
- Create: `projects/price-action-lab/src/price_action/bars.py`
- Create: `projects/price-action-lab/src/price_action/indicators.py`
- Create: `projects/price-action-lab/src/price_action/context.py`
- Create: `projects/price-action-lab/tests/test_bars.py`
- Create: `projects/price-action-lab/tests/test_indicators.py`
- Create: `projects/price-action-lab/tests/test_context.py`

**Interfaces:**
- Produces `add_bar_geometry(frame)`, `ema(series, span)`, `atr(frame, period)`, `add_context_features(frame, config)`.
- Context fields include `ema20`, `ema20_slope`, `atr`, `close_ema_atr`, `recent_close_above_ema_fraction`, and `rolling_overlap_ratio`.

- [ ] **Step 1: Write deterministic geometry tests**

```python
def test_bar_geometry_uses_only_current_and_prior_bar(two_bars):
    result = add_bar_geometry(two_bars)
    row = result.iloc[1]
    assert row["body"] == pytest.approx(abs(row["close"] - row["open"]))
    assert 0 <= row["close_location"] <= 1
    assert 0 <= row["overlap_prev"] <= 1
```

- [ ] **Step 2: Write indicator reference tests**

Use a short hand-calculated fixture and compare EMA with `pandas.Series.ewm(span=20, adjust=False).mean()`. ATR uses Wilder true range with only present/past bars and `ewm(alpha=1/period, adjust=False)` after true range construction.

- [ ] **Step 3: Add explicit no-lookahead regression**

```python
def test_appending_future_bars_does_not_change_existing_context(prefix_frame, future_rows):
    before = add_context_features(prefix_frame.copy(), config)
    after = add_context_features(pd.concat([prefix_frame, future_rows]), config)
    pd.testing.assert_frame_equal(before, after.iloc[: len(before)][before.columns])
```

- [ ] **Step 4: Run focused tests and verify RED**

Run: `cd projects/price-action-lab && python -m pytest tests/test_bars.py tests/test_indicators.py tests/test_context.py -q`
Expected: genuine assertion failures against absent/incomplete production behavior.

- [ ] **Step 5: Implement minimal causal features**

No centered rolling windows, negative shifts, or future fill operations are permitted. Keep all configurable lookbacks in a typed context configuration model.

- [ ] **Step 6: Verify and commit**

Run focused pytest, Ruff, mypy.  
Commit: `feat: add causal price-action feature primitives`

---

### PAL-003: Causal pivots, swings, and directional pushes

**Files:**
- Create: `projects/price-action-lab/src/price_action/swings.py`
- Create: `projects/price-action-lab/src/price_action/pushes.py`
- Create: `projects/price-action-lab/tests/test_swings.py`
- Create: `projects/price-action-lab/tests/test_pushes.py`
- Create: `projects/price-action-lab/data/fixtures/three_push_synthetic.csv`
- Create: `projects/price-action-lab/data/fixtures/trading_range_synthetic.csv`

**Interfaces:**
- Produces `Pivot`, `Swing`, `Push`, `detect_pivots(frame, config)`, `build_swings(frame, pivots)`, `extract_down_pushes(frame, swings, config)`.
- Every pivot has `observed_at` separate from `pivot_bar` so delayed causal confirmation is explicit.

- [ ] **Step 1: Write causal-pivot tests**

Create a fixture where a low at bar 5 is confirmable only at bar 7. Assert that the pivot references bar 5 but has `observed_at` equal to bar 7 and cannot appear in a scan ending at bar 6.

- [ ] **Step 2: Write three-push extraction tests**

```python
def test_three_down_pushes_are_distinct_and_ordered(three_push_frame, config):
    pushes = extract_down_pushes(three_push_frame, detect_and_build(three_push_frame, config), config)
    assert len(pushes) >= 3
    assert pushes[-3].end_bar < pushes[-2].end_bar < pushes[-1].end_bar
    assert all(push.direction == "down" for push in pushes[-3:])
```

- [ ] **Step 3: Run focused tests and verify RED**

Run: `cd projects/price-action-lab && python -m pytest tests/test_swings.py tests/test_pushes.py -q`

- [ ] **Step 4: Implement versioned causal pivot rule and push features**

Store start/end swing references, bar count, raw price distance, ATR-normalized distance, bounce retracement, overlap summary, and duration. Do not collapse pushes into wedge labels.

- [ ] **Step 5: Verify and commit**

Commit: `feat: add causal swing and push extraction`

---

### PAL-004: Broad Wedge Bull Flag candidate detector

**Files:**
- Create: `projects/price-action-lab/config/detector.yaml`
- Create: `projects/price-action-lab/src/price_action/wedges.py`
- Create: `projects/price-action-lab/tests/test_wedges.py`
- Create: `projects/price-action-lab/data/fixtures/wedge_candidate_synthetic.csv`
- Create: `projects/price-action-lab/data/fixtures/deep_pullback_synthetic.csv`

**Interfaces:**
- Produces `WedgeCandidate`, `DetectorConfig`, `detect_wedge_bull_flag_candidates(frame, dataset_metadata, config) -> list[WedgeCandidate]`.
- Each candidate stores `candidate_id`, `detector_version`, `dataset_version`, `symbol`, `decision_bar`, `setup_start`, `setup_end`, push references, and full deterministic feature snapshot.

- [ ] **Step 1: Write permissive-detector tests**

Assert a synthetic valid three-push bull-context fixture emits exactly one `WEDGE_BULL_FLAG_CANDIDATE`, while a 70% pullback fixture fails the default 20–65% pullback gate.

- [ ] **Step 2: Write future-invariance test**

Append extreme future bars after the decision bar and assert the candidate identity and stored feature snapshot remain byte-equivalent.

- [ ] **Step 3: Run RED, implement v0.1, verify GREEN**

Detector v0.1 defaults: positive EMA20 slope, recent closes predominantly above EMA20, pullback 20%–65%, at least three down pushes, final push within 1 ATR of EMA20, setup duration 10–60 bars.

- [ ] **Step 4: Commit**

Commit: `feat: add broad Wedge Bull Flag candidate detector`

---

### PAL-005: Label model and future-safe chart payloads

**Files:**
- Create: `projects/price-action-lab/src/price_action/labeling.py`
- Create: `projects/price-action-lab/src/price_action/charts.py`
- Create: `projects/price-action-lab/tests/test_labeling.py`
- Create: `projects/price-action-lab/tests/test_charts.py`

**Interfaces:**
- Produces `PatternLabel`, `LabelRecord`, `LabelStore`, `build_labeling_chart_payload(frame, candidate, pre_context_bars)`, `build_review_chart_payload(...)`.

- [ ] **Step 1: Write label validation tests**

Accept only `YES`, `NO`, `UNCERTAIN`. Require candidate ID, detector version, annotator, timestamp. Keep reasons structured and optional note bounded.

- [ ] **Step 2: Write future-hiding chart test**

Assert labeling payload max timestamp is `<= candidate.decision_bar`; review payload may include configured post bars only after a committed label exists.

- [ ] **Step 3: Run RED, implement, verify**

Use JSONL label persistence with atomic append/replace semantics suitable for a local single-user MVP; deterministic features are referenced, not overwritten into mutable label fields.

- [ ] **Step 4: Commit**

Commit: `feat: add auditable labeling and chart payloads`

---

### PAL-006: Browser labeling UI

**Files:**
- Create: `projects/price-action-lab/web/package.json`
- Create: `projects/price-action-lab/web/tsconfig.json`
- Create: `projects/price-action-lab/web/vite.config.ts`
- Create: `projects/price-action-lab/web/src/main.tsx`
- Create: `projects/price-action-lab/web/src/App.tsx`
- Create: `projects/price-action-lab/web/src/types.ts`
- Create: `projects/price-action-lab/web/src/api.ts`
- Create: `projects/price-action-lab/web/src/CandidateChart.tsx`
- Create: `projects/price-action-lab/web/src/LabelPanel.tsx`
- Create: `projects/price-action-lab/web/src/App.test.tsx`
- Create: `projects/price-action-lab/web/src/LabelPanel.test.tsx`

**Interfaces:**
- Consumes static/local candidate queue JSON and a narrow label-save endpoint or file-backed dev adapter.
- Produces candidate navigation, candlestick/EMA/push display, deterministic feature summary, label controls, reason controls, and progress counts.

- [ ] **Step 1: Write UI test that future bars are absent before labeling**

Mock a labeling payload and assert only supplied setup/pre-context data are rendered; the UI must not request or render post-setup outcome data until a label save succeeds.

- [ ] **Step 2: Write label submission test**

Click `YES`, choose `valid wedge structure`, submit, assert exact payload includes candidate ID and detector version.

- [ ] **Step 3: Implement minimal research UI**

No ranking, trade recommendation, brokerage controls, or live scanner in this task.

- [ ] **Step 4: Verify and commit**

Run `npm test -- --run` and `npm run build`.  
Commit: `feat: add Wedge candidate labeling interface`

---

### PAL-007: Forward outcomes, MFE, MAE, and threshold events

**Files:**
- Create: `projects/price-action-lab/src/price_action/outcomes.py`
- Create: `projects/price-action-lab/tests/test_outcomes.py`

**Interfaces:**
- Produces `OutcomeRecord`, `measure_outcomes(frame, candidate, horizons=(5,10,20))`.

- [ ] **Step 1: Write exact synthetic MFE/MAE tests**

Use a candidate with decision close 100 and ATR 2; future highs/lows are hand-constructed so expected MFE/MAE and +1 ATR before -1 ATR are unambiguous.

- [ ] **Step 2: Assert decision bar exclusion**

The decision bar itself must never count toward outcome extrema or threshold ordering.

- [ ] **Step 3: Run RED, implement, verify**

Return insufficient-data markers when a horizon extends beyond available data rather than silently shortening it.

- [ ] **Step 4: Commit**

Commit: `feat: add leakage-safe Wedge outcome measurements`

---

### PAL-008: Experiment registry and detector comparison

**Files:**
- Create: `projects/price-action-lab/src/price_action/experiments.py`
- Create: `projects/price-action-lab/tests/test_experiments.py`
- Create: `projects/price-action-lab/experiments/EXP-001.yaml`

**Interfaces:**
- Produces `ExperimentDefinition`, `ExperimentResult`, `ExperimentDecision`, `load_experiment(path)`, `compare_detector_versions(...)`, `write_experiment_result(...)`.

- [ ] **Step 1: Write schema tests**

Require experiment ID `EXP-<digits>`, hypothesis, baseline detector version, exactly one primary rule change unless `interaction_effect=true`, dataset version/date range, partition declaration, candidate count, and decision in `RETAIN|REJECT|REVISE`.

- [ ] **Step 2: Write rejected-experiment preservation test**

Assert writing a new revision does not delete or overwrite a prior rejected experiment artifact.

- [ ] **Step 3: Implement comparison outputs**

When human labels exist, publish sample count, precision for `YES`, recall against labeled candidate universe where meaningful, `NO` false-positive rate, and `UNCERTAIN` count separately. Outcome metrics stay separate from label-quality metrics.

- [ ] **Step 4: Verify and commit**

Commit: `feat: add auditable Price Action experiment registry`

---

### PAL-009: Train/validation/OOS partition enforcement

**Files:**
- Create: `projects/price-action-lab/src/price_action/validation.py`
- Create: `projects/price-action-lab/tests/test_validation.py`

**Interfaces:**
- Produces `ResearchSplit`, `assign_partition(timestamp, split)`, `freeze_detector_cycle(...)`, `evaluate_frozen_detector(...)`.

- [ ] **Step 1: Write non-overlap tests**

Reject any train/validation/OOS boundary overlap and any timestamp not deterministically assignable.

- [ ] **Step 2: Write OOS freeze test**

After detector version freeze, evaluation must refuse parameter mutation or a mismatched detector hash/version.

- [ ] **Step 3: Run RED, implement, verify**

Results are always grouped at least by symbol; optional regime/calendar slices require explicit minimum sample size.

- [ ] **Step 4: Commit**

Commit: `feat: enforce Price Action out-of-sample validation`

---

### PAL-010: End-to-end research runner and first candidate batch

**Files:**
- Create: `projects/price-action-lab/src/price_action/runner.py`
- Create: `projects/price-action-lab/src/price_action/reporting.py`
- Create: `projects/price-action-lab/tests/test_runner.py`
- Create: `projects/price-action-lab/reports/.gitkeep`
- Create: `projects/price-action-lab/README.md`

**Interfaces:**
- Produces CLI commands `price-action ingest`, `price-action scan`, `price-action label-export`, `price-action outcomes`, `price-action experiment`, and `price-action report`.

- [ ] **Step 1: Write fixture-only end-to-end test**

Load synthetic ES fixture → add causal features → detect candidate → build future-safe labeling payload → record label → measure outcomes → write EXP result → render a research summary. Assert every artifact carries dataset and detector versions.

- [ ] **Step 2: Run RED, implement orchestration, verify fixture E2E**

No network access is required for the test suite. Real raw ES/NQ CSV remains an operator-provided local input.

- [ ] **Step 3: Run full verification**

Run:
`cd projects/price-action-lab && python -m pytest -q`
`cd projects/price-action-lab && python -m ruff check src tests`
`cd projects/price-action-lab && python -m mypy src`
`cd projects/price-action-lab/web && npm test -- --run`
`cd projects/price-action-lab/web && npm run build`
`git diff --check`
Expected: all exit 0 and no changed path begins with `projects/cot-radar/`.

- [ ] **Step 4: Produce first real candidate batch when ES/NQ CSV is available**

Run ingestion and v0.1 scan against the declared local dataset, write only non-restricted candidate metadata/chart payloads, and prepare an unlabeled queue. Do not compute or reveal post-decision outcomes in the pre-label queue.

- [ ] **Step 5: Commit**

Commit: `feat: complete Price Action Lab MVP research loop`

---

## Global completion gate

The implementation is ready for final audit only when all PAL-001 through PAL-010 task checks are green, leakage-control regressions pass, no Price Action task modified COT Radar source, the browser labeling flow hides future outcome bars before commitment, and a first unlabeled ES/NQ Wedge Bull Flag candidate batch can be produced from local data without publishing restricted raw bars.
