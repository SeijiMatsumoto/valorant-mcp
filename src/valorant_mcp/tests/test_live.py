"""Smoke tests against the real Henrik API and valorant-api.com.

Skipped by default. Set the player in .env (or the environment) and run:
    VALORANT_SMOKE_PLAYER=name#TAG
    uv run pytest -m live

Needs HENRIK_API_KEY (env or .env). Uses ~13 requests of the 30/min budget, so
wait a minute between back-to-back runs.
"""

import json
import os

import pytest
import pytest_asyncio
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from valorant_mcp import agents, callouts, server
from valorant_mcp.analysis import analyze_match, attacking_team_by_round
from valorant_mcp.cache import MatchCache
from valorant_mcp.config import Settings
from valorant_mcp.henrik import HenrikAPIError, HenrikClient, parse_username

# One event loop + client for the module so the match-list cache is shared between tests.
pytestmark = [pytest.mark.live, pytest.mark.asyncio(loop_scope="module")]



class LiveSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    valorant_smoke_player: str | None = None


# Kept out of the repo on purpose: real Riot IDs live only in your local .env.
PLAYER = os.environ.get("VALORANT_SMOKE_PLAYER") or LiveSettings().valorant_smoke_player or ""
MATCH_COUNT = 12  # > one page of 10, so paging is exercised


@pytest.fixture(scope="module")
def settings():
    if not PLAYER:
        pytest.skip("set VALORANT_SMOKE_PLAYER=name#TAG in .env to run live tests")
    try:
        return Settings()
    except ValidationError:
        pytest.skip("HENRIK_API_KEY not set")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def client(settings, tmp_path_factory):
    c = HenrikClient(settings.henrik_api_key, base_url=settings.henrik_base_url,
                     region=settings.valorant_region, platform=settings.valorant_platform,
                     cache=MatchCache(tmp_path_factory.mktemp("cache")))
    yield c
    await c.aclose()


@pytest.fixture
def real_callouts(monkeypatch, tmp_path):
    # Undo conftest's stub and force a fresh download from valorant-api.com.
    monkeypatch.setattr(callouts, "_cache", None)
    monkeypatch.setattr(callouts, "_refreshed", False)
    monkeypatch.setattr(callouts, "CACHE_FILE", tmp_path / "maps.json")
    monkeypatch.setattr(agents, "_cache", None)
    monkeypatch.setattr(agents, "_refreshed", False)
    monkeypatch.setattr(agents, "CACHE_FILE", tmp_path / "agents.json")


# --- raw endpoints ---

async def test_account_v2(client):
    account = await client.get_account(PLAYER)
    name, tag = parse_username(PLAYER)
    assert (account.name.casefold(), account.tag.casefold()) == (name.casefold(), tag.casefold())
    assert account.puuid


async def test_mmr_v3(client):
    mmr = await client.get_mmr(PLAYER)
    assert mmr.current.tier.name
    assert 0 <= mmr.current.rr <= 100 or mmr.current.tier.name.startswith("Radiant")
    assert mmr.seasonal, "expected at least one season of ranked history"


async def test_stored_mmr_history_v2(client):
    history = await client.get_mmr_history(PLAYER, 5)
    assert 0 < len(history) <= 5
    assert all(e.match_id and e.tier.name for e in history)


async def test_v4_matches_pages_and_parses(client):
    matches = await client.get_matches(PLAYER, MATCH_COUNT)
    assert len(matches) == MATCH_COUNT, "player needs at least 12 competitive matches"
    ids = [m.metadata.match_id for m in matches]
    assert len(set(ids)) == len(ids), "paging returned duplicate matches"
    starts = [m.metadata.started_at for m in matches]
    assert starts == sorted(starts, reverse=True), "expected newest first"
    for m in matches:
        assert len(m.players) == 10
        assert m.rounds and m.rounds[0].id == 0, "v4 round ids should be 0-indexed"
        assert {k.round for k in m.kills} <= {r.id for r in m.rounds}


async def test_v4_match_by_id_and_disk_cache(client):
    match_id = (await client.get_matches(PLAYER, 1))[0].metadata.match_id
    client.cache.dir.joinpath(f"{match_id}.json").unlink(missing_ok=True)
    fetched = await client.get_match(match_id)
    assert fetched.metadata.match_id == match_id
    assert client.cache.get(match_id) is not None


async def test_unknown_player_raises(client):
    with pytest.raises(HenrikAPIError, match="(?i)not found"):
        await client.get_account("zz-no-such-player-zz#0000")


async def test_valorant_api_callouts(real_callouts):
    await callouts.ensure_loaded()
    assert "ascent" in callouts._cache
    assert callouts.zone_label("Ascent", 0, 0)


# --- derived analysis vs. what the API reports ---

async def test_derived_data_is_consistent(client):
    matches = await client.get_matches(PLAYER, MATCH_COUNT)
    puuid = (await client.get_account(PLAYER)).puuid
    for m in matches:
        sides = attacking_team_by_round(m)
        assert len(sides) == len(m.rounds), f"couldn't derive sides for {m.metadata.match_id}"

        rec = analyze_match(m, puuid)
        assert rec is not None, "player missing from their own match"
        assert rec.rounds_won + rec.rounds_lost == len(m.rounds)
        assert sum(r.kills for r in rec.rounds) == rec.kills, "kill feed disagrees with scoreboard"

        # When the 4.10 fields are populated, our derivations should agree with them.
        for r in m.rounds:
            if r.winning_team_role in ("Attacker", "Defender"):
                attacker = sides[r.id]
                assert (r.winning_team == attacker) == (r.winning_team_role == "Attacker")
            if r.first_blood:
                first = min((k for k in m.kills if k.round == r.id),
                            key=lambda k: k.time_in_round_in_ms)
                assert first.killer.puuid == r.first_blood.puuid


# --- MCP tools end to end ---

async def test_all_tools(client, real_callouts, monkeypatch):
    monkeypatch.setattr(server, "henrik_client", client)

    profile = json.loads(await server.get_player_profile(PLAYER))
    assert profile["current"]["rank"]

    report = json.loads(await server.get_performance_report(PLAYER, count=MATCH_COUNT))
    assert report["sample"]["matches"] == MATCH_COUNT
    for section in ("overview", "by_side", "economy", "by_agent", "by_map",
                    "death_positions", "weapons", "by_party"):
        assert report[section], f"empty section: {section}"
    assert 0 <= report["overview"]["kast_pct"] <= 100
    zones = [z for m in report["death_positions"].values() for s in m.values()
             for z in s["top_death_zones"]]
    assert any(z != "unknown" for z in zones), "callouts never resolved"

    bench = json.loads(await server.get_benchmarks(PLAYER, count=MATCH_COUNT))
    assert bench["vs_lobby"]["acs"]["lobby"] is not None
    assert bench["vs_lobby"]["median_teammate_distance_at_death_m"]["you"] is not None
    assert "Unknown" not in report["by_role"], "agent roles from valorant-api.com didn't resolve"
    assert any(":" in k for a in bench["by_agent"].values() for k in a["utility_per_round"]), \
        "ability names from valorant-api.com didn't resolve"

    teamplay = json.loads(await server.get_teamplay_report(PLAYER, count=MATCH_COUNT))
    assert teamplay["overall"]["trade_chances"]["chances"] > 0

    sites = json.loads(await server.get_site_report(PLAYER, count=MATCH_COUNT))
    assert sites["overall"]["attack"]["by_site"], "no plants found in any attack round"

    assert "isolated death" in server.glossary()

    comparison = json.loads(await server.compare_periods(PLAYER, 5, 5))
    assert "win_pct" in comparison["metrics"]

    rr = json.loads(await server.get_rr_history(PLAYER, 10))
    assert rr["history"]

    history = json.loads(await server.get_match_history(PLAYER, 5))
    assert len(history) == 5

    match_id = history[0]["match_id"]
    details = json.loads(await server.get_match_details(match_id))
    assert len(details["rounds"]) > 0
    narrative = json.loads(await server.get_match_details(
        match_id, "narrative", focus_username=PLAYER, rounds=[1, 2]))
    assert [r["round"] for r in narrative["rounds"]] == [1, 2]
    assert "(YOU)" in json.dumps(narrative, ensure_ascii=False)
