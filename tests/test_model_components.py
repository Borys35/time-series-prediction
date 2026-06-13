import sys
import unittest
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kalman_filter import LinearKalmanFilter
from model_artifact import load_model
from mpc_setup import LinearMPC


class ModelComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = load_model()

    def test_model_dimensions(self):
        self.assertEqual(self.model.A.shape, (20, 20))
        self.assertEqual(self.model.B.shape, (20, 11))
        self.assertEqual(self.model.C.shape, (41, 20))
        self.assertLess(np.max(np.abs(np.linalg.eigvals(self.model.A))), 1.0)

    def test_scaling_round_trip(self):
        measurements = self.model.measurement_mean + self.model.measurement_scale
        controls = self.model.control_mean - 0.5 * self.model.control_scale
        np.testing.assert_allclose(
            self.model.inverse_measurement(self.model.scale_measurement(measurements)),
            measurements,
        )
        np.testing.assert_allclose(
            self.model.inverse_control(self.model.scale_control(controls)),
            controls,
        )

    def test_kalman_forecast_is_finite(self):
        kalman = LinearKalmanFilter(self.model)
        measurement = np.zeros(self.model.n_measurements)
        control = np.zeros(self.model.n_controls)
        state = kalman.process_measurement(measurement, None)
        forecast = kalman.forecast(control)
        self.assertTrue(np.isfinite(state).all())
        self.assertTrue(np.isfinite(forecast).all())

    def test_mpc_respects_control_bounds(self):
        mpc = LinearMPC(self.model, horizon=4)
        scaled_control = mpc.make_step(np.zeros(self.model.n_states))
        control = self.model.inverse_control(scaled_control)
        self.assertTrue(mpc.last_success)
        self.assertTrue(np.all(control >= self.model.control_lower - 1e-8))
        self.assertTrue(np.all(control <= self.model.control_upper + 1e-8))


if __name__ == "__main__":
    unittest.main()
