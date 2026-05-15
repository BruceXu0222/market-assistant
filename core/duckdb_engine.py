"""DuckDB execution helper."""

from __future__ import annotations

from typing import Optional

import duckdb
import pandas as pd


class DuckDBEngine:
    """Small context-manager wrapper around a DuckDB connection."""

    def __init__(self, database: str = ":memory:"):
        """Open a DuckDB connection."""
        self.database = database
        self.conn = duckdb.connect(self.database)

    def execute(self, sql: str, params: Optional[dict] = None) -> pd.DataFrame:
        """Execute SQL and return a pandas DataFrame."""
        if not self.conn:
            raise RuntimeError("DuckDB connection is not initialized")
        result = self.conn.execute(sql, params) if params else self.conn.execute(sql)
        return result.df()

    def execute_many(self, sql: str, params_list: list) -> None:
        """Execute a statement against many parameter sets."""
        if not self.conn:
            raise RuntimeError("DuckDB connection is not initialized")
        self.conn.executemany(sql, params_list)

    def close(self) -> None:
        """Close the connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self) -> "DuckDBEngine":
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager."""
        self.close()


if __name__ == "__main__":
    with DuckDBEngine() as engine:
        demo = engine.execute("SELECT 1 AS id, 'AAPL' AS symbol, 150.0 AS price")
        print(demo)
