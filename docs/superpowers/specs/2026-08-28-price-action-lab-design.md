# Price Action Research Lab — Design Specification

**Date:** 2026-08-28  
**Repository:** `ZBH0421/gsquant`  
**Project:** `projects/price-action-lab`

## 1. Product goal

Build a reproducible research platform for translating selected Al Brooks price-action concepts into measurable, testable hypotheses. The first research target is the **Wedge Bull Flag** on ES and NQ 5-minute regular trading hours. The product is a research and training system, not an automated trading bot and not a claim that subjective price-action concepts can be perfectly reduced to fixed rules.

The platform must separate four layers:

1. deterministic market facts and features;
2. broad machine-generated candidates;
3. human Brooks-style labels and reasons;
4. historical outcome statistics and experiment decisions.

The first release succeeds when it can reliably surface useful Wedge Bull Flag candidates for human review and preserve the evidence needed to refine the definition over repeated experiments.

## 2. MVP scope

The first release covers:

- Markets: ES and NQ.
- Timeframe: 5-minute bars.
- Session: US regular trading hours only.
- First pattern family: Wedge Bull Flag.
- Context features: EMA20, ATR, trend structure, pullback depth, overlap, push count, push compression, swing structure, and signal-bar characteristics.
- Human labels: `YES`, `NO`, `UNCERTAIN` plus optional rejection/acceptance reasons.
- Forward outcome measurements: MFE, MAE, +1 ATR / +2 ATR reach, setup-low failure, new swing high, and fixed forward horizons.
- Experiment registry with versioned hypotheses and one-axis-at-a-time rule changes.
- Out-of-sample evaluation after exploratory rule development.
- A lightweight browser interface for reviewing chart candidates and recording labels.

The MVP excludes live execution, broker integration, automated order placement, runtime LLM trade recommendations, and attempting to cover the full Al Brooks taxonomy.

## 3. Research principle

The system must not treat a machine rule as ground truth simply because it fires. The first detector is intentionally broad and emits `WEDGE_BULL_FLAG_CANDIDATE`, not `WEDGE_BULL_FLAG_CONFIRMED`.

The research loop is:

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
→ retain / reject / revise
```

Only one primary rule axis should be changed per experiment unless the experiment explicitly states that it is testing an interaction effect.

## 4. Data architecture

Raw historical data is provider-agnostic. The initial ingestion path supports local CSV exports so research is not blocked by a particular paid vendor. Future providers may be added behind the same interface.

Canonical bar schema:

- `timestamp`
- `symbol`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `session`

The source adapter normalizes timestamps to an explicit timezone, removes or marks duplicate bars, validates monotonic chronology, and classifies regular-trading-hours bars deterministically.

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

The Price Action Lab remains isolated from `projects/cot-radar/`. Root-level files should be modified only when required for shared dependency or CI support and should be kept to the smallest possible change to reduce conflicts with concurrent COT work.

## 6. Base feature model

### Bar geometry

For every bar, derive at least:

- total range;
- body size;
- upper-tail size;
- lower-tail size;
- body/range ratio;
- close location within range;
- bull / bear / doji classification;
- overlap with the prior bar;
- ATR-normalized range.

### Trend/location

Derive at least:

- EMA20;
- EMA20 slope over configurable lookback;
- ATR;
- close distance from EMA20 in ATR units;
- fraction of recent closes above EMA20;
- recent higher-high / higher-low and lower-high / lower-low structure;
- rolling overlap ratio.

All features must be computed using information available at or before the bar being classified. Lookahead is forbidden.

## 7. Swing and push model

A pivot detector converts bars into candidate swing highs and lows using a configurable, causal rule. The implementation must make the pivot rule explicit and versioned because the definition of a Brooks-style "push" is a central research variable.

A downward push contains at least:

- start swing high;
- end swing low;
- bar count;
- price distance;
- ATR-normalized distance;
- retracement from the previous push/bounce;
- overlap statistics;
- time duration.

A three-push structure is a sequence of at least three distinct downward pushes separated by qualifying bounces. The detector must expose the raw push features rather than collapsing them immediately into a binary wedge decision.

## 8. Broad Wedge Bull Flag candidate detector

The initial detector is intentionally permissive. Version 0.1 uses configurable conditions approximately equivalent to:

- prior bull context: positive EMA20 slope and price predominantly above EMA20 before the pullback;
- pullback depth within a broad configurable range, initially 20%–65% of the preceding upswing;
- at least three detected downward pushes;
- final push ending within a configurable distance of EMA20, initially 1 ATR;
- total setup duration within a broad configurable range, initially 10–60 bars.

These thresholds are starting hypotheses, not claims about the canonical Brooks definition.

Each candidate stores its detector version and complete feature snapshot so later rule versions can be compared without ambiguity.

## 9. Human labeling

The labeling interface displays a bounded chart window containing sufficient pre-context, the setup region, and a limited post-setup window when appropriate for review tasks that allow it. Pattern-labeling mode must avoid revealing future outcome data before the user records the pattern label.

Allowed pattern labels:

- `YES`
- `NO`
- `UNCERTAIN`

Optional structured reasons include:

- not three distinct pushes;
- prior trend too weak;
- trading-range context;
- pullback too deep;
- EMA context inappropriate;
- push structure poor;
- signal bar poor;
- valid wedge structure;
- other free-text note.

Each label records candidate ID, detector version, label, reasons, timestamp, and annotator identity. Human labels never overwrite deterministic features.

## 10. Outcome engine

Pattern quality and trade profitability are separate research questions. Before defining a specific trading strategy, the system measures market response after each labeled/candidate setup.

Required forward metrics include:

- forward close return at 5, 10, and 20 bars;
- maximum favorable excursion in ATR units;
- maximum adverse excursion in ATR units;
- whether +1 ATR is reached before -1 ATR;
- whether +2 ATR is reached before -1 ATR;
- whether price breaks below setup low;
- whether price makes a new qualifying swing high.

Outcome windows begin only after the candidate's decision bar so classification features cannot use future bars.

## 11. Experiment registry

Every hypothesis is stored as a versioned experiment under `experiments/` with at least:

- experiment ID;
- hypothesis statement;
- baseline detector version;
- single primary parameter/rule change;
- dataset version and date range;
- train / validation / out-of-sample partition;
- candidate count;
- human-label precision/recall metrics when labels exist;
- outcome metrics;
- decision: `RETAIN`, `REJECT`, or `REVISE`;
- rationale and known limitations.

Example research sequence:

```text
PA-001 pivot definition
PA-002 three-push separation
PA-003 broad wedge candidate detector
PA-004 EMA-distance hypothesis
PA-005 pullback-depth hypothesis
PA-006 push-compression hypothesis
PA-007 signal-bar features
```

The registry must preserve rejected experiments. Failed hypotheses are research results, not files to delete.

## 12. Validation strategy

Exploratory rule development uses a declared training period. Parameter decisions are checked on a separate validation period. A final untouched out-of-sample period is evaluated only after a detector version is frozen for that cycle.

Results must be reported separately for:

- ES;
- NQ;
- calendar/regime slices where sample size permits.

Metrics must always show sample count. Small samples must be identified rather than extrapolated.

The platform must not optimize exclusively for P&L or Sharpe during the pattern-definition phase. Initial detector quality is assessed primarily against human labels and the stability of the discovered feature relationships.

## 13. Web experience

The first web interface is a research labeling tool, not a trading dashboard. It must support:

- candidate queue;
- candlestick chart with EMA20 and marked pushes;
- deterministic feature summary;
- `YES / NO / UNCERTAIN` controls;
- structured reason selection;
- progress and label counts;
- later review of labeled examples;
- experiment summary views once outcome analysis exists.

Future scanner views may rank recent candidates only after the historical research pipeline is working reliably.

## 14. Testing and leakage controls

Required automated coverage includes:

- ingestion schema and chronology validation;
- RTH session filtering;
- EMA/ATR calculations;
- causal swing/pivot behavior;
- deterministic push extraction;
- candidate reproducibility from fixed fixtures;
- no future-bar access during candidate feature generation;
- label schema validation;
- MFE/MAE and threshold-event calculations;
- train/validation/OOS partition integrity;
- experiment serialization and comparison.

Fixtures should include hand-constructed edge cases for three-push structures, trading ranges, deep pullbacks, missing bars, duplicate timestamps, and candidates near EMA20.

## 15. Concurrency with COT Radar

Price Action Lab and COT Radar may be developed concurrently because their project directories are isolated. Price Action tasks should use separate Git branches/worktrees. Root dependency files and `.github/workflows/` are shared collision points; tasks should avoid them unless necessary and rebase before publication when concurrent changes occur.

No Price Action task may modify COT Radar source files.

## 16. Agent workflow

The intended development control model is:

- ChatGPT: architecture, task decomposition, acceptance criteria, evidence review, final audit, and experiment-control decisions.
- Codex: source/test implementation within declared task scope.
- GitHub: source of truth for specs, plans, Issues, branches, PRs, CI, and durable research decisions.

Implementation tasks follow test-first development. A task should be small enough to produce one independently reviewable and testable deliverable.

The current ChatGPT environment can operate GitHub but does not itself expose a direct Codex execution-session control endpoint. Until the orchestrator/runtime path is available, GitHub tasks and plans can be prepared here while code execution must be launched through an available Codex environment.

## 17. Initial implementation task sequence

The first engineering cycle is decomposed into:

1. `PA-001` — project skeleton, canonical bar model, and CSV ingestion;
2. `PA-002` — bar geometry, EMA20, ATR, and causal feature primitives;
3. `PA-003` — swing pivots and directional push extraction;
4. `PA-004` — broad Wedge Bull Flag candidate detector;
5. `PA-005` — deterministic chart payloads and labeling data model;
6. `PA-006` — browser labeling UI;
7. `PA-007` — forward outcome, MFE, and MAE engine;
8. `PA-008` — experiment registry and detector-version comparison;
9. `PA-009` — train/validation/out-of-sample evaluation pipeline;
10. `PA-010` — research summary/reporting and first end-to-end validation run.

## 18. MVP acceptance criteria

The MVP is complete only when:

- ES/NQ 5-minute CSV data can be normalized into the canonical schema and restricted to RTH;
- causal bar, indicator, swing, push, and context features are reproducible from tests;
- the detector generates versioned Wedge Bull Flag candidates without using future bars;
- candidates can be reviewed in a browser and labeled `YES / NO / UNCERTAIN` with reasons;
- labels and deterministic features remain separate and auditable;
- forward outcome and MFE/MAE statistics can be generated without leakage;
- experiments preserve hypotheses, dataset/version information, results, and retain/reject/revise decisions;
- train/validation/OOS splits are enforced;
- tests pass for all leakage-critical and structural behaviors;
- COT Radar source code is untouched by Price Action tasks;
- the first labeled candidate batch is ready for human Brooks-style review.

## 19. Deferred work

Only after the Wedge Bull Flag research loop is demonstrably useful should the framework expand to H2/L2, Failed Breakout, Double Bottom/Top, Major Trend Reversal, other timeframes, live scanning, ranking models, or vision/ML-assisted classification.
