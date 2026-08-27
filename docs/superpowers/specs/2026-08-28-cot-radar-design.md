# CFTC COT Positioning & Reversal Radar — Design Specification

**Date:** 2026-08-28  
**Repository:** `ZBH0421/gsquant`  
**Project:** `projects/cot-radar`

## 1. Product goal

Build a weekly ES/NQ research dashboard that turns CFTC positioning data into a traceable evidence chain. The product must separate observable facts, deterministic rule outcomes, market inferences, alternative explanations, and invalidation conditions. It is a crowding and reversal-risk research tool, not an intraday entry signal or automated trading system.

## 2. MVP scope

The first release covers:

- ES: E-mini S&P 500 positioning, with SPY as the price-confirmation proxy.
- NQ: E-mini Nasdaq-100 positioning, with QQQ as the price-confirmation proxy.
- CFTC Traders in Financial Futures, Futures Only.
- Leveraged Funds as the primary crowding series.
- Asset Manager/Institutional as the comparison series.
- Dealer/Intermediary, Other Reportables, and Non-reportable positions as supporting facts.
- Traditional Chinese interface with original English indicator names retained.
- Overview, ES detail, NQ detail, historical validation, methodology, and data-status views.
- Derived CSV and JSON downloads without redistribution of a complete raw price history.

The MVP excludes live prices, intraday signals, broker integration, order execution, runtime LLM-generated analysis, and markets other than ES/NQ.

## 3. Data sources and availability

### CFTC

Use the official CFTC Public Reporting Environment dataset `gpe5-46if` (TFF Futures Only). The adapter first resolves ES/NQ contracts from the dataset's market catalog using configured name patterns, then downloads only matching contract rows. Every row retains its report date, market name, contract code, and ingestion timestamp.

COT observations represent Tuesday positions and are normally released Friday. For historical analysis, `available_at` is conservatively assigned to Friday 15:30 America/New_York, three calendar days after the report date. The methodology page must disclose that holidays or exceptional CFTC delays can alter the actual release time.

### Price confirmation

Use Alpha Vantage `TIME_SERIES_WEEKLY` for SPY and QQQ when `ALPHA_VANTAGE_API_KEY` is available. A keyless Stooq weekly adapter is an operational fallback. The generated status file and interface must always identify the provider actually used and label SPY/QQQ as proxies rather than ES/NQ futures prices.

Only derived price information is published: current proxy close, 10-week moving average, four-week momentum, and a normalized chart series. Complete raw Alpha Vantage or Stooq price files are not included in downloads.

## 4. Repository architecture

```text
projects/cot-radar/
├── config/                 # Versioned market and signal settings
├── narratives/             # User-authored subjective notes
├── pipeline/
│   ├── src/cot_radar/      # Data adapters, analytics, states, narratives, export
│   └── tests/              # Unit, contract, and integration tests
├── data/derived/           # Versioned generated JSON/CSV outputs
└── web/
    ├── src/                # React dashboard
    ├── public/data/        # Copy of deployable derived outputs
    └── tests/              # Front-end tests
.github/workflows/          # CI, weekly refresh, and Pages deployment
docs/superpowers/           # Approved design and implementation plan
```

Python performs retrieval, validation, computation, and static artifact generation. React reads static JSON and therefore requires no always-on backend.

## 5. Metric definitions

For trader category `c` at week `t`:

- `net_c(t) = long_c(t) - short_c(t)`
- `net_pct_oi_c(t) = 100 × net_c(t) / open_interest(t)`
- `weekly_change_c(t) = net_pct_oi_c(t) - net_pct_oi_c(t-1)`
- `percentile_156(t)` is the percentile rank of the current value against only the preceding 156 observations, excluding the current observation.
- `zscore_156(t)` uses the mean and sample standard deviation of only the preceding 156 observations.
- A minimum of 52 prior observations is required before percentile and z-score values are emitted.

The implementation uses GS Quant for standard time-series operations such as differences and moving averages. Prior-only percentile and z-score calculations are implemented explicitly because excluding the current observation is a hard anti-lookahead requirement.

## 6. State model

Thresholds are versioned in `config/settings.yaml`:

- Crowded long: Leveraged Funds prior-only percentile is at or above 90.
- Crowded short: percentile is at or below 10.
- Extreme lookback: 156 weeks.
- Minimum history: 52 weeks.
- Unwind memory: four reports.
- Price trend: 10-week moving average and four-week momentum.

States are mutually exclusive:

1. `NORMAL`: no active extreme or qualifying unwind sequence.
2. `EXTREME_LONG`: current percentile is at least 90.
3. `EXTREME_SHORT`: current percentile is at most 10.
4. `UNWINDING_LONG`: a long extreme occurred within four reports, the current percentile has exited below 90, and net percentage of open interest is falling.
5. `UNWINDING_SHORT`: a short extreme occurred within four reports, the current percentile has exited above 10, and net percentage of open interest is rising.
6. `CONFIRMED_BEARISH`: `UNWINDING_LONG` plus proxy close below its 10-week moving average and four-week momentum below zero.
7. `CONFIRMED_BULLISH`: `UNWINDING_SHORT` plus proxy close above its 10-week moving average and four-week momentum above zero.

A current extreme remains an extreme even when price weakens. Confirmation requires the position series to exit its extreme zone first, preserving the sequence `EXTREME → UNWINDING → CONFIRMED`.

## 7. Evidence-chain narratives

Each ES/NQ snapshot contains five deterministic sections:

1. **Objective facts:** dates, source, net position, percentage of open interest, prior-only percentile, z-score, and weekly changes.
2. **Rule classification:** the exact state and the thresholds that produced it.
3. **Market inference:** bounded language describing crowding or unwind risk without issuing a buy/sell instruction.
4. **Alternative explanations:** roll activity, changing aggregate open interest, hedging, or classification effects.
5. **Confirmation/invalidation:** the next positioning and price conditions that would strengthen or invalidate the inference.

User-authored notes live in `narratives/notes.yaml` and are rendered in a separate “主觀觀察” panel with author and date. They never overwrite deterministic text.

## 8. Historical validation

Signal events are state transitions rather than every week spent in a state. Each event is aligned to the first available weekly proxy close on or after `available_at`. Outcomes are measured after 1, 4, 8, and 13 weeks.

For every symbol, state, direction, and horizon, publish:

- sample count;
- median forward return;
- reversal-direction win rate;
- median maximum adverse excursion.

For a crowded-long reversal thesis, a negative forward return is a win and positive excursion is adverse. For crowded-short, a positive forward return is a win and negative excursion is adverse. Empty or undersized samples are displayed honestly, without extrapolated statistics.

## 9. Reliability and failure behavior

Adapters enforce timeouts, HTTP status checks, required-column validation, numeric conversion checks, chronological ordering, and duplicate detection. A refresh writes artifacts atomically only after both CFTC and price data validate.

When a scheduled refresh fails, the last successful data remains deployable. The interface marks data stale when the most recent COT report is more than ten days old and displays the last successful generation timestamp and provider status.

## 10. Web experience

Use React, TypeScript, Vite, and Plotly in a responsive dark institutional-research style. The first viewport shows:

- current ES and NQ states;
- data-as-of and freshness;
- Leveraged Funds crowding percentile and net percentage of open interest;
- Asset Manager comparison;
- proxy price confirmation.

Detail views show positioning history, normalized proxy price, state transitions, the five-layer evidence chain, and any separate subjective note. The historical-validation view makes sample size prominent. The methodology view documents formulas, sources, timing, proxy limitations, and non-investment-advice status.

The deploy artifact is rooted so the canonical MVP URL is `https://zbh0421.github.io/gsquant/cot-radar/`.

## 11. Automation and deployment

- CI runs Python unit/integration tests, lint/type checks, front-end tests, and a production build on pull requests and pushes.
- Weekly refresh runs Saturday 00:00 UTC (08:00 Asia/Taipei), regenerates derived artifacts, commits changed derived data, and leaves the last successful snapshot intact on failure.
- GitHub Pages deploys the tested static build from `main`.
- Workflows use least-privilege permissions. The Alpha Vantage key is read only from the repository secret `ALPHA_VANTAGE_API_KEY`.

## 12. Acceptance criteria

The release is complete only when:

- ES and NQ resolve from official CFTC TFF Futures Only data.
- Generated artifacts contain current state, history, evidence chains, backtest summaries, status, and downloads.
- Prior-only calculations and release-date alignment have regression tests.
- The UI clearly distinguishes facts, rules, inference, alternatives, invalidation, and subjective notes.
- Python tests, type/lint checks, front-end tests, and production build pass.
- Weekly refresh and deployment workflows are present.
- The public URL responds successfully and displays the latest valid snapshot.
- The repository contains an MIT license and a research-use/non-investment-advice disclaimer.
