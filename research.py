from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from trading_strategy import next_round, update_experiments_csv


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
        sessions = pi_session_positions()
        run(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                args.service,
            ]
        )
        record_agent_usage(
            data_dir / f"{round_number:04d}" / "metrics.json",
            pi_usage_since(sessions),
        )
        update_experiments_csv(data_dir)


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, check=True)


def pi_session_positions(root: Path = Path(".pi/agent/sessions")) -> dict[Path, int]:
    if not root.exists():
        return {}
    return {path: line_count(path) for path in root.rglob("*.jsonl")}


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def pi_usage_since(before: dict[Path, int]) -> dict[str, float]:
    usage = {
        "agent_input_tokens": 0,
        "agent_output_tokens": 0,
        "agent_cache_read_tokens": 0,
        "agent_cache_write_tokens": 0,
        "agent_total_tokens": 0,
        "agent_cost": 0.0,
    }
    root = Path(".pi/agent/sessions")
    if not root.exists():
        return usage
    for path in root.rglob("*.jsonl"):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[before.get(path, 0) :]:
            event = json.loads(line)
            message_usage = event.get("message", {}).get("usage")
            if not message_usage:
                continue
            usage["agent_input_tokens"] += int(message_usage.get("input", 0))
            usage["agent_output_tokens"] += int(message_usage.get("output", 0))
            usage["agent_cache_read_tokens"] += int(message_usage.get("cacheRead", 0))
            usage["agent_cache_write_tokens"] += int(message_usage.get("cacheWrite", 0))
            usage["agent_total_tokens"] += int(message_usage.get("totalTokens", 0))
            usage["agent_cost"] += float(message_usage.get("cost", {}).get("total", 0.0))
    return usage


def record_agent_usage(metrics_path: Path, usage: dict[str, float]) -> None:
    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    payload["metrics"].update(usage)
    metrics_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
