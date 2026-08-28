# Credit Stress / Reversal Radar Design

## Goal
Build a traceable research dashboard that classifies US credit stress, detects stabilization/reversal, and checks whether equity price confirms the credit signal. It is not a trading signal generator and must never emit buy/sell advice.

## Scope
V1 lives in `projects/credit-radar` beside `projects/cot-radar` and reuses the repository's Python/React/GitHub Pages patterns without changing COT Radar behavior.

### Public data
- HY credit: FRED `BAMLH0A0HYM2` (ICE BofA US High Yield Index OAS)
- IG credit: FRED `BAMLC0A0CM` (ICE BofA US Corporate Index OAS)
- Equity volatility: FRED `VIXCLS`
- Equity proxies: weekly SPY for ES and QQQ for NQ, primarily from Stooq with the proxy label shown everywhere.

FRED now limits the public ICE BofA OAS history to roughly three years. V1 therefore uses a configurable 3-year prior-only percentile (756 trading observations) and explicitly reports the available history. The provider interface must permit a longer licensed/history source later without changing analytics or the UI contract.

## Core research rules
### Prior-only percentile
For observation `t`, percentile rank uses observations strictly before `t`. Current data must never contribute to its own reference distribution and future data must never enter the calculation.

Default parameters:
- percentile lookback: 756 trading observations
- minimum history: 252 observations
- stressed percentile: 85
- extreme-stress percentile: 95
- deteriorating percentile: 70
- spread trend: 50 trading-day SMA
- short change: 5 trading days
- medium change: 20 trading days
- price trend: 10 weekly observations
- price momentum: 4 weekly observations
- HY/IG divergence threshold: 20 percentile points
- credit/VIX divergence threshold: 20 percentile points
- minimum backtest sample for win-rate display: 10

## Credit state machine
States are deterministic and derived in Python:

1. `NORMAL`: no active stress condition.
2. `DETERIORATING`: HY percentile >= 70, HY spread > SMA50, and 20D change > 0.
3. `STRESSED`: HY percentile >= 85.
4. `EXTREME_STRESS`: HY percentile >= 95.
5. `STABILIZING`: a recent stressed/extreme episode remains in memory, HY is no longer making a 20D high, and 20D change is falling versus the previous observation.
6. `CREDIT_REVERSAL`: recent stressed/extreme episode remains in memory, HY spread < SMA50 and 20D change < 0.
7. `CONFIRMED_RISK_ON`: credit reversal is active and at least one equity proxy has positive 4W momentum and is above its 10W SMA. Both ES/SPY and NQ/QQQ confirmations are shown separately.

State precedence is `EXTREME_STRESS` > `STRESSED` > `DETERIORATING` > `CONFIRMED_RISK_ON` > `CREDIT_REVERSAL` > `STABILIZING` > `NORMAL`. Stress-memory defaults to 60 trading days and expires automatically.

## Cross-asset evidence
The dashboard must present facts separately from interpretation:
- HY percentile and trend
- IG percentile and trend
- HY minus IG percentile gap
- VIX percentile
- HY minus VIX percentile gap
- ES/SPY and NQ/QQQ 4W momentum and 10W SMA confirmation

Derived labels:
- `HY_SPECIFIC_STRESS` when HY percentile - IG percentile >= threshold
- `SYSTEMIC_CREDIT_STRESS` when both HY and IG percentiles >= stressed threshold
- `CREDIT_LEADS_VOL` when HY percentile - VIX percentile >= threshold
- `VOL_LEADS_CREDIT` when VIX percentile - HY percentile >= threshold

Every label exports its formula, threshold, evidence, and falsification condition.

## Backtest / event study
For state transitions into `STRESSED`, `EXTREME_STRESS`, `CREDIT_REVERSAL`, and `CONFIRMED_RISK_ON`, compute SPY/QQQ forward returns at 1/4/8/13/26 weeks, sample size, median return, positive-return rate, maximum adverse excursion, and maximum favorable excursion. Small samples suppress the positive-return rate and carry a warning. Results must state proxy source, sample period, and that historical results do not imply future performance.

## Data freshness and provenance
`status.json` and the dashboard payload expose:
- generated timestamp in UTC
- last successful fetch timestamp
- latest observation date for HY, IG, VIX, SPY, QQQ
- provider and source URL/series ID for every input
- available history start/end
- stale flag and warning
- explicit SPY/QQQ proxy wording

If a scheduled refresh fails, deployment keeps the last validated artifacts and surfaces a visible warning rather than publishing partial/corrupt data.

## Artifacts
Python owns all analytics and exports:
- `data/derived/dashboard.json`
- `data/derived/history.json`
- `data/derived/backtest.json`
- `data/derived/credit_state.csv`
- `data/derived/status.json`

The same JSON files are copied to `web/public/data/`. Frontend code only renders these outputs; it does not recalculate states or thresholds.

## Frontend
Dark Traditional Chinese dashboard with:
1. current regime and freshness
2. HY/IG/VIX fact cards
3. confirmation/invalidation checklist for SPY/QQQ
4. deterministic cross-asset divergence evidence
5. state history / transitions
6. historical event-study table
7. methodology, formulas, limitations, source links, and derived-data downloads

Responsive mobile layout is required. No runtime LLM.

## Engineering constraints
- Python 3.11, pandas, gs-quant pinned by root project, httpx, PyYAML.
- React/Vite/TypeScript frontend.
- Tests first for each behavior.
- Ruff and strict mypy for Python; Vitest, TypeScript build, and Vite build for web.
- GitHub Actions runs COT and Credit checks independently.
- GitHub Pages publishes both `/cot-radar/` and `/credit-radar/`.
- No secrets required for FRED/Stooq V1.
- Dates are calendar-safe and never shifted by Asia/Taipei rendering.
