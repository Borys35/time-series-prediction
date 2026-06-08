import time
import pandas as pd
from sqlalchemy import create_engine, text
import pyreadr
from mqtt_config import (create_mqtt_client, TOPIC_SENSORS_OUTPUTS, BROKER_HOST, BROKER_PORT)

def start_plant_simulator():
    client = create_mqtt_client(client_id="plant_simulator")
    client.connect(BROKER_HOST, BROKER_PORT)

    engine = create_engine('postgresql://postgres:postgres@127.0.0.1:5435/tep_db')

    # clear existing data in the table
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM sensor_data"))
        connection.commit()

    testing_data = pyreadr.read_r('./datasets/tep/TEP_FaultFree_Testing.RData')
    df = pd.DataFrame(testing_data['fault_free_testing'])
    df = df[df['simulationRun'] == 1]

    input_columns = [col for col in df.columns if col.startswith('xmeas')]
    df = df[input_columns]

    print("Starting plant simulator...")

    for index, row in df.iterrows():
        print(f"Inserting record {index + 1}/{len(df)} into the database...")
        pd.DataFrame([row]).to_sql('sensor_data', engine, if_exists='append', index=False)
        client.publish(TOPIC_SENSORS_OUTPUTS)
        time.sleep(1) # Sleep for 1 second before inserting the next record


if __name__ == "__main__":
    start_plant_simulator()