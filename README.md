# Prediction Time Series

This project uses Docker for PostgreSQL and Mosquitto, MQTT for sensor/control messaging, and an MPC controller for estimating the next control action. Project uses Tennessee Eastman Process dataset for mock data.

## Prerequirements

- Docker + Docker compose
- Python 3
- Recommended: Create python virtual environment

## How to run the project?

Run following commands in three seperate terminals:

1. Start Docker:
   `docker compose up`

2. Start the MPC controller:
   `python src/controller_node.py`

3. Start the plant simulator:
   `python src/plant_simulator.py`

The controller reads sensor data from PostgreSQL, estimates the state with MPC, and publishes control inputs over MQTT.
