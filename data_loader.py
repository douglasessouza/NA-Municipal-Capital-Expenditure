"""Load the Combined sheet of P1_Municipal_CapEx_Combined.xlsx into a typed DataFrame."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

WORKBOOK_PATH = Path(__file__).parent / "P1_Municipal_CapEx_Combined.xlsx"
SHEET_NAME = "Combined"

EXPECTED_COLUMNS = [
    "country",
    "municipality",
    "state_province",
    "population",
    "currency",
    "capex_local",
    "capex_per_capita",
    "fx_rate_to_usd",
    "capex_usd_equiv",
    "capex_score",
    "vision_score_raw",
    "vision_score_norm",
    "tier",
    "classification_method",
    "fiscal_year",
    "data_source",
    "governance_type",
    "notes",
]


@st.cache_data(show_spinner="Loading workbook…")
def load_combined() -> pd.DataFrame:
    """Return the Combined sheet as a typed DataFrame."""
    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(f"Workbook not found: {WORKBOOK_PATH}")

    df = pd.read_excel(WORKBOOK_PATH, sheet_name=SHEET_NAME, engine="openpyxl")

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Combined sheet missing expected columns: {missing}")

    df = df[EXPECTED_COLUMNS].copy()

    for col in ("population", "capex_local", "capex_score", "fiscal_year"):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    for col in (
        "capex_per_capita",
        "fx_rate_to_usd",
        "capex_usd_equiv",
        "vision_score_raw",
        "vision_score_norm",
    ):
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")

    for col in (
        "country",
        "municipality",
        "state_province",
        "currency",
        "tier",
        "classification_method",
        "data_source",
        "governance_type",
        "notes",
    ):
        df[col] = df[col].astype("string")

    return df
