"""United States page — 419 municipalities, FY2022, single-axis tiering, USD."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from data_loader import load_combined
from geocoding import attach_coords
from theme import (
    TIER_COLORS_HEX,
    TIER_COLORS_RGB,
    US_TIERS,
    state_abbrev,
)

CURRENCY = "USD"
INTERNAL_COLUMNS: tuple[str, ...] = (
    "fx_rate_to_usd",
    "classification_method",
    "data_source",
)
PAGE_KEYS: tuple[str, ...] = (
    "us_tier_select",
    "us_state_select",
    "us_population_range",
    "us_capex_pc_range",
    "us_map_metric",
    "us_compare_select",
    "us_show_all_cols",
)


def _reset_filters() -> None:
    for key in PAGE_KEYS:
        st.session_state.pop(key, None)


st.set_page_config(layout="wide", page_title="United States — Municipal CapEx")

st.title("United States")
st.caption(
    "419 municipalities, FY2022, single-axis tiering (capex per capita "
    "thresholds). Source: US Census Bureau Annual Survey, construction CapEx "
    "only. Currency: USD."
)

df_all = load_combined()
df = df_all[df_all["country"] == "US"].copy()

# --- Sidebar filters -------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    st.button("Reset filters", on_click=_reset_filters, use_container_width=True)

    selected_tiers: list[str] = st.multiselect(
        "Tier",
        options=list(US_TIERS),
        default=list(US_TIERS),
        key="us_tier_select",
    )

    state_options = sorted(df["state_province"].dropna().unique().tolist())
    selected_states: list[str] = st.multiselect(
        "State",
        options=state_options,
        default=state_options,
        key="us_state_select",
    )

    pop_min = int(df["population"].min())
    pop_max = int(df["population"].max())
    if pop_min == pop_max:
        pop_max = pop_min + 1
    population_range: tuple[int, int] = st.slider(
        "Population",
        min_value=pop_min,
        max_value=pop_max,
        value=(pop_min, pop_max),
        step=1000,
        key="us_population_range",
    )

    cpc_min = float(df["capex_per_capita"].min())
    cpc_max = float(df["capex_per_capita"].max())
    if cpc_min == cpc_max:
        cpc_max = cpc_min + 1.0
    capex_pc_range: tuple[float, float] = st.slider(
        f"Capex per capita ({CURRENCY})",
        min_value=float(round(cpc_min, 2)),
        max_value=float(round(cpc_max, 2)),
        value=(float(round(cpc_min, 2)), float(round(cpc_max, 2))),
        step=10.0,
        key="us_capex_pc_range",
    )


def _apply_filters(
    base: pd.DataFrame,
    tiers: list[str],
    states: list[str],
    pop_range: tuple[int, int],
    cpc_range: tuple[float, float],
) -> pd.DataFrame:
    out = base
    out = out[out["tier"].isin(tiers)] if tiers else out.iloc[0:0]
    out = out[out["state_province"].isin(states)] if states else out.iloc[0:0]
    lo, hi = pop_range
    out = out[(out["population"] >= lo) & (out["population"] <= hi)]
    cpc_lo, cpc_hi = cpc_range
    out = out[
        (out["capex_per_capita"] >= cpc_lo) & (out["capex_per_capita"] <= cpc_hi)
    ]
    return out


filtered = _apply_filters(
    df, selected_tiers, selected_states, population_range, capex_pc_range
)

# --- KPI cards -------------------------------------------------------------
st.subheader("Summary")

n_munis = len(filtered)
total_capex = float(filtered["capex_local"].sum()) if n_munis else 0.0
if n_munis and filtered["population"].sum():
    avg_capex_pc = total_capex / float(filtered["population"].sum())
else:
    avg_capex_pc = 0.0

kpi_cols = st.columns(3)
kpi_cols[0].metric("Municipalities", f"{n_munis:,}")
kpi_cols[1].metric(f"Total capex ({CURRENCY})", f"${total_capex:,.0f}")
kpi_cols[2].metric(
    f"Avg capex per capita ({CURRENCY})",
    f"${avg_capex_pc:,.0f}",
    help="Population-weighted: total capex / total population in the filtered set.",
)

st.markdown("**Tier counts**")
tier_counts = filtered["tier"].value_counts().reindex(US_TIERS, fill_value=0)
tier_cols = st.columns(len(US_TIERS))
for col, tier in zip(tier_cols, US_TIERS):
    color = TIER_COLORS_HEX[tier]
    count = int(tier_counts[tier])
    col.markdown(
        f"<div style='border-left:6px solid {color};padding:6px 12px;"
        "background-color:rgba(127,127,127,0.06);border-radius:4px;'>"
        f"<div style='font-size:0.78rem;color:#6b7280;'>{tier}</div>"
        f"<div style='font-size:1.6rem;font-weight:600;'>{count:,}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()

# --- Map -------------------------------------------------------------------
st.subheader("Map")
st.caption(
    "One bubble per municipality. Bubble size encodes capex; color encodes "
    "tier. Hover for details."
)

map_metric = st.radio(
    "Bubble size by",
    options=(f"Total capex ({CURRENCY})", f"Capex per capita ({CURRENCY})"),
    index=0,
    horizontal=True,
    key="us_map_metric",
)

map_df = attach_coords(filtered).copy()
map_df = map_df.dropna(subset=["lat", "lon"])

if map_df.empty:
    st.info("No mappable rows in the current filter.")
else:
    map_df["lat"] = map_df["lat"].astype(float)
    map_df["lon"] = map_df["lon"].astype(float)
    map_df["population_int"] = map_df["population"].astype(int)
    map_df["capex_local_f"] = map_df["capex_local"].astype(float)
    map_df["capex_per_capita_f"] = map_df["capex_per_capita"].astype(float)

    if map_metric == f"Total capex ({CURRENCY})":
        radius_basis = map_df["capex_local_f"]
        radius_max_meters = 60_000.0
    else:
        radius_basis = map_df["capex_per_capita_f"]
        radius_max_meters = 40_000.0

    basis_max = float(radius_basis.max()) or 1.0
    map_df["bubble_radius"] = (
        (radius_basis / basis_max).clip(lower=0.05) * radius_max_meters
    )

    map_df["fill_color"] = map_df["tier"].map(
        lambda t: list(TIER_COLORS_RGB.get(t, (160, 160, 160))) + [180]
    )

    map_df["capex_disp"] = map_df["capex_local_f"].map(
        lambda v: f"${v:,.0f} {CURRENCY}"
    )
    map_df["capex_pc_disp"] = map_df["capex_per_capita_f"].map(
        lambda v: f"${v:,.0f} {CURRENCY}"
    )
    map_df["population_disp"] = map_df["population_int"].map(lambda v: f"{v:,}")

    view_state = pdk.ViewState(
        latitude=39.5, longitude=-98.0, zoom=3.5, pitch=0, bearing=0
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_fill_color="fill_color",
        get_radius="bubble_radius",
        radius_min_pixels=3,
        radius_max_pixels=40,
        pickable=True,
        stroked=True,
        get_line_color=[40, 40, 40, 200],
        line_width_min_pixels=0.5,
    )

    tooltip = {
        "html": (
            "<b>{municipality}</b>, {state_province}<br/>"
            "Tier: <b>{tier}</b><br/>"
            "Population: {population_disp}<br/>"
            "Capex: {capex_disp}<br/>"
            "Capex per capita: {capex_pc_disp}"
        ),
        "style": {
            "backgroundColor": "rgba(20,20,24,0.92)",
            "color": "white",
            "fontSize": "12px",
            "padding": "8px",
            "borderRadius": "4px",
        },
    }

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=None,
    )
    st.pydeck_chart(deck, use_container_width=True)

    legend_cols = st.columns(len(US_TIERS))
    for col, tier in zip(legend_cols, US_TIERS):
        col.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;'>"
            f"<span style='width:12px;height:12px;border-radius:50%;"
            f"background:{TIER_COLORS_HEX[tier]};display:inline-block;'></span>"
            f"<span style='font-size:0.9rem;'>{tier}</span></div>",
            unsafe_allow_html=True,
        )

    n_unmapped = len(filtered) - len(map_df)
    if n_unmapped:
        st.caption(
            f"Note: {n_unmapped} row(s) in the current filter could not be "
            "geocoded and are not shown on the map."
        )

st.divider()

# --- Distributions & Rankings ---------------------------------------------
st.subheader("Distributions & rankings")
st.caption(
    "Charts respond to the sidebar filters. Picking cities in the comparison "
    "view below highlights them on the histogram."
)

if filtered.empty:
    st.info("No municipalities match the current filter.")
else:
    chart_df = filtered.copy()
    chart_df["state_abbr"] = chart_df["state_province"].map(state_abbrev)
    chart_df["label"] = (
        chart_df["municipality"].astype(str) + ", " + chart_df["state_abbr"]
    )
    chart_df["capex_per_capita_f"] = chart_df["capex_per_capita"].astype(float)

    grid = st.columns(3)

    # --- Chart 1: Top & Bottom Rankings ------------------------------------
    with grid[0]:
        st.markdown("**Top & bottom by capex per capita**")
        st.caption(f"Ranked by capex per capita ({CURRENCY}).")
        ranked = chart_df.sort_values("capex_per_capita_f", ascending=False)
        if len(ranked) <= 20:
            display = ranked.copy()
            display["_group"] = "All"
        else:
            top10 = ranked.head(10).copy()
            top10["_group"] = "Top 10"
            bot10 = ranked.tail(10).copy()
            bot10["_group"] = "Bottom 10"
            display = pd.concat([top10, bot10], ignore_index=True)
        display = display.iloc[::-1].reset_index(drop=True)

        fig1 = px.bar(
            display,
            x="capex_per_capita_f",
            y="label",
            color="tier",
            color_discrete_map=TIER_COLORS_HEX,
            orientation="h",
            facet_row="_group" if display["_group"].nunique() > 1 else None,
            category_orders={"tier": list(US_TIERS)},
        )
        fig1.update_layout(
            xaxis_title=f"Capex per capita ({CURRENCY})",
            yaxis_title=None,
            margin=dict(l=10, r=10, t=10, b=10),
            height=520,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        fig1.update_yaxes(matches=None, showticklabels=True)
        fig1.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig1, use_container_width=True)

    # --- Chart 2: Distribution histogram -----------------------------------
    with grid[1]:
        st.markdown("**Capex per capita distribution**")
        st.caption(
            "Histogram across the filtered set. Vertical lines mark cities "
            "currently selected in the comparison view; dashed line is the "
            "median."
        )
        fig2 = go.Figure()
        fig2.add_trace(
            go.Histogram(
                x=chart_df["capex_per_capita_f"],
                nbinsx=25,
                marker_color="rgba(107,114,128,0.55)",
                marker_line_color="rgba(60,60,60,0.6)",
                marker_line_width=0.5,
                hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>",
                name="Filtered set",
            )
        )

        median_val = float(chart_df["capex_per_capita_f"].median())
        fig2.add_vline(
            x=median_val,
            line_dash="dash",
            line_color="#374151",
            annotation_text=f"Median: ${median_val:,.0f}",
            annotation_position="top",
        )

        selected_compare_labels = st.session_state.get("us_compare_select", [])
        if selected_compare_labels:
            compare_lookup = filtered.copy()
            compare_lookup["_label"] = (
                compare_lookup["municipality"].astype(str)
                + ", "
                + compare_lookup["state_province"].astype(str)
            )
            sel_rows = compare_lookup[
                compare_lookup["_label"].isin(selected_compare_labels)
            ]
            for _, row in sel_rows.iterrows():
                color = TIER_COLORS_HEX.get(row["tier"], "#374151")
                fig2.add_vline(
                    x=float(row["capex_per_capita"]),
                    line_dash="solid",
                    line_color=color,
                    annotation_text=str(row["municipality"]),
                    annotation_position="bottom",
                    annotation_font_color=color,
                )

        fig2.update_layout(
            xaxis_title=f"Capex per capita ({CURRENCY})",
            yaxis_title="Municipalities",
            margin=dict(l=10, r=10, t=10, b=10),
            height=520,
            showlegend=False,
            bargap=0.05,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # --- Chart 3: State averages (population-weighted) ---------------------
    with grid[2]:
        st.markdown("**State averages (population-weighted)**")
        st.caption(
            f"Average capex per capita ({CURRENCY}) by state, weighted by "
            "population."
        )
        agg = (
            chart_df.groupby("state_province", dropna=True)
            .agg(
                total_capex=("capex_local", "sum"),
                total_pop=("population", "sum"),
                n=("municipality", "count"),
            )
            .reset_index()
        )
        agg["weighted_avg"] = agg["total_capex"] / agg["total_pop"]
        agg = agg.sort_values("weighted_avg", ascending=True)
        truncated_total = len(agg)
        truncated = False
        if len(agg) > 25:
            agg = agg.tail(25)
            truncated = True
        agg["display_label"] = agg.apply(
            lambda r: (
                f"{r['state_province']}*" if r["n"] == 1 else r["state_province"]
            ),
            axis=1,
        )
        agg["count_text"] = agg["n"].map(lambda v: f"n={v}")

        fig3 = go.Figure(
            go.Bar(
                x=agg["weighted_avg"],
                y=agg["display_label"],
                orientation="h",
                marker_color="rgba(37,99,235,0.85)",
                text=agg["count_text"],
                textposition="outside",
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Pop-weighted avg: $%{x:,.0f}<br>"
                    "%{text}<extra></extra>"
                ),
            )
        )
        fig3.update_layout(
            xaxis_title=f"Capex per capita ({CURRENCY})",
            yaxis_title=None,
            margin=dict(l=10, r=40, t=10, b=10),
            height=520,
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.caption(
            "States marked with `*` contain a single municipality — the "
            "value reflects that city, not a regional average."
        )
        if truncated:
            st.caption(f"Showing top 25 of {truncated_total} states.")

st.divider()

# --- Comparison view -------------------------------------------------------
st.subheader("Compare municipalities")
st.caption(
    "Pick up to 3 municipalities from the current filter to compare side by "
    "side."
)

filtered_for_compare = filtered.copy()
filtered_for_compare["_label"] = (
    filtered_for_compare["municipality"].astype(str)
    + ", "
    + filtered_for_compare["state_province"].astype(str)
)
compare_options = filtered_for_compare["_label"].sort_values().tolist()

selected_labels: list[str] = st.multiselect(
    "Municipalities",
    options=compare_options,
    default=[],
    max_selections=3,
    key="us_compare_select",
)

if not selected_labels:
    st.caption("No municipalities selected.")
else:
    sel = filtered_for_compare[filtered_for_compare["_label"].isin(selected_labels)]

    def _fmt_int(v: object) -> str:
        if pd.isna(v):
            return "N/A"
        return f"{int(v):,}"

    def _fmt_money(v: object) -> str:
        if pd.isna(v):
            return "N/A"
        return f"${float(v):,.0f} {CURRENCY}"

    def _fmt_str(v: object) -> str:
        if pd.isna(v) or v == "":
            return "N/A"
        return str(v)

    cols = st.columns(len(sel))
    for col, (_, row) in zip(cols, sel.iterrows()):
        with col:
            st.markdown(
                f"<div style='border-left:6px solid "
                f"{TIER_COLORS_HEX.get(row['tier'], '#6b7280')};"
                "padding:6px 12px;background-color:rgba(127,127,127,0.06);"
                "border-radius:4px;margin-bottom:8px;'>"
                f"<div style='font-size:1.1rem;font-weight:600;'>"
                f"{row['municipality']}</div>"
                f"<div style='font-size:0.85rem;color:#6b7280;'>"
                f"{row['state_province']}</div>"
                f"<div style='font-size:0.85rem;'>Tier: <b>{row['tier']}</b></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            rows_to_show: list[tuple[str, str]] = [
                ("Population", _fmt_int(row["population"])),
                ("Capex", _fmt_money(row["capex_local"])),
                ("Capex per capita", _fmt_money(row["capex_per_capita"])),
                ("Capex score (0-4)", _fmt_int(row["capex_score"])),
                ("Data source", _fmt_str(row["data_source"])),
            ]
            comp_df = pd.DataFrame(rows_to_show, columns=["Field", "Value"])
            st.dataframe(
                comp_df,
                use_container_width=True,
                hide_index=True,
                height=min(40 + 36 * len(comp_df), 520),
            )

st.divider()

# --- Drill-down table + CSV download --------------------------------------
st.subheader("Filtered results")
st.caption(f"Showing **{len(filtered):,}** of {len(df):,} US municipalities.")

show_all_cols = st.toggle(
    "Show all columns (including internal fields)",
    value=False,
    key="us_show_all_cols",
)

if show_all_cols:
    table_df = filtered
else:
    table_df = filtered.drop(columns=list(INTERNAL_COLUMNS), errors="ignore")

st.dataframe(table_df, use_container_width=True, height=400, hide_index=True)

csv_bytes = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download filtered data (CSV)",
    data=csv_bytes,
    file_name="municipal_capex_us.csv",
    mime="text/csv",
)
