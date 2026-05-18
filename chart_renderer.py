"""chart_renderer.py — shared rendering logic for the View Builder and Dashboards pages.

Exposes two public functions:
  - apply_filters(df, filters)  → filtered DataFrame
  - render_chart(config, df)    → renders a Plotly chart or st.dataframe inline

Both pages import from here so the render logic lives in exactly one place.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

ROW_COUNT_COL = "row_count"


def apply_filters(base: pd.DataFrame, fs: dict[str, Any]) -> pd.DataFrame:
    """Apply saved filter config to a DataFrame and return the filtered result."""
    out = base
    for col, val in fs.items():
        if col not in out.columns:
            continue
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


def render_chart(config: dict[str, Any], df: pd.DataFrame) -> None:
    """Render a chart or table from a saved view config dict.

    Reads all fields from config and renders inline using Streamlit.
    Safe to call inside st.columns() cells.

    Args:
        config: the dict saved by the View Builder (chart_type, x, y, etc.)
        df:     the full municipal DataFrame (pre-filtered or not — filters
                inside config are always re-applied here for consistency)
    """
    chart_type: str = config.get("chart_type", "bar")
    x_col: str | None = config.get("x")
    y_col: str | None = config.get("y")
    aggregation: str = config.get("aggregation", "none")
    color_col: str | None = config.get("color")
    hover_cols: list[str] = config.get("hover_cols") or []
    selected_columns: list[str] | None = config.get("columns")
    group_by: list[str] | None = config.get("group_by")
    measures: list[str] | None = config.get("measures")
    sort_by: str | None = config.get("sort_by")
    sort_dir: str = config.get("sort_dir", "asc")
    filters: dict[str, Any] = config.get("filters", {})

    filtered = apply_filters(df, filters)

    st.caption(f"{len(filtered):,} rows after filters.")

    if filtered.empty:
        st.info("No rows match the saved filters.")
        return

    # ------------------------------------------------------------------ table
    if chart_type == "table":
        if group_by:
            valid_groups = [c for c in group_by if c in filtered.columns]
            valid_measures = [c for c in (measures or []) if c in filtered.columns]
            if valid_measures:
                agg_df = filtered.copy()
                for m in valid_measures:
                    agg_df[m] = pd.to_numeric(agg_df[m], errors="coerce")
                table_df = (
                    agg_df.groupby(valid_groups, dropna=False)
                    .agg({m: aggregation for m in valid_measures})
                    .reset_index()
                )
            else:
                table_df = (
                    filtered.groupby(valid_groups, dropna=False)
                    .size()
                    .reset_index(name=ROW_COUNT_COL)
                )
        else:
            cols_to_show = [
                c for c in (selected_columns or list(filtered.columns))
                if c in filtered.columns
            ]
            table_df = filtered[cols_to_show] if cols_to_show else filtered

        if sort_by and sort_by in table_df.columns:
            table_df = table_df.sort_values(
                by=sort_by,
                ascending=(sort_dir == "asc"),
                na_position="last",
            )

        st.dataframe(table_df, use_container_width=True, height=400, hide_index=True)
        return

    # ------------------------------------------------------------------ charts
    if y_col is None:
        st.info("This view has no Y axis configured.")
        return

    plot_df = filtered.copy()

    if aggregation != "none":
        group_cols: list[str] = [x_col] if x_col else []
        if color_col and color_col != x_col:
            group_cols.append(color_col)
        if y_col in group_cols:
            st.warning("Y axis conflicts with X or Color — cannot aggregate.")
            return
        if group_cols:
            plot_df = (
                plot_df.groupby(group_cols, dropna=False)
                .agg({y_col: aggregation})
                .reset_index()
            )

    kwargs: dict[str, Any] = {"x": x_col, "y": y_col}
    if color_col:
        kwargs["color"] = color_col
    extra_hover = [c for c in hover_cols if c in plot_df.columns]
    if extra_hover:
        kwargs["hover_data"] = extra_hover

    if chart_type == "bar":
        fig = px.bar(plot_df, **kwargs)
    elif chart_type == "line":
        fig = px.line(plot_df, **kwargs)
    else:  # scatter
        fig = px.scatter(plot_df, **kwargs)

    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=400)
    st.plotly_chart(fig, use_container_width=True)
