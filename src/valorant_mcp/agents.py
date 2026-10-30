"""Agent roles and ability names from valorant-api.com, cached on disk."""

import json
from collections.abc import Iterable
from pathlib import Path

import httpx

CACHE_FILE = Path.home() / ".cache" / "valorant-mcp" / "agents.json"
AGENTS_URL = "https://valorant-api.com/v1/agents?isPlayableCharacter=true"

# Henrik's ability_casts keys -> valorant-api.com ability slots (and default keybinds).
SLOTS = {"grenade": ("Grenade", "C"), "ability1": ("Ability1", "Q"),
         "ability2": ("Ability2", "E"), "ultimate": ("Ultimate", "X")}

_cache: dict | None = None  # agent name (lower) -> {"role": str, "abilities": {key: name}}
_refreshed = False


async def ensure_loaded(required: Iterable[str] = ()) -> None:
    """Load the agent table; re-download once if an agent we need is missing (new release)."""
    global _cache, _refreshed
    if _cache is None and CACHE_FILE.exists():
        try:
            _cache = json.loads(CACHE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            _cache = None
    missing = _cache is None or any(a and a.lower() not in _cache for a in required)
    if not missing or (_cache is not None and _refreshed):
        return
    _refreshed = True
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(AGENTS_URL, timeout=15.0)
            response.raise_for_status()
            data = response.json()["data"]
    except (httpx.HTTPError, KeyError, ValueError):
        _cache = _cache or {}
        return

    agents = {}
    for a in data:
        by_slot = {ab.get("slot"): ab.get("displayName") for ab in a.get("abilities") or []}
        agents[a["displayName"].lower()] = {
            "role": (a.get("role") or {}).get("displayName"),
            "abilities": {key: by_slot.get(slot) for key, (slot, _) in SLOTS.items()},
        }
    _cache = agents
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(agents))
    except OSError:
        pass


def role(agent: str | None) -> str:
    if not agent or not _cache:
        return "Unknown"
    return (_cache.get(agent.lower()) or {}).get("role") or "Unknown"


def ability_label(agent: str | None, key: str) -> str:
    """e.g. 'Q: Wingman'. Falls back to the keybind alone."""
    slot_key = SLOTS[key][1]
    name = ((_cache or {}).get((agent or "").lower()) or {}).get("abilities", {}).get(key)
    return f"{slot_key}: {name}" if name else slot_key
