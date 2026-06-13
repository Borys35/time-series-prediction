import paho.mqtt.client as mqtt

from settings import MQTT_HOST, MQTT_KEEPALIVE, MQTT_PORT


TOPIC_SENSORS_OUTPUTS = "tep/sensors/outputs"
TOPIC_CONTROL_INPUTS = "tep/control/inputs"


def create_mqtt_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Connected to MQTT broker with reason code {reason_code}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        print(f"Disconnected from MQTT broker with reason code {reason_code}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    return client


def connect_mqtt_client(client: mqtt.Client) -> None:
    client.connect(MQTT_HOST, MQTT_PORT, MQTT_KEEPALIVE)
