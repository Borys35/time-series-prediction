# TEP Time-Series Prediction and MPC

This project demonstrates time-series analysis, one-step forecasting, Kalman
state estimation and Model Predictive Control for the Tennessee Eastman
Process (TEP). PostgreSQL stores measurements and results, while MQTT carries
events between the process simulator and controller.

## Main components

- A 20-state linear model trained from fault-free TEP runs.
- PCA-based state representation and a Kalman filter.
- One-step forecasts evaluated with MAE, RMSE and normalized RMSE.
- A finite-horizon MPC with control limits learned from training data.
- Historical replay and model-based closed-loop simulation modes.
- PostgreSQL tables for runs, measurements, process inputs, forecasts and MPC
  controls.

The old notebook in `notebooks/` is kept as the initial experiment. Runtime
code uses `models/tep_state_space_model.npz`, which also contains scaling and
noise parameters missing from the original model file.

## Requirements

- Python 3.11 or newer
- Docker Desktop with Docker Compose
- TEP `.RData` files placed locally in `datasets/tep/`

The `datasets/` directory is intentionally ignored by Git because the source
files are large. Create `datasets/tep/` after cloning the repository and put
the files there using these exact names:

```text
datasets/tep/TEP_FaultFree_Training.RData
datasets/tep/TEP_FaultFree_Testing.RData
datasets/tep/TEP_Faulty_Training.RData
datasets/tep/TEP_Faulty_Testing.RData
```

The current application and visualizations use the two `FaultFree` files.
The `Faulty` files are kept for a possible anomaly-detection extension.

## Quick start on Windows

Create a virtual environment and install the runtime dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Optional notebook dependencies are in `requirements-notebook.txt`.

Start PostgreSQL and Mosquitto:

```powershell
docker compose up -d
docker compose ps
```

On the first start, wait until PostgreSQL finishes initializing. Its status
can be checked with:

```powershell
docker compose logs -f postgres
```

Continue when the log contains `database system is ready to accept
connections`. Stop following the log with `Ctrl+C`; the container will keep
running.

Open a second PowerShell terminal, activate the environment and start the
controller:

```powershell
.\.venv\Scripts\Activate.ps1
python src/controller_node.py
```

The expected message is `Controller is listening for sensor samples...`.

Open a third terminal and run a short historical replay:

```powershell
.\.venv\Scripts\Activate.ps1
python src/plant_simulator.py --mode replay --simulation-run 1 --limit 20 --interval 0.05
```

The simulator writes samples to PostgreSQL, publishes MQTT events and lets
the controller calculate forecasts and MPC recommendations. The trained model
in `models/tep_state_space_model.npz` is committed to the repository, so model
training is not required for this quick start.

Stop the controller with `Ctrl+C`, then stop the infrastructure with:

```powershell
docker compose down
```

## Train and evaluate the model

A trained artifact is committed to the repository. It can be rebuilt from the
fault-free training set:

```powershell
python src/train_model.py --evaluation-runs 5
```

The command evaluates one-step forecasts on independent testing runs and
compares them with the naive forecast: next value equals current value.

Basic analysis of selected time series can be run without visualizations:

```powershell
python src/analyze_time_series.py --simulation-run 1
```

Generate the presentation-ready plots and refresh the evaluation summary:

```powershell
python src/generate_visualizations.py
```

The figures are written to `artifacts/visualizations/`, while numerical
results are stored in `artifacts/results/`.

## Application modes

If a Docker volume created by the older database schema already exists, reset
it once. This deletes data in that local project volume:

```powershell
docker compose down -v
docker compose up -d
```

### Historical replay

Replay one real testing run after starting the controller:

```powershell
python src/plant_simulator.py --mode replay --simulation-run 1
```

For a short, fast test:

```powershell
python src/plant_simulator.py --mode replay --simulation-run 1 --limit 20 --interval 0.05
```

In replay mode, recorded TEP inputs are used for forecasting. MPC controls are
recommendations and do not alter the historical measurements.

### Closed-loop simulation

To demonstrate actual feedback, use the identified linear model as the plant:

```powershell
python src/plant_simulator.py --mode closed-loop --simulation-run 1 --limit 100 --interval 0.1
```

The controller publishes an MPC action over MQTT and the simulator applies it
when calculating the next model state.

## Database tables

- `simulation_runs`: metadata and status of each replay or simulation.
- `sensor_data`: 41 process measurements for every sample.
- `process_inputs`: 11 recorded or applied process inputs.
- `predictions`: next-sample forecasts and their error metrics.
- `input_controls`: constrained controls recommended by MPC.

The legacy `db/tep_db_dump.sql` contains results from the previous schema and
is not imported automatically by Docker Compose.

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests cover model dimensions and stability, scaling round trips, Kalman
filter output and MPC control bounds.
