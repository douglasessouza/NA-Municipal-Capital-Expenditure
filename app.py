"""Overview & methodology — landing page of the multipage dashboard.

The actual country dashboards live under `pages/`. This page has no widgets;
it explains the cohort, the methodology asymmetry, and the tier definitions,
and points users to the per-country pages.
"""

from __future__ import annotations

import streamlit as st

from data_loader import load_combined
from theme import TIER_COLORS_HEX, TIER_ORDER

st.set_page_config(
    layout="wide",
    page_title="Municipal CapEx — Overview",
    page_icon=None,
)

st.title("North American Municipal Capital Expenditure")
st.caption(
    "Mid-size cities (75,000–300,000 residents) across the US and Canada. "
    "Each country is its own dashboard — pick one from the sidebar."
)

df = load_combined()
n_total = len(df)
n_ca = int((df["country"] == "Canada").sum())
n_us = int((df["country"] == "US").sum())

count_cols = st.columns(3)
count_cols[0].metric("Canada", f"{n_ca:,}")
count_cols[1].metric("United States", f"{n_us:,}")
count_cols[2].metric("Total", f"{n_total:,}")

st.divider()

st.subheader("How to use this dashboard")
st.markdown(
    "- Open the **Canada** or **United States** page from the sidebar.\n"
    "- Use the sidebar filters on each page to narrow the cohort.\n"
    "- Hover over the map for city-level detail; pick up to three cities in "
    "the comparison view to see them side by side; download the filtered "
    "set as CSV at the bottom of each page.\n"
    "- The two pages are deliberately separate. The data behind them was "
    "collected and scored differently and is not directly comparable. "
    "Read the methodology note below before drawing cross-country "
    "conclusions."
)

st.divider()

st.subheader("Methodology — why the two countries are on separate pages")
st.info(
    "**The two countries were measured differently.** Combining them in a "
    "single view would invite the wrong comparison. Here's what differs:"
)

methodology_rows = [
    ("Source", "US Census Bureau Annual Survey FY2022",
     "Municipal open-data portals, FY2025/26"),
    ("Capex coverage", "Construction CapEx only", "Total CapEx"),
    ("Scoring", "Single-axis (capex per capita)",
     "Two-axis (capex per capita + strategic-vision score)"),
    ("Vision score", "Not collected", "0–6 raw, normalized to 0–4"),
    ("Currency", "USD", "CAD"),
    ("Cohort size", f"{n_us} cities", f"{n_ca} cities"),
]
st.table(
    {
        "Dimension": [r[0] for r in methodology_rows],
        "United States": [r[1] for r in methodology_rows],
        "Canada": [r[2] for r in methodology_rows],
    }
)

st.markdown(
    "Implications:\n\n"
    "- A 'Visionary' in the US (high per-capita capex) and a 'Visionary' "
    "in Canada (above-median capex **and** above-median vision score) do "
    "not mean the same thing.\n"
    "- The US tier mix is heavy on 'Niche Players' and includes "
    "'Challengers'; Canada has neither. That is a methodology artifact, "
    "not a real-world finding.\n"
    "- Total-dollar comparisons understate US capex relative to Canadian "
    "capex because the US figures are construction-only and three years "
    "older."
)

st.divider()

st.subheader("Tier definitions")
st.caption(
    "The same tier names are used on both pages, but the underlying "
    "scoring rubric differs by country (see methodology table above)."
)

tier_descriptions = {
    "Leaders": (
        "High capex per capita. In Canada, also pairs with a high "
        "strategic-vision score."
    ),
    "Challengers": (
        "Above-median capex per capita but not at Leaders level. "
        "**US only** — the Canadian dataset has no Challengers tier."
    ),
    "Visionaries": (
        "In the US, mid-range capex per capita. In Canada, lower capex "
        "with a strong strategic-vision score. The label is the same; the "
        "criteria are different."
    ),
    "Niche Players": (
        "Lower capex per capita. **US only** — no Canadian municipality "
        "is classified as Niche Players."
    ),
}

for tier in TIER_ORDER:
    color = TIER_COLORS_HEX[tier]
    st.markdown(
        f"<div style='border-left:6px solid {color};padding:8px 12px;"
        "background-color:rgba(127,127,127,0.06);border-radius:4px;"
        "margin-bottom:6px;'>"
        f"<div style='font-weight:600;'>{tier}</div>"
        f"<div style='font-size:0.9rem;color:#374151;'>"
        f"{tier_descriptions[tier]}</div></div>",
        unsafe_allow_html=True,
    )

st.divider()
st.caption(
    "Pick **Canada** or **United States** in the sidebar to start "
    "exploring."
)
