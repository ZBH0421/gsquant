# Macro Radar

以可稽核資料、公開規則與明確反證條件描述市場狀態的研究工具。第一個模組是 **CFTC COT 期貨部位擁擠／反轉雷達**。

## COT Radar

目前版本追蹤：

- ES（E-mini S&P 500）與 NQ（E-mini Nasdaq-100）
- CFTC **TFF Futures Only** dataset `gpe5-46if`：Leveraged Funds 為主要擁擠觀察對象，Asset Managers／Institutional 為對照；Dealer、Other Reportables 保留為客觀資料
- 156 週 prior-only 百分位，90／10 極端門檻；當期觀察值不進入自己的歷史參考分布
- 七狀態規則機：`NORMAL`、`EXTREME_LONG`、`EXTREME_SHORT`、`UNWINDING_LONG`、`UNWINDING_SHORT`、`CONFIRMED_BEARISH`、`CONFIRMED_BULLISH`
- 10 週價格均線與 4 週價格動能作確認；所有狀態門檻集中於 `projects/cot-radar/config/settings.yaml`
- SPY／QQQ 週線只作 ES／NQ 價格方向代理，**不是正式 ES／NQ 期貨結算價**
- ES／NQ 客觀比較：Leveraged／Asset Manager 淨部位／OI、156 週 prior-only 百分位、1／4 週部位變化、4 週價格動能、相對 10 週均線、同步擁擠、公式化部位分歧、較極端市場與可反駁條件
- 1、4、8、13 週歷史驗證：樣本數、中位報酬、反轉勝率、最大不利走勢、方向、統計期間與價格代理來源；樣本低於公開門檻時不顯示勝率結論
- 客觀事實、規則判定、市場推論、替代解釋、確認與失效條件分層呈現

網站：<https://zbh0421.github.io/gsquant/cot-radar/>

### 資料新鮮度

公開 `status.json` 與網站分開呈現不同時間語意：

- `latest_report_date`：CFTC 部位所屬星期二
- `scheduled_release_at`：該期正常排程發布時間（週五 15:30 America/New_York）
- `fetched_at`：本次系統實際抓取時間
- `last_successful_update_at`：最近一次成功產生完整 snapshot 的時間
- `next_expected_release_at`：下一期正常排程發布時間
- `next_scheduled_update_at`：下一次 GitHub Actions 預定更新時間
- `publication_state`：`current`、`waiting_for_cftc` 或 `stale`

如果下一期尚未到正常發布時間，或剛到發布時間但官方可能延遲，網站會顯示「等待 CFTC 發布」，不把它誤判成系統更新失敗。若 GitHub Actions 抓取／驗證失敗，部署流程保留最後成功資料並在公開 status 與前端加入失敗警告。

### 本機產生資料

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m cot_radar.cli --price-provider stooq
```

若設定 `ALPHA_VANTAGE_API_KEY`，`--price-provider auto` 會優先使用 Alpha Vantage；未設定或來源失敗時，依序嘗試 Stooq 與 Yahoo Finance 的 SPY／QQQ 週線。所有來源都經相同資料契約驗證，網站會顯示實際採用者。API Key 只由 GitHub Secret／執行環境提供，不寫入 repository。

### 本機啟動網站

```bash
cd projects/cot-radar/web
npm install
npm run dev
```

### 驗證

```bash
python -m pytest projects/cot-radar/pipeline/tests -q
python -m ruff check projects/cot-radar/pipeline/src projects/cot-radar/pipeline/tests
python -m mypy projects/cot-radar/pipeline/src
git diff --check
cd projects/cot-radar/web
npm test -- --run
npx tsc -b --pretty false
npx vite build
```

## 自動化

- 每週六 08:00（Asia/Taipei）更新衍生資料；GitHub cron 為週六 00:00 UTC。
- `main` 更新後由 GitHub Actions 重新抓取／驗證資料、執行 Python 與前端測試，再建置並部署 GitHub Pages。
- 更新失敗時不覆蓋市場 snapshot；Pages 仍可使用最後成功資料並顯示最新一次更新失敗警告，工作流最後保持 failure 狀態方便稽核。
- 原始價格序列不對外散布，只提供研究必要的衍生 JSON／CSV。

## 重要限制

COT 通常反映週二部位並於週五發布，適合中期風險背景，不是即時進出場訊號。歷史資料沒有逐筆實際發布時間，本版以正常排程的週五 15:30 ET 作可得時間；假日或營運延遲未逐筆重建，因此延遲週的歷史驗證可能偏樂觀。SPY／QQQ 是 ES／NQ 的價格確認代理，不是期貨結算價；網站另列 CFTC 官方市場名稱，避免將 Consolidated 報告誤解為單一期貨合約。交易者分類與部位變化可能受換月、避險及總未平倉量改變影響。小樣本不顯示具結論意味的勝率，任何歷史統計皆不代表未來報酬。

本專案僅供研究與教育用途，不構成投資建議。