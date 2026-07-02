from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class Bar:
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float
    volume: float | None


@dataclass(frozen=True)
class Params:
    ma_months: int = 10
    momentum_months: int = 12
    high_weight: float = 1.0
    mid_weight: float = 0.7
    low_weight: float = 0.3
    vol_window_short: int = 20
    vol_window_long: int = 60
    vol_lookback: int = 252
    vol_quantile: float = 0.8
    vol_cut: float = 0.2
    trading_days: int = 252


def load_bars(db_path: Path) -> list[Bar]:
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            """
            select date, open, high, low, close, volume
            from bars
            where symbol = '0050'
            order by date
            """
        ).fetchall()
    bars = [
        Bar(date.fromisoformat(row[0]), *(_num(value) for value in row[1:]))
        for row in rows
    ]
    seen: set[date] = set()
    for bar in bars:
        if bar.date in seen:
            raise ValueError(f"duplicate date: {bar.date}")
        if not math.isfinite(bar.close) or bar.close <= 0:
            raise ValueError(f"invalid close on {bar.date}: {bar.close}")
        seen.add(bar.date)
    return bars


def indicators(bars: list[Bar], p: Params) -> list[dict[str, object]]:
    daily_returns = [now.close / prev.close - 1 for prev, now in zip(bars, bars[1:])]
    monthly_closes: list[tuple[tuple[int, int], float]] = []
    previous_month: tuple[int, int] | None = None
    signal_weight = 0.0
    trade_weight = 0.0
    equity = 1.0
    out: list[dict[str, object]] = []

    for i, bar in enumerate(bars):
        month = (bar.date.year, bar.date.month)
        if month != previous_month:
            monthly_closes.append((month, bar.close))
            previous_month = month
            trade_weight = signal_weight
        else:
            monthly_closes[-1] = (month, bar.close)

        month_end = i == len(bars) - 1 or (
            bars[i + 1].date.year,
            bars[i + 1].date.month,
        ) != month
        trend_weight = _trend_weight(monthly_closes, p)
        high_vol, short_vol, long_vol, vol_threshold = _vol_state(daily_returns, i, p)
        if month_end:
            signal_weight = max(0.0, trend_weight - p.vol_cut) if high_vol else trend_weight
        daily_return = 0.0 if i == 0 else daily_returns[i - 1]
        strategy_return = trade_weight * daily_return
        equity *= 1.0 + strategy_return

        out.append(
            {
                "date": bar.date.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "month_end": int(month_end),
                "trend_weight": trend_weight,
                "high_vol": int(high_vol),
                "short_vol": short_vol,
                "long_vol": long_vol,
                "vol_threshold": vol_threshold,
                "signal_weight": signal_weight if month_end else "",
                "trade_weight": trade_weight,
                "daily_return": daily_return,
                "strategy_return": strategy_return,
                "equity": equity,
            }
        )
    return out


def trade_records(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    trades: list[dict[str, object]] = []
    previous = 0.0
    for row in rows:
        current = float(row["trade_weight"])
        if current != previous:
            trades.append(
                {
                    "date": row["date"],
                    "close": row["close"],
                    "from_weight": previous,
                    "to_weight": current,
                    "delta_weight": current - previous,
                }
            )
            previous = current
    return trades


def metrics(rows: list[dict[str, object]], trades: list[dict[str, object]], p: Params) -> dict[str, object]:
    returns = [float(row["strategy_return"]) for row in rows[1:]]
    equity = [float(row["equity"]) for row in rows]
    years = len(returns) / p.trading_days if returns else 0.0
    total_return = equity[-1] - 1.0 if equity else 0.0
    annualized_return = equity[-1] ** (1.0 / years) - 1.0 if years and equity[-1] > 0 else 0.0
    peak = 1.0
    max_drawdown = 0.0
    for value in equity:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    mean = sum(returns) / len(returns) if returns else 0.0
    variance = (
        sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        if len(returns) > 1
        else 0.0
    )
    sharpe = mean / math.sqrt(variance) * math.sqrt(p.trading_days) if variance > 0 else 0.0
    trade_count = len(trades)
    composite_score = annualized_return + 0.1 * sharpe + max_drawdown - 0.001 * trade_count
    return {
        "start_date": rows[0]["date"] if rows else "",
        "end_date": rows[-1]["date"] if rows else "",
        "bars": len(rows),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "average_exposure": sum(float(row["trade_weight"]) for row in rows) / len(rows) if rows else 0.0,
        "trade_count": trade_count,
        "composite_score": composite_score,
    }


def _trend_weight(monthly_closes: list[tuple[tuple[int, int], float]], p: Params) -> float:
    closes = [close for _, close in monthly_closes]
    if len(closes) <= max(p.ma_months, p.momentum_months):
        return 0.0
    above_ma = closes[-1] > sum(closes[-p.ma_months - 1 : -1]) / p.ma_months
    positive_momentum = closes[-1] > closes[-p.momentum_months - 1]
    if above_ma and positive_momentum:
        return p.high_weight
    if above_ma or positive_momentum:
        return p.mid_weight
    return p.low_weight


def _vol_state(returns: list[float], index: int, p: Params) -> tuple[bool, float, float, float]:
    long_values = returns[max(0, index - p.vol_window_long) : index]
    short_values = returns[max(0, index - p.vol_window_short) : index]
    if len(long_values) < p.vol_window_long or len(short_values) < p.vol_window_short:
        return False, 0.0, 0.0, 0.0
    long_vol = _annualized_vol(long_values, p.trading_days)
    short_vol = _annualized_vol(short_values, p.trading_days)
    history = [
        _annualized_vol(returns[max(0, end - p.vol_window_long) : end], p.trading_days)
        for end in range(max(0, index - p.vol_lookback), index)
        if end >= p.vol_window_long
    ]
    if len(history) < min(126, p.vol_lookback - p.vol_window_long + 1):
        return False, short_vol, long_vol, 0.0
    threshold = sorted(history)[int((len(history) - 1) * p.vol_quantile)]
    return max(short_vol, long_vol) > threshold, short_vol, long_vol, threshold


def _annualized_vol(values: list[float], trading_days: int) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(variance) * math.sqrt(trading_days)


def _num(value: object) -> float | None:
    return float(value) if value is not None else None


def next_round(data_dir: Path) -> int:
    rounds = [int(path.name) for path in data_dir.iterdir() if path.is_dir() and path.name.isdigit()]
    return max(rounds, default=0) + 1


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def update_experiments_csv(data_dir: Path) -> None:
    rows: list[dict[str, object]] = []
    for path in sorted(data_dir.iterdir()):
        metrics_path = path / "metrics.json"
        if not path.is_dir() or not path.name.isdigit() or not metrics_path.exists():
            continue
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        row = {"round": f"{int(payload['round']):04d}"}
        row.update({f"param_{key}": value for key, value in payload["params"].items()})
        row.update(payload["metrics"])
        rows.append(row)
    write_csv(data_dir / "experiments.csv", rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/market_0050.sqlite")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--round", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--ma-months", type=int, default=10)
    parser.add_argument("--momentum-months", type=int, default=12)
    parser.add_argument("--high-weight", type=float, default=1.0)
    parser.add_argument("--mid-weight", type=float, default=0.7)
    parser.add_argument("--low-weight", type=float, default=0.3)
    parser.add_argument("--vol-window-short", type=int, default=20)
    parser.add_argument("--vol-window-long", type=int, default=60)
    parser.add_argument("--vol-lookback", type=int, default=252)
    parser.add_argument("--vol-quantile", type=float, default=0.8)
    parser.add_argument("--vol-cut", type=float, default=0.2)
    parser.add_argument("--trading-days", type=int, default=252)
    args = parser.parse_args()

    params = Params(
        ma_months=args.ma_months,
        momentum_months=args.momentum_months,
        high_weight=args.high_weight,
        mid_weight=args.mid_weight,
        low_weight=args.low_weight,
        vol_window_short=args.vol_window_short,
        vol_window_long=args.vol_window_long,
        vol_lookback=args.vol_lookback,
        vol_quantile=args.vol_quantile,
        vol_cut=args.vol_cut,
        trading_days=args.trading_days,
    )
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    round_number = args.round or next_round(data_dir)
    round_dir = data_dir / f"{round_number:04d}"
    if round_dir.exists() and not args.force:
        raise SystemExit(f"{round_dir} already exists; use --force to overwrite")
    round_dir.mkdir(parents=True, exist_ok=True)

    rows = indicators(load_bars(Path(args.db)), params)
    trades = trade_records(rows)
    result = metrics(rows, trades, params)
    payload = {"round": round_number, "params": params.__dict__, "metrics": result}

    write_csv(round_dir / "indicators.csv", rows)
    write_csv(round_dir / "trades.csv", trades)
    (round_dir / "params.json").write_text(json.dumps(params.__dict__, indent=2), encoding="utf-8")
    (round_dir / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (round_dir / "summary.txt").write_text(
        "\n".join(
            [
                f"round: {round_number:04d}",
                f"annualized_return: {result['annualized_return']:.6f}",
                f"max_drawdown: {result['max_drawdown']:.6f}",
                f"sharpe: {result['sharpe']:.6f}",
                f"average_exposure: {result['average_exposure']:.6f}",
                f"trade_count: {result['trade_count']}",
                f"composite_score: {result['composite_score']:.6f}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_experiments_csv(data_dir)
    print(f"wrote round {round_number:04d} to {round_dir}")


if __name__ == "__main__":
    main()
