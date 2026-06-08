from sqlalchemy import create_engine, text
from mqtt_config import (
    BROKER_HOST, 
    BROKER_PORT, 
    TOPIC_SENSORS_OUTPUTS, 
    TOPIC_CONTROL_INPUTS, 
    create_mqtt_client
)
from mpc_setup import create_mpc


def start_mpc_controller():
    mpc, estimator, model = create_mpc()

    engine = create_engine('postgresql://postgres:postgres@127.0.0.1:5435/tep_db')

    print("MPC controller created postgresql engine")

    with engine.connect() as connection:
        client = create_mqtt_client("mpc_controller")

        print("MPC controller is listening...")

        def on_message(client, userdata, msg):
            cursor = connection.execute(text("SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 1"))
            sensor_data = cursor.fetchone()
            print(f"Received new sensor data: {sensor_data}")

        client.on_message = on_message
        client.connect(BROKER_HOST, BROKER_PORT)
        client.subscribe(TOPIC_SENSORS_OUTPUTS)
        client.loop_forever()


if __name__ == "__main__":
    start_mpc_controller()