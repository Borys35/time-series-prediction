import numpy as np

from model_artifact import TEPModel


class LinearKalmanFilter:
    def __init__(self, model: TEPModel):
        self.model = model
        self.state: np.ndarray | None = None
        self.covariance = np.eye(model.n_states)

    def initialize(self, measurement: np.ndarray) -> np.ndarray:
        measurement = np.asarray(measurement, dtype=float).reshape(-1)
        state, *_ = np.linalg.lstsq(self.model.C, measurement, rcond=None)
        self.state = state
        self.covariance = np.eye(self.model.n_states)
        return self.update(measurement)

    def predict(self, control: np.ndarray) -> np.ndarray:
        if self.state is None:
            raise RuntimeError("Kalman filter must be initialized before prediction")

        control = np.asarray(control, dtype=float).reshape(-1)
        self.state = self.model.A @ self.state + self.model.B @ control
        self.covariance = (
            self.model.A @ self.covariance @ self.model.A.T
            + self.model.process_noise
        )
        return self.state

    def update(self, measurement: np.ndarray) -> np.ndarray:
        if self.state is None:
            raise RuntimeError("Kalman filter must be initialized before update")

        measurement = np.asarray(measurement, dtype=float).reshape(-1)
        innovation = measurement - self.model.C @ self.state
        innovation_covariance = (
            self.model.C @ self.covariance @ self.model.C.T
            + self.model.measurement_noise
        )
        cross_covariance = self.covariance @ self.model.C.T
        gain = np.linalg.solve(innovation_covariance, cross_covariance.T).T

        self.state = self.state + gain @ innovation
        identity = np.eye(self.model.n_states)
        update_matrix = identity - gain @ self.model.C
        self.covariance = (
            update_matrix @ self.covariance @ update_matrix.T
            + gain @ self.model.measurement_noise @ gain.T
        )
        return self.state

    def process_measurement(
        self,
        measurement: np.ndarray,
        previous_control: np.ndarray | None,
    ) -> np.ndarray:
        if self.state is None:
            return self.initialize(measurement)

        if previous_control is None:
            raise ValueError("Previous control is required after initialization")

        self.predict(previous_control)
        return self.update(measurement)

    def forecast(self, control: np.ndarray) -> np.ndarray:
        if self.state is None:
            raise RuntimeError("Kalman filter must be initialized before forecasting")

        control = np.asarray(control, dtype=float).reshape(-1)
        next_state = self.model.A @ self.state + self.model.B @ control
        return self.model.C @ next_state + self.model.D @ control
