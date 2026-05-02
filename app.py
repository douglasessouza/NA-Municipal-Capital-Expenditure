"""Streamlit dashboard: North American Municipal CapEx (75K-300K population)."""

from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from data_loader import load_combined
from geocoding import attach_coords

TIER_ORDER: tuple[str, ...] = (
    "Leaders",
    "Challengers",
    "Visionaries",
    "Niche Players",
)

TIER_COLORS_HEX: dict[str, str] = {
    "Leaders": "#22c55e",        # green
    "Challengers": "#2563eb",    # blue
    "Visionaries": "#8b5cf6",    # purple
    "Niche Players": "#6b7280",  # grey
}

TIER_COLORS_RGB: dict[str, tuple[int, int, int]] = {
    "Leaders": (34, 197, 94),
    "Challengers": (37, 99, 235),
    "Visionaries": (139, 92, 246),
    "Niche Players": (107, 114, 128),
}

COUNTRY_OPTIONS: tuple[str, ...] = ("Both", "Canada", "US")


def _country_filter(df: pd.DataFrame, choice: str) -> pd.DataFrame:
    if choice == "Both":
        return df
    return df[df["country"] == choice]


def _reset_filters() -> None:
    """Clear all filter widgets by deleting their session_state keys."""
    for key in (
        "country_choice",
        "tier_select",
        "state_select",
        "fy_select",
        "population_range",
    ):
        st.session_state.pop(key, None)
    # Capex-per-capita slider is keyed per country choice
    for c in COUNTRY_OPTIONS:
        st.session_state.pop(f"capex_pc_range_{c}", None)


st.set_page_config(
    layout="wide",
    page_title="Municipal CapEx Dashboard",
    page_icon=None,
)

st.title("North American Municipal Capital Expenditure")
st.caption(
    "Mid-size cities (75,000-300,000 residents) across the US and Canada - "
    "explore how much each municipality invests in capital projects, and how "
    "they're tiered."
)

with st.expander("How to read this dashboard - methodology note", expanded=True):
    st.info(
        "**The two countries were measured differently.** US tiers come from "
        "capital expenditure per capita alone (single-axis), using FY2022 US "
        "Census Bureau data covering construction CapEx only. Canadian tiers "
        "use both capital expenditure **and** a strategic-vision score "
        "(two-axis), using FY2025/26 figures pulled directly from municipal "
        "open-data portals and covering total CapEx.\n\n"
        "As a result:\n"
        "- A US 'Visionary' and a Canadian 'Visionary' do not mean the same "
        "thing.\n"
        "- US municipalities have no vision score (shown as N/A).\n"
        "- Direct dollar comparisons are imperfect: US figures are "
        "construction-only and three years older.\n\n"
        "When both countries are visible, capital expenditure is shown in "
        "USD-equivalent. When a single country is selected, it's shown in "
        "local currency. Currency labels are always present."
    )

df = load_combined()

# Country toggle (top of page, above sidebar filters)
country_choice: str = st.radio(
    "Country",
    options=COUNTRY_OPTIONS,
    index=0,
    horizontal=True,
    key="country_choice",
    help="Switch between viewing both countries together, only Canada, or only the US.",
)

country_df = _country_filter(df, country_choice)

# Sidebar filters
with st.sidebar:
    st.header("Filters")
    st.button("Reset filters", on_click=_reset_filters, use_container_width=True)
    st.caption(
        "Tier counts differ structurally by country (the two countries were "
        "scored with different methods). The methodology note at the top "
        "explains why."
    )

    tier_options = [t for t in TIER_ORDER if t in set(country_df["tier"].dropna())]
    selected_tiers: list[str] = st.multiselect(
        "Tier",
        options=tier_options,
        default=tier_options,
        key="tier_select",
    )

    state_options = sorted(country_df["state_province"].dropna().unique().tolist())
    state_label = "Province" if country_choice == "Canada" else (
        "State" if country_choice == "US" else "State / Province"
    )
    selected_states: list[str] = st.multiselect(
        state_label,
        options=state_options,
        default=state_options,
        key="state_select",
    )

    fy_options = sorted(int(v) for v in country_df["fiscal_year"].dropna().unique())
    selected_fys: list[int] = st.multiselect(
        "Fiscal year",
        options=fy_options,
        default=fy_options,
        key="fy_select",
        help="US data is FY2022; Canadian data is FY2025/26.",
    )

    pop_min = int(country_df["population"].min())
    pop_max = int(country_df["population"].max())
    if pop_min == pop_max:
        pop_max = pop_min + 1
    population_range: tuple[int, int] = st.slider(
        "Population",
        min_value=pop_min,
        max_value=pop_max,
        value=(pop_min, pop_max),
        step=1000,
        key="population_range",
    )

    # Capex-per-capita slider: switches between USD-equiv (Both) and local
    # currency (single country). Widget is keyed on country so changing the
    # country toggle forces a fresh slider instance with the right range.
    if country_choice == "Both":
        cpc_series = country_df["capex_usd_equiv"] / country_df["population"]
        cpc_unit = "USD"
    elif country_choice == "Canada":
        cpc_series = country_df["capex_per_capita"]
        cpc_unit = "CAD"
    else:  # US
        cpc_series = country_df["capex_per_capita"]
        cpc_unit = "USD"

    cpc_min = float(cpc_series.min())
    cpc_max = float(cpc_series.max())
    if cpc_min == cpc_max:
        cpc_max = cpc_min + 1.0
    capex_pc_range: tuple[float, float] = st.slider(
        f"Capex per capita ({cpc_unit})",
        min_value=float(round(cpc_min, 2)),
        max_value=float(round(cpc_max, 2)),
        value=(float(round(cpc_min, 2)), float(round(cpc_max, 2))),
        step=10.0,
        key=f"capex_pc_range_{country_choice}",
        help=(
            "Per-capita capital expenditure. When 'Both' is selected, this is "
            "USD-equivalent across both countries; otherwise it's local currency."
        ),
    )


def _apply_filters(
    base: pd.DataFrame,
    tiers: list[str],
    states: list[str],
    fys: list[int],
    pop_range: tuple[int, int],
    cpc_range: tuple[float, float],
    cpc_country_choice: str,
) -> pd.DataFrame:
    out = base
    if tiers:
        out = out[out["tier"].isin(tiers)]
    else:
        out = out.iloc[0:0]
    if states:
        out = out[out["state_province"].isin(states)]
    else:
        out = out.iloc[0:0]
    if fys:
        out = out[out["fiscal_year"].isin(fys)]
    else:
        out = out.iloc[0:0]
    lo, hi = pop_range
    out = out[(out["population"] >= lo) & (out["population"] <= hi)]

    cpc_lo, cpc_hi = cpc_range
    if cpc_country_choice == "Both":
        cpc = out["capex_usd_equiv"] / out["population"]
    else:
        cpc = out["capex_per_capita"]
    out = out[(cpc >= cpc_lo) & (cpc <= cpc_hi)]
    return out


filtered = _apply_filters(
    country_df,
    selected_tiers,
    selected_states,
    selected_fys,
    population_range,
    capex_pc_range,
    country_choice,
)

# --- KPI cards -------------------------------------------------------------
st.subheader("Summary")

n_munis = len(filtered)
total_capex_usd = (
    float(filtered["capex_usd_equiv"].sum()) if n_munis else 0.0
)
if n_munis and filtered["population"].sum():
    avg_capex_pc_usd = total_capex_usd / float(filtered["population"].sum())
else:
    avg_capex_pc_usd = 0.0

kpi_cols = st.columns(3)
kpi_cols[0].metric("Municipalities", f"{n_munis:,}")
kpi_cols[1].metric("Total capex (USD)", f"${total_capex_usd:,.0f}")
kpi_cols[2].metric(
    "Avg capex per capita (USD)",
    f"${avg_capex_pc_usd:,.0f}",
    help=(
        "Population-weighted: total capex (USD-equiv) divided by total "
        "population in the filtered set."
    ),
)

st.markdown("**Tier counts**")
tier_counts = (
    filtered["tier"].value_counts().reindex(TIER_ORDER, fill_value=0)
)
tier_cols = st.columns(len(TIER_ORDER))
for col, tier in zip(tier_cols, TIER_ORDER):
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
    options=("Total capex (USD)", "Capex per capita (USD)"),
    index=0,
    horizontal=True,
    key="map_metric",
)

map_df = attach_coords(filtered).copy()
map_df = map_df.dropna(subset=["lat", "lon"])

if map_df.empty:
    st.info("No mappable rows in the current filter.")
else:
    # Coerce nullable dtypes to plain Python floats/ints for pydeck/JSON.
    map_df["lat"] = map_df["lat"].astype(float)
    map_df["lon"] = map_df["lon"].astype(float)
    map_df["population_int"] = map_df["population"].astype(int)
    map_df["capex_usd_equiv_f"] = map_df["capex_usd_equiv"].astype(float)
    map_df["capex_local_f"] = map_df["capex_local"].astype(float)
    map_df["capex_per_capita_f"] = map_df["capex_per_capita"].astype(float)
    map_df["capex_pc_usd_f"] = (
        map_df["capex_usd_equiv_f"] / map_df["population_int"]
    )

    if map_metric == "Total capex (USD)":
        radius_basis = map_df["capex_usd_equiv_f"]
        radius_max_meters = 60_000.0
    else:
        radius_basis = map_df["capex_pc_usd_f"]
        radius_max_meters = 40_000.0

    basis_max = float(radius_basis.max()) or 1.0
    map_df["bubble_radius"] = (
        (radius_basis / basis_max).clip(lower=0.05) * radius_max_meters
    )

    map_df["fill_color"] = map_df["tier"].map(
        lambda t: list(TIER_COLORS_RGB.get(t, (160, 160, 160))) + [180]
    )

    # Pre-format display strings so the tooltip stays simple HTML
    map_df["capex_local_disp"] = map_df.apply(
        lambda r: f"{r['capex_local_f']:,.0f} {r['currency']}", axis=1
    )
    map_df["capex_usd_disp"] = map_df["capex_usd_equiv_f"].map(
        lambda v: f"${v:,.0f}"
    )
    map_df["capex_pc_disp"] = map_df.apply(
        lambda r: f"{r['capex_per_capita_f']:,.0f} {r['currency']}", axis=1
    )
    map_df["population_disp"] = map_df["population_int"].map(lambda v: f"{v:,}")
    map_df["fy_disp"] = map_df["fiscal_year"].astype("Int64").astype(str)

    # Default North America view
    view_state = pdk.ViewState(
        latitude=45.0,
        longitude=-95.0,
        zoom=3,
        pitch=0,
        bearing=0,
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
            "<b>{municipality}</b>, {state_province} ({country})<br/>"
            "Tier: <b>{tier}</b><br/>"
            "Population: {population_disp}<br/>"
            "Capex (local): {capex_local_disp}<br/>"
            "Capex (USD-equiv): {capex_usd_disp}<br/>"
            "Capex per capita: {capex_pc_disp}<br/>"
            "Fiscal year: {fy_disp}<br/>"
            "Method: {classification_method}"
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
        map_style=None,  # neutral default; no Mapbox token required
    )
    st.pydeck_chart(deck, use_container_width=True)

    # Legend (matches tier colors used everywhere else)
    legend_cols = st.columns(len(TIER_ORDER))
    for col, tier in zip(legend_cols, TIER_ORDER):
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

# --- Comparison view -------------------------------------------------------
st.subheader("Compare municipalities")
st.caption(
    "Pick up to 3 municipalities from the current filter to compare side by "
    "side. Capex is shown in both local currency and USD-equivalent."
)

filtered_for_compare = filtered.copy()
filtered_for_compare["_label"] = (
    filtered_for_compare["municipality"].astype(str)
    + ", "
    + filtered_for_compare["state_province"].astype(str)
    + " ("
    + filtered_for_compare["country"].astype(str)
    + ")"
)
compare_options = filtered_for_compare["_label"].sort_values().tolist()

selected_labels: list[str] = st.multiselect(
    "Municipalities",
    options=compare_options,
    default=[],
    max_selections=3,
    key="compare_select",
)

if not selected_labels:
    st.caption("No municipalities selected.")
else:
    sel = filtered_for_compare[filtered_for_compare["_label"].isin(selected_labels)]

    countries_in_sel = set(sel["country"].dropna().unique())
    fys_in_sel = set(int(v) for v in sel["fiscal_year"].dropna().unique())
    methods_in_sel = set(sel["classification_method"].dropna().unique())

    if len(countries_in_sel) > 1 or len(fys_in_sel) > 1 or len(methods_in_sel) > 1:
        st.warning(
            "You're comparing municipalities across different countries, "
            "fiscal years, or scoring methods. Direct comparisons are "
            "imperfect — see the methodology note at the top."
        )

    def _fmt_int(v: object) -> str:
        if pd.isna(v):
            return "N/A"
        return f"{int(v):,}"

    def _fmt_money(v: object, unit: str) -> str:
        if pd.isna(v):
            return "N/A"
        return f"{float(v):,.0f} {unit}"

    def _fmt_float(v: object, digits: int = 2) -> str:
        if pd.isna(v):
            return "N/A"
        return f"{float(v):,.{digits}f}"

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
                f"{row['state_province']}, {row['country']}</div>"
                f"<div style='font-size:0.85rem;'>Tier: <b>{row['tier']}</b></div>"
                "</div>",
                unsafe_allow_html=True,
            )

            local_unit = str(row["currency"])
            rows_to_show: list[tuple[str, str]] = [
                ("Population", _fmt_int(row["population"])),
                ("Fiscal year", _fmt_int(row["fiscal_year"])),
                (
                    "Capex (local)",
                    _fmt_money(row["capex_local"], local_unit),
                ),
                (
                    "Capex (USD-equiv)",
                    _fmt_money(row["capex_usd_equiv"], "USD"),
                ),
                (
                    "Capex per capita (local)",
                    _fmt_money(row["capex_per_capita"], local_unit),
                ),
                ("FX rate to USD", _fmt_float(row["fx_rate_to_usd"], 4)),
                ("Capex score (0-4)", _fmt_int(row["capex_score"])),
                (
                    "Vision score raw (0-6)",
                    _fmt_float(row["vision_score_raw"], 1),
                ),
                (
                    "Vision score norm (0-4)",
                    _fmt_float(row["vision_score_norm"], 1),
                ),
                ("Classification method", _fmt_str(row["classification_method"])),
                ("Governance type", _fmt_str(row["governance_type"])),
                ("Data source", _fmt_str(row["data_source"])),
            ]
            comp_df = pd.DataFrame(rows_to_show, columns=["Field", "Value"])
            st.dataframe(
                comp_df,
                use_container_width=True,
                hide_index=True,
                height=min(40 + 36 * len(comp_df), 520),
            )

            notes = row.get("notes")
            if pd.notna(notes) and str(notes).strip():
                with st.expander("Notes"):
                    st.write(str(notes))

st.divider()

# --- Drill-down table + CSV download --------------------------------------
st.subheader("Filtered results")
st.caption(
    f"Showing **{len(filtered):,}** of {len(df):,} municipalities "
    f"(country: {country_choice})."
)

INTERNAL_COLUMNS: tuple[str, ...] = (
    "fx_rate_to_usd",
    "classification_method",
    "data_source",
)

show_all_cols = st.toggle(
    "Show all columns (including internal fields)",
    value=False,
    key="show_all_cols",
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
    file_name="municipal_capex_filtered.csv",
    mime="text/csv",
)
