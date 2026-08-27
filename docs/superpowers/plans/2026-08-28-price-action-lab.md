# Price Action Research Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible ES/NQ 5-minute Wedge Bull Flag research platform that separates deterministic features, broad candidates, human Brooks-style labels, outcome statistics, and out-of-sample experiment decisions.

**Architecture:** Python under `projects/price-action-lab/src/price_action` owns ingestion, causal market-structure features, candidate generation, labels, outcomes, experiments, and chart payloads. A lightweight browser UI consumes candidate payloads and persists labels through a narrow local boundary. Raw licensed data stays local and out of Git; only fixtures, code, metadata, and derived non-restricted artifacts are versioned.

**Tech Stack:** Python 3.11+, pandas, NumPy, PyYAML, Pydantic 2, pytest, Ruff, mypy; React 19, TypeScript, Vite, lightweight-charts or Plotly, Vitest, Testing Library.

**Spec:** `docs/superpowers/specs/2026-08-28-price-action-lab-design.md`

## Global Constraints

- MVP markets are ES and NQ only; timeframe is 5-minute bars only.
- RTH is 09:30–16:00 America/New_York using bar-start timestamps, 09:30 inclusive and 16:00 exclusive.
- Classification uses only data available at or before the decision bar; centered windows, negative shifts, and future fills are forbidden.
- The machine emits `WEDGE_BULL_FLAG_CANDIDATE`, never a machine-asserted confirmed Brooks pattern.
- Raw licensed market data must not be committed to Git.
- Futures roll/continuous-series policy must be explicit in dataset metadata and must not be silently mixed across experiments.
- Human labels remain separate from deterministic features and are never overwritten by recalculation.
- Pattern-labeling mode must not reveal future outcome bars before label commitment.
- Research experiment IDs use `EXP-xxx`; engineering task IDs use `PAL-xxx`.
- No Price Action task may modify `projects/cot-radar/`.
- Root dependency files and `.github/workflows/` are shared collision points and are out of scope unless a task explicitly authorizes the smallest possible shared change.
- Codex is the source/test implementation writer. ChatGPT controls architecture, task contracts, evidence review, and final audit.
- **Collection-safe RED rule:** before a focused RED run, Codex may create only import-safe interface skeletons required for the tests to collect. Those skeletons must contain no successful production behavior. The RED must be an executed failing assertion or `NotImplementedError`; import/collection errors do not satisfy the gate.
- Each task must end with focused tests, Ruff, mypy where applicable, `git diff --check`, and a declared-file-scope check before commit/PR.

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
- `Bar`, `DatasetMetadata`, `Dataset`.
- `CsvBarLoader.load(path: Path, metadata: DatasetMetadata) -> Dataset`.
- `filter_rth(frame: pd.DataFrame) -> pd.DataFrame`.
- `Bar` fields: `timestamp`, `symbol`, `contract`, `open`, `high`, `low`, `close`, `volume`, `session`, `source`.
- `DatasetMetadata` records `dataset_version`, `source`, `timezone`, `bar_interval`, `roll_policy`, `symbols`, `start_date`, `end_date`.

- [ ] **Step 1: Create import-safe interface skeletons only**

`models.py` must expose the named models and `ingestion.py` the named loader/functions, but behavioral methods may only raise `NotImplementedError`. Do not implement validation or normalization yet.

- [ ] **Step 2: Write failing model tests**

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
            symbol="ES", contract="ESH26",
            open=-1, high=2, low=1, close=1.5, volume=100,
            session="RTH", source="fixture",
        )


def test_dataset_metadata_requires_explicit_roll_policy():
    with pytest.raises(ValidationError):
        DatasetMetadata(
            dataset_version="fixture-v1", source="fixture",
            timezone="America/New_York", bar_interval="5m", roll_policy="",
            symbols=["ES", "NQ"], start_date="2026-01-02", end_date="2026-01-05",
        )
```

- [ ] **Step 3: Run model RED**

Run: `cd projects/price-action-lab && python -m pytest tests/test_models.py -q`  
Expected: tests collect and fail because skeletons do not yet enforce the contracts.

- [ ] **Step 4: Implement strict typed models**

Use Pydantic `extra="forbid"`; positive OHLC, non-negative volume, timezone-aware timestamps, `symbol in {ES,NQ}`, `high >= max(open, close, low)`, `low <= min(open, close, high)`, non-empty source, and non-empty roll policy.

- [ ] **Step 5: Write ingestion tests**

```python
def test_loader_normalizes_to_new_york_and_sorts(es_csv, metadata):
    dataset = CsvBarLoader().load(es_csv, metadata)
    assert str(dataset.frame["timestamp"].dt.tz) == "America/New_York"
    assert dataset.frame["timestamp"].is_monotonic_increasing


def test_rth_uses_0930_inclusive_1600_exclusive(sample_frame):
    result = filter_rth(sample_frame)
    times = result["timestamp"].dt.strftime("%H:%M").tolist()
    assert "09:30" in times
    assert "15:55" in times
    assert "16:00" not in times


def test_duplicate_timestamp_symbol_is_rejected(duplicate_csv, metadata):
    with pytest.raises(DuplicateBarError):
        CsvBarLoader().load(duplicate_csv, metadata)
```

- [ ] **Step 6: Run ingestion RED, then implement ingestion**

Run: `cd projects/price-action-lab && python -m pytest tests/test_ingestion.py -q`.  
Then implement configurable CSV aliases, explicit input timezone, normalization to America/New_York, chronological sort, duplicate `(timestamp,symbol)` rejection, five-minute interval validation where observations are contiguous, missing-gap reporting without synthetic fills, and deterministic RTH marking.

- [ ] **Step 7: Verify and commit**

Run focused pytest, `python -m ruff check src tests`, `python -m mypy src`, and `git diff --check`.  
Commit: `feat: add Price Action Lab data foundation`.

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
- `add_bar_geometry(frame) -> pd.DataFrame`.
- `ema(series, span) -> pd.Series`.
- `atr(frame, period) -> pd.Series`.
- `add_context_features(frame, config) -> pd.DataFrame`.
- Context fields: `ema20`, `ema20_slope`, `atr`, `close_ema_atr`, `recent_close_above_ema_fraction`, `rolling_overlap_ratio`.

- [ ] **Step 1: Create import-safe skeletons, then write geometry/indicator/context tests**

Geometry asserts body/tails/range/close-location and prior-bar overlap. EMA reference is `Series.ewm(span=20, adjust=False).mean()`. ATR builds true range from current high/low and prior close, then Wilder-style `ewm(alpha=1/period, adjust=False)`.

- [ ] **Step 2: Add explicit future-invariance RED**

```python
def test_appending_future_bars_does_not_change_existing_context(prefix_frame, future_rows, config):
    before = add_context_features(prefix_frame.copy(), config)
    after = add_context_features(pd.concat([prefix_frame, future_rows]), config)
    pd.testing.assert_frame_equal(before, after.iloc[: len(before)][before.columns])
```

- [ ] **Step 3: Run RED, implement causal features, verify**

No centered rolling window, negative shift, backward fill, or feature computed from bars after the row timestamp is permitted.

- [ ] **Step 4: Commit**

Commit: `feat: add causal price-action feature primitives`.

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
- `Pivot`, `Swing`, `Push`.
- `detect_pivots(frame, config) -> list[Pivot]`.
- `build_swings(frame, pivots) -> list[Swing]`.
- `extract_down_pushes(frame, swings, config) -> list[Push]`.
- `Pivot` stores both `pivot_bar` and causal `observed_at`.

- [ ] **Step 1: Create skeletons and write causal-pivot RED**

A fixture low at bar 5 confirmable only at bar 7 must reference bar 5 but have `observed_at=bar7`; scanning only through bar 6 must not expose it.

- [ ] **Step 2: Write push RED**

```python
def test_three_down_pushes_are_distinct_and_ordered(three_push_frame, config):
    pivots = detect_pivots(three_push_frame, config)
    swings = build_swings(three_push_frame, pivots)
    pushes = extract_down_pushes(three_push_frame, swings, config)
    assert len(pushes) >= 3
    assert pushes[-3].end_bar < pushes[-2].end_bar < pushes[-1].end_bar
    assert all(p.direction == "down" for p in pushes[-3:])
```

- [ ] **Step 3: Implement versioned causal pivots and raw push features**

Store start/end swing, bar count, raw/ATR-normalized distance, bounce retracement, overlap summary, and duration. Do not produce a wedge label here.

- [ ] **Step 4: Verify and commit**

Commit: `feat: add causal swing and push extraction`.

---

### PAL-004: Broad Wedge Bull Flag candidate detector

**Files:**
- Create: `projects/price-action-lab/config/detector.yaml`
- Create: `projects/price-action-lab/src/price_action/wedges.py`
- Create: `projects/price-action-lab/tests/test_wedges.py`
- Create: `projects/price-action-lab/data/fixtures/wedge_candidate_synthetic.csv`
- Create: `projects/price-action-lab/data/fixtures/deep_pullback_synthetic.csv`

**Interfaces:**
- `DetectorConfig`, `WedgeCandidate`.
- `detect_wedge_bull_flag_candidates(frame, dataset_metadata, config) -> list[WedgeCandidate]`.
- Candidate fields include `candidate_id`, `kind`, `detector_version`, `dataset_version`, `symbol`, `decision_bar`, `setup_start`, `setup_end`, push references, and immutable feature snapshot.

- [ ] **Step 1: Create skeleton and write broad-detector RED**

The synthetic three-push bull-context fixture emits one `WEDGE_BULL_FLAG_CANDIDATE`; a 70% pullback fails the default 20–65% pullback gate.

- [ ] **Step 2: Write future-invariance RED**

Append extreme future bars after the decision bar and assert candidate identity and stored feature snapshot remain unchanged.

- [ ] **Step 3: Implement detector v0.1**

Defaults: positive EMA20 slope; configurable majority of pre-pullback closes above EMA20; pullback 20%–65% of preceding upswing; at least three down pushes; final push within 1 ATR of EMA20; setup duration 10–60 bars. These are configurable research hypotheses, not canonical Brooks claims.

- [ ] **Step 4: Verify and commit**

Commit: `feat: add broad Wedge Bull Flag candidate detector`.

---

### PAL-005: Label model and future-safe chart payloads

**Files:**
- Create: `projects/price-action-lab/src/price_action/labeling.py`
- Create: `projects/price-action-lab/src/price_action/charts.py`
- Create: `projects/price-action-lab/tests/test_labeling.py`
- Create: `projects/price-action-lab/tests/test_charts.py`

**Interfaces:**
- `PatternLabel = YES|NO|UNCERTAIN`, `LabelRecord`, `LabelStore`.
- `build_labeling_chart_payload(frame, candidate, pre_context_bars)`.
- `build_review_chart_payload(frame, candidate, label, post_bars)`.

- [ ] **Step 1: Write label RED**

Require candidate ID, detector version, label, annotator, timestamp; reasons are structured and free text is optional. Deterministic feature records are referenced by ID/version and not mutable through labels.

- [ ] **Step 2: Write future-hiding RED**

Labeling payload max timestamp must be `<= candidate.decision_bar`. Review payload may include post bars only when supplied a committed label record.

- [ ] **Step 3: Implement JSONL single-user persistence with atomic replacement**

Duplicate labels for the same `(candidate_id, annotator)` replace only that annotator's prior label atomically while retaining audit timestamp history in an adjacent event log.

- [ ] **Step 4: Verify and commit**

Commit: `feat: add auditable labeling and chart payloads`.

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

**Interfaces:** candidate queue input, labeling payload display, label-save adapter, and post-commit review payload retrieval.

- [ ] **Step 1: Write UI RED for hidden future bars**

Mock a pre-label payload and assert no outcome/post-setup series is requested or rendered before a successful label save.

- [ ] **Step 2: Write label-submission RED**

Selecting `YES` plus `valid wedge structure` submits candidate ID, detector version, label, reasons, and annotator exactly once.

- [ ] **Step 3: Implement minimal research UI**

Render candlesticks, EMA20, marked pushes, deterministic feature summary, YES/NO/UNCERTAIN controls, structured reasons, progress and label counts. No ranking, broker controls, live scanner, or trade recommendation.

- [ ] **Step 4: Verify and commit**

Run `npm test -- --run` and `npm run build`.  
Commit: `feat: add Wedge candidate labeling interface`.

---

### PAL-007: Forward outcomes, MFE, MAE, and threshold events

**Files:**
- Create: `projects/price-action-lab/src/price_action/outcomes.py`
- Create: `projects/price-action-lab/tests/test_outcomes.py`

**Interfaces:**
- `OutcomeRecord`.
- `measure_outcomes(frame, candidate, horizons=(5, 10, 20)) -> OutcomeRecord`.

- [ ] **Step 1: Write exact synthetic MFE/MAE RED**

For decision close 100 and decision ATR 2, hand-construct future highs/lows so MFE, MAE, +1 ATR-before--1 ATR and +2 ATR-before--1 ATR have exact expected values.

- [ ] **Step 2: Assert decision-bar exclusion and insufficient horizon behavior**

Decision bar cannot count toward outcome extrema. A horizon extending past available data returns an explicit unavailable marker rather than a shortened statistic.

- [ ] **Step 3: Implement outcomes and verify**

Also compute forward close returns at 5/10/20 bars, setup-low break, and new qualifying swing high using only bars strictly after decision bar.

- [ ] **Step 4: Commit**

Commit: `feat: add leakage-safe Wedge outcome measurements`.

---

### PAL-008: Experiment registry and detector comparison

**Files:**
- Create: `projects/price-action-lab/src/price_action/experiments.py`
- Create: `projects/price-action-lab/tests/test_experiments.py`
- Create: `projects/price-action-lab/experiments/EXP-001.yaml`

**Interfaces:**
- `ExperimentDefinition`, `ExperimentResult`, `ExperimentDecision`.
- `load_experiment(path)`, `compare_detector_versions(...)`, `write_experiment_result(...)`.

- [ ] **Step 1: Write experiment-schema RED**

Require `EXP-<digits>`, hypothesis, baseline detector version, one primary rule change unless `interaction_effect=true`, dataset version/date range, partition declaration, candidate count, and decision in `RETAIN|REJECT|REVISE`.

- [ ] **Step 2: Write preservation RED**

A new experiment/revision must not delete or overwrite a previously rejected experiment result.

- [ ] **Step 3: Implement comparison metrics**

When labels exist, publish sample count, YES precision, recall against the labeled candidate universe where defined, NO false-positive rate, and UNCERTAIN count separately. Keep outcome metrics separate from pattern-label quality metrics.

- [ ] **Step 4: Verify and commit**

Commit: `feat: add auditable Price Action experiment registry`.

---

### PAL-009: Train/validation/OOS enforcement

**Files:**
- Create: `projects/price-action-lab/src/price_action/validation.py`
- Create: `projects/price-action-lab/tests/test_validation.py`

**Interfaces:**
- `ResearchSplit`.
- `assign_partition(timestamp, split)`.
- `freeze_detector_cycle(config, dataset_metadata) -> FrozenDetector`.
- `evaluate_frozen_detector(frozen, dataset, labels) -> EvaluationResult`.

- [ ] **Step 1: Write non-overlap RED**

Reject overlapping train/validation/OOS ranges, gaps that make an evaluated timestamp unassignable, and split definitions with non-monotonic boundaries.

- [ ] **Step 2: Write frozen-OOS RED**

After freezing, evaluation refuses a detector config hash/version or dataset version different from the frozen record.

- [ ] **Step 3: Implement partition/evaluation enforcement**

Always report ES and NQ separately; optional calendar/regime slices require an explicit minimum sample count configured before evaluation.

- [ ] **Step 4: Verify and commit**

Commit: `feat: enforce Price Action out-of-sample validation`.

---

### PAL-010: End-to-end research runner and first candidate batch

**Files:**
- Create: `projects/price-action-lab/src/price_action/runner.py`
- Create: `projects/price-action-lab/src/price_action/reporting.py`
- Create: `projects/price-action-lab/tests/test_runner.py`
- Create: `projects/price-action-lab/reports/.gitkeep`
- Create: `projects/price-action-lab/README.md`

**Interfaces:** CLI commands `price-action ingest`, `price-action scan`, `price-action label-export`, `price-action outcomes`, `price-action experiment`, and `price-action report`.

- [ ] **Step 1: Write fixture-only end-to-end RED**

Synthetic ES fixture → canonical dataset → causal features → candidate → future-safe labeling payload → label → outcome → EXP result → research summary. Every artifact must retain dataset and detector versions.

- [ ] **Step 2: Implement orchestration and verify fixture E2E**

The automated test suite requires no network and no proprietary data.

- [ ] **Step 3: Run global verification**

Run Python pytest/Ruff/mypy, web Vitest/build, `git diff --check`, and a changed-path assertion that rejects any `projects/cot-radar/` modification.

- [ ] **Step 4: Produce the first real unlabeled candidate batch when local ES/NQ CSV is available**

Ingest the declared local dataset, run frozen detector v0.1, export only non-restricted candidate metadata and pre-label chart payloads, and do not reveal or precompute outcome data in the labeling queue.

- [ ] **Step 5: Commit**

Commit: `feat: complete Price Action Lab MVP research loop`.

---

## Global Completion Gate

Final audit requires PAL-001 through PAL-010 green; leakage regressions green; no Price Action task changed COT Radar source; pre-label UI hides future bars; experiment results preserve failed hypotheses; train/validation/OOS enforcement is active; and a first unlabeled ES/NQ Wedge Bull Flag candidate batch can be produced from an explicitly versioned local dataset without publishing restricted raw bars.
