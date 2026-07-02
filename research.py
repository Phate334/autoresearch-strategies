from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from trading_strategy import next_round


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--service", default="pi")
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--metric", default="composite_score")
    parser.add_argument("--min-improvement", type=float, default=0.001)
    parser.add_argument("--skip-agent", action="store_true")
    args, strategy_args = parser.parse_known_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    best = best_metric(data_dir, args.metric)
    stale_rounds = 0

    for _ in range(args.max_rounds):
        round_number = next_round(data_dir)
        run(
            [
                "uv",
                "run",
                "python",
                "trading_strategy.py",
                "--data-dir",
                args.data_dir,
                "--round",
                str(round_number),
                *next_params(data_dir),
                *strategy_args,
            ]
        )
        value = read_metric(
            data_dir / f"{round_number:04d}" / "metrics.json", args.metric
        )
        if best is None or value > best + args.min_improvement:
            best = value
            stale_rounds = 0
        else:
            stale_rounds += 1
        print(f"{args.metric}={value:.6f} best={best:.6f} stale_rounds={stale_rounds}")

        if stale_rounds >= args.patience:
            print(
                f"stop: no {args.metric} improvement above "
                f"{args.min_improvement:g} for {args.patience} rounds"
            )
            break
        if args.skip_agent:
            break
        run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                args.service,
                "AGENTS.md",
            ]
        )


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def next_params(data_dir: Path) -> list[str]:
    path = data_dir / "next_params.json"
    if not path.exists():
        return []
    params = json.loads(path.read_text(encoding="utf-8"))
    return [
        item
        for key, value in params.items()
        for item in (f"--{key.replace('_', '-')}", str(value))
        if value is not None
    ]


def best_metric(data_dir: Path, metric: str) -> float | None:
    values = [
        read_metric(path / "metrics.json", metric)
        for path in data_dir.iterdir()
        if path.is_dir() and path.name.isdigit() and (path / "metrics.json").exists()
    ]
    return max(values, default=None)


def read_metric(path: Path, metric: str) -> float:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload["metrics"][metric])


if __name__ == "__main__":
    main()
