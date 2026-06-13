import argparse
import json
import threading
import time

import numpy as np
import pandas as pd
import pyreadr
from sqlalchemy import text

from database import (
    MEASUREMENT_COLUMNS,
    PROCESS_INPUT_COLUMNS,
    create_database_engine,
    vector_parameters,
)
from mqtt_config import (
    TOPIC_CONTROL_INPUTS,
    TOPIC_SENSORS_OUTPUTS,
    connect_mqtt_client,
    create_mqtt_client,
)
from settings import DATA_DIR
from model_artifact import load_model


DATASETS = {
    "fault-free-testing": (
        "TEP_FaultFree_Testing.RData",
        "fault_free_testing",
    ),
    "fault-free-training": (
        "TEP_FaultFree_Training.RData",
        "fault_free_training",
    ),
}


def load_run(dataset_name: str, simulation_run: int) -> pd.DataFrame:
    filename, object_name = DATASETS[dataset_name]
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    frame = pd.DataFrame(pyreadr.read_r(str(path))[object_name])
    run = frame[frame["simulationRun"] == simulation_run].copy()
    if run.empty:
        raise ValueError(f"Simulation run {simulation_run} is not present in {filename}")
    return run.sort_values("sample")


def create_simulation_run(
    engine,
    dataset_name: str,
    source_run: int,
    mode: str,
) -> int:
    with engine.begin() as connection:
        return connection.execute(
            text(
                """
                INSERT INTO simulation_runs (mode, dataset, source_simulation_run)
                VALUES (:mode, :dataset, :source_run)
                RETURNING id
                """
            ),
            {"mode": mode, "dataset": dataset_name, "source_run": source_run},
        ).scalar_one()


def insert_sample(engine, run_id: int, row: pd.Series) -> int:
    measurement_names = ", ".join(MEASUREMENT_COLUMNS)
    measurement_values = ", ".join(f":{name}" for name in MEASUREMENT_COLUMNS)
    input_names = ", ".join(PROCESS_INPUT_COLUMNS)
    input_values = ", ".join(f":{name}" for name in PROCESS_INPUT_COLUMNS)

    measurement = row[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    process_input = row[PROCESS_INPUT_COLUMNS].to_numpy(dtype=float)
    parameters = {
        "run_id": run_id,
        "sample": int(row["sample"]),
        **vector_parameters(MEASUREMENT_COLUMNS, measurement),
    }

    with engine.begin() as connection:
        sensor_data_id = connection.execute(
            text(
                f"""
                INSERT INTO sensor_data (run_id, sample, {measurement_names})
                VALUES (:run_id, :sample, {measurement_values})
                RETURNING id
                """
            ),
            parameters,
        ).scalar_one()
        connection.execute(
            text(
                f"""
                INSERT INTO process_inputs (sensor_data_id, {input_names})
                VALUES (:sensor_data_id, {input_values})
                """
            ),
            {
                "sensor_data_id": sensor_data_id,
                **vector_parameters(PROCESS_INPUT_COLUMNS, process_input),
            },
        )
    return sensor_data_id


def set_run_status(engine, run_id: int, status: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE simulation_runs
                SET status = :status, completed_at = CURRENT_TIMESTAMP
                WHERE id = :run_id
                """
            ),
            {"status": status, "run_id": run_id},
        )


def start_replay(
    dataset_name: str,
    simulation_run: int,
    interval: float,
    limit: int | None,
) -> None:
    run = load_run(dataset_name, simulation_run)
    if limit is not None:
        run = run.head(limit)

    engine = create_database_engine()
    mqtt_client = create_mqtt_client("plant_simulator")
    connect_mqtt_client(mqtt_client)
    mqtt_client.loop_start()

    run_id = create_simulation_run(engine, dataset_name, simulation_run, "replay")
    status = "completed"
    print(
        f"Starting replay run {run_id}: dataset={dataset_name}, "
        f"source_run={simulation_run}, samples={len(run)}"
    )

    try:
        for position, (_, row) in enumerate(run.iterrows(), start=1):
            sensor_data_id = insert_sample(engine, run_id, row)
            payload = json.dumps(
                {
                    "run_id": run_id,
                    "sensor_data_id": sensor_data_id,
                    "sample": int(row["sample"]),
                }
            )
            publish_result = mqtt_client.publish(TOPIC_SENSORS_OUTPUTS, payload)
            publish_result.wait_for_publish()
            print(f"Published sample {position}/{len(run)} (id={sensor_data_id})")
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        status = "stopped"
        print("Replay stopped by user")
    except Exception:
        status = "failed"
        raise
    finally:
        set_run_status(engine, run_id, status)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        engine.dispose()


def start_closed_loop(
    dataset_name: str,
    simulation_run: int,
    interval: float,
    limit: int | None,
) -> None:
    source_run = load_run(dataset_name, simulation_run)
    steps = limit or len(source_run)
    initial_row = source_run.iloc[0]
    model = load_model()
    initial_measurement = initial_row[MEASUREMENT_COLUMNS].to_numpy(dtype=float)
    current_control = initial_row[PROCESS_INPUT_COLUMNS].to_numpy(dtype=float)
    state, *_ = np.linalg.lstsq(
        model.C,
        model.scale_measurement(initial_measurement),
        rcond=None,
    )

    engine = create_database_engine()
    mqtt_client = create_mqtt_client("closed_loop_plant")
    received_controls: dict[int, np.ndarray] = {}
    condition = threading.Condition()

    def on_control(client, userdata, message):
        event = json.loads(message.payload.decode("utf-8"))
        if event.get("skipped"):
            return
        with condition:
            received_controls[int(event["sensor_data_id"])] = np.asarray(
                event["control"], dtype=float
            )
            condition.notify_all()

    mqtt_client.on_message = on_control
    connect_mqtt_client(mqtt_client)
    mqtt_client.subscribe(TOPIC_CONTROL_INPUTS)
    mqtt_client.loop_start()

    run_id = create_simulation_run(
        engine, dataset_name, simulation_run, "closed-loop"
    )
    status = "completed"
    measurement = initial_measurement
    print(
        f"Starting closed-loop run {run_id}: source_run={simulation_run}, "
        f"steps={steps}"
    )

    try:
        for sample in range(1, steps + 1):
            row = pd.Series(
                {
                    "sample": sample,
                    **dict(zip(MEASUREMENT_COLUMNS, measurement)),
                    **dict(zip(PROCESS_INPUT_COLUMNS, current_control)),
                }
            )
            sensor_data_id = insert_sample(engine, run_id, row)
            payload = json.dumps(
                {
                    "run_id": run_id,
                    "sensor_data_id": sensor_data_id,
                    "sample": sample,
                }
            )
            mqtt_client.publish(TOPIC_SENSORS_OUTPUTS, payload).wait_for_publish()

            with condition:
                received = condition.wait_for(
                    lambda: sensor_data_id in received_controls,
                    timeout=15.0,
                )
                if not received:
                    raise TimeoutError(
                        f"No MPC control received for sensor row {sensor_data_id}"
                    )
                current_control = received_controls.pop(sensor_data_id)

            scaled_control = model.scale_control(current_control)
            state = model.A @ state + model.B @ scaled_control
            measurement = model.inverse_measurement(model.C @ state)
            print(f"Completed closed-loop step {sample}/{steps}")
            if interval > 0:
                time.sleep(interval)
    except KeyboardInterrupt:
        status = "stopped"
        print("Closed-loop simulation stopped by user")
    except Exception:
        status = "failed"
        raise
    finally:
        set_run_status(engine, run_id, status)
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        engine.dispose()


def start_plant_simulator(
    mode: str,
    dataset_name: str,
    simulation_run: int,
    interval: float,
    limit: int | None,
) -> None:
    if mode == "closed-loop":
        start_closed_loop(dataset_name, simulation_run, interval, limit)
    else:
        start_replay(dataset_name, simulation_run, interval, limit)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay a Tennessee Eastman run")
    parser.add_argument("--mode", choices=["replay", "closed-loop"], default="replay")
    parser.add_argument(
        "--dataset",
        choices=sorted(DATASETS),
        default="fault-free-testing",
    )
    parser.add_argument("--simulation-run", type=int, default=1)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    start_plant_simulator(
        mode=arguments.mode,
        dataset_name=arguments.dataset,
        simulation_run=arguments.simulation_run,
        interval=arguments.interval,
        limit=arguments.limit,
    )
