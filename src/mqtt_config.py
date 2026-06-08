import paho.mqtt.client as mqtt

BROKER_HOST = "localhost"
BROKER_PORT = 1883
KEEPALIVE = 60

TOPIC_SENSORS_OUTPUTS = "tep/sensors/outputs"
TOPIC_CONTROL_INPUTS = "tep/control/inputs"

def create_mqtt_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(client_id=client_id)
    client.connect(BROKER_HOST, BROKER_PORT, KEEPALIVE)

    def on_connect(client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")

    def on_disconnect(client, userdata, rc):
        print(f"Disconnected from MQTT broker with result code {rc}")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    return client