import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";

import type {
  BacktestData,
  DashboardData,
  Evidence,
  HistoryData,
  HistoryRow,
  MarketComparison,
  MarketSnapshot,
  StatusData,
} from "./types";

type View = "overview" | "ES" | "NQ" | "backtest" | "method";

interface DataBundle {
  dashboard: DashboardData;
  history: HistoryData;
  backtest: BacktestData;
  status: StatusData;
}

const stateLabels: Record<string, string> = {
  NORMAL: "一般監測",
  EXTREME_LONG: "多頭極端擁擠",
  EXTREME_SHORT: "空頭極端擁擠",
  UNWINDING_LONG: "多頭部位鬆動",
  UNWINDING_SHORT: "空頭部位回補",
  CONFIRMED_BEARISH: "價格確認偏空",
  CONFIRMED_BULLISH: "價格確認偏多",
};

const stateTone = (state: string) => {
  if (state.startsWith("CONFIRMED")) return "confirmed";
  if (state.startsWith("UNWINDING")) return "unwinding";
  if (state.startsWith("EXTREME")) return "extreme";
  return "normal";
};

const value = (primary?: number | null, fallback?: number | null) =>
  primary ?? fallback ?? null;

const number = (input: number | null | undefined, digits = 1) =>
  input == null || !Number.isFinite(input) ? "—" : input.toFixed(digits);

const signedNumber = (input: number | null | undefined, digits = 1) => {
  if (input == null || !Number.isFinite(input)) return "—";
  return `${input > 0 ? "+" : ""}${input.toFixed(digits)}`;
};

const percent = (input: number | null | undefined, digits = 1) =>
  input == null || !Number.isFinite(input) ? "—" : `${(input * 100).toFixed(digits)}%`;

const normalizeTimestamp = (input: string) =>
  input.includes("T") && !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(input)
    ? `${input}Z`
    : input;

const dateLabel = (input?: string) => {
  if (!input) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(normalizeTimestamp(input)));
};

const dateTimeLabel = (input?: string) => {
  if (!input) return "—";
  return `${new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Taipei",
  }).format(new Date(normalizeTimestamp(input)))} 台北`;
};

const normalizeHistory = (data: HistoryData): HistoryRow[] => {
  if (data.history) return data.history;
  return Object.values(data.markets ?? {}).flat();
};

const getEvidence = (market: MarketSnapshot) => {
  const source: Evidence = market.evidence ??
    market.narrative ?? {
      confirmation: "—",
      invalidation: "—",
    };
  return {
    facts: source.objective_facts ?? source.facts ?? "本期敘事尚未產生。",
    rule: source.rule_classification ?? source.rule ?? "—",
    inference: source.market_inference ?? source.inference ?? "—",
    alternatives:
      source.alternative_explanations ??
      source.alternatives ??
      source.alternative ??
      "—",
    confirmation: source.confirmation,
    invalidation: source.invalidation,
  };
};

async function loadJson<T>(name: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/${name}`);
  if (!response.ok) throw new Error(`無法載入 ${name}`);
  return response.json() as Promise<T>;
}

function StateBadge({ state }: { state: string }) {
  return (
    <span className={`state-badge ${stateTone(state)}`}>
      <span className="state-dot" aria-hidden="true" />
      {state}
    </span>
  );
}

function DataStatusPanel({ status }: { status: StatusData }) {
  const publicationLabel = status.stale
    ? "資料 stale"
    : status.publication_state === "waiting_for_cftc"
      ? "等待 CFTC 發布"
      : "資料正常";
  return (
    <section className="status-panel" aria-labelledby="data-status-title">
      <div className="section-heading compact-heading">
        <div>
          <span className="eyebrow">DATA STATUS</span>
          <h2 id="data-status-title">資料新鮮度與更新狀態</h2>
        </div>
        <span className={`publication-badge ${status.stale ? "stale" : ""}`}>
          {publicationLabel}
        </span>
      </div>
      {status.warning && <div className="status-warning" role="status">{status.warning}</div>}
      <div className="status-grid">
        <div><span>CFTC 部位所屬星期二</span><strong>{dateLabel(status.latest_report_date)}</strong></div>
        <div><span>正常排程發布時間</span><strong>{dateTimeLabel(status.scheduled_release_at)}</strong><small>週五 15:30 ET</small></div>
        <div><span>系統實際抓取時間</span><strong>{dateTimeLabel(status.fetched_at ?? status.generated_at)}</strong></div>
        <div><span>最近一次成功更新</span><strong>{dateTimeLabel(status.last_successful_update_at ?? status.generated_at)}</strong></div>
        <div><span>下一次預定更新</span><strong>{dateTimeLabel(status.next_scheduled_update_at)}</strong><small>GitHub Actions</small></div>
        <div><span>下一期正常發布</span><strong>{dateTimeLabel(status.next_expected_release_at)}</strong></div>
        <div><span>CFTC dataset ID</span><strong>{status.cftc_dataset ?? "gpe5-46if"}</strong></div>
        <div><span>價格資料供應商</span><strong>{status.price_provider}</strong></div>
      </div>
    </section>
  );
}

function MarketCard({
  market,
  active,
  onSelect,
}: {
  market: MarketSnapshot;
  active: boolean;
  onSelect: () => void;
}) {
  const proxy = market.proxy_symbol ?? (market.symbol === "ES" ? "SPY" : "QQQ");
  return (
    <article className={`market-card ${active ? "active" : ""}`}>
      <div className="card-topline">
        <div>
          <span className="symbol">{market.symbol}</span>
          <h2>{market.display_name}</h2>
        </div>
        <StateBadge state={market.state} />
      </div>
      <p className="state-label">{stateLabels[market.state] ?? "自訂規則狀態"}</p>
      <div className="metric-grid">
        <div>
          <span>Leveraged Funds 百分位</span>
          <strong>{number(market.leveraged_percentile)}<small>th</small></strong>
        </div>
        <div>
          <span>槓桿基金淨部位／OI</span>
          <strong>
            {number(value(market.leveraged_net_pct_oi, market.leveraged_net_oi_pct))}
            <small>%</small>
          </strong>
        </div>
        <div>
          <span>Asset Managers／OI</span>
          <strong>
            {number(value(market.asset_manager_net_pct_oi, market.asset_manager_net_oi_pct))}
            <small>%</small>
          </strong>
        </div>
        <div>
          <span>四週價格動能</span>
          <strong>{percent(market.price_momentum)}</strong>
        </div>
      </div>
      <div className="proxy-line">價格確認：{proxy} 代理（非 {market.symbol} 期貨結算價）</div>
      {market.market_name && (
        <div className="proxy-line">CFTC 官方市場：{market.market_name}</div>
      )}
      <button className="text-button" onClick={onSelect} aria-pressed={active}>
        查看證據鏈 <span aria-hidden="true">→</span>
      </button>
    </article>
  );
}

function ComparisonPanel({ comparison }: { comparison: MarketComparison }) {
  const es = comparison.markets.ES;
  const nq = comparison.markets.NQ;
  const rows = [
    ["Leveraged Funds 淨部位／OI", `${number(es.leveraged_net_pct_oi)}%`, `${number(nq.leveraged_net_pct_oi)}%`],
    ["Asset Managers 淨部位／OI", `${number(es.asset_manager_net_pct_oi)}%`, `${number(nq.asset_manager_net_pct_oi)}%`],
    ["156 週 prior-only 百分位", number(es.leveraged_percentile), number(nq.leveraged_percentile)],
    ["一週部位變化（百分點）", signedNumber(es.leveraged_change_1w), signedNumber(nq.leveraged_change_1w)],
    ["四週部位變化（百分點）", number(es.leveraged_change_4w), number(nq.leveraged_change_4w)],
    ["四週價格動能", percent(es.price_momentum_4w), percent(nq.price_momentum_4w)],
    ["價格相對十週均線", percent(es.price_vs_sma_10w), percent(nq.price_vs_sma_10w)],
  ];
  return (
    <section className="comparison-panel" aria-labelledby="comparison-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">ES / NQ CROSS-MARKET</span>
          <h2 id="comparison-title">ES／NQ 客觀比較</h2>
        </div>
        <span className="as-of">公式判定 · 非文字生成</span>
      </div>
      <div className="comparison-summary">
        <span>同步擁擠：{comparison.synchronized_crowding ? "是" : "否"}</span>
        <span>部位分歧：{comparison.position_divergence ? "是" : "否"}</span>
        <span>更極端市場：{comparison.more_extreme_market ?? "無"}</span>
      </div>
      <div className="table-scroll">
        <table className="comparison-table">
          <thead><tr><th>客觀指標</th><th>ES</th><th>NQ</th></tr></thead>
          <tbody>
            {rows.map(([label, esValue, nqValue]) => (
              <tr key={label}><td>{label}</td><td>{esValue}</td><td>{nqValue}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="divergence-chain">
        <article><span>分歧證據</span><p>{comparison.evidence}</p></article>
        <article><span>可反駁條件</span><p>{comparison.falsification}</p></article>
      </div>
    </section>
  );
}

function EvidencePanel({ market }: { market: MarketSnapshot }) {
  const evidence = getEvidence(market);
  const facts = Array.isArray(evidence.facts) ? evidence.facts.join(" ") : evidence.facts;
  return (
    <section className="evidence-panel" aria-label={`${market.symbol} 證據鏈`}>
      <div className="section-heading">
        <div>
          <span className="eyebrow">EVIDENCE CHAIN · {market.symbol}</span>
          <h2>可稽核市場敘事</h2>
        </div>
        <span className="as-of">資料日 {dateLabel(market.report_date)}</span>
      </div>
      <div className="evidence-grid">
        <article className="evidence-item fact">
          <span className="step">01</span>
          <div><h3>客觀事實</h3><p>{facts}</p></div>
        </article>
        <article className="evidence-item rule">
          <span className="step">02</span>
          <div><h3>規則判定</h3><p>{evidence.rule}</p></div>
        </article>
        <article className="evidence-item inference">
          <span className="step">03</span>
          <div><h3>市場推論</h3><p>{evidence.inference}</p></div>
        </article>
        <article className="evidence-item alternative">
          <span className="step">04</span>
          <div><h3>替代解釋</h3><p>{evidence.alternatives}</p></div>
        </article>
        <article className="evidence-item conditions">
          <span className="step">05</span>
          <div>
            <h3>確認與失效條件</h3>
            <p><b>確認：</b>{evidence.confirmation}</p>
            <p><b>失效：</b>{evidence.invalidation}</p>
          </div>
        </article>
      </div>
      {(market.subjective_notes?.length ?? 0) > 0 && (
        <div className="subjective-note">
          <span>主觀推論</span>
          {market.subjective_notes!.map((note) => (
            <p key={`${note.date}-${note.author}`}>
              {note.text} — {note.author}，{dateLabel(note.date)}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

function MarketChart({ symbol, rows }: { symbol: "ES" | "NQ"; rows: HistoryRow[] }) {
  const market = rows.filter((row) => row.symbol === symbol);
  const x = market.map((row) => row.report_date);
  const position = market.map((row) =>
    value(row.leveraged_net_pct_oi, row.leveraged_net_oi_pct),
  );
  const asset = market.map((row) =>
    value(row.asset_manager_net_pct_oi, row.asset_manager_net_oi_pct),
  );
  const percentile = market.map((row) => row.leveraged_percentile);
  const transitions = market.filter((row, index) => index === 0 || row.state !== market[index - 1]?.state);

  return (
    <div className="chart-shell">
      <div className="chart-header">
        <div>
          <span className="eyebrow">POSITION HISTORY</span>
          <h3>{symbol} 交易者部位與歷史百分位</h3>
          <p className="chart-note">極端區間固定為 90th／10th；菱形標記代表狀態轉換時間點。</p>
        </div>
        <div className="chart-legend">
          <span className="legend-leveraged">Leveraged Funds</span>
          <span className="legend-asset">Asset Managers</span>
          <span className="legend-percentile">百分位</span>
        </div>
      </div>
      <Plot
        divId={`${symbol.toLowerCase()}-position-chart`}
        data={[
          {
            x,
            y: position,
            type: "scatter",
            mode: "lines",
            name: "Leveraged Funds / OI",
            line: { color: "#38e8c6", width: 2.4 },
          },
          {
            x,
            y: asset,
            type: "scatter",
            mode: "lines",
            name: "Asset Managers / OI",
            line: { color: "#6687ff", width: 2 },
          },
          {
            x,
            y: percentile,
            type: "scatter",
            mode: "lines",
            name: "Leveraged percentile",
            yaxis: "y2",
            line: { color: "#f5b85a", width: 1.5, dash: "dot" },
          },
          {
            x: transitions.map((row) => row.report_date),
            y: transitions.map((row) => row.leveraged_percentile),
            type: "scatter",
            mode: "markers",
            name: "State transition",
            yaxis: "y2",
            text: transitions.map((row) => row.state),
            hovertemplate: "%{x}<br>%{text}<extra></extra>",
            marker: { symbol: "diamond", size: 8, color: "#ff6b78" },
          },
        ]}
        layout={{
          autosize: true,
          height: 410,
          margin: { l: 56, r: 56, t: 20, b: 50 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { color: "#8ea3b3", family: "Inter, system-ui, sans-serif" },
          xaxis: { gridcolor: "#172a35", zeroline: false },
          yaxis: { title: { text: "淨部位／OI (%)" }, gridcolor: "#172a35", zerolinecolor: "#38505e" },
          yaxis2: {
            title: { text: "百分位" },
            overlaying: "y" as never,
            side: "right",
            range: [0, 100],
            showgrid: false,
          },
          shapes: [
            { type: "rect", xref: "paper", x0: 0, x1: 1, yref: "y2", y0: 90, y1: 100, fillcolor: "rgba(245,184,90,.07)", line: { width: 0 } },
            { type: "rect", xref: "paper", x0: 0, x1: 1, yref: "y2", y0: 0, y1: 10, fillcolor: "rgba(102,135,255,.07)", line: { width: 0 } },
          ],
          showlegend: false,
          hovermode: "x unified",
        }}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: "100%", height: "100%" }}
      />
    </div>
  );
}

function BacktestView({ data }: { data: BacktestData }) {
  const rows = data.summary ?? data.rows ?? [];
  const metadata = data.metadata;
  const minimum = metadata?.minimum_sample_size ?? 10;
  return (
    <section className="page-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">NO-LOOKAHEAD VALIDATION</span>
          <h2>歷史訊號驗證</h2>
        </div>
      </div>
      <div className="method-warning-grid">
        <p>{metadata?.availability_assumption ?? "報酬從 COT 正常排程可得後的第一個週線價格開始計算。"}</p>
        <p>{metadata?.historical_release_limit ?? "假日或營運延遲未逐筆重建，延遲週的結果可能偏樂觀。"}</p>
        <p>{metadata?.disclaimer ?? "歷史結果不代表未來報酬。"}</p>
      </div>
      {rows.length === 0 ? (
        <div className="empty-state">現有資料尚無足夠的完整訊號樣本；系統不會用不足樣本製造結論。</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>市場</th><th>狀態</th><th>訊號方向</th><th>期間</th><th>樣本</th>
              <th>中位報酬</th><th>反轉勝率</th><th>最大不利走勢</th><th>統計期間</th><th>價格代理來源</th>
            </tr></thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.symbol}-${row.state}-${row.horizon_weeks}-${index}`}>
                  <td>{row.symbol}</td><td>{row.state}</td><td>{row.signal_direction ?? row.extreme_direction}</td>
                  <td>{row.horizon_weeks} 週</td>
                  <td>
                    {row.sample_count}
                    {row.small_sample && <span className="small-sample">樣本不足（&lt; {minimum}）</span>}
                  </td>
                  <td>{percent(row.median_forward_return)}</td>
                  <td>{row.small_sample ? "不顯示" : percent(row.reversal_win_rate)}</td>
                  <td>{percent(row.median_max_adverse_excursion)}</td>
                  <td>{dateLabel(row.period_start)} – {dateLabel(row.period_end)}</td>
                  <td>{row.proxy_symbol ?? "—"} · {row.price_provider ?? metadata?.price_provider ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MethodView({ dashboard, status }: { dashboard: DashboardData; status: StatusData }) {
  const stateMachine = dashboard.methodology?.state_machine ?? {};
  const dataset = status.cftc_dataset ?? "gpe5-46if";
  const downloads = ["signals.csv", "signals.json", "dashboard.json", "history.json", "backtest.json", "status.json"];
  return (
    <section className="page-section method-page">
      <div className="section-heading">
        <div><span className="eyebrow">METHODOLOGY</span><h2>方法與資料</h2></div>
      </div>
      <div className="method-grid">
        <article><span>01</span><h3>資料口徑</h3><p>CFTC TFF Futures Only；週二部位通常週五發布。系統使用排定發布時間對齊價格；假日或營運延遲可能使實際發布更晚，歷史驗證未逐筆重建例外發布時間。</p></article>
        <article><span>02</span><h3>擁擠衡量</h3><p>Leveraged Funds 淨部位除以總 OI，使用 156 週 prior-only 歷史窗計算百分位；當期值不進入自己的參考分布。</p></article>
        <article><span>03</span><h3>狀態機</h3><p>第 90／10 百分位定義 EXTREME；退出極端且部位反向變化為 UNWINDING；代理價格的 10 週均線與 4 週動能共同確認。所有門檻均由公開設定檔提供。</p></article>
        <article><span>04</span><h3>價格代理</h3><p>ES 使用 SPY、NQ 使用 QQQ。它們只用於週頻方向確認，不等同 ES／NQ 期貨結算價，也不作精確期貨損益回測。</p></article>
      </div>

      <div className="rules-section">
        <div className="section-heading compact-heading">
          <div><span className="eyebrow">PUBLIC RULES</span><h2>狀態機公開規則</h2></div>
        </div>
        <div className="table-scroll">
          <table className="rules-table">
            <thead><tr><th>狀態</th><th>進入條件</th><th>保持條件</th><th>退出條件</th><th>價格確認</th><th>推論失效</th></tr></thead>
            <tbody>
              {Object.entries(stateMachine).map(([state, rule]) => (
                <tr key={state}>
                  <td><StateBadge state={state} /></td>
                  <td>{rule.entry}</td><td>{rule.hold}</td><td>{rule.exit}</td>
                  <td>{rule.price_confirmation}</td><td>{rule.invalidation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="source-card">
        <div><span>官方資料集</span><strong><a href={`https://publicreporting.cftc.gov/resource/${dataset}`} target="_blank" rel="noreferrer">CFTC TFF Futures Only</a></strong><small>{dataset}</small></div>
        <div><span>價格來源</span><strong>{status.price_provider}</strong><small>SPY／QQQ 僅為代理</small></div>
        <div><span>最新報告</span><strong>{dateLabel(status.latest_report_date)}</strong></div>
        <div><span>正常發布</span><strong>週五 15:30 ET</strong></div>
      </div>
      <div className="download-card">
        <span>衍生 CSV／JSON 下載</span>
        <div>{downloads.map((name) => <a key={name} href={`${import.meta.env.BASE_URL}data/${name}`}>{name}</a>)}</div>
        <p>只提供研究所需的衍生資料；不提供完整原始價格序列。</p>
      </div>
      <p className="disclaimer">僅供研究與教育用途，不構成投資建議。COT 為彙總資料，無法識別單一機構或每筆交易目的。</p>
    </section>
  );
}

export default function App() {
  const [view, setView] = useState<View>("overview");
  const [selected, setSelected] = useState<"ES" | "NQ">("ES");
  const [data, setData] = useState<DataBundle | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      loadJson<DashboardData>("dashboard.json"),
      loadJson<HistoryData>("history.json"),
      loadJson<BacktestData>("backtest.json"),
      loadJson<StatusData>("status.json"),
    ])
      .then(([dashboard, history, backtest, status]) =>
        setData({ dashboard, history, backtest, status }),
      )
      .catch((reason: unknown) =>
        setError(reason instanceof Error ? reason.message : "資料載入失敗"),
      );
  }, []);

  const history = useMemo(
    () => (data ? normalizeHistory(data.history) : []),
    [data],
  );
  const current = data?.dashboard.markets.find((market) => market.symbol === selected);

  const navigate = (next: View) => {
    setView(next);
    if (next === "ES" || next === "NQ") setSelected(next);
  };

  return (
    <div className="app-shell">
      <header className="site-header">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="COT Radar 首頁">
          <span className="brand-mark">CR</span>
          <span><b>MACRO RADAR</b><small>CFTC POSITIONING</small></span>
        </a>
        <nav aria-label="主要導覽">
          <button className={view === "overview" ? "active" : ""} onClick={() => navigate("overview")}>總覽</button>
          <button className={view === "ES" ? "active" : ""} onClick={() => navigate("ES")}>ES</button>
          <button className={view === "NQ" ? "active" : ""} onClick={() => navigate("NQ")}>NQ</button>
          <button className={view === "backtest" ? "active" : ""} onClick={() => navigate("backtest")}>歷史驗證</button>
          <button className={view === "method" ? "active" : ""} onClick={() => navigate("method")}>方法與資料</button>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div>
            <span className="eyebrow">POSITIONING · CROWDING · REVERSAL RISK</span>
            <h1>CFTC 期貨部位擁擠／反轉雷達</h1>
            <p>用可驗證數據建立市場證據鏈：先看大型交易者部位，再辨識鬆動，最後等待價格確認。</p>
          </div>
          {data && (
            <div className={`freshness ${data.status.stale ? "stale" : ""}`}>
              <span>{data.status.publication_state === "waiting_for_cftc" ? "等待 CFTC" : data.status.stale ? "資料逾期" : "資料正常"}</span>
              <strong>{dateLabel(data.status.latest_report_date)}</strong>
              <small>週頻 · {data.status.price_provider}</small>
            </div>
          )}
        </section>

        {error && <div className="error-banner" role="alert">{error}；目前無法安全呈現市場結論。</div>}
        {!data && !error && <div className="loading">正在載入可稽核資料…</div>}

        {data && <DataStatusPanel status={data.status} />}

        {data && view === "overview" && (
          <>
            {data.dashboard.comparison && <ComparisonPanel comparison={data.dashboard.comparison} />}
            <section className="market-grid" aria-label="市場總覽">
              {data.dashboard.markets.map((market) => (
                <MarketCard
                  key={market.symbol}
                  market={market}
                  active={market.symbol === selected}
                  onSelect={() => setSelected(market.symbol)}
                />
              ))}
            </section>
            {current && <EvidencePanel market={current} />}
          </>
        )}

        {data && (view === "ES" || view === "NQ") && current && (
          <section className="page-section market-page">
            <MarketCard market={current} active onSelect={() => undefined} />
            <MarketChart symbol={current.symbol} rows={history} />
            <EvidencePanel market={current} />
          </section>
        )}

        {data && view === "backtest" && <BacktestView data={data.backtest} />}
        {data && view === "method" && <MethodView dashboard={data.dashboard} status={data.status} />}
      </main>

      <footer>
        <span>COT POSITIONING & REVERSAL RADAR</span>
        <span>研究用途 · 非投資建議 · <a href="https://github.com/ZBH0421/gsquant">GitHub</a></span>
      </footer>
    </div>
  );
}