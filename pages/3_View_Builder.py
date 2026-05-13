"""View Builder — compose a chart or table from municipal_data, save it, reload it.

v1 flow:
  1. Click "Load Excel into DB" once to populate `municipal_data`.
  2. Pick chart type, X, Y, aggregation, color, and filters.
  3. Preview updates live.
  4. Name the view and save; it goes into the `views` table.
  5. Pick a saved view from the dropdown to reproduce it later.

Filters auto-detect from column dtypes:
  - numeric  -> range slider
  - categorical -> multiselect

Chart types: bar, line, scatter, table. Map skipped for v1.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from db import (
    data_table_exists,
    delete_view,
    get_columns_info,
    init_schema,
    list_views,
    load_excel_to_db,
    load_view,
    read_data,
    save_view,
)

CHART_TYPES: tuple[str, ...] = ("bar", "line", "scatter", "table")
AGGREGATIONS: tuple[str, ...] = ("none", "sum", "mean", "count", "min", "max")
TABLE_AGGREGATIONS: tuple[str, ...] = ("sum", "mean", "count", "min", "max")
NONE_LABEL = "(none)"
ROW_COUNT_COL = "row_count"

st.set_page_config(layout="wide", page_title="View Builder")
st.title("View Builder")
st.caption(
    "Build a chart or table from the municipal data, save it, and reload "
    "it later from the dropdown."
)

init_schema()

# --- Data load section -----------------------------------------------------
with st.container(border=True):
    cols = st.columns([3, 1])
    with cols[0]:
        if data_table_exists():
            st.success("Data table is loaded.")
        else:
            st.warning("No data loaded yet. Click the button to import the Excel file.")
    with cols[1]:
        if st.button("Load Excel into DB", use_container_width=True):
            n = load_excel_to_db()
            st.toast(f"Loaded {n:,} rows into municipal_data")
            st.rerun()

if not data_table_exists():
    st.stop()

# --- Saved views dropdown --------------------------------------------------
saved = list_views()
view_names = ["(new view)"] + [v["name"] for v in saved]

# Consume any pending selection queued by Save/Delete on the previous run.
# Assigning to a widget's session_state key is only legal BEFORE the widget
# is instantiated, hence the sentinel-and-rerun dance.
if "_vb_pending_select" in st.session_state:
    pending = st.session_state.pop("_vb_pending_select")
    if pending in view_names:
        st.session_state["vb_selected_view"] = pending

selected_name: str = st.selectbox(
    "Load saved view",
    options=view_names,
    key="vb_selected_view",
)
loaded_config: dict[str, Any] | None = (
    load_view(selected_name) if selected_name != "(new view)" else None
)

st.divider()


def _idx(options: list[str] | tuple[str, ...], value: str | None, fallback: int = 0) -> int:
    """Safe index lookup that falls back when the saved value is no longer valid."""
    if value is None:
        return fallback
    try:
        return list(options).index(value)
    except ValueError:
        return fallback


# --- Builder controls + preview --------------------------------------------
columns_info = get_columns_info()
all_cols: list[str] = [c["name"] for c in columns_info]
numeric_cols: list[str] = [c["name"] for c in columns_info if c["kind"] == "numeric"]

control_col, preview_col = st.columns([1, 2])

# Make widget keys depend on the loaded view name so picking a saved view
# resets every widget cleanly without fighting Streamlit's state machine.
ns = f"vb_{selected_name}"

with control_col:
    st.subheader("Build")

    chart_type: str = st.selectbox(
        "Chart type",
        options=CHART_TYPES,
        index=_idx(CHART_TYPES, (loaded_config or {}).get("chart_type")),
        key=f"{ns}_chart_type",
    )

    # Defaults so config-building stays uniform regardless of chart_type.
    x_col: str | None = None
    y_col: str | None = None
    aggregation: str = "none"
    color_col: str | None = None
    selected_columns: list[str] | None = None
    sort_by: str | None = None
    sort_dir: str = "asc"
    group_by: list[str] | None = None
    measures: list[str] | None = None
    hover_cols: list[str] | None = None

    if chart_type == "table":
        saved_group_by = (loaded_config or {}).get("group_by") or []
        saved_group_by = [c for c in saved_group_by if c in all_cols]
        group_by = st.multiselect(
            "Group by (leave empty for raw rows)",
            options=all_cols,
            default=saved_group_by,
            key=f"{ns}_groupby",
        )

        if group_by:
            saved_measures = (loaded_config or {}).get("measures") or []
            saved_measures = [c for c in saved_measures if c in numeric_cols]
            measures = st.multiselect(
                "Measures (numeric columns to aggregate)",
                options=numeric_cols,
                default=saved_measures,
                key=f"{ns}_measures",
                help="Leave empty to count rows per group.",
            )
            aggregation = st.selectbox(
                "Aggregation",
                options=TABLE_AGGREGATIONS,
                index=_idx(
                    TABLE_AGGREGATIONS,
                    (loaded_config or {}).get("aggregation"),
                    fallback=0,
                ),
                key=f"{ns}_table_agg",
            )
            sort_options = [NONE_LABEL] + group_by + (measures or [ROW_COUNT_COL])
        else:
            cols_default = (loaded_config or {}).get("columns") or all_cols
            cols_default = [c for c in cols_default if c in all_cols] or all_cols
            selected_columns = st.multiselect(
                "Columns to display",
                options=all_cols,
                default=cols_default,
                key=f"{ns}_cols",
            )
            sort_options = [NONE_LABEL] + (selected_columns or all_cols)

        sort_by_pick: str = st.selectbox(
            "Sort by",
            options=sort_options,
            index=_idx(sort_options, (loaded_config or {}).get("sort_by") or NONE_LABEL),
            key=f"{ns}_sortby",
        )
        sort_by = None if sort_by_pick == NONE_LABEL else sort_by_pick

        sort_dir = st.radio(
            "Sort direction",
            options=("asc", "desc"),
            index=0 if (loaded_config or {}).get("sort_dir", "asc") == "asc" else 1,
            horizontal=True,
            disabled=(sort_by is None),
            key=f"{ns}_sortdir",
        )
    else:
        x_col = st.selectbox(
            "X axis",
            options=all_cols,
            index=_idx(all_cols, (loaded_config or {}).get("x")),
            key=f"{ns}_x",
        )

        y_options = [NONE_LABEL] + numeric_cols
        y_pick: str = st.selectbox(
            "Y axis",
            options=y_options,
            index=_idx(y_options, (loaded_config or {}).get("y") or NONE_LABEL),
            key=f"{ns}_y",
        )
        y_col = None if y_pick == NONE_LABEL else y_pick

        aggregation = st.selectbox(
            "Aggregation",
            options=AGGREGATIONS,
            index=_idx(AGGREGATIONS, (loaded_config or {}).get("aggregation", "none")),
            key=f"{ns}_agg",
        )

        color_options = [NONE_LABEL] + all_cols
        color_pick: str = st.selectbox(
            "Color by (optional)",
            options=color_options,
            index=_idx(color_options, (loaded_config or {}).get("color") or NONE_LABEL),
            key=f"{ns}_color",
        )
        color_col = None if color_pick == NONE_LABEL else color_pick

        # X / Y / Color are already in the default Plotly tooltip; offer the
        # rest as opt-in extras.
        already_shown = {x_col, y_col, color_col}
        hover_options = [c for c in all_cols if c not in already_shown]
        saved_hover = (loaded_config or {}).get("hover_cols") or []
        hover_default = [c for c in saved_hover if c in hover_options]
        hover_cols = st.multiselect(
            "Add to hover tooltip",
            options=hover_options,
            default=hover_default,
            key=f"{ns}_hover",
            help="Extra columns to show when hovering a data point.",
        )

    df_for_filters = read_data()
    saved_filters: dict[str, Any] = (loaded_config or {}).get("filters", {})
    filters: dict[str, Any] = {}

    # Open the expander automatically when a saved view brings filters with it,
    # otherwise keep it collapsed so the page stays compact.
    filter_label = (
        f"Filters ({len(saved_filters)} active)" if saved_filters else "Filters"
    )
    with st.expander(filter_label, expanded=bool(saved_filters)):
        for c in columns_info:
            col = c["name"]
            if c["kind"] == "categorical":
                options = sorted(
                    df_for_filters[col].dropna().astype(str).unique().tolist()
                )
                if not options:
                    continue
                saved_val = saved_filters.get(col)
                default = saved_val if isinstance(saved_val, list) else options
                default = [v for v in default if v in options]
                picked = st.multiselect(
                    col,
                    options=options,
                    default=default,
                    key=f"{ns}_f_{col}",
                )
                if picked and picked != options:
                    filters[col] = picked
            else:
                series = pd.to_numeric(df_for_filters[col], errors="coerce").dropna()
                if series.empty:
                    continue
                lo, hi = float(series.min()), float(series.max())
                if lo == hi:
                    continue
                saved_val = saved_filters.get(col)
                if isinstance(saved_val, list) and len(saved_val) == 2:
                    v_lo = max(lo, float(saved_val[0]))
                    v_hi = min(hi, float(saved_val[1]))
                else:
                    v_lo, v_hi = lo, hi
                picked_range = st.slider(
                    col,
                    min_value=lo,
                    max_value=hi,
                    value=(v_lo, v_hi),
                    key=f"{ns}_f_{col}",
                )
                if (picked_range[0], picked_range[1]) != (lo, hi):
                    filters[col] = [picked_range[0], picked_range[1]]

config: dict[str, Any] = {
    "chart_type": chart_type,
    "x": x_col,
    "y": y_col,
    "aggregation": aggregation,
    "color": color_col,
    "hover_cols": hover_cols,
    "columns": selected_columns,
    "group_by": group_by,
    "measures": measures,
    "sort_by": sort_by,
    "sort_dir": sort_dir,
    "filters": filters,
}


def _apply_filters(base: pd.DataFrame, fs: dict[str, Any]) -> pd.DataFrame:
    out = base
    for col, val in fs.items():
        if (
            isinstance(val, list)
            and len(val) == 2
            and all(isinstance(v, (int, float)) for v in val)
        ):
            num = pd.to_numeric(out[col], errors="coerce")
            out = out[(num >= val[0]) & (num <= val[1])]
        elif isinstance(val, list):
            out = out[out[col].astype(str).isin([str(v) for v in val])]
    return out


with preview_col:
    st.subheader("Preview")
    df = _apply_filters(read_data(), filters)
    st.caption(f"{len(df):,} rows after filters.")

    if df.empty:
        st.info("No rows match the current filters.")
    elif chart_type == "table":
        if group_by:
            valid_groups = [c for c in group_by if c in df.columns]
            valid_measures = [c for c in (measures or []) if c in df.columns]
            if valid_measures:
                # Coerce measure cols to numeric so SQLite TEXT round-trips
                # don't poison the aggregation.
                agg_df = df.copy()
                for m in valid_measures:
                    agg_df[m] = pd.to_numeric(agg_df[m], errors="coerce")
                table_df = (
                    agg_df.groupby(valid_groups, dropna=False)
                    .agg({m: aggregation for m in valid_measures})
                    .reset_index()
                )
            else:
                table_df = (
                    df.groupby(valid_groups, dropna=False)
                    .size()
                    .reset_index(name=ROW_COUNT_COL)
                )
        else:
            cols_to_show = [
                c for c in (selected_columns or list(df.columns)) if c in df.columns
            ]
            table_df = df[cols_to_show] if cols_to_show else df

        if sort_by and sort_by in table_df.columns:
            table_df = table_df.sort_values(
                by=sort_by,
                ascending=(sort_dir == "asc"),
                na_position="last",
            )
        st.dataframe(table_df, use_container_width=True, height=540, hide_index=True)
    elif y_col is None:
        st.info("Pick a Y axis column to render this chart type.")
    else:
        plot_df = df.copy()
        if aggregation != "none":
            # Dedupe so picking the same column for X and Color (or X == Y)
            # doesn't blow up reset_index with duplicate column names.
            group_cols: list[str] = [x_col]
            if color_col and color_col != x_col:
                group_cols.append(color_col)
            if y_col in group_cols:
                st.warning(
                    "Y axis can't be the same column as X or Color when "
                    "aggregating. Pick a different Y or set aggregation to 'none'."
                )
                st.stop()
            plot_df = (
                plot_df.groupby(group_cols, dropna=False)
                .agg({y_col: aggregation})
                .reset_index()
            )

        kwargs: dict[str, Any] = {"x": x_col, "y": y_col}
        if color_col:
            kwargs["color"] = color_col
        # Only pass hover columns that survived the (possible) groupby.
        extra_hover = [c for c in (hover_cols or []) if c in plot_df.columns]
        if extra_hover:
            kwargs["hover_data"] = extra_hover

        if chart_type == "bar":
            fig = px.bar(plot_df, **kwargs)
        elif chart_type == "line":
            fig = px.line(plot_df, **kwargs)
        else:  # scatter
            fig = px.scatter(plot_df, **kwargs)

        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=540)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Save / delete ---------------------------------------------------------
st.subheader("Save")
save_cols = st.columns([3, 1, 1])
with save_cols[0]:
    name_default = selected_name if selected_name != "(new view)" else ""
    save_name: str = st.text_input("View name", value=name_default, key=f"{ns}_savename")
with save_cols[1]:
    if st.button(
        "Save view",
        use_container_width=True,
        disabled=not save_name.strip(),
    ):
        save_view(save_name.strip(), config)
        st.toast(f"Saved view: {save_name}")
        st.session_state["_vb_pending_select"] = save_name.strip()
        st.rerun()
with save_cols[2]:
    can_delete = selected_name != "(new view)"
    if st.button(
        "Delete view",
        use_container_width=True,
        disabled=not can_delete,
    ):
        delete_view(selected_name)
        st.toast(f"Deleted view: {selected_name}")
        st.session_state["_vb_pending_select"] = "(new view)"
        st.rerun()
