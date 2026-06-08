import json
from mqtt_config import (
    BROKER_HOST, 
    BROKER_PORT, 
    TOPIC_SENSORS_OUTPUTS, 
    TOPIC_CONTROL_INPUTS, 
    create_mqtt_client
)
from mpc_setup import create_mpc_controller

mpc, estimator, model = create_mpc_controller()

client = create_mqtt_client("mpc_controller")

def on_message(client, userdata, msg):
    print(f"Received new sensor data")

client.on_message = on_message
client.connect(BROKER_HOST, BROKER_PORT)
client.subscribe(TOPIC_SENSORS_OUTPUTS)
client.loop_forever()