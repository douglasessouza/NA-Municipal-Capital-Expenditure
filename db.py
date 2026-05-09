"""SQLite-backed storage for the View Builder.

Two tables:
  - municipal_data: rows from P1_Municipal_CapEx_Combined.xlsx
  - views: saved view configs (name + JSON)

The DB file lives next to the workbook. Streamlit Cloud has an ephemeral
filesystem; for a real deployment swap to Postgres/Supabase.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from data_loader import load_combined

DB_PATH = Path(__file__).parent / "app.db"
DATA_TABLE = "municipal_data"
VIEWS_TABLE = "views"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection that auto-commits on success."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    """Create the views table if missing. Idempotent."""
    with connect() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {VIEWS_TABLE} (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                config_json TEXT NOT NULL,
                created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def data_table_exists() -> bool:
    with connect() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (DATA_TABLE,),
        )
        return cur.fetchone() is not None


def load_excel_to_db() -> int:
    """Drop and recreate municipal_data from the workbook. Returns row count."""
    df = load_combined()
    # SQLite doesn't grok pandas nullable dtypes cleanly; coerce NA -> None
    # so the round-trip via to_sql/read_sql doesn't smuggle in 'NA' strings.
    df = df.astype(object).where(pd.notna(df), None)
    with connect() as conn:
        df.to_sql(DATA_TABLE, conn, if_exists="replace", index=False)
    return len(df)


def get_columns_info() -> list[dict[str, str]]:
    """Return [{name, kind}] where kind is 'numeric' or 'categorical'.

    Used by the View Builder to auto-detect filter widgets.
    """
    if not data_table_exists():
        return []
    with connect() as conn:
        df = pd.read_sql(f"SELECT * FROM {DATA_TABLE} LIMIT 200", conn)
    info: list[dict[str, str]] = []
    for col in df.columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        threshold = max(1, len(df) // 2)
        kind = "numeric" if coerced.notna().sum() >= threshold else "categorical"
        info.append({"name": col, "kind": kind})
    return info


def read_data() -> pd.DataFrame:
    """Return the full municipal_data table."""
    with connect() as conn:
        return pd.read_sql(f"SELECT * FROM {DATA_TABLE}", conn)


def save_view(name: str, config: dict[str, Any]) -> None:
    """Insert or update a saved view by name."""
    with connect() as conn:
        conn.execute(
            f"""
            INSERT INTO {VIEWS_TABLE} (name, config_json)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET config_json = excluded.config_json
            """,
            (name, json.dumps(config)),
        )


def list_views() -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            f"SELECT id, name, config_json, created_at FROM {VIEWS_TABLE} "
            "ORDER BY created_at DESC"
        )
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "config": json.loads(r["config_json"]),
                "created_at": r["created_at"],
            }
            for r in cur.fetchall()
        ]


def load_view(name: str) -> dict[str, Any] | None:
    with connect() as conn:
        cur = conn.execute(
            f"SELECT config_json FROM {VIEWS_TABLE} WHERE name = ?", (name,)
        )
        row = cur.fetchone()
        return json.loads(row["config_json"]) if row else None


def delete_view(name: str) -> None:
    with connect() as conn:
        conn.execute(f"DELETE FROM {VIEWS_TABLE} WHERE name = ?", (name,))
