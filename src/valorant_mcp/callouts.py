import json
import math
from collections.abc import Iterable
from pathlib import Path

import httpx

CACHE_FILE = Path.home() / ".cache" / "valorant-mcp" / "maps.json"
MAPS_URL = "https://valorant-api.com/v1/maps"

_cache: dict | None = None
_refreshed = False


async def ensure_loaded(required: Iterable[str] = ()) -> None:
    """Load callouts; re-download once if a map we need is missing (new map release)."""
    global _cache, _refreshed
    if _cache is None and CACHE_FILE.exists():
        try:
            _cache = json.loads(CACHE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            _cache = None
    missing = _cache is None or any(m and m.lower() not in _cache for m in required)
    if not missing or (_cache is not None and _refreshed):
        return
    _refreshed = True
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MAPS_URL, timeout=15.0)
            response.raise_for_status()
            data = response.json()["data"]
    except (httpx.HTTPError, KeyError, ValueError):
        _cache = _cache or {}
        return

    maps: dict[str, list[dict]] = {}
    for m in data:
        name = (m.get("displayName") or "").lower()
        if not name:
            continue
        callouts = []
        for co in m.get("callouts") or []:
            loc = co.get("location") or {}
            if loc.get("x") is None or loc.get("y") is None:
                continue
            callouts.append({
                "region": co.get("regionName"),
                "super": co.get("superRegionName"),
                "x": loc["x"],
                "y": loc["y"],
            })
        if callouts:
            maps[name] = callouts

    _cache = maps
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(maps))
    except OSError:
        pass


def resolve(map_name: str, x: float | None, y: float | None) -> tuple[str | None, str | None]:
    if _cache is None or x is None or y is None:
        return None, None
    callouts = _cache.get((map_name or "").lower())
    if not callouts:
        return None, None

    best = None
    best_d = math.inf
    for c in callouts:
        d = (c["x"] - x) ** 2 + (c["y"] - y) ** 2
        if d < best_d:
            best_d = d
            best = c
    return (best["region"], best["super"]) if best else (None, None)


def zone_label(map_name: str, x: float | None, y: float | None) -> str | None:
    """Callout with its group, e.g. 'A Main' or 'Mid Courtyard'."""
    region, super_region = resolve(map_name, x, y)
    if not region:
        return None
    if not super_region or region.lower().split()[0] == super_region.lower():
        return region
    return f"{super_region} {region}"
