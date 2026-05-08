# Municipal CapEx Dashboard

A Streamlit dashboard for exploring capital expenditure across mid-size
North American municipalities (population 75,000–300,000). Built for a
Master of Data Analytics co-op project; intended for non-technical
stakeholders who want to explore the data the way they'd explore a Power BI
report — clicking filters, hovering on a map — without writing code.

## App layout

The app is a **Streamlit multipage app with three pages**, deliberately
split because the underlying datasets are not directly comparable (see
"Why two pages?" below).

1. **Overview & Methodology** (landing, `app.py`) — no dashboard. Shows
   the cohort counts (Canada 62 / US 419 / Total 481), how to use the
   app, the methodology asymmetry between the two datasets, and tier
   definitions. Read this first.
2. **Canada** (`pages/1_Canada.py`) — Canada-only dashboard. CAD throughout.
   Tier filter limited to the tiers present in the Canadian data
   (Leaders, Visionaries). Province filter, fiscal-year filter (FY2025/26),
   population and capex-per-capita range sliders. Map, KPI cards,
   **Distributions & rankings** section (Top/Bottom rankings, capex-per-capita
   histogram with comparison-view overlays, province pop-weighted averages,
   and a Canada-only tier scatter of capex score vs vision score with
   quadrant shading), comparison view (with vision-score and governance
   fields), drill-down table, CSV export to `municipal_capex_canada.csv`.
3. **United States** (`pages/2_United_States.py`) — US-only dashboard.
   USD throughout. All four tiers in the filter. State filter, no
   fiscal-year filter (only FY2022 — surfaced in a caption). Population
   and capex-per-capita range sliders. Map, KPI cards, **Distributions &
   rankings** section (Top/Bottom rankings, capex-per-capita histogram
   with comparison-view overlays, state pop-weighted averages — no tier
   scatter on this page since US data has no vision score), comparison
   view (no vision-score, governance, FX rate, or classification rows —
   they are uninformative for US data), drill-down table, CSV export to
   `municipal_capex_us.csv`.

Each country page has independent session state (filter keys are
prefixed `ca_*` and `us_*`), so switching pages does not bleed filter
state from one country into the other.

## Files

| File | Purpose |
|---|---|
| `app.py` | Overview & methodology landing page (no widgets) |
| `pages/1_Canada.py` | Canada-only dashboard |
| `pages/2_United_States.py` | US-only dashboard |
| `theme.py` | Tier ordering, colors (hex + RGB), per-country tier sets, state/province abbreviations |
| `data_loader.py` | Loads the `Combined` sheet of the workbook (cached) |
| `geocoding.py` | Nominatim geocoder + JSON cache |
| `geocode_cache.json` | Pre-computed coordinates for every municipality |
| `P1_Municipal_CapEx_Combined.xlsx` | Source workbook |
| `requirements.txt` | Pinned Python dependencies |

## Why two pages?

Earlier versions had a single dashboard with a `Both / Canada / US`
toggle. That was misleading: it put two structurally different datasets
in the same view and invited cross-country comparisons that the data
does not support. The split removes the structural problem instead of
papering over it with callouts.

| Dimension | US (419 cities) | Canada (62 cities) |
|---|---|---|
| Source | US Census Bureau Annual Survey FY2022 | Municipal open-data portals, FY2025/26 |
| Capex coverage | Construction CapEx only | Total CapEx |
| Scoring | Single-axis (capex per capita) | Two-axis (capex + strategic-vision score) |
| Vision score | Not collected | 0–6 raw, 0–4 normalized |
| Currency | USD | CAD |

A "Visionary" in the US (high per-capita construction capex) and a
"Visionary" in Canada (above-median total capex *and* above-median
strategic-vision score) do not mean the same thing, even though they
share a label. Putting both on one page hid this; putting them on two
pages makes the asymmetry obvious.

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

Two reasonable options:

- **Local / on-prem**: run `streamlit run app.py` on any machine that can
  reach the workbook. No external services are required at runtime — the
  geocode cache is read from disk.
- **Streamlit Community Cloud** (free for public repos): push this folder
  to a GitHub repo and connect it from <https://share.streamlit.io>. Set
  the main file to `app.py` and the Python version to 3.11. Streamlit
  auto-discovers files under `pages/`, so all three pages will be
  navigable. The committed `geocode_cache.json` means the deployed app
  never needs to call Nominatim, which matters because Streamlit Cloud's
  outbound network and Nominatim's rate limits do not mix well.

No database, no auth, no secrets.

## Honest-data behaviors built into the pages

- Currency unit (`USD` or `CAD`) is always printed next to a capex
  number — there is never a raw figure without its unit.
- The Canada page only lists tiers actually present in Canadian data
  (Leaders, Visionaries). The US page lists all four.
- The US comparison view does not show vision-score / governance / FX /
  classification rows, since none of those fields are populated for US
  municipalities. They are simply absent rather than rendered as "N/A".
- The Canada comparison view warns when selected cities span FY2025 and
  FY2026.
- The Overview page is the single place that talks about cross-country
  asymmetry; the country pages do not duplicate or invite that
  comparison.
- State/province average bars are **population-weighted**
  (`sum(capex_local) / sum(population)`), not simple means. Single-city
  groups are flagged with `*` and a caption clarifying they reflect one
  city, not a regional average.
- The histogram on each country page reads the comparison-view selection
  from session state and overlays vertical lines for selected cities;
  picking cities in the comparison view highlights them on the
  histogram automatically.

## Geocoding overrides

A few municipalities cannot be resolved by Nominatim (e.g. names with
slashes like **Greater Sudbury / Grand Sudbury**, Ontario). Coordinates
for these are hardcoded in `MANUAL_OVERRIDES` at the top of
`geocoding.py` and re-seeded into the cache on every rebuild, so
`python geocoding.py` is safe to re-run without losing them.
