import argparse

import numpy as np

from plant_simulator import DATASETS, load_run


DEFAULT_COLUMNS = ["xmeas_1", "xmeas_7", "xmeas_21"]


def lag_correlation(values: np.ndarray, lag: int) -> float:
    if len(values) <= lag:
        return float("nan")
    current = values[lag:]
    previous = values[:-lag]
    if np.std(current) < 1e-12 or np.std(previous) < 1e-12:
        return 0.0
    return float(np.corrcoef(current, previous)[0, 1])


def analyze_column(samples: np.ndarray, values: np.ndarray) -> dict[str, float]:
    slope = np.polyfit(samples, values, deg=1)[0]
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "lag_1": lag_correlation(values, 1),
        "lag_5": lag_correlation(values, 5),
        "trend_per_100_samples": float(slope * 100),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Basic TEP time-series analysis")
    parser.add_argument(
        "--dataset", choices=sorted(DATASETS), default="fault-free-testing"
    )
    parser.add_argument("--simulation-run", type=int, default=1)
    parser.add_argument("--columns", nargs="+", default=DEFAULT_COLUMNS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run = load_run(args.dataset, args.simulation_run)
    unknown = [column for column in args.columns if column not in run.columns]
    if unknown:
        raise ValueError(f"Unknown columns: {', '.join(unknown)}")

    print(
        f"Dataset: {args.dataset}, simulationRun={args.simulation_run}, "
        f"samples={len(run)}, missing_values={int(run[args.columns].isna().sum().sum())}"
    )
    print(
        "column | mean | std | min | max | autocorr(1) | autocorr(5) "
        "| trend/100 samples"
    )
    samples = run["sample"].to_numpy(dtype=float)
    for column in args.columns:
        metrics = analyze_column(samples, run[column].to_numpy(dtype=float))
        print(
            f"{column:8s} | {metrics['mean']:9.4f} | {metrics['std']:9.4f} "
            f"| {metrics['min']:9.4f} | {metrics['max']:9.4f} "
            f"| {metrics['lag_1']:11.4f} | {metrics['lag_5']:11.4f} "
            f"| {metrics['trend_per_100_samples']:17.4f}"
        )


if __name__ == "__main__":
    main()
