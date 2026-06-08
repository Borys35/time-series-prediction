import time
import pandas as pd
from sqlalchemy import create_engine
import pyreadr
from mqtt_config import (create_mqtt_client, TOPIC_SENSORS_OUTPUTS, BROKER_HOST, BROKER_PORT)

def start_plant_simulator():
    client = create_mqtt_client(client_id="plant_simulator")
    client.connect(BROKER_HOST, BROKER_PORT)

    engine = create_engine('postgresql://postgres:postgres@localhost:5432/tep_db')

    testing_data = pyreadr.read_r('./datasets/tep/TEP_FaultFree_Testing.RData')
    df = pd.DataFrame(testing_data['fault_free_testing'])

    input_columns = [col for col in df.columns if col.startswith('xmeas')]
    df = df[input_columns]

    for index, row in df.iterrows():
        row.to_sql('sensor_data', engine, if_exists='append', index=False)
        client.publish(TOPIC_SENSORS_OUTPUTS)
        time.sleep(1) # Sleep for 1 second before inserting the next record


if __name__ == "__main__":
    start_plant_simulator()