---
name: trading-parameter-review
description: Review existing backtest rounds and choose the next trading strategy parameters for this repo. Use when Codex or pi agent needs to analyze data/experiments.csv, recent round files, trades, metrics, or indicators, then write data/next_params.json.
---

# Trading Parameter Review

Run `uv run python analyze_results.py` first.

If no rounds exist, write the default starter parameters from `AGENTS.md`.

For existing rounds:

1. Compare all rows in `data/experiments.csv`.
2. Inspect the latest 3 rounds: `summary.txt`, `params.json`, `metrics.json`, `trades.csv`.
3. Read `indicators.csv` only through a short one-off Python summary when drawdown, exposure, or signal timing needs explanation.
4. Pick one baseline round from the current data.
5. Copy that full parameter set and change one small direction.
6. Write only strategy parameters to `data/next_params.json`.
7. Validate with `python -m json.tool data/next_params.json`.

Prefer instruction-only analysis. Add a script only after the same manual calculation is repeated across several rounds and needs deterministic reuse.
