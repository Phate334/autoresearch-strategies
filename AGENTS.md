# AGENTS.md

你在 pi agent 容器中只需要做一件事：讀取既有實驗結果，決定下一輪要跑的策略參數，並寫入 `./data/next_params.json`。

## 先讀哪些檔案

每輪結果在 `./data/<四位數輪次>/`，例如 `./data/0001/`。

- `./data/experiments.csv`：所有輪次的參數與指標總表，先讀這個比較歷史實驗。
- `summary.txt`：單輪精簡摘要。
- `params.json`：該輪實際使用的策略參數。
- `metrics.json`：該輪績效指標，包含年化報酬、最大跌幅、夏普值、平均曝險比例、交易次數與綜合分數。
- `trades.csv`：每次 `trade_weight` 改變的交易紀錄。
- `indicators.csv`：逐日資料、月末信號、實際曝險、日報酬與 equity curve；需要細查原因時再讀。

不要只看最後一輪；至少參考最近 3 輪的 `summary.txt`、`params.json`、`metrics.json` 和 `trades.csv`，若不足 3 輪就看全部既有輪次。

## 分析方式

先執行固定分析腳本，讀取輸出後再判斷下一輪參數：

```bash
uv run python analyze_results.py
```

分析腳本會摘要 `experiments.csv`、最近 3 輪 `metrics.json` / `params.json` / `trades.csv`，以及最新一輪 `indicators.csv` 的報酬、曝險、equity 與最大回撤。

必要時再用文字工具快速掃描小檔案：

```bash
head -n 20 ./data/experiments.csv
cat ./data/0001/summary.txt
cat ./data/0001/params.json
cat ./data/0001/metrics.json
```

`trades.csv` 通常很小，可以完整讀；`indicators.csv` 是逐日時間序列，可能有數千列，不要整份貼進對話。先以 `analyze_results.py` 的摘要為主，需要更細時再寫一次性 `uv run python` 分析。

建議摘要方向：

- 比較最近幾輪的 `composite_score`、`annualized_return`、`max_drawdown`、`sharpe`、`trade_count`。
- 檢查 `trades.csv` 的交易次數是否集中在特定年份，或是否因參數造成換倉太頻繁。
- 從 `indicators.csv` 摘要 `trade_weight`、`high_vol`、`strategy_return`、`equity` 的分布。
- 找最大回撤區間附近的日期，觀察當時 `trade_weight`、`trend_weight`、`high_vol` 是否合理。
- 若只是微幅改善，不要大改策略；下一輪優先小幅調整一個參數方向。

## 下一輪參數

把下一輪要執行的策略參數寫到 `./data/next_params.json`。這個檔案只放策略參數，不放流程參數。

範例：

```json
{
  "ma_months": 8,
  "momentum_months": 10,
  "vol_cut": 0.15
}
```

可用參數：

- `ma_months`：月線均線期數。
- `momentum_months`：動能比較期數。
- `high_weight`：趨勢與動能都成立時的曝險。
- `mid_weight`：只成立一個條件時的曝險。
- `low_weight`：兩個條件都不成立時的曝險。
- `vol_window_short`：短期波動視窗。
- `vol_window_long`：長期波動視窗。
- `vol_lookback`：波動分位數回看天數。
- `vol_quantile`：高波動門檻分位數。
- `vol_cut`：高波動時扣掉的曝險。
- `trading_days`：年化用交易日數。

## 修改原則

一次只改一個小方向。優先修改 `./data/next_params.json`；只有參數無法表達假設時，才修改 `trading_strategy.py` 的策略邏輯。

如果修改 `trading_strategy.py` 的話要複製一份到 `./data/<四位數輪次>/` 目錄下作為紀錄，並在 `summary.txt` 記錄修改原因。

保留月末產生訊號、下一個交易日才生效的精神，避免同一根 K 線收盤同時計算訊號並成交。
