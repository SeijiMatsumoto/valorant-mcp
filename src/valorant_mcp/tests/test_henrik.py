import httpx
import pytest
import respx

from valorant_mcp import henrik
from valorant_mcp.cache import MatchCache
from valorant_mcp.henrik import HenrikAPIError, HenrikClient, parse_username

from .conftest import make_match, make_round

BASE = "https://api.henrikdev.xyz/valorant"
LIST_URL = f"{BASE}/v4/matches/na/pc/TenZ/00005"


@pytest.fixture
def client():
    return HenrikClient(api_key="test-key")


def raw_match(match_id: str) -> dict:
    return make_match([make_round(0, "Red")], match_id=match_id).model_dump()


class TestParseUsername:
    def test_splits_name_and_tag(self):
        assert parse_username("TenZ#00005") == ("TenZ", "00005")

    def test_keeps_spaces_in_name(self):
        assert parse_username("Some Name#NA1") == ("Some Name", "NA1")

    @pytest.mark.parametrize("bad", ["NoHashHere", "#tag", "name#"])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_username(bad)


class TestGetMatches:
    @respx.mock
    @pytest.mark.asyncio
    async def test_paginates_until_count(self, client):
        route = respx.get(LIST_URL).mock(side_effect=[
            httpx.Response(200, json={"data": [raw_match(f"a{i}") for i in range(10)]}),
            httpx.Response(200, json={"data": [raw_match(f"b{i}") for i in range(10)]}),
        ])
        matches = await client.get_matches("TenZ#00005", 15)
        assert len(matches) == 15
        assert [c.request.url.params["start"] for c in route.calls] == ["0", "10"]
        assert route.calls[0].request.headers["Authorization"] == "test-key"

    @respx.mock
    @pytest.mark.asyncio
    async def test_stops_on_short_page(self, client):
        route = respx.get(LIST_URL).mock(
            return_value=httpx.Response(200, json={"data": [raw_match("a"), raw_match("b")]}))
        assert len(await client.get_matches("TenZ#00005", 30)) == 2
        assert route.call_count == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_reuses_recent_list(self, client):
        route = respx.get(LIST_URL).mock(
            return_value=httpx.Response(200, json={"data": [raw_match(f"a{i}") for i in range(10)]}))
        await client.get_matches("TenZ#00005", 10)
        await client.get_matches("tenz#00005", 5)
        assert route.call_count == 1


class TestErrors:
    @respx.mock
    @pytest.mark.asyncio
    async def test_404_uses_api_message(self, client):
        respx.get(f"{BASE}/v2/account/Nobody/0000").mock(return_value=httpx.Response(
            404, json={"errors": [{"code": 22, "message": "Account not found", "status": 404}]}))
        with pytest.raises(HenrikAPIError, match="Account not found"):
            await client.get_account("Nobody#0000")

    @respx.mock
    @pytest.mark.asyncio
    async def test_retries_short_rate_limit(self, client, monkeypatch):
        sleeps = []

        async def fake_sleep(s):
            sleeps.append(s)
        monkeypatch.setattr(henrik.asyncio, "sleep", fake_sleep)
        respx.get(LIST_URL).mock(side_effect=[
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"data": [raw_match("a")]}),
        ])
        assert len(await client.get_matches("TenZ#00005", 1)) == 1
        assert sleeps == [2.0]

    @respx.mock
    @pytest.mark.asyncio
    async def test_long_rate_limit_raises(self, client):
        respx.get(LIST_URL).mock(return_value=httpx.Response(429, headers={"Retry-After": "55"}))
        with pytest.raises(HenrikAPIError, match="Rate limited"):
            await client.get_matches("TenZ#00005", 1)


class TestMatchCache:
    @respx.mock
    @pytest.mark.asyncio
    async def test_get_match_uses_disk_cache(self, tmp_path):
        client = HenrikClient(api_key="k", cache=MatchCache(tmp_path))
        route = respx.get(f"{BASE}/v4/match/na/m1").mock(
            return_value=httpx.Response(200, json={"data": raw_match("m1")}))
        first = await client.get_match("m1")
        second = await client.get_match("m1")
        assert first.metadata.match_id == second.metadata.match_id == "m1"
        assert route.call_count == 1

    def test_skips_incomplete_matches(self, tmp_path):
        cache = MatchCache(tmp_path)
        raw = raw_match("live")
        raw["metadata"]["is_completed"] = False
        cache.put(raw)
        assert cache.get("live") is None
