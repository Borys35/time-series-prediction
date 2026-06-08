import time
import pandas as pd
from sqlalchemy import create_engine
import pyreadr

engine = create_engine('postgresql://postgres:postgres@localhost:5432/tep_db')

testing_data = pyreadr.read_r('./datasets/tep/TEP_FaultFree_Testing.RData')
df = pd.DataFrame(testing_data['fault_free_testing'])

input_columns = [col for col in df.columns if col.startswith('xmeas')]
df = df[input_columns]

for index, row in df.iterrows():
    row.to_sql('sensor_data', engine, if_exists='append', index=False)
    time.sleep(1) # Sleep for 1 second before inserting the next record