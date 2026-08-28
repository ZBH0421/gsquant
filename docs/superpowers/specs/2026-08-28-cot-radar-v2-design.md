# COT Radar V2 Design

## Goal

Improve the existing ES/NQ COT Radar without changing its core market scope or research philosophy. V2 must make data freshness, deterministic ES/NQ comparison, state transitions, backtest limitations, and derived downloads auditable from the public site.

## Invariants

- Markets remain ES and NQ only.
- CFTC source remains TFF Futures Only dataset `gpe5-46if`.
- Leveraged Funds are the primary crowding signal; Asset Managers are the comparison cohort.
- Dealer and Other Reportables remain objective context only.
- SPY/QQQ remain clearly labeled price proxies, never ES/NQ settlement prices.
- Facts, rule classification, inference, alternatives, confirmation, and invalidation remain separated.
- No runtime LLM and no direct trading advice.
- All historical percentile/statistical calculations remain prior-only.
- CFTC report calendar dates are rendered without timezone drift.
- No secrets are committed.

## Architecture

Keep the current pipeline and static React/Vite deployment. Add deterministic metadata and comparison objects to the derived artifacts so the frontend only renders rules that are already computed in Python. Centralize all state-machine and comparison thresholds in `settings.yaml` and `RadarSettings`.

### Freshness model

The pipeline emits, in both `status.json` and the dashboard payload:

- `latest_report_date`: Tuesday position date.
- `scheduled_release_at`: normal Friday 15:30 America/New_York availability for that report.
- `fetched_at`: current pipeline retrieval timestamp.
- `last_successful_update_at`: same timestamp for a successful atomic artifact publication.
- `next_scheduled_update_at`: next Saturday 08:00 Asia/Taipei workflow expectation.
- `cftc_dataset` and `price_provider`.
- `publication_state`: `current`, `waiting_for_cftc`, or `stale`.
- `warning`: human-readable warning or null.

`waiting_for_cftc` is used when the normal scheduled release for the next Tuesday report has not yet passed. `stale` is reserved for data that should have been published already but is older than the configured grace window. GitHub Actions continues to publish only after the complete pipeline succeeds, so failed runs leave the prior successful static artifacts intact.

### ES/NQ comparison

A deterministic `comparison` object is generated from the latest ES/NQ rows. It contains each market's Leveraged Funds net/OI, Asset Manager net/OI, prior-only percentile, 1-week and 4-week position changes, 4-week price momentum, price-vs-10-week-SMA spread, and state. It also emits:

- `synchronized_crowding`: both markets are simultaneously above the high threshold or below the low threshold.
- `position_divergence`: true when the absolute percentile gap is at least the configured divergence threshold.
- `more_extreme_market`: market whose percentile is farther from 50.
- `evidence`: formula-backed statement with numeric values.
- `falsification`: exact condition that makes the divergence flag false.

### State machine

The seven existing states remain. Entry/hold/exit rules are exposed in `methodology.state_machine` and are driven only by config:

- `NORMAL`: no active extreme/unwind memory.
- `EXTREME_LONG` / `EXTREME_SHORT`: percentile at or beyond 90/10; remain while threshold is still met.
- `UNWINDING_LONG` / `UNWINDING_SHORT`: recent extreme memory plus position change in the unwind direction; remain while memory is live and unwind direction persists.
- `CONFIRMED_BEARISH` / `CONFIRMED_BULLISH`: unwind state plus price below/above 10-week SMA and 4-week momentum negative/positive after configured confirmation delay. Hold while confirmation remains true and memory is live.
- Exit to `NORMAL` when memory expires, unwind direction reverses, or confirmation/hold conditions fail without a renewed extreme.

The config owns all thresholds, including divergence gap, confirmation delay, and minimum backtest sample size.

### Backtest credibility

Backtest events continue to start from normal scheduled availability and never from the Tuesday report date. Summary rows include horizon, sample count, median return, reversal win rate, median maximum adverse excursion, direction, market, statistical period, and proxy source. Win rate is set to null when the sample count is below the configured minimum and a `small_sample` flag is emitted.

The frontend states the normal Tuesday/Friday publication convention, the un-reconstructed historical-delay limitation, proxy source, and non-predictive nature of the results.

### Frontend

Preserve the existing dark Traditional Chinese research UI. Add a top data-status panel, ES/NQ comparison table and divergence evidence chain, visible extreme bands/state transition markers in history charts, state-rule methodology table, small-sample warnings, CFTC/source links, and links to derived CSV/JSON downloads. No raw price history is republished.

## Verification

Required gates: Python tests, Ruff, mypy, frontend tests, TypeScript/Vite production build, `git diff --check`, PR CI, Pages deployment, live HTTP verification, live asset/version verification, public `status.json` consistency, and an Asia/Taipei report-date regression test.