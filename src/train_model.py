import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadr

from kalman_filter import LinearKalmanFilter
from model_artifact import TEPModel
from settings import DATA_DIR, MODEL_PATH


MEASUREMENT_COLUMNS = [f"xmeas_{index}" for index in range(1, 42)]
CONTROL_COLUMNS = [f"xmv_{index}" for index in range(1, 12)]


def load_rdata(path: Path, object_name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.DataFrame(pyreadr.read_r(str(path))[object_name])


def fit_model(training_data: pd.DataFrame, n_states: int = 20) -> TEPModel:
    measurements = training_data[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    controls = training_data[CONTROL_COLUMNS].to_numpy(dtype=float)

    measurement_mean = measurements.mean(axis=0)
    measurement_scale = measurements.std(axis=0)
    control_mean = controls.mean(axis=0)
    control_scale = controls.std(axis=0)
    measurement_scale[measurement_scale < 1e-12] = 1.0
    control_scale[control_scale < 1e-12] = 1.0

    scaled_measurements = (measurements - measurement_mean) / measurement_scale
    scaled_controls = (controls - control_mean) / control_scale

    covariance = scaled_measurements.T @ scaled_measurements
    covariance /= max(len(scaled_measurements) - 1, 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1][:n_states]
    components = eigenvectors[:, order].T
    states = scaled_measurements @ components.T

    run_ids = training_data["simulationRun"].to_numpy()
    valid_transition = run_ids[1:] == run_ids[:-1]
    features = np.hstack(
        [states[:-1][valid_transition], scaled_controls[:-1][valid_transition]]
    )
    targets = states[1:][valid_transition]

    ridge = 1e-4
    gram = features.T @ features + ridge * np.eye(features.shape[1])
    coefficients = np.linalg.solve(gram, features.T @ targets)
    A = coefficients[:n_states].T
    B = coefficients[n_states:].T

    spectral_radius = float(np.max(np.abs(np.linalg.eigvals(A))))
    if spectral_radius >= 0.999:
        A *= 0.995 / spectral_radius

    C = components.T
    D = np.zeros((len(MEASUREMENT_COLUMNS), len(CONTROL_COLUMNS)))

    state_residuals = targets - features @ coefficients
    process_noise = np.cov(state_residuals, rowvar=False)
    process_noise += np.eye(n_states) * 1e-6

    reconstructed_measurements = states @ components
    measurement_residuals = scaled_measurements - reconstructed_measurements
    measurement_noise = np.cov(measurement_residuals, rowvar=False)
    measurement_noise += np.eye(len(MEASUREMENT_COLUMNS)) * 1e-4

    control_lower = training_data[CONTROL_COLUMNS].quantile(0.005).to_numpy(float)
    control_upper = training_data[CONTROL_COLUMNS].quantile(0.995).to_numpy(float)

    return TEPModel(
        A=A,
        B=B,
        C=C,
        D=D,
        process_noise=process_noise,
        measurement_noise=measurement_noise,
        measurement_mean=measurement_mean,
        measurement_scale=measurement_scale,
        control_mean=control_mean,
        control_scale=control_scale,
        control_lower=control_lower,
        control_upper=control_upper,
    )


def save_model(model: TEPModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        A=model.A,
        B=model.B,
        C=model.C,
        D=model.D,
        process_noise=model.process_noise,
        measurement_noise=model.measurement_noise,
        measurement_mean=model.measurement_mean,
        measurement_scale=model.measurement_scale,
        control_mean=model.control_mean,
        control_scale=model.control_scale,
        control_lower=model.control_lower,
        control_upper=model.control_upper,
    )


def evaluate_model(model: TEPModel, testing_data: pd.DataFrame, runs: int) -> None:
    print("\nOne-step forecast evaluation")
    print("run | model NRMSE | naive NRMSE | model MAE | naive MAE")
    for run_id in sorted(testing_data["simulationRun"].unique())[:runs]:
        run = testing_data[testing_data["simulationRun"] == run_id]
        measurements = run[MEASUREMENT_COLUMNS].to_numpy(float)
        controls = run[CONTROL_COLUMNS].to_numpy(float)
        kalman = LinearKalmanFilter(model)
        previous_control = None
        predictions = []

        for index in range(len(run) - 1):
            scaled_measurement = model.scale_measurement(measurements[index])
            kalman.process_measurement(scaled_measurement, previous_control)
            scaled_control = model.scale_control(controls[index])
            prediction = kalman.forecast(scaled_control)
            predictions.append(model.inverse_measurement(prediction))
            previous_control = scaled_control

        predictions = np.asarray(predictions)
        actual = measurements[1:]
        naive = measurements[:-1]
        normalized_error = (predictions - actual) / model.measurement_scale
        naive_normalized_error = (naive - actual) / model.measurement_scale
        model_nrmse = np.sqrt(np.mean(normalized_error**2))
        naive_nrmse = np.sqrt(np.mean(naive_normalized_error**2))
        model_mae = np.mean(np.abs(predictions - actual))
        naive_mae = np.mean(np.abs(naive - actual))
        print(
            f"{int(run_id):3d} | {model_nrmse:11.4f} | {naive_nrmse:11.4f} "
            f"| {model_mae:9.4f} | {naive_mae:9.4f}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the TEP state-space model")
    parser.add_argument("--states", type=int, default=20)
    parser.add_argument("--evaluation-runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=MODEL_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    training_data = load_rdata(
        DATA_DIR / "TEP_FaultFree_Training.RData", "fault_free_training"
    )
    model = fit_model(training_data, n_states=args.states)
    save_model(model, args.output)

    measurements = training_data[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    scaled_measurements = model.scale_measurement(measurements)
    covariance = np.cov(scaled_measurements, rowvar=False)
    explained = np.trace(model.C.T @ covariance @ model.C) / np.trace(covariance)
    spectral_radius = np.max(np.abs(np.linalg.eigvals(model.A)))
    print(f"Saved model to: {args.output}")
    print(f"States: {model.n_states}")
    print(f"Spectral radius(A): {spectral_radius:.4f}")
    print(f"PCA explained variance: {explained:.4f}")

    if args.evaluation_runs > 0:
        testing_data = load_rdata(
            DATA_DIR / "TEP_FaultFree_Testing.RData", "fault_free_testing"
        )
        evaluate_model(model, testing_data, args.evaluation_runs)


if __name__ == "__main__":
    main()
