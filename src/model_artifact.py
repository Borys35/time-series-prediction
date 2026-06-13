from dataclasses import dataclass
from pathlib import Path

import numpy as np

from settings import MODEL_PATH


@dataclass(frozen=True)
class TEPModel:
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    D: np.ndarray
    process_noise: np.ndarray
    measurement_noise: np.ndarray
    measurement_mean: np.ndarray
    measurement_scale: np.ndarray
    control_mean: np.ndarray
    control_scale: np.ndarray
    control_lower: np.ndarray
    control_upper: np.ndarray

    @property
    def n_states(self) -> int:
        return self.A.shape[0]

    @property
    def n_measurements(self) -> int:
        return self.C.shape[0]

    @property
    def n_controls(self) -> int:
        return self.B.shape[1]

    def scale_measurement(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        return (values - self.measurement_mean) / self.measurement_scale

    def inverse_measurement(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        return values * self.measurement_scale + self.measurement_mean

    def scale_control(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        return (values - self.control_mean) / self.control_scale

    def inverse_control(self, values: np.ndarray) -> np.ndarray:
        values = np.asarray(values, dtype=float)
        return values * self.control_scale + self.control_mean


def load_model(path: Path | str = MODEL_PATH) -> TEPModel:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Model artifact not found at {path}. Run: python src/train_model.py"
        )

    with np.load(path) as data:
        return TEPModel(
            A=data["A"],
            B=data["B"],
            C=data["C"],
            D=data["D"],
            process_noise=data["process_noise"],
            measurement_noise=data["measurement_noise"],
            measurement_mean=data["measurement_mean"],
            measurement_scale=data["measurement_scale"],
            control_mean=data["control_mean"],
            control_scale=data["control_scale"],
            control_lower=data["control_lower"],
            control_upper=data["control_upper"],
        )
