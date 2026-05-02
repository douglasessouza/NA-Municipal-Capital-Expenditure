"""Geocode municipalities via Nominatim with a JSON-file cache.

Cache file: geocode_cache.json next to this module.
Cache key:  "{country}|{state_province}|{municipality}"
Cache value: {"lat": float, "lon": float, "display": str} or None on failure.

Run as a script to populate the cache for every row in the Combined sheet:

    python geocoding.py
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import TypedDict

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent / "geocode_cache.json"
USER_AGENT = "municipal-capex-dashboard (academic project)"
NOMINATIM_DELAY_SECONDS = 1.1


class Coord(TypedDict):
    lat: float
    lon: float
    display: str


def _cache_key(country: str, state_province: str, municipality: str) -> str:
    return f"{country}|{state_province}|{municipality}"


def _load_cache() -> dict[str, Coord | None]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Geocode cache is corrupt; starting fresh.")
        return {}


def _save_cache(cache: dict[str, Coord | None]) -> None:
    CACHE_PATH.write_text(
        json.dumps(cache, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _query_nominatim(
    municipality: str, state_province: str, country: str
) -> Coord | None:
    """Single Nominatim lookup. Returns None on miss or transient error."""
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut
    from geopy.geocoders import Nominatim

    geocoder = Nominatim(user_agent=USER_AGENT, timeout=10)
    country_q = "United States" if country == "US" else country
    query = f"{municipality}, {state_province}, {country_q}"
    try:
        loc = geocoder.geocode(query, addressdetails=False, exactly_one=True)
    except (GeocoderServiceError, GeocoderTimedOut) as exc:
        logger.warning("Geocoder error for %s: %s", query, exc)
        return None
    if loc is None:
        return None
    return {
        "lat": float(loc.latitude),
        "lon": float(loc.longitude),
        "display": str(loc.address),
    }


def build_cache(df: pd.DataFrame, *, force: bool = False) -> dict[str, Coord | None]:
    """Geocode every (country, state_province, municipality) in df.

    Persists to disk after every successful lookup so a crash mid-run doesn't
    discard prior progress. Already-cached keys are skipped unless force=True.
    """
    cache = {} if force else _load_cache()
    rows = df[["country", "state_province", "municipality"]].drop_duplicates()
    total = len(rows)
    new_lookups = 0

    for i, (country, state_province, municipality) in enumerate(
        rows.itertuples(index=False, name=None), start=1
    ):
        key = _cache_key(country, state_province, municipality)
        if key in cache:
            continue

        coord = _query_nominatim(municipality, state_province, country)
        cache[key] = coord
        new_lookups += 1

        status = "OK" if coord else "MISS"
        msg = f"[{i}/{total}] {key} -> {status}"
        logger.info(msg)
        print(msg)

        _save_cache(cache)
        time.sleep(NOMINATIM_DELAY_SECONDS)

    print(f"Done. {new_lookups} new lookups, {total} unique keys total.")
    return cache


def attach_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with `lat` and `lon` columns from the cache.

    Rows whose key is missing from the cache or whose cache value is None
    receive NaN for lat/lon.
    """
    cache = _load_cache()
    out = df.copy()

    def _lookup(row: pd.Series) -> tuple[float | None, float | None]:
        key = _cache_key(row["country"], row["state_province"], row["municipality"])
        coord = cache.get(key)
        if coord is None:
            return (None, None)
        return (coord["lat"], coord["lon"])

    coords = out.apply(_lookup, axis=1, result_type="expand")
    out["lat"] = pd.to_numeric(coords[0], errors="coerce").astype("Float64")
    out["lon"] = pd.to_numeric(coords[1], errors="coerce").astype("Float64")
    return out


def report_missing(df: pd.DataFrame) -> list[str]:
    """Return cache keys present in df but missing or null in the cache."""
    cache = _load_cache()
    missing: list[str] = []
    for country, state_province, municipality in (
        df[["country", "state_province", "municipality"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    ):
        key = _cache_key(country, state_province, municipality)
        if key not in cache or cache[key] is None:
            missing.append(key)
    return missing


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from data_loader import load_combined

    df = load_combined()
    build_cache(df)
    miss = report_missing(df)
    if miss:
        print(f"\n{len(miss)} keys still missing after run:")
        for m in miss:
            print(f"  - {m}")
    else:
        print("\nAll keys cached.")
