import json

import httpx
import pytest
import respx

from valorant_mcp import server
from valorant_mcp.henrik import HenrikClient

from .conftest import make_match, make_round

LIST_URL = "https://api.henrikdev.xyz/valorant/v4/matches/na/pc/me/NA1"


def _page(season: str, n: int, start: int) -> list[dict]:
    return [make_match([make_round(0, "Red")], match_id=f"{season}-{start + i}",
                       started_at=f"2026-10-01T{20 - (start + i) // 10:02d}:{59 - (start + i) % 60:02d}:00Z",
                       season=season).model_dump() for i in range(n)]


@pytest.fixture
def client(monkeypatch):
    c = HenrikClient(api_key="k")
    monkeypatch.setattr(server, "henrik_client", c)
    return c


def _mock_pages(*pages: list[dict]):
    return respx.get(LIST_URL).mock(side_effect=[httpx.Response(200, json={"data": p}) for p in pages])


class TestSeason:
    @respx.mock
    @pytest.mark.asyncio
    async def test_current_act_stops_at_older_act(self, client):
        route = _mock_pages(_page("e11a6", 10, 0), _page("e11a6", 3, 10) + _page("e11a5", 7, 13))
        out = json.loads(await server.get_match_history("me#NA1", season="current"))
        assert out["scope"]["season"] == "e11a6"
        assert len(out["matches"]) == 13
        assert route.call_count == 2

    @respx.mock
    @pytest.mark.asyncio
    async def test_named_past_act(self, client):
        _mock_pages(_page("e11a6", 10, 0), _page("e11a5", 10, 10), _page("e11a5", 2, 20) + _page("e11a4", 8, 22))
        out = json.loads(await server.get_match_history("me#NA1", season="e11a5"))
        assert out["scope"]["season"] == "e11a5"
        assert len(out["matches"]) == 12

    @pytest.mark.asyncio
    async def test_bad_season_rejected(self, client):
        with pytest.raises(ValueError, match="act like"):
            await server.get_match_history("me#NA1", season="last month")


class TestScope:
    @respx.mock
    @pytest.mark.asyncio
    async def test_flags_more_history(self, client):
        _mock_pages(_page("e11a6", 10, 0))
        out = json.loads(await server.get_match_history("me#NA1", count=5))
        assert out["scope"]["matches_used"] == 5
        assert "more_history" in out["scope"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_hint_when_history_runs_out(self, client):
        _mock_pages(_page("e11a6", 3, 0))
        out = json.loads(await server.get_match_history("me#NA1", count=10))
        assert out["scope"]["matches_used"] == 3
        assert "more_history" not in out["scope"]
