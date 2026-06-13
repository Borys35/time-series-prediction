import numpy as np
from sqlalchemy import create_engine

from settings import DATABASE_URL


MEASUREMENT_COLUMNS = [f"xmeas_{index}" for index in range(1, 42)]
PROCESS_INPUT_COLUMNS = [f"xmv_{index}" for index in range(1, 12)]
CONTROL_COLUMNS = [f"u{index}" for index in range(1, 12)]


def create_database_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)


def vector_from_row(row, columns: list[str]) -> np.ndarray:
    values = [row[column] for column in columns]
    if any(value is None for value in values):
        raise ValueError(f"Incomplete database row for columns: {columns}")
    return np.asarray(values, dtype=float)


def vector_parameters(columns: list[str], values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=float).reshape(-1)
    return {column: float(value) for column, value in zip(columns, values)}
