import numpy as np
from scipy.optimize import lsq_linear

from model_artifact import TEPModel, load_model


class LinearMPC:
    def __init__(
        self,
        model: TEPModel,
        horizon: int = 8,
        control_weight: float = 0.2,
        change_weight: float = 0.5,
    ):
        self.model = model
        self.horizon = horizon
        self.control_weight = control_weight
        self.change_weight = change_weight
        self.last_success = True
        self._build_prediction_matrices()

    def _build_prediction_matrices(self) -> None:
        n_x = self.model.n_states
        n_y = self.model.n_measurements
        n_u = self.model.n_controls
        horizon = self.horizon

        self.free_response = np.zeros((horizon * n_y, n_x))
        self.control_response = np.zeros((horizon * n_y, horizon * n_u))

        for step in range(horizon):
            row = slice(step * n_y, (step + 1) * n_y)
            self.free_response[row] = self.model.C @ np.linalg.matrix_power(
                self.model.A, step + 1
            )
            for control_step in range(step + 1):
                column = slice(control_step * n_u, (control_step + 1) * n_u)
                transition = np.linalg.matrix_power(
                    self.model.A, step - control_step
                )
                self.control_response[row, column] = (
                    self.model.C @ transition @ self.model.B
                )

        self.control_difference = np.zeros((horizon * n_u, horizon * n_u))
        for step in range(horizon):
            row = slice(step * n_u, (step + 1) * n_u)
            self.control_difference[row, row] = np.eye(n_u)
            if step > 0:
                previous = slice((step - 1) * n_u, step * n_u)
                self.control_difference[row, previous] = -np.eye(n_u)

        lower = self.model.scale_control(self.model.control_lower)
        upper = self.model.scale_control(self.model.control_upper)
        self.lower_bounds = np.tile(lower, horizon)
        self.upper_bounds = np.tile(upper, horizon)

    def make_step(
        self,
        state: np.ndarray,
        previous_control: np.ndarray | None = None,
    ) -> np.ndarray:
        state = np.asarray(state, dtype=float).reshape(-1)
        n_u = self.model.n_controls
        if previous_control is None:
            previous_control = np.zeros(n_u)
        previous_control = np.asarray(previous_control, dtype=float).reshape(-1)

        control_penalty = np.sqrt(self.control_weight) * np.eye(
            self.horizon * n_u
        )
        change_penalty = np.sqrt(self.change_weight) * self.control_difference
        matrix = np.vstack(
            [self.control_response, control_penalty, change_penalty]
        )

        target_changes = np.concatenate(
            [previous_control, np.zeros((self.horizon - 1) * n_u)]
        )
        target = np.concatenate(
            [
                -self.free_response @ state,
                np.zeros(self.horizon * n_u),
                np.sqrt(self.change_weight) * target_changes,
            ]
        )

        solution = lsq_linear(
            matrix,
            target,
            bounds=(self.lower_bounds, self.upper_bounds),
            lsmr_tol="auto",
            max_iter=100,
        )
        self.last_success = bool(solution.success)
        return solution.x[:n_u].reshape(-1)


def create_mpc(model: TEPModel | None = None) -> LinearMPC:
    return LinearMPC(model or load_model())
