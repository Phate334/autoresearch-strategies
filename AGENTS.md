# AGENTS.md

你是 pi agent。`research.py` 會負責跑回測與呼叫你；你只分析既有結果，補充最新輪次觀察，選下一輪策略參數，寫入 `data/next_params.json`。

## Commands

- 摘要結果：`uv run python analyze_results.py`
- 檢查輸出：`python -m json.tool data/next_params.json`

## Result Files

- `data/experiments.csv`：所有輪次的參數與指標總表，用來比較歷史結果與挑基準輪次。
- `data/<round>/summary.txt`：單輪實驗觀察。不要重複貼 `metrics.json`；記錄該輪相對上一輪/基準輪的取捨、交易集中年份、回撤區間、下一輪值得驗證的假設。
- `data/<round>/params.json`：該輪實際策略參數。產生下一輪時，先複製某個基準輪次的完整參數再小改。
- `data/<round>/metrics.json`：該輪完整績效指標，是判斷好壞的主要來源。
- `data/<round>/trades.csv`：每次 `trade_weight` 改變的紀錄，用來檢查換倉頻率與是否集中在特定年份。
- `data/<round>/indicators.csv`：逐日訊號、曝險、報酬與 equity curve。只有排查回撤、曝險或訊號原因時才摘要讀取。
- `data/next_params.json`：下一輪策略參數，只能放策略參數。

## Analysis

1. 先跑 `uv run python analyze_results.py`，用它掌握總表、最近輪次、交易分布與最新回撤摘要。
2. 若已有輪次，讀 `data/experiments.csv`，再讀最近 3 輪的 `summary.txt`、`params.json`、`metrics.json`、`trades.csv`。
3. 優先比較 `annualized_return` 與 `total_return`；再把 `max_drawdown`、`sharpe`、`average_exposure`、`trade_count` 當作風險/品質約束；`composite_score` 只當參考，不當主要目標。
4. 若需要解釋回撤、曝險或訊號時機，再用一次性 Python 摘要 `indicators.csv`；不要整份讀進對話。
5. 更新最新輪次的 `summary.txt`：寫 3-6 行觀察，說明本輪是否為了降低風險犧牲報酬、是否值得延續、下一輪應驗證什麼。
6. 不要把舊實驗結論寫死；每輪都從目前 `data/` 重新判斷。

## Parameter Choice

- 從目前資料挑一個基準輪次，優先選 `annualized_return` 最好的輪次；若其回撤或交易次數明顯失控，才改選次佳報酬且風險可接受的輪次。
- 複製基準輪次的完整參數，只改一個小方向。
- 目標是提高或恢復報酬，同時控制回撤、Sharpe、曝險與交易次數不要明顯惡化。
- 若最近輪次靠降低曝險/提高 `vol_cut` 才改善分數但報酬下降，視為過度保守；下一輪優先放鬆一個參數，例如降低 `vol_cut`、提高 `low_weight` 或提高 `mid_weight`。
- 只有在報酬增加但回撤或交易次數明顯惡化時，才收緊相關參數。
- 若改善很小，不要大改參數；但不要連續多輪只往更低曝險方向試。
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

- 優先只改 `data/next_params.json` 與最新輪次 `summary.txt`。
- 不要修改 `trading_strategy.py`，除非參數無法表達下一輪假設。
- 若修改策略邏輯，保留月末產生訊號、下一個交易日生效的設計。
- 不新增常駐分析工具；現有 CSV/JSON 用 `analyze_results.py` 或一次性 Python 即可。
