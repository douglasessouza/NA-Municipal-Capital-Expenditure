# Municipal CapEx Dashboard

A Streamlit dashboard for exploring capital expenditure across mid-size
North American municipalities (population 75,000–300,000). Built for a
Master of Data Analytics co-op project; intended for non-technical
stakeholders who want to explore the data the way they'd explore a Power BI
report — clicking filters, hovering on a map — without writing code.

## What it shows

- **Country toggle** (Both / Canada / US, default Both)
- **Sidebar filters**: tier, state/province, fiscal year, population range,
  capex per capita range (unit auto-switches between USD-equivalent and local
  currency depending on country selection)
- **KPI cards**: # municipalities, total capex (USD), population-weighted avg
  capex per capita (USD), and per-tier counts in the project's tier colors
- **Interactive bubble map** (pydeck): one bubble per city, sized by capex
  (toggle between total and per-capita), colored by tier, with a hover
  tooltip showing all key fields
- **Comparison view**: pick up to 3 municipalities and see them side by side;
  warns when the selected munis span different countries / fiscal years /
  scoring methods
- **Drill-down table** with a "show all columns" toggle and CSV export

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI |
| `data_loader.py` | Loads the `Combined` sheet of the workbook (cached) |
| `geocoding.py` | Nominatim geocoder + JSON cache |
| `geocode_cache.json` | Pre-computed coordinates for every municipality |
| `P1_Municipal_CapEx_Combined.xlsx` | Source workbook |
| `requirements.txt` | Pinned Python dependencies |

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The dashboard opens at <http://localhost:8501>.

The geocode cache (`geocode_cache.json`) is committed alongside the app, so
you do not need to re-geocode on first run. If you ever want to rebuild it
from scratch:

```bash
python geocoding.py
```

This calls Nominatim once per unique `(country, state_province, municipality)`
key with a 1.1-second delay between requests (their ToS limit), and saves
after every lookup, so it is safe to interrupt and resume.

## Deployment

Two reasonable options for this kind of single-page Streamlit app:

- **Local / on-prem**: just run `streamlit run app.py` on any machine that
  can reach the workbook. No external services are required at runtime —
  the geocode cache is read from disk.
- **Streamlit Community Cloud** (free for public repos): push this folder
  to a GitHub repo and connect it from <https://share.streamlit.io>. Set the
  main file to `app.py` and the Python version to 3.11. The committed
  `geocode_cache.json` means the deployed app never needs to call Nominatim,
  which is important because Streamlit Cloud's outbound network and
  Nominatim's rate limits don't mix well.

No database, no auth, no secrets.

## Methodology — important asymmetry between US and Canada

This dashboard combines two datasets that were collected and scored
**differently**. Surface this honestly to anyone reading the dashboard;
it's also the first thing the dashboard itself says in its methodology
expander.

| Dimension | US (419 cities) | Canada (62 cities) |
|---|---|---|
| Source | US Census Bureau Annual Survey FY2022 | Municipal open-data portals, FY2025/26 |
| Capex coverage | Construction CapEx only | Total CapEx |
| Scoring | Single-axis (capex per capita) | Two-axis (capex + strategic-vision score) |
| Vision score | Not collected | 0–6 raw, 0–4 normalized |

Implications:

- A "Visionary" in the US (high per-capita capex) and a "Visionary" in
  Canada (above-median capex *and* above-median vision score) do not mean
  the same thing.
- The US tier mix is heavy on "Niche Players" and includes "Challengers";
  Canada has neither. This is a **methodology artifact**, not a real-world
  finding.
- Total-dollar comparisons understate US capex relative to Canadian capex
  because the US figures are construction-only and three years older.

The dashboard handles this by:
- Showing a methodology callout at the top, expanded by default.
- Defaulting cross-country views to USD-equivalent and labeling units
  explicitly everywhere.
- Rendering "N/A" for fields like `vision_score_norm` on US rows rather
  than fabricating a value.
- Warning in the comparison view when selected cities span different
  countries, fiscal years, or scoring methods.

## Known issues

- **Greater Sudbury / Grand Sudbury** (Ontario) currently fails Nominatim
  geocoding because of the slash in the official name. It will not appear
  on the map until a manual override coordinate is added to
  `geocode_cache.json`. All other 480 municipalities are mapped.
