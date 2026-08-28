# Macro Radar

以可稽核資料、公開規則與明確反證條件描述市場狀態的研究工具。第一個模組是 **CFTC COT 期貨部位擁擠／反轉雷達**。

## COT Radar

第一版追蹤：

- ES（E-mini S&P 500）與 NQ（E-mini Nasdaq-100）
- CFTC TFF Futures Only：Leveraged Funds 為主，Asset Managers 為對照
- 156 週 prior-only 百分位，90／10 極端門檻
- 三階段狀態：極端擁擠、部位鬆動、價格確認
- SPY／QQQ 週線作價格確認代理，並清楚標示資料來源
- 1、4、8、13 週歷史驗證
- 客觀事實、規則、推論、替代解釋、確認與失效條件分層呈現

網站：<https://zbh0421.github.io/gsquant/cot-radar/>

### 本機產生資料

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m cot_radar.cli --price-provider stooq
```

若設定 `ALPHA_VANTAGE_API_KEY`，`--price-provider auto` 會優先使用 Alpha Vantage；未設定或來源失敗時，依序嘗試 Stooq 與 Yahoo Finance 的 SPY／QQQ 週線。所有來源都經相同資料契約驗證，網站會顯示實際採用者。

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
cd projects/cot-radar/web
npm test -- --run
npm run build
```

## 自動化

- 每週六 08:00（Asia/Taipei）更新衍生資料。
- `main` 更新後由 GitHub Actions 建置並部署 GitHub Pages。
- 更新失敗時保留最後成功資料；網站依資料日期顯示 stale 警告。
- 原始價格序列不對外散布，只提供訊號與衍生指標 JSON／CSV。

## 重要限制

COT 通常反映週二部位並於週五發布，適合中期風險背景，不是即時進出場訊號。SPY／QQQ 是 ES／NQ 的價格確認代理，不是期貨結算價。交易者分類與部位變化可能受換月、避險及總未平倉量改變影響。

本專案僅供研究與教育用途，不構成投資建議。
