import json

import pytest

from valorant_mcp.stats import format_match_details, format_match_narrative

from .conftest import ME, make_kill, make_match, make_round


def _match():
    rounds = [make_round(0, "Red", planter="r2"), make_round(1, "Blue")]
    kills = [make_kill(0, 1000, ME, "b1"), make_kill(0, 3000, "b2", "r2"),
             make_kill(1, 2000, "b1", ME), make_kill(1, 4000, "r3", "b1")]
    return make_match(rounds, kills)


@pytest.mark.asyncio
async def test_details_summary():
    out = json.loads(await format_match_details(_match()))
    assert out["teams"]["Red"]["started_on"] == "attack"
    me = next(p for p in out["teams"]["Red"]["players"] if p["name"] == "me#NA1")
    assert me["fk_fd"] == "1/1"
    assert me["deaths_traded_pct"] == 100.0
    assert out["rounds"][0]["round"] == 1
    assert out["rounds"][0]["first_blood"].startswith("me > b1")
    assert out["rounds"][1]["sides"] == {"Blue": "defense", "Red": "attack"}


@pytest.mark.asyncio
async def test_narrative_tags_and_focus():
    out = json.loads(await format_match_narrative(_match(), focus_puuid=ME))
    r2 = out["rounds"][1]["timeline"]
    assert r2[0]["tags"] == ["first_blood"]
    assert r2[0]["target"].endswith("(YOU)")
    assert r2[1]["tags"] == ["trade"]


@pytest.mark.asyncio
async def test_narrative_round_filter():
    out = json.loads(await format_match_narrative(_match(), only_rounds=[2]))
    assert [r["round"] for r in out["rounds"]] == [2]
