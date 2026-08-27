# Price Action Research Lab — Design Specification

**Date:** 2026-08-28  
**Repository:** `ZBH0421/gsquant`  
**Project:** `projects/price-action-lab`

## 1. Product goal

Build a reproducible research platform for translating selected Al Brooks price-action concepts into measurable, testable hypotheses. The first research target is the **Wedge Bull Flag** on ES and NQ 5-minute regular trading hours. The product is a research and training system, not an automated trading bot and not a claim that subjective price-action concepts can be perfectly reduced to fixed rules.

The platform separates four layers: deterministic market facts/features; broad machine-generated candidates; human Brooks-style labels/reasons; and historical outcome statistics/experiment decisions. The first release succeeds when it can surface useful Wedge Bull Flag candidates for human review and preserve the evidence needed to refine the definition over repeated experiments.

## 2. MVP scope

The first release covers:

- Markets: ES and NQ.
- Timeframe: 5-minute bars.
- Session: US equity-index RTH, **09:30–16:00 America/New_York**, using exchange-local timestamps after normalization.
- First pattern family: Wedge Bull Flag.
- Context features: EMA20, ATR, trend structure, pullback depth, overlap, push count, push compression, swing structure, and signal-bar characteristics.
- Human labels: `YES`, `NO`, `UNCERTAIN` plus optional rejection/acceptance reasons.
- Forward outcome measurements: MFE, MAE, +1 ATR / +2 ATR reach, setup-low failure, new swing high, and fixed forward horizons.
- Experiment registry with versioned hypotheses and one-axis-at-a-time rule changes.
- Out-of-sample evaluation after exploratory rule development.
- A lightweight browser interface for reviewing chart candidates and recording labels.

The MVP excludes live execution, broker integration, automated order placement, runtime LLM trade recommendations, and the full Al Brooks taxonomy.

## 3. Research principle

A machine rule is never ground truth merely because it fires. The first detector is intentionally broad and emits `WEDGE_BULL_FLAG_CANDIDATE`, not `WEDGE_BULL_FLAG_CONFIRMED`.

```text
Observation
→ measurable hypothesis
→ deterministic candidate rule
→ candidate set
→ human labels
→ feature comparison
→ revised hypothesis
→ historical outcome analysis
→ out-of-sample validation
→ RETAIN / REJECT / REVISE
```

Only one primary rule axis changes per experiment unless the experiment explicitly tests an interaction effect.

## 4. Data architecture

Raw historical data is provider-agnostic. The initial ingestion path supports local CSV exports so research is not blocked by a particular paid vendor. Future providers may be added behind the same interface.

Canonical bar schema:

- `timestamp`
- `symbol`
- `contract` (optional when the source is already a continuous series)
- `open`
- `high`
- `low`
- `close`
- `volume`
- `session`
- `source`

The source adapter normalizes timestamps to `America/New_York`, validates monotonic chronology, rejects ambiguous duplicate bars unless an explicit deterministic resolution rule is configured, and marks RTH using 09:30 inclusive through 16:00 exclusive bar-start timestamps.

For futures contract data, roll/continuous-series policy must be explicit in dataset metadata. Detector experiments may not silently mix incompatible roll conventions. Roll-adjacent observations can be flagged and excluded in sensitivity checks.

Raw licensed market data must not be committed to Git. Small synthetic or redistribution-safe fixtures may be committed for tests. Derived research artifacts may be versioned when they do not redistribute restricted source data.

## 5. Repository architecture

```text
projects/price-action-lab/
├── config/
│   ├── markets.yaml
│   └── detector.yaml
├── data/
│   ├── raw/                 # gitignored source files
│   ├── processed/           # local normalized bars
│   └── fixtures/            # tiny test fixtures only
├── src/price_action/
│   ├── models.py            # typed canonical data/research models
│   ├── ingestion.py         # provider-agnostic loaders and normalization
│   ├── bars.py              # per-bar geometric features
│   ├── indicators.py        # EMA/ATR and rolling deterministic features
│   ├── swings.py            # pivot and swing extraction
│   ├── pushes.py            # directional push representation
│   ├── context.py           # trend/pullback/location/context features
│   ├── wedges.py            # broad Wedge Bull Flag candidate detector
│   ├── outcomes.py          # forward-return, MFE/MAE and event outcomes
│   ├── experiments.py       # experiment definitions and comparison
│   ├── labeling.py          # label persistence and validation
│   └── charts.py            # deterministic chart payload/render helpers
├── tests/
├── experiments/
├── labels/
├── reports/
└── web/
    ├── src/
    └── tests/
```

Price Action Lab remains isolated from `projects/cot-radar/`. Root-level files are modified only when required for shared dependency or CI support and must be kept to the smallest possible change to reduce conflicts with concurrent COT work.

## 6. Base feature model

### Bar geometry

For every bar derive at least total range, body size, upper/lower tail size, body/range ratio, close location within range, bull/bear/doji classification, overlap with the prior bar, and ATR-normalized range.

### Trend/location

Derive at least EMA20, configurable EMA20 slope, ATR, close distance from EMA20 in ATR units, fraction of recent closes above EMA20, recent HH/HL/LH/LL structure, and rolling overlap ratio.

All classification features use only information available at or before the decision bar. Lookahead is forbidden.

## 7. Swing and push model

A pivot detector converts bars into candidate swing highs/lows using a configurable **causal** rule. The pivot rule is explicit and versioned because the definition of a Brooks-style push is a central research variable.

A downward push stores at least start swing high, end swing low, bar count, price distance, ATR-normalized distance, retracement from the prior push/bounce, overlap statistics, and duration.

A three-push structure is at least three distinct downward pushes separated by qualifying bounces. Raw push features remain exposed rather than being collapsed immediately into a binary wedge decision.

## 8. Broad Wedge Bull Flag candidate detector

Detector v0.1 is intentionally permissive and uses configurable starting hypotheses:

- prior bull context: positive EMA20 slope and price predominantly above EMA20 before the pullback;
- pullback depth initially 20%–65% of the preceding upswing;
- at least three detected downward pushes;
- final push ending within initially 1 ATR of EMA20;
- total setup duration initially 10–60 bars.

These values are research starting points, not claims about a canonical Brooks definition. Every candidate stores detector version, dataset version, decision bar, setup bounds, and its complete feature snapshot.

## 9. Human labeling

Pattern-labeling mode displays sufficient **pre-context and setup bars only** before the user records the label; future outcome bars must not be visible. After a label is committed, a separate review mode may reveal later bars.

Allowed labels are `YES`, `NO`, and `UNCERTAIN`. Optional reasons include: not three distinct pushes; prior trend too weak; trading-range context; pullback too deep; EMA context inappropriate; push structure poor; signal bar poor; valid wedge structure; and free-text note.

Each label records candidate ID, detector version, label, reasons, timestamp, and annotator identity. Human labels never overwrite deterministic features.

## 10. Outcome engine

Pattern quality and trade profitability are separate questions. Before defining a trading strategy, measure:

- forward close return at 5, 10, and 20 bars;
- MFE and MAE in ATR units;
- +1 ATR before -1 ATR;
- +2 ATR before -1 ATR;
- break below setup low;
- new qualifying swing high.

Outcome windows begin after the candidate decision bar. Candidate classification code may not access outcome windows.

## 11. Experiment registry

Research experiments use IDs `EXP-001`, `EXP-002`, ... and contain: hypothesis; baseline detector version; one primary rule change; dataset version/date range; train/validation/OOS partition; candidate count; human-label metrics when available; outcome metrics; decision (`RETAIN`, `REJECT`, `REVISE`); rationale; limitations.

Example sequence:

```text
EXP-001 pivot definition
EXP-002 three-push separation
EXP-003 EMA-distance hypothesis
EXP-004 pullback-depth hypothesis
EXP-005 push-compression hypothesis
EXP-006 signal-bar features
```

Rejected experiments are retained as research results.

## 12. Validation strategy

Exploratory rule development uses a declared training period. Parameter decisions are checked on a separate validation period. A final untouched OOS period is evaluated only after a detector version is frozen for that cycle.

Report ES and NQ separately and calendar/regime slices only where sample size permits. Every statistic shows sample count. Small samples are identified rather than extrapolated.

The pattern-definition phase does not optimize exclusively for P&L or Sharpe. Detector quality is assessed primarily against human labels and stability of feature relationships.

## 13. Web experience

The first interface is a research labeling tool, not a trading dashboard. It supports candidate queue, candlestick chart with EMA20 and marked pushes, deterministic feature summary, `YES / NO / UNCERTAIN`, structured reasons, progress/label counts, review of labeled examples, and experiment summaries once outcome analysis exists.

## 14. Testing and leakage controls

Automated coverage includes ingestion schema/chronology, RTH filtering, EMA/ATR, causal pivot behavior, deterministic push extraction, fixed-fixture candidate reproducibility, no future-bar access during classification, label validation, MFE/MAE and threshold events, partition integrity, and experiment serialization/comparison.

Fixtures include hand-constructed three-push structures, trading ranges, deep pullbacks, missing bars, duplicate timestamps, and candidates near EMA20.

## 15. Concurrency with COT Radar

Price Action Lab and COT Radar may run concurrently because project directories are isolated. Price Action tasks use separate branches/worktrees. Root dependency files and `.github/workflows/` are shared collision points; tasks avoid them unless necessary and rebase before publication when concurrent changes occur.

No Price Action task may modify COT Radar source files.

## 16. Agent workflow

- ChatGPT: architecture, task decomposition, acceptance criteria, evidence review, final audit, and experiment-control decisions.
- Codex: source/test implementation within declared task scope.
- GitHub: source of truth for specs, plans, Issues, branches, PRs, CI, and durable research decisions.

Implementation follows test-first development. Each engineering task is independently reviewable and testable.

The current ChatGPT environment can operate GitHub but does not expose a direct Codex execution-session control endpoint. Until an orchestrator/runtime path is available, GitHub tasks/plans can be prepared here while code execution must be launched through an available Codex environment.

## 17. Initial engineering task sequence

Engineering tasks use IDs `PAL-001`, `PAL-002`, ... to avoid collision with research experiment IDs.

1. `PAL-001` — project skeleton, canonical bar model, CSV ingestion, RTH normalization, dataset metadata;
2. `PAL-002` — bar geometry, EMA20, ATR, causal feature primitives;
3. `PAL-003` — swing pivots and directional push extraction;
4. `PAL-004` — broad Wedge Bull Flag candidate detector;
5. `PAL-005` — deterministic chart payloads and labeling data model;
6. `PAL-006` — browser labeling UI;
7. `PAL-007` — forward outcome, MFE, MAE engine;
8. `PAL-008` — experiment registry and detector-version comparison;
9. `PAL-009` — train/validation/OOS evaluation pipeline;
10. `PAL-010` — research summary/reporting and first end-to-end validation run.

## 18. MVP acceptance criteria

The MVP is complete only when:

- ES/NQ 5-minute CSV data can be normalized into the canonical schema and RTH contract;
- dataset metadata records source and futures roll/continuous-series policy;
- causal bar, indicator, swing, push, and context features are reproducible from tests;
- detector candidates are versioned and generated without future bars;
- browser labeling hides future outcome data until after label commitment;
- labels and deterministic features remain separate/auditable;
- forward outcome and MFE/MAE statistics are generated without leakage;
- experiments preserve hypothesis, dataset/version, results, and decision;
- train/validation/OOS splits are enforced;
- leakage-critical and structural tests pass;
- COT Radar source code is untouched by Price Action tasks;
- the first labeled candidate batch is ready for human Brooks-style review.

## 19. Deferred work

Only after the Wedge Bull Flag loop is demonstrably useful should the framework expand to H2/L2, Failed Breakout, Double Bottom/Top, Major Trend Reversal, other timeframes, live scanning, ranking models, or vision/ML-assisted classification.
