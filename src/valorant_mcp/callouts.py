import json
import math
from pathlib import Path

import httpx

CACHE_FILE = Path.home() / ".cache" / "valorant-mcp" / "maps.json"
MAPS_URL = "https://valorant-api.com/v1/maps"

_cache: dict | None = None


async def ensure_loaded() -> None:
    global _cache
    if _cache is not None:
        return
    if CACHE_FILE.exists():
        _cache = json.loads(CACHE_FILE.read_text())
        return
    async with httpx.AsyncClient() as client:
        response = await client.get(MAPS_URL)
        response.raise_for_status()
        data = response.json()["data"]

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

    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(maps))
    _cache = maps


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
