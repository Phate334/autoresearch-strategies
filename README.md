# Autoresearch Trading Strategies

這是 `trading_strategy.py` 的最小 autoresearch 沙盒：先跑策略回測，輸出交易紀錄與指標，再讓 pi agent 讀結果並決定下一輪策略參數。

## 使用方式

```bash
uv run python trading_strategy.py
```

會讀取 `data/market_0050.sqlite`，輸出到 `data/<四位數輪次>/`。

要啟動完整自動實驗流程：

```bash
uv run python research.py
```

`research.py` 會持續跑實驗並觀察指標，預設連續 5 輪 `composite_score` 沒有明顯改善就停止。每輪結果在 `data/<四位數輪次>/`，總表在 `data/experiments.csv`，下一輪參數讀自 `data/next_params.json`。

實驗流程與輸出檔細節見 `docs/README.md`。

## Pi agent 容器流程

```bash
docker compose run --rm pi
```

容器會掛入 `AGENTS.md`、`analyze_results.py`、`trading_strategy.py`、`data/`、`pyproject.toml` 和 `uv.lock`。`trading_strategy.py` 與 `data/` 可回寫到本機。

容器內執行 Python 腳本請使用 uv：

```bash
uv run python trading_strategy.py
```

詳細 agent 任務與輸出檔用途見 `AGENTS.md`。
