"""Dashboards — combine saved views from the View Builder into a multi-chart layout.

Flow:
  1. Pick one or more saved views from the multiselect.
  2. Choose a column layout (1, 2, or 3 columns).
  3. All selected charts render together in a responsive grid.
"""

from __future__ import annotations

import streamlit as st

from chart_renderer import render_chart
from db import data_table_exists, init_schema, list_views, read_data

st.set_page_config(layout="wide", page_title="Dashboards")

st.title("Dashboards")
st.caption(
    "Combine saved views from the View Builder into a single dashboard. "
    "Go to View Builder to create and save charts first."
)

init_schema()

# --- Guard: DB must be loaded -----------------------------------------------
if not data_table_exists():
    st.warning(
        "No data loaded yet. Go to **View Builder** and click **Load Excel into DB** first."
    )
    st.stop()

# --- Guard: need at least one saved view ------------------------------------
saved = list_views()

if not saved:
    st.info(
        "No saved views found. "
        "Head to **View Builder**, build a chart, and click **Save view** — "
        "then come back here to assemble your dashboard."
    )
    st.stop()

# --- Controls ----------------------------------------------------------------
st.divider()

control_left, control_right = st.columns([3, 1])

with control_left:
    view_names = [v["name"] for v in saved]
    selected_names = st.multiselect(
        "Select views to display",
        options=view_names,
        default=view_names[:min(2, len(view_names))],
        help="Pick one or more saved views. Order here = order on the dashboard.",
    )

with control_right:
    n_cols = st.selectbox(
        "Layout",
        options=[1, 2, 3],
        index=1,
        format_func=lambda x: f"{x} column{'s' if x > 1 else ''}",
    )

if not selected_names:
    st.info("Select at least one view above to build your dashboard.")
    st.stop()

st.divider()

# --- Build a lookup: name -> config -----------------------------------------
config_map = {v["name"]: v["config"] for v in saved}
df = read_data()

# --- Render grid ------------------------------------------------------------
selected_views = [n for n in selected_names if n in config_map]

# Split into rows of n_cols
rows = [selected_views[i : i + n_cols] for i in range(0, len(selected_views), n_cols)]

for row in rows:
    cols = st.columns(n_cols)
    for col_idx, view_name in enumerate(row):
        with cols[col_idx]:
            st.subheader(view_name)
            render_chart(config_map[view_name], df)
