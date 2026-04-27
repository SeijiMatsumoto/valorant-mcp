import pytest
import respx
import httpx
from valorant_mcp.henrik import HenrikClient
from valorant_mcp.models import PlayerInfo


@pytest.fixture
def client():
    return HenrikClient(api_key="test-key")


class TestParseUsername:
    def test_splits_name_and_tag(self, client):
        name, tag = client._parse_username("TenZ#00005")
        assert name == "TenZ"
        assert tag == "00005"

    def test_raises_on_invalid_format(self, client):
        with pytest.raises(ValueError):
            client._parse_username("NoHashHere")


class TestGetPlayerInfo:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_player_info(self, client):
        respx.get("https://api.henrikdev.xyz/valorant/v1/account/TenZ/00005").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "puuid": "abc-123",
                    "region": "na",
                    "account_level": 100,
                    "name": "TenZ",
                    "tag": "00005",
                }
            })
        )
        result = await client.get_player_info("TenZ#00005")
        assert isinstance(result, PlayerInfo)
        assert result.name == "TenZ"
        assert result.account_level == 100

    @respx.mock
    @pytest.mark.asyncio
    async def test_sends_auth_header(self, client):
        route = respx.get("https://api.henrikdev.xyz/valorant/v1/account/TenZ/00005").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "puuid": "abc-123",
                    "region": "na",
                    "account_level": 100,
                    "name": "TenZ",
                    "tag": "00005",
                }
            })
        )
        await client.get_player_info("TenZ#00005")
        assert route.calls[0].request.headers["Authorization"] == "test-key"


class TestGetMatchHistory:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_match_list(self, client):
        respx.get(
            "https://api.henrikdev.xyz/valorant/v3/matches/na/TenZ/00005",
            params={"mode": "competitive", "size": "5"},
        ).mock(
            return_value=httpx.Response(200, json={
                "data": [
                    {
                        "metadata": {
                            "map": "Bind",
                            "game_start_patched": "Wednesday, March 25, 2026",
                            "matchid": "match-001",
                        },
                        "players": {
                            "all_players": [
                                {
                                    "name": "TenZ",
                                    "tag": "00005",
                                    "character": "Jett",
                                    "team": "Red",
                                    "currenttier_patched": "Gold 2",
                                    "stats": {
                                        "score": 5000,
                                        "kills": 20,
                                        "deaths": 15,
                                        "assists": 5,
                                        "headshots": 10,
                                        "bodyshots": 30,
                                        "legshots": 2,
                                    },
                                    "economy": {
                                        "spent": {"overall": 50000, "average": 2500.0},
                                        "loadout_value": {"overall": 70000, "average": 3500.0},
                                    },
                                    "damage_made": 3000,
                                    "damage_received": 2500,
                                }
                            ],
                            "red": [],
                            "blue": [],
                        },
                        "teams": {
                            "red": {"has_won": True, "rounds_won": 13, "rounds_lost": 9},
                            "blue": {"has_won": False, "rounds_won": 9, "rounds_lost": 13},
                        },
                    }
                ]
            })
        )
        result = await client.get_match_history("TenZ#00005", "na", 5)
        assert len(result) == 1
        assert result[0].metadata.map == "Bind"


class TestGetMMR:
    @respx.mock
    @pytest.mark.asyncio
    async def test_returns_mmr_data(self, client):
        respx.get("https://api.henrikdev.xyz/valorant/v2/mmr/na/TenZ/00005").mock(
            return_value=httpx.Response(200, json={
                "data": {
                    "name": "TenZ",
                    "tag": "00005",
                    "current_data": {
                        "currenttierpatched": "Gold 2",
                        "ranking_in_tier": 45,
                        "mmr_change_to_last_game": 18,
                        "elo": 945,
                    },
                    "highest_rank": {"patched_tier": "Platinum 1", "season": "e5a3"},
                    "by_season": {},
                }
            })
        )
        result = await client.get_mmr("TenZ#00005", "na")
        assert result.current_data.currenttierpatched == "Gold 2"
        assert result.current_data.elo == 945
