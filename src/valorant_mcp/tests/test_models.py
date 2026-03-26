import json
import pytest
from valorant_mcp.models import (
    PlayerInfo, MatchData, V4MatchData, MMRData,
)


class TestPlayerInfo:
    def test_parses_valid_data(self):
        data = {
            "puuid": "abc-123",
            "region": "na",
            "account_level": 100,
            "name": "SayGG",
            "tag": "11111",
        }
        player = PlayerInfo(**data)
        assert player.name == "SayGG"
        assert player.puuid == "abc-123"
        assert player.account_level == 100

    def test_rejects_missing_fields(self):
        with pytest.raises(Exception):
            PlayerInfo(puuid="abc", region="na")


class TestMatchData:
    @pytest.fixture
    def sample_match(self):
        with open("sample_matches.json") as f:
            data = json.load(f)
        return data["data"][0]

    def test_parses_sample_match(self, sample_match):
        match = MatchData(**sample_match)
        assert match.metadata.map == "Bind"
        assert match.metadata.matchid is not None
        assert "all_players" in match.players
        assert len(match.players["all_players"]) > 0

    def test_player_has_stats(self, sample_match):
        match = MatchData(**sample_match)
        player = match.players["all_players"][0]
        assert player.stats.kills >= 0
        assert player.stats.headshots >= 0
        assert player.stats.bodyshots >= 0

    def test_player_has_economy(self, sample_match):
        match = MatchData(**sample_match)
        player = match.players["all_players"][0]
        assert player.economy.spent.overall > 0
        assert player.economy.loadout_value.overall > 0

    def test_player_has_damage(self, sample_match):
        match = MatchData(**sample_match)
        player = match.players["all_players"][0]
        assert player.damage_made >= 0
        assert player.damage_received >= 0

    def test_teams_parsed(self, sample_match):
        match = MatchData(**sample_match)
        assert "red" in match.teams
        assert "blue" in match.teams
        assert isinstance(match.teams["red"].has_won, bool)


class TestV4MatchData:
    @pytest.fixture
    def sample_v4_match(self):
        with open("sample_match_details.json") as f:
            data = json.load(f)
        return data["data"]

    def test_parses_sample_v4_match(self, sample_v4_match):
        match = V4MatchData(**sample_v4_match)
        assert match.metadata.map.name is not None
        assert len(match.players) > 0
        assert len(match.teams) == 2

    def test_v4_player_has_damage(self, sample_v4_match):
        match = V4MatchData(**sample_v4_match)
        player = match.players[0]
        assert player.stats.damage.dealt > 0
        assert player.stats.damage.received > 0

    def test_v4_player_has_economy(self, sample_v4_match):
        match = V4MatchData(**sample_v4_match)
        player = match.players[0]
        assert player.economy.spent.overall > 0

    def test_v4_player_has_headshots(self, sample_v4_match):
        match = V4MatchData(**sample_v4_match)
        player = match.players[0]
        assert player.stats.headshots >= 0
        assert player.stats.bodyshots >= 0
        assert player.stats.legshots >= 0


class TestMMRData:
    def test_parses_valid_data(self):
        data = {
            "name": "SayGG",
            "tag": "11111",
            "current_data": {
                "currenttierpatched": "Gold 2",
                "ranking_in_tier": 45,
                "mmr_change_to_last_game": 18,
                "elo": 945,
            },
            "highest_rank": {
                "patched_tier": "Platinum 1",
                "season": "e5a3",
            },
            "by_season": {
                "e9a1": {
                    "wins": 30,
                    "number_of_games": 50,
                    "final_rank_patched": "Gold 2",
                },
            },
        }
        mmr = MMRData(**data)
        assert mmr.current_data.currenttierpatched == "Gold 2"
        assert mmr.current_data.elo == 945
        assert mmr.by_season["e9a1"].wins == 30
