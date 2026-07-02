from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path


def main() -> None:
    root = Path("data")
    rounds = sorted(path for path in root.iterdir() if path.is_dir() and path.name.isdigit())
    if not rounds:
        raise SystemExit("no experiment rounds found")

    experiments = root / "experiments.csv"
    if experiments.exists():
        print("== experiments.csv ==")
        with experiments.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows[-5:]:
            print(
                row["round"],
                "score", row.get("composite_score", ""),
                "ann", row.get("annualized_return", ""),
                "dd", row.get("max_drawdown", ""),
                "sharpe", row.get("sharpe", ""),
                "trades", row.get("trade_count", ""),
            )

    print("\n== recent rounds ==")
    for path in rounds[-3:]:
        metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))["metrics"]
        params = json.loads((path / "params.json").read_text(encoding="utf-8"))
        print(path.name, json.dumps(metrics, ensure_ascii=False))
        print(path.name, "params", json.dumps(params, ensure_ascii=False))
        summarize_trades(path / "trades.csv")

    print("\n== latest indicators ==")
    summarize_indicators(rounds[-1] / "indicators.csv")


def summarize_trades(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_year = Counter(row["date"][:4] for row in rows)
    print(path.parent.name, "trade_count", len(rows), "trades_by_year", dict(by_year))


def summarize_indicators(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    returns = [float(row["strategy_return"]) for row in rows]
    weights = [float(row["trade_weight"]) for row in rows]
    equity = [float(row["equity"]) for row in rows]
    print("rows", len(rows))
    print("strategy_return", stats(returns))
    print("trade_weight", stats(weights))
    print("equity", stats(equity))
    print("high_vol_days", sum(int(row["high_vol"]) for row in rows))
    peak = equity[0]
    worst = (0.0, rows[0]["date"], rows[0]["date"])
    peak_date = rows[0]["date"]
    for row, value in zip(rows, equity):
        if value > peak:
            peak = value
            peak_date = row["date"]
        drawdown = value / peak - 1.0
        if drawdown < worst[0]:
            worst = (drawdown, peak_date, row["date"])
    print("worst_drawdown", worst)


def stats(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


if __name__ == "__main__":
    main()
