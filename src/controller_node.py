import numpy as np
from sqlalchemy import create_engine, text
from mqtt_config import (
    BROKER_HOST, 
    BROKER_PORT, 
    TOPIC_SENSORS_OUTPUTS, 
    TOPIC_CONTROL_INPUTS, 
    create_mqtt_client
)
from mpc_setup import create_mpc


SENSOR_COLUMNS = [f"xmeas_{index}" for index in range(1, 42)]


def load_model_matrices():
    model_data = np.load('./notebooks/tep_mpc_model.npz')
    return model_data['C'], model_data['D']


def extract_measurement(sensor_row):
    values = [sensor_row[column] for column in SENSOR_COLUMNS]
    if any(value is None for value in values):
        return None
    return np.asarray(values, dtype=float).reshape(-1, 1)


def estimate_state(measurement, output_matrix, feedthrough_matrix, previous_u):
    residual = measurement - feedthrough_matrix @ previous_u
    state_estimate, *_ = np.linalg.lstsq(output_matrix, residual, rcond=None)
    return state_estimate.reshape(-1, 1)


def start_mpc_controller():
    mpc, _, _ = create_mpc()
    output_matrix, feedthrough_matrix = load_model_matrices()
    previous_u = np.zeros((feedthrough_matrix.shape[1], 1))

    engine = create_engine('postgresql://postgres:postgres@127.0.0.1:5435/tep_db')

    print("MPC controller created postgresql engine")

    with engine.connect() as connection:
        client = create_mqtt_client("mpc_controller")
        mpc.x0 = np.zeros((output_matrix.shape[1], 1))
        mpc.set_initial_guess()

        print("MPC controller is listening...")

        def on_message(client, userdata, msg):
            nonlocal previous_u

            cursor = connection.execute(text("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1"))
            sensor_data = cursor.mappings().first()
            if sensor_data is None:
                print("No sensor data available")
                return

            measurement = extract_measurement(sensor_data)
            if measurement is None:
                print("Incomplete sensor data received")
                return

            x_hat = estimate_state(measurement, output_matrix, feedthrough_matrix, previous_u)
            mpc.x0 = x_hat
            control = mpc.make_step(x_hat)
            previous_u = np.asarray(control, dtype=float).reshape(-1, 1)

            client.publish(TOPIC_CONTROL_INPUTS, np.array2string(previous_u.ravel(), separator=", "))

            print(f"Estimated state: {x_hat.ravel()}")
            print(f"Control action: {previous_u.ravel()}")
            connection.execute(text(f'INSERT INTO input_controls (timestamp, u1, u2, u3, u4, u5, u6, u7, u8, u9, u10, u11) VALUES (CURRENT_TIMESTAMP, {', '.join(map(str, previous_u.ravel().tolist()))})'))
        client.on_message = on_message
        client.connect(BROKER_HOST, BROKER_PORT)
        client.subscribe(TOPIC_SENSORS_OUTPUTS)
        client.loop_forever()


if __name__ == "__main__":
    start_mpc_controller()