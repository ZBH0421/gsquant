import { useEffect, useMemo, useState } from "react";
import Plot from "react-plotly.js";

import type {
  BacktestData,
  DashboardData,
  Evidence,
  HistoryData,
  HistoryRow,
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

const percent = (input: number | null | undefined, digits = 1) =>
  input == null || !Number.isFinite(input) ? "—" : `${(input * 100).toFixed(digits)}%`;

const dateLabel = (input?: string) => {
  if (!input) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(input));
};

const normalizeHistory = (data: HistoryData): HistoryRow[] => {
  if (data.history) return data.history;
  return Object.values(data.markets ?? {}).flat();
};

const getEvidence = (market: MarketSnapshot): Evidence =>
  market.evidence ??
  market.narrative ?? {
    facts: "本期敘事尚未產生。",
    rule: "—",
    inference: "—",
    alternatives: "—",
    confirmation: "—",
    invalidation: "—",
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
      <button className="text-button" onClick={onSelect} aria-pressed={active}>
        查看證據鏈 <span aria-hidden="true">→</span>
      </button>
    </article>
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
          <div><h3>替代解釋</h3><p>{evidence.alternatives ?? evidence.alternative}</p></div>
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

  return (
    <div className="chart-shell">
      <div className="chart-header">
        <div>
          <span className="eyebrow">POSITION HISTORY</span>
          <h3>{symbol} 交易者部位與歷史百分位</h3>
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
        ]}
        layout={{
          autosize: true,
          height: 390,
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
  return (
    <section className="page-section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">NO-LOOKAHEAD VALIDATION</span>
          <h2>歷史訊號驗證</h2>
        </div>
      </div>
      <p className="section-intro">
        報酬從 COT 實際可得後的第一個週線價格開始計算，避免把週二部位提前視為已知。
      </p>
      {rows.length === 0 ? (
        <div className="empty-state">現有資料尚無足夠的完整訊號樣本；系統不會用不足樣本製造結論。</div>
      ) : (
        <div className="table-scroll">
          <table>
            <thead><tr>
              <th>市場</th><th>狀態</th><th>方向</th><th>期間</th><th>樣本</th>
              <th>中位報酬</th><th>反轉勝率</th><th>中位最大不利走勢</th>
            </tr></thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={`${row.symbol}-${row.state}-${row.horizon_weeks}-${index}`}>
                  <td>{row.symbol}</td><td>{row.state}</td><td>{row.extreme_direction}</td>
                  <td>{row.horizon_weeks} 週</td><td>{row.sample_count}</td>
                  <td>{percent(row.median_forward_return)}</td>
                  <td>{percent(row.reversal_win_rate)}</td>
                  <td>{percent(row.median_max_adverse_excursion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function MethodView({ status }: { status: StatusData }) {
  return (
    <section className="page-section method-page">
      <div className="section-heading">
        <div><span className="eyebrow">METHODOLOGY</span><h2>方法與資料</h2></div>
      </div>
      <div className="method-grid">
        <article><span>01</span><h3>資料口徑</h3><p>CFTC TFF Futures Only；週二部位通常週五發布。系統以實際可得時間對齊價格，避免偷看未發布資料。</p></article>
        <article><span>02</span><h3>擁擠衡量</h3><p>Leveraged Funds 淨部位除以總 OI，使用 156 週 prior-only 歷史窗計算百分位；當期值不進入自己的參考分布。</p></article>
        <article><span>03</span><h3>狀態機</h3><p>第 90／10 百分位定義 EXTREME；退出極端且部位反向變化為 UNWINDING；代理價格的 10 週均線與 4 週動能共同確認。</p></article>
        <article><span>04</span><h3>價格代理</h3><p>ES 使用 SPY、NQ 使用 QQQ。它們只用於週頻方向確認，不等同 ES／NQ 期貨結算價，也不作精確損益回測。</p></article>
      </div>
      <div className="source-card">
        <div><span>資料集</span><strong>CFTC {status.cftc_dataset ?? "gpe5-46if"}</strong></div>
        <div><span>價格來源</span><strong>{status.price_provider}</strong></div>
        <div><span>最新報告</span><strong>{dateLabel(status.latest_report_date)}</strong></div>
        <div><span>衍生資料下載</span><strong><a href={`${import.meta.env.BASE_URL}data/signals.csv`}>CSV</a> · <a href={`${import.meta.env.BASE_URL}data/signals.json`}>JSON</a></strong></div>
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
              <span>{data.status.stale ? "資料逾期" : "資料正常"}</span>
              <strong>{dateLabel(data.status.latest_report_date)}</strong>
              <small>週頻 · {data.status.price_provider}</small>
            </div>
          )}
        </section>

        {error && <div className="error-banner" role="alert">{error}；目前無法安全呈現市場結論。</div>}
        {!data && !error && <div className="loading">正在載入可稽核資料…</div>}

        {data && view === "overview" && (
          <>
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
          <section className="page-section">
            <MarketCard market={current} active onSelect={() => undefined} />
            <MarketChart symbol={current.symbol} rows={history} />
            <EvidencePanel market={current} />
          </section>
        )}

        {data && view === "backtest" && <BacktestView data={data.backtest} />}
        {data && view === "method" && <MethodView status={data.status} />}
      </main>

      <footer>
        <span>COT POSITIONING & REVERSAL RADAR</span>
        <span>研究用途 · 非投資建議 · <a href="https://github.com/ZBH0421/gsquant">GitHub</a></span>
      </footer>
    </div>
  );
}
