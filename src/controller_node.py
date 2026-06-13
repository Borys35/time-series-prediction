import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy import text

from database import (
    CONTROL_COLUMNS,
    MEASUREMENT_COLUMNS,
    PROCESS_INPUT_COLUMNS,
    create_database_engine,
    vector_from_row,
    vector_parameters,
)
from kalman_filter import LinearKalmanFilter
from model_artifact import TEPModel, load_model
from mpc_setup import LinearMPC
from mqtt_config import (
    TOPIC_CONTROL_INPUTS,
    TOPIC_SENSORS_OUTPUTS,
    connect_mqtt_client,
    create_mqtt_client,
)


@dataclass
class RunContext:
    kalman: LinearKalmanFilter
    previous_process_input: np.ndarray | None = None
    previous_mpc_control: np.ndarray | None = None
    last_sample: int = 0


def load_sample(connection, sensor_data_id: int):
    selected_measurements = ", ".join(f"s.{name}" for name in MEASUREMENT_COLUMNS)
    selected_inputs = ", ".join(f"p.{name}" for name in PROCESS_INPUT_COLUMNS)
    return connection.execute(
        text(
            f"""
            SELECT s.id, s.run_id, s.sample, r.mode,
                   {selected_measurements}, {selected_inputs}
            FROM sensor_data s
            JOIN process_inputs p ON p.sensor_data_id = s.id
            JOIN simulation_runs r ON r.id = s.run_id
            WHERE s.id = :sensor_data_id
            """
        ),
        {"sensor_data_id": sensor_data_id},
    ).mappings().first()


def evaluate_prediction(
    connection,
    model: TEPModel,
    run_id: int,
    sample: int,
    sensor_data_id: int,
    actual_measurement: np.ndarray,
) -> None:
    selected = ", ".join(MEASUREMENT_COLUMNS)
    prediction = connection.execute(
        text(
            f"""
            SELECT id, {selected}
            FROM predictions
            WHERE run_id = :run_id
              AND target_sample = :sample
              AND actual_sensor_data_id IS NULL
            """
        ),
        {"run_id": run_id, "sample": sample},
    ).mappings().first()
    if prediction is None:
        return

    predicted_measurement = vector_from_row(prediction, MEASUREMENT_COLUMNS)
    error = predicted_measurement - actual_measurement
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    normalized_rmse = float(
        np.sqrt(np.mean((error / model.measurement_scale) ** 2))
    )
    connection.execute(
        text(
            """
            UPDATE predictions
            SET actual_sensor_data_id = :sensor_data_id,
                evaluated_at = CURRENT_TIMESTAMP,
                mae = :mae,
                rmse = :rmse,
                normalized_rmse = :normalized_rmse
            WHERE id = :prediction_id
            """
        ),
        {
            "sensor_data_id": sensor_data_id,
            "mae": mae,
            "rmse": rmse,
            "normalized_rmse": normalized_rmse,
            "prediction_id": prediction["id"],
        },
    )


def save_prediction(
    connection,
    run_id: int,
    sensor_data_id: int,
    target_sample: int,
    prediction: np.ndarray,
) -> None:
    columns = ", ".join(MEASUREMENT_COLUMNS)
    values = ", ".join(f":{name}" for name in MEASUREMENT_COLUMNS)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in MEASUREMENT_COLUMNS)
    connection.execute(
        text(
            f"""
            INSERT INTO predictions (
                run_id, source_sensor_data_id, target_sample, {columns}
            )
            VALUES (:run_id, :source_sensor_data_id, :target_sample, {values})
            ON CONFLICT (source_sensor_data_id) DO UPDATE
            SET target_sample = EXCLUDED.target_sample, {updates}
            """
        ),
        {
            "run_id": run_id,
            "source_sensor_data_id": sensor_data_id,
            "target_sample": target_sample,
            **vector_parameters(MEASUREMENT_COLUMNS, prediction),
        },
    )


def save_control(
    connection,
    sensor_data_id: int,
    control: np.ndarray,
    optimization_success: bool,
) -> int:
    columns = ", ".join(CONTROL_COLUMNS)
    values = ", ".join(f":{name}" for name in CONTROL_COLUMNS)
    updates = ", ".join(f"{name} = EXCLUDED.{name}" for name in CONTROL_COLUMNS)
    return connection.execute(
        text(
            f"""
            INSERT INTO input_controls (
                sensor_data_id, optimization_success, {columns}
            )
            VALUES (:sensor_data_id, :optimization_success, {values})
            ON CONFLICT (sensor_data_id) DO UPDATE
            SET optimization_success = EXCLUDED.optimization_success, {updates}
            RETURNING id
            """
        ),
        {
            "sensor_data_id": sensor_data_id,
            "optimization_success": optimization_success,
            **vector_parameters(CONTROL_COLUMNS, control),
        },
    ).scalar_one()


def process_sample(
    engine,
    model: TEPModel,
    mpc: LinearMPC,
    contexts: dict[int, RunContext],
    sensor_data_id: int,
) -> dict:
    with engine.begin() as connection:
        sample_row = load_sample(connection, sensor_data_id)
        if sample_row is None:
            raise ValueError(f"Sensor data row {sensor_data_id} does not exist")

        run_id = int(sample_row["run_id"])
        sample = int(sample_row["sample"])
        context = contexts.setdefault(
            run_id, RunContext(kalman=LinearKalmanFilter(model))
        )
        if sample <= context.last_sample:
            return {"skipped": True, "run_id": run_id, "sample": sample}

        measurement = vector_from_row(sample_row, MEASUREMENT_COLUMNS)
        process_input = vector_from_row(sample_row, PROCESS_INPUT_COLUMNS)
        scaled_measurement = model.scale_measurement(measurement)
        scaled_process_input = model.scale_control(process_input)

        evaluate_prediction(
            connection,
            model,
            run_id,
            sample,
            sensor_data_id,
            measurement,
        )

        state = context.kalman.process_measurement(
            scaled_measurement,
            context.previous_process_input,
        )
        scaled_control = mpc.make_step(state, context.previous_mpc_control)
        control = model.inverse_control(scaled_control)
        control = np.clip(control, model.control_lower, model.control_upper)

        if sample_row["mode"] == "closed-loop":
            forecast_input = scaled_control
        else:
            forecast_input = scaled_process_input
        scaled_prediction = context.kalman.forecast(forecast_input)
        prediction = model.inverse_measurement(scaled_prediction)

        save_prediction(
            connection,
            run_id,
            sensor_data_id,
            sample + 1,
            prediction,
        )
        control_id = save_control(
            connection,
            sensor_data_id,
            control,
            mpc.last_success,
        )

        context.previous_process_input = forecast_input
        context.previous_mpc_control = scaled_control
        context.last_sample = sample

    return {
        "skipped": False,
        "run_id": run_id,
        "sample": sample,
        "sensor_data_id": sensor_data_id,
        "control_id": control_id,
        "optimization_success": mpc.last_success,
        "control": control.tolist(),
    }


def start_controller() -> None:
    model = load_model()
    mpc = LinearMPC(model)
    engine = create_database_engine()
    contexts: dict[int, RunContext] = {}
    client = create_mqtt_client("mpc_controller")

    def on_message(client, userdata, message):
        try:
            event = json.loads(message.payload.decode("utf-8"))
            result = process_sample(
                engine,
                model,
                mpc,
                contexts,
                int(event["sensor_data_id"]),
            )
            if result["skipped"]:
                print(
                    f"Skipped duplicate/out-of-order sample "
                    f"{result['run_id']}:{result['sample']}"
                )
                return

            client.publish(TOPIC_CONTROL_INPUTS, json.dumps(result))
            print(
                f"Processed run={result['run_id']} sample={result['sample']} "
                f"control_id={result['control_id']}"
            )
        except Exception as error:
            print(f"Failed to process MQTT message: {error}")

    client.on_message = on_message
    connect_mqtt_client(client)
    client.subscribe(TOPIC_SENSORS_OUTPUTS)
    print("Controller is listening for sensor samples...")
    try:
        client.loop_forever()
    finally:
        client.disconnect()
        engine.dispose()


if __name__ == "__main__":
    start_controller()
