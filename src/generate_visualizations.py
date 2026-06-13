import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadr
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from kalman_filter import LinearKalmanFilter
from model_artifact import TEPModel, load_model
from mpc_setup import LinearMPC
from settings import DATA_DIR, PROJECT_ROOT


MEASUREMENT_COLUMNS = [f"xmeas_{index}" for index in range(1, 42)]
CONTROL_COLUMNS = [f"xmv_{index}" for index in range(1, 12)]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "visualizations"
RESULTS_DIR = PROJECT_ROOT / "artifacts" / "results"

BLUE = "#2463A6"
ORANGE = "#E07A2D"
GREEN = "#2E8B57"
RED = "#C44536"
GRAY = "#5D6670"
LIGHT_BLUE = "#E7F0FA"


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 13,
            "axes.labelsize": 10,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 140,
            "savefig.dpi": 180,
            "savefig.bbox": "tight",
        }
    )


def load_testing_data() -> pd.DataFrame:
    path = DATA_DIR / "TEP_FaultFree_Testing.RData"
    return pd.DataFrame(pyreadr.read_r(str(path))["fault_free_testing"])


def forecast_run(
    model: TEPModel,
    run: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    measurements = run[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    controls = run[CONTROL_COLUMNS].to_numpy(dtype=float)
    kalman = LinearKalmanFilter(model)
    previous_control = None
    predictions = []

    for index in range(len(run) - 1):
        scaled_measurement = model.scale_measurement(measurements[index])
        kalman.process_measurement(scaled_measurement, previous_control)
        scaled_control = model.scale_control(controls[index])
        scaled_prediction = kalman.forecast(scaled_control)
        predictions.append(model.inverse_measurement(scaled_prediction))
        previous_control = scaled_control

    return measurements[1:], np.asarray(predictions), measurements[:-1], controls[:-1]


def calculate_metrics(
    model: TEPModel,
    actual: np.ndarray,
    prediction: np.ndarray,
) -> dict[str, float]:
    error = prediction - actual
    normalized_error = error / model.measurement_scale
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "nrmse": float(np.sqrt(np.mean(normalized_error**2))),
    }


def save_figure(fig: plt.Figure, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_DIR / filename, facecolor="white")
    plt.close(fig)


def plot_architecture() -> None:
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.2)
    ax.axis("off")

    boxes = [
        (0.35, 3.25, 2.05, 1.1, "Dane TEP", "41 pomiarów\n11 wejść"),
        (3.05, 3.25, 2.15, 1.1, "Symulator", "replay lub\nclosed-loop"),
        (5.9, 3.25, 2.15, 1.1, "PostgreSQL", "historia, prognozy,\nsterowania"),
        (8.75, 3.25, 2.15, 1.1, "MQTT", "zdarzenia o nowych\npróbkach"),
        (8.75, 0.85, 2.15, 1.25, "Kontroler", "Kalman + prognoza\n+ MPC"),
        (5.9, 0.85, 2.15, 1.25, "Wyniki", "MAE, RMSE, NRMSE\ni ograniczone u"),
    ]
    for x, y, width, height, title, subtitle in boxes:
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            linewidth=1.4,
            edgecolor=BLUE,
            facecolor=LIGHT_BLUE,
        )
        ax.add_patch(patch)
        ax.text(x + width / 2, y + height * 0.68, title, ha="center", va="center", fontsize=12, weight="bold", color="#173B63")
        ax.text(x + width / 2, y + height * 0.30, subtitle, ha="center", va="center", fontsize=9, color="#31485F")

    arrows = [
        ((2.4, 3.8), (3.05, 3.8)),
        ((5.2, 3.8), (5.9, 3.8)),
        ((8.05, 3.8), (8.75, 3.8)),
        ((9.83, 3.25), (9.83, 2.1)),
        ((8.75, 1.48), (8.05, 1.48)),
        ((6.98, 2.1), (6.98, 3.25)),
    ]
    for start, end in arrows:
        ax.add_patch(
            FancyArrowPatch(
                start,
                end,
                arrowstyle="-|>",
                mutation_scale=14,
                linewidth=1.6,
                color=GRAY,
            )
        )

    ax.text(10.08, 2.65, "identyfikator próbki", fontsize=8.2, color=GRAY, rotation=90, va="center")
    ax.set_title("Architektura przepływu danych w projekcie", fontsize=16, weight="bold", color="#173B63", pad=16)
    save_figure(fig, "01_architektura.png")


def plot_selected_series(run: pd.DataFrame) -> None:
    selected = [
        ("xmeas_1", "Pomiar 1"),
        ("xmeas_7", "Pomiar 7"),
        ("xmeas_21", "Pomiar 21"),
    ]
    subset = run.head(300)
    fig, axes = plt.subplots(3, 1, figsize=(11, 7.5), sharex=True)
    for axis, (column, label) in zip(axes, selected):
        axis.plot(subset["sample"], subset[column], color=BLUE, linewidth=1.3)
        axis.set_ylabel(label)
        autocorrelation = subset[column].autocorr(lag=1)
        axis.set_title(f"{column}: autokorelacja dla opóźnienia 1 = {autocorrelation:.3f}", loc="left", fontsize=10.5)
    axes[-1].set_xlabel("Numer próbki")
    fig.suptitle("Przykładowe szeregi czasowe procesu TEP", fontsize=15, weight="bold", color="#173B63")
    fig.tight_layout()
    save_figure(fig, "02_przykladowe_szeregi.png")


def plot_forecasts(
    run: pd.DataFrame,
    actual: np.ndarray,
    prediction: np.ndarray,
) -> None:
    selected = [0, 6, 20]
    labels = ["xmeas_1", "xmeas_7", "xmeas_21"]
    samples = run["sample"].to_numpy()[1:201]
    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    for axis, column_index, label in zip(axes, selected, labels):
        axis.plot(samples, actual[:200, column_index], label="wartość rzeczywista", color=BLUE, linewidth=1.5)
        axis.plot(samples, prediction[:200, column_index], label="prognoza na 1 krok", color=ORANGE, linewidth=1.25, alpha=0.9)
        axis.set_ylabel(label)
        axis.legend(loc="upper right", frameon=False, ncol=2)
    axes[-1].set_xlabel("Numer próbki")
    fig.suptitle("Wartości rzeczywiste i prognozowane", fontsize=15, weight="bold", color="#173B63")
    fig.tight_layout()
    save_figure(fig, "03_prognoza_vs_rzeczywistosc.png")


def plot_prediction_error(model: TEPModel, actual: np.ndarray, prediction: np.ndarray) -> None:
    normalized_error = (prediction - actual) / model.measurement_scale
    sample_nrmse = np.sqrt(np.mean(normalized_error**2, axis=1))
    rolling = pd.Series(sample_nrmse).rolling(25, min_periods=1).mean().to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(sample_nrmse, color="#8FB7D9", linewidth=0.8, label="błąd próbki")
    axes[0].plot(rolling, color=RED, linewidth=2.0, label="średnia krocząca (25)")
    axes[0].set_xlabel("Krok prognozy")
    axes[0].set_ylabel("NRMSE dla próbki")
    axes[0].legend(frameon=False)
    axes[0].set_title("Zmiana błędu w czasie")

    axes[1].hist(sample_nrmse, bins=35, color=BLUE, alpha=0.8, edgecolor="white")
    axes[1].axvline(np.mean(sample_nrmse), color=RED, linewidth=2, label=f"średnia = {np.mean(sample_nrmse):.3f}")
    axes[1].set_xlabel("NRMSE dla próbki")
    axes[1].set_ylabel("Liczba wystąpień")
    axes[1].legend(frameon=False)
    axes[1].set_title("Rozkład błędu")
    fig.suptitle("Analiza błędu prognozy na jeden krok", fontsize=15, weight="bold", color="#173B63")
    fig.tight_layout()
    save_figure(fig, "04_blad_prognozy.png")


def plot_metric_comparison(metrics: list[dict[str, float]]) -> None:
    runs = [int(row["run"]) for row in metrics]
    model_values = [row["model_nrmse"] for row in metrics]
    naive_values = [row["naive_nrmse"] for row in metrics]
    positions = np.arange(len(runs))
    width = 0.37

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.bar(positions - width / 2, model_values, width, label="model stanowy + Kalman", color=BLUE)
    ax.bar(positions + width / 2, naive_values, width, label="prognoza naiwna", color="#BFC7D1")
    ax.set_xticks(positions, [str(run) for run in runs])
    ax.set_xlabel("simulationRun")
    ax.set_ylabel("NRMSE")
    ax.set_title("Porównanie jakości prognoz dla niezależnych przebiegów", fontsize=15, weight="bold", color="#173B63")
    ax.legend(frameon=False)
    ax.set_ylim(0, max(naive_values) * 1.15)
    improvement = 100 * (np.mean(naive_values) - np.mean(model_values)) / np.mean(naive_values)
    ax.text(0.99, 0.96, f"Średnia poprawa NRMSE: {improvement:.1f}%", transform=ax.transAxes, ha="right", va="top", fontsize=11, color=GREEN, weight="bold")
    fig.tight_layout()
    save_figure(fig, "05_model_vs_naiwny.png")


def calculate_mpc_recommendations(
    model: TEPModel,
    run: pd.DataFrame,
    steps: int = 120,
) -> tuple[np.ndarray, np.ndarray]:
    measurements = run[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    recorded = run[CONTROL_COLUMNS].to_numpy(dtype=float)
    kalman = LinearKalmanFilter(model)
    mpc = LinearMPC(model)
    previous_process_input = None
    previous_mpc_control = None
    recommendations = []

    for index in range(min(steps, len(run) - 1)):
        state = kalman.process_measurement(
            model.scale_measurement(measurements[index]),
            previous_process_input,
        )
        scaled_recommendation = mpc.make_step(state, previous_mpc_control)
        recommendation = np.clip(
            model.inverse_control(scaled_recommendation),
            model.control_lower,
            model.control_upper,
        )
        recommendations.append(recommendation)
        previous_process_input = model.scale_control(recorded[index])
        previous_mpc_control = scaled_recommendation

    return recorded[: len(recommendations)], np.asarray(recommendations)


def plot_mpc_controls(
    model: TEPModel,
    recorded: np.ndarray,
    recommended: np.ndarray,
) -> None:
    selected = [0, 1, 6, 7]
    labels = ["xmv_1 / u1", "xmv_2 / u2", "xmv_7 / u7", "xmv_8 / u8"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True)
    for axis, index, label in zip(axes.ravel(), selected, labels):
        axis.plot(recorded[:, index], color=GRAY, linewidth=1.15, label="wejście zapisane w TEP")
        axis.plot(recommended[:, index], color=ORANGE, linewidth=1.45, label="rekomendacja MPC")
        axis.axhspan(model.control_lower[index], model.control_upper[index], color=LIGHT_BLUE, alpha=0.45, label="dopuszczalny zakres")
        axis.set_title(label)
        axis.set_ylabel("wartość sterowania")
    axes[1, 0].set_xlabel("Numer próbki")
    axes[1, 1].set_xlabel("Numer próbki")
    handles, legend_labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Rzeczywiste wejścia procesu i rekomendacje MPC", fontsize=15, weight="bold", color="#173B63")
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    save_figure(fig, "06_sterowania_mpc.png")


def simulate_closed_loop(model: TEPModel, steps: int = 80) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    initial_state = np.zeros(model.n_states)
    initial_state[:5] = np.array([3.0, -2.0, 2.5, -1.5, 2.0])
    controlled_state = initial_state.copy()
    uncontrolled_state = initial_state.copy()
    controller = LinearMPC(model)
    previous_control = np.zeros(model.n_controls)
    controlled_norm = []
    uncontrolled_norm = []
    controls = []

    for _ in range(steps):
        scaled_control = controller.make_step(controlled_state, previous_control)
        controlled_state = model.A @ controlled_state + model.B @ scaled_control
        uncontrolled_state = model.A @ uncontrolled_state
        controlled_norm.append(np.sqrt(np.mean((model.C @ controlled_state) ** 2)))
        uncontrolled_norm.append(np.sqrt(np.mean((model.C @ uncontrolled_state) ** 2)))
        controls.append(scaled_control)
        previous_control = scaled_control

    return np.asarray(controlled_norm), np.asarray(uncontrolled_norm), np.asarray(controls)


def plot_closed_loop(model: TEPModel) -> None:
    controlled, uncontrolled, controls = simulate_closed_loop(model)
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [1.3, 1]})
    axes[0].plot(controlled, color=GREEN, linewidth=2, label="z MPC")
    axes[0].plot(uncontrolled, color=GRAY, linewidth=1.5, linestyle="--", label="bez korekty sterowania")
    axes[0].set_ylabel("RMS wyjść w skali standaryzowanej")
    axes[0].set_title("Wygaszanie przykładowego zaburzenia")
    axes[0].legend(frameon=False)

    for index, color in zip([0, 1, 6, 7], [BLUE, ORANGE, GREEN, RED]):
        physical = controls[:, index] * model.control_scale[index] + model.control_mean[index]
        axes[1].plot(physical, label=f"u{index + 1}", color=color, linewidth=1.3)
    axes[1].set_xlabel("Krok symulacji")
    axes[1].set_ylabel("Sterowanie MPC")
    axes[1].set_title("Wybrane sterowania w pętli zamkniętej")
    axes[1].legend(frameon=False, ncol=4)
    fig.suptitle("Demonstracja działania pętli zamkniętej", fontsize=15, weight="bold", color="#173B63")
    fig.tight_layout()
    save_figure(fig, "07_petla_zamknieta.png")


def write_results(metrics: list[dict[str, float]], model: TEPModel) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(metrics[0].keys())
    with (RESULTS_DIR / "metryki_przebiegow.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(metrics)

    average_model_nrmse = float(np.mean([row["model_nrmse"] for row in metrics]))
    average_naive_nrmse = float(np.mean([row["naive_nrmse"] for row in metrics]))
    summary = {
        "evaluated_runs": len(metrics),
        "average_model_nrmse": average_model_nrmse,
        "average_naive_nrmse": average_naive_nrmse,
        "nrmse_improvement_percent": 100 * (average_naive_nrmse - average_model_nrmse) / average_naive_nrmse,
        "average_model_mae": float(np.mean([row["model_mae"] for row in metrics])),
        "average_naive_mae": float(np.mean([row["naive_mae"] for row in metrics])),
        "pca_states": model.n_states,
        "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(model.A)))),
    }
    (RESULTS_DIR / "podsumowanie_wynikow.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    configure_style()
    model = load_model()
    testing = load_testing_data()
    run_ids = sorted(testing["simulationRun"].unique())[:10]
    metrics = []
    selected_run = testing[testing["simulationRun"] == run_ids[0]].copy()
    selected_actual = selected_prediction = None

    for run_id in run_ids:
        run = testing[testing["simulationRun"] == run_id].copy()
        actual, prediction, naive, _ = forecast_run(model, run)
        model_metrics = calculate_metrics(model, actual, prediction)
        naive_metrics = calculate_metrics(model, actual, naive)
        metrics.append(
            {
                "run": int(run_id),
                "model_nrmse": model_metrics["nrmse"],
                "naive_nrmse": naive_metrics["nrmse"],
                "model_mae": model_metrics["mae"],
                "naive_mae": naive_metrics["mae"],
                "model_rmse": model_metrics["rmse"],
                "naive_rmse": naive_metrics["rmse"],
            }
        )
        if run_id == run_ids[0]:
            selected_actual = actual
            selected_prediction = prediction

    if selected_actual is None or selected_prediction is None:
        raise RuntimeError("No testing run was available")

    plot_architecture()
    plot_selected_series(selected_run)
    plot_forecasts(selected_run, selected_actual, selected_prediction)
    plot_prediction_error(model, selected_actual, selected_prediction)
    plot_metric_comparison(metrics)
    recorded, recommended = calculate_mpc_recommendations(model, selected_run)
    plot_mpc_controls(model, recorded, recommended)
    plot_closed_loop(model)
    write_results(metrics, model)

    print(f"Generated {len(list(OUTPUT_DIR.glob('*.png')))} figures in {OUTPUT_DIR}")
    print(f"Saved metric files in {RESULTS_DIR}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Visualization generation failed: {error}", file=sys.stderr)
        raise
