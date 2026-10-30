import json
from pathlib import Path

import pytest

from valorant_mcp.models import MMR, Match, MMRHistoryEntry

SAMPLE = Path(__file__).parents[3] / "sample_match_details.json"


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample payload not present")
def test_parses_real_v4_payload():
    raw = json.loads(SAMPLE.read_text())
    match = Match(**raw.get("data", raw))
    assert len(match.players) == 10
    assert match.rounds[0].id == 0
    assert all(k.round >= 0 for k in match.kills)


def test_410_fields_are_optional():
    match = Match.model_validate({
        "metadata": {"match_id": "m", "map": {"id": "x", "name": "Bind"}, "started_at": "2026-01-01T00:00:00Z"},
        "players": [], "teams": [], "kills": [],
        "rounds": [{"id": 0, "result": "Elimination", "winning_team": "Red", "stats": [],
                    "winning_team_role": None, "first_blood": None}],
    })
    assert match.rounds[0].first_blood is None
    assert match.metadata.mvp is None


def test_performance_ratings_parse():
    from valorant_mcp.models import Performance
    perf = Performance.model_validate({
        "score": 191.4,
        "breakdown": {"damage": 99.3, "defuses": None},
        "ratings": {"grade": "pass", "combat": {"damage": "down"}, "utility": None},
    })
    assert perf.ratings.grade == "pass"
    assert perf.breakdown["defuses"] is None


def test_mmr_v3():
    mmr = MMR.model_validate({
        "account": {"puuid": "p", "name": "n", "tag": "t"},
        "current": {"tier": {"id": 12, "name": "Gold 1"}, "rr": 20, "last_change": -13, "elo": 920},
        "peak": {"season": {"id": "s", "short": "e1a1"}, "tier": {"id": 18, "name": "Diamond 1"}, "rr": 0},
        "seasonal": [],
    })
    assert mmr.peak.tier.name == "Diamond 1"


def test_mmr_history_entry_nullable_bonus():
    entry = MMRHistoryEntry.model_validate({
        "match_id": "m", "date": "2026-01-01T00:00:00Z", "map": {"id": "x", "name": "Bind"},
        "season": {"id": "s", "short": "e11a5"}, "tier": {"id": 12, "name": "Gold 1"},
        "rr": 20, "last_change": -13, "elo": 920, "rr_performance_bonus": None,
    })
    assert entry.rr_performance_bonus is None
