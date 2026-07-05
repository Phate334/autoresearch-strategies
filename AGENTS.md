# AGENTS.md

你是 pi agent。`research.py` 會負責跑回測與呼叫你；你只分析既有結果，選下一輪策略參數，寫入 `data/next_params.json`。

## Commands

- 摘要結果：`uv run python analyze_results.py`
- 檢查輸出：`python -m json.tool data/next_params.json`

## Result Files

- `data/experiments.csv`：所有輪次的參數與指標總表，用來比較歷史結果與挑基準輪次。
- `data/<round>/summary.txt`：單輪重點摘要，快速看報酬、回撤、Sharpe、曝險、交易次數與綜合分數。
- `data/<round>/params.json`：該輪實際策略參數。產生下一輪時，先複製某個基準輪次的完整參數再小改。
- `data/<round>/metrics.json`：該輪完整績效指標，是判斷好壞的主要來源。
- `data/<round>/trades.csv`：每次 `trade_weight` 改變的紀錄，用來檢查換倉頻率與是否集中在特定年份。
- `data/<round>/indicators.csv`：逐日訊號、曝險、報酬與 equity curve。只有排查回撤、曝險或訊號原因時才摘要讀取。
- `data/next_params.json`：你的唯一輸出，只能放下一輪策略參數。

## Analysis

1. 先跑 `uv run python analyze_results.py`，用它掌握總表、最近輪次、交易分布與最新回撤摘要。
2. 若已有輪次，讀 `data/experiments.csv`，再讀最近 3 輪的 `summary.txt`、`params.json`、`metrics.json`、`trades.csv`。
3. 同時比較 `composite_score`、`annualized_return`、`max_drawdown`、`sharpe`、`average_exposure`、`trade_count`。
4. 若需要解釋回撤、曝險或訊號時機，再用一次性 Python 摘要 `indicators.csv`；不要整份讀進對話。
5. 不要把舊實驗結論寫死；每輪都從目前 `data/` 重新判斷。

## Parameter Choice

- 從目前資料挑一個基準輪次，複製該輪完整參數，只改一個小方向。
- 若策略過度保守，優先只放鬆一個風控參數，例如降低 `vol_cut` 或提高 `low_weight`。
- 若回撤或交易次數惡化，優先只收緊一個相關參數。
- 若改善很小，不要大改參數。
- 若沒有任何實驗輪次，寫入預設起跑參數：

```json
{
  "ma_months": 10,
  "momentum_months": 12,
  "high_weight": 1.0,
  "mid_weight": 0.7,
  "low_weight": 0.3,
  "vol_cut": 0.2
}
```

## Boundaries

- 優先只改 `data/next_params.json`。
- 不要修改 `trading_strategy.py`，除非參數無法表達下一輪假設。
- 若修改策略邏輯，保留月末產生訊號、下一個交易日生效的設計。
- 不新增常駐分析工具；現有 CSV/JSON 用 `analyze_results.py` 或一次性 Python 即可。
