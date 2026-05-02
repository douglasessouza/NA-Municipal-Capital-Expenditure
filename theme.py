"""Shared visual tokens: tier ordering, palette, and per-country tier sets."""

from __future__ import annotations

TIER_ORDER: tuple[str, ...] = (
    "Leaders",
    "Challengers",
    "Visionaries",
    "Niche Players",
)

TIER_COLORS_HEX: dict[str, str] = {
    "Leaders": "#22c55e",
    "Challengers": "#2563eb",
    "Visionaries": "#8b5cf6",
    "Niche Players": "#6b7280",
}

TIER_COLORS_RGB: dict[str, tuple[int, int, int]] = {
    "Leaders": (34, 197, 94),
    "Challengers": (37, 99, 235),
    "Visionaries": (139, 92, 246),
    "Niche Players": (107, 114, 128),
}

# Tiers actually present in each country's data. Spec requires Canada to
# show only the tiers it has, US to show all four.
CANADA_TIERS: tuple[str, ...] = ("Leaders", "Visionaries")
US_TIERS: tuple[str, ...] = TIER_ORDER

# Full state/province name -> 2-letter abbreviation, restricted to entries
# present in the workbook (43 US states + 8 Canadian provinces).
STATE_ABBREVIATIONS: dict[str, str] = {
    # US
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Florida": "FL",
    "Georgia": "GA",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Virginia": "VA",
    "Washington": "WA",
    "Wisconsin": "WI",
    # Canada
    "Alberta": "AB",
    "British Columbia": "BC",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Nova Scotia": "NS",
    "Ontario": "ON",
    "Quebec": "QC",
    "Saskatchewan": "SK",
}


def state_abbrev(name: str | None) -> str:
    """Return 2-letter abbreviation, or the original name if not in the map."""
    if name is None:
        return ""
    return STATE_ABBREVIATIONS.get(name, name)
