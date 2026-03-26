import json
from valorant_mcp.stats import (
    _find_player, format_match_history, format_match_details,
    compute_agent_stats, compute_map_stats,
)
from .conftest import make_player, make_match, make_v4_player, make_v4_match


# --- _find_player ---

class TestFindPlayer:
    def test_finds_exact_match(self):
        player = make_player(name="SayGG", tag="11111")
        match = make_match([player])
        assert _find_player(match, "SayGG", "11111") == player

    def test_case_insensitive(self):
        player = make_player(name="SayGG", tag="11111")
        match = make_match([player])
        assert _find_player(match, "saygg", "11111") == player

    def test_returns_none_when_not_found(self):
        player = make_player(name="SayGG", tag="11111")
        match = make_match([player])
        assert _find_player(match, "Other", "99999") is None

    def test_empty_match(self):
        match = make_match([])
        assert _find_player(match, "SayGG", "11111") is None


# --- format_match_history ---

class TestFormatMatchHistory:
    def _make_full_match(self):
        me = make_player(name="SayGG", tag="11111", team="Red", character="Jett",
                         kills=20, deaths=10, assists=5, headshots=10, bodyshots=20, legshots=0,
                         damage_made=4000, damage_received=2000)
        teammate = make_player(name="Ally", tag="0001", team="Red", character="Sage",
                               kills=15, deaths=12, assists=8, headshots=5, bodyshots=25, legshots=5,
                               damage_made=3000, damage_received=2500)
        opponent = make_player(name="Enemy", tag="9999", team="Blue", character="Phoenix",
                               kills=18, deaths=14, assists=3)
        return make_match([me, teammate, opponent], red_won=True)

    def test_returns_valid_json(self):
        match = self._make_full_match()
        result = format_match_history([match], "SayGG", "11111")
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1

    def test_player_stats_included(self):
        match = self._make_full_match()
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        player = result[0]["player"]
        assert player["kda"] == "20/10/5"
        assert player["agent"] == "Jett"
        assert player["headshot_pct"] == "33%"
        assert player["damage_made"] == 4000
        assert player["damage_received"] == 2000
        assert "economy" in player

    def test_teammate_stats_included(self):
        match = self._make_full_match()
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        teammates = result[0]["teammates"]
        assert len(teammates) == 1
        tm = teammates[0]
        assert tm["agent"] == "Sage"
        assert tm["headshot_pct"] == "14%"
        assert tm["damage_made"] == 3000
        assert "economy" in tm

    def test_player_not_in_teammates(self):
        match = self._make_full_match()
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        teammate_names = [t["name"] for t in result[0]["teammates"]]
        assert "SayGG#11111" not in teammate_names

    def test_opponents_are_simple_strings(self):
        match = self._make_full_match()
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        opponents = result[0]["opponents"]
        assert len(opponents) == 1
        assert isinstance(opponents[0], str)
        assert "Phoenix" in opponents[0]

    def test_win_loss_result(self):
        match = self._make_full_match()
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        assert result[0]["result"] == "Win"

    def test_loss_result(self):
        me = make_player(name="SayGG", tag="11111", team="Blue")
        match = make_match([me], red_won=True)
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        assert result[0]["result"] == "Loss"

    def test_skips_match_without_player(self):
        other = make_player(name="Other", tag="0000", team="Red")
        match = make_match([other])
        result = json.loads(format_match_history([match], "SayGG", "11111"))
        assert len(result) == 0

    def test_multiple_matches(self):
        me1 = make_player(name="SayGG", tag="11111", team="Red")
        me2 = make_player(name="SayGG", tag="11111", team="Blue")
        match1 = make_match([me1], matchid="m1", map_name="Bind")
        match2 = make_match([me2], matchid="m2", map_name="Haven", red_won=False)
        result = json.loads(format_match_history([match1, match2], "SayGG", "11111"))
        assert len(result) == 2
        assert result[0]["map"] == "Bind"
        assert result[1]["map"] == "Haven"


# --- format_match_details ---

class TestFormatMatchDetails:
    def _make_v4_match(self):
        red1 = make_v4_player(name="SayGG", tag="11111", team_id="Red", agent_name="Jett",
                              kills=20, deaths=10, assists=5, headshots=10, bodyshots=20, legshots=0,
                              damage_dealt=4000, damage_received=2000)
        red2 = make_v4_player(name="Ally", tag="0001", team_id="Red", agent_name="Sage",
                              kills=15, deaths=12, assists=8)
        blue1 = make_v4_player(name="Enemy", tag="9999", team_id="Blue", agent_name="Phoenix",
                               kills=18, deaths=14, assists=3)
        return make_v4_match([red1, red2, blue1])

    def test_returns_valid_json(self):
        match = self._make_v4_match()
        result = format_match_details(match)
        parsed = json.loads(result)
        assert "red_team" in parsed
        assert "blue_team" in parsed

    def test_player_details(self):
        match = self._make_v4_match()
        result = json.loads(format_match_details(match))
        red_players = result["red_team"]["players"]
        assert len(red_players) == 2
        jett = red_players[0]
        assert jett["agent"] == "Jett"
        assert jett["headshot_pct"] == "33%"
        assert jett["damage_dealt"] == 4000
        assert jett["damage_received"] == 2000
        assert "economy" in jett

    def test_team_results(self):
        match = self._make_v4_match()
        result = json.loads(format_match_details(match))
        assert result["red_team"]["result"] == "Win"
        assert result["blue_team"]["result"] == "Loss"
        assert result["red_team"]["rounds"] == "13-9"

    def test_metadata(self):
        match = self._make_v4_match()
        result = json.loads(format_match_details(match))
        assert result["map"] == "Bind"
        assert result["region"] == "na"
        assert result["match_id"] == "match-v4-001"


# --- compute_agent_stats ---

class TestComputeAgentStats:
    def test_single_agent(self):
        me = make_player(name="SayGG", tag="11111", character="Jett",
                         kills=20, deaths=10, assists=5)
        match = make_match([me], red_won=True)
        result = json.loads(compute_agent_stats([match], "SayGG", "11111"))
        assert "Jett" in result
        assert result["Jett"]["games"] == 1
        assert result["Jett"]["wins"] == 1
        assert result["Jett"]["losses"] == 0
        assert result["Jett"]["win_rate"] == "100%"

    def test_multiple_games_same_agent(self):
        me1 = make_player(name="SayGG", tag="11111", character="Jett", kills=20, deaths=10, assists=5)
        me2 = make_player(name="SayGG", tag="11111", character="Jett", kills=10, deaths=15, assists=3)
        match1 = make_match([me1], red_won=True, matchid="m1")
        match2 = make_match([me2], red_won=False, matchid="m2")
        result = json.loads(compute_agent_stats([match1, match2], "SayGG", "11111"))
        assert result["Jett"]["games"] == 2
        assert result["Jett"]["wins"] == 1
        assert result["Jett"]["losses"] == 1
        assert result["Jett"]["win_rate"] == "50%"
        assert result["Jett"]["avg_kills"] == 15.0

    def test_multiple_agents(self):
        me1 = make_player(name="SayGG", tag="11111", character="Jett", kills=20, deaths=10, assists=5)
        me2 = make_player(name="SayGG", tag="11111", character="Sage", kills=10, deaths=8, assists=15)
        match1 = make_match([me1], matchid="m1")
        match2 = make_match([me2], matchid="m2")
        result = json.loads(compute_agent_stats([match1, match2], "SayGG", "11111"))
        assert "Jett" in result
        assert "Sage" in result
        assert result["Jett"]["games"] == 1
        assert result["Sage"]["games"] == 1

    def test_skips_matches_without_player(self):
        other = make_player(name="Other", tag="0000", character="Jett")
        match = make_match([other])
        result = json.loads(compute_agent_stats([match], "SayGG", "11111"))
        assert result == {}


# --- compute_map_stats ---

class TestComputeMapStats:
    def test_single_map(self):
        me = make_player(name="SayGG", tag="11111")
        match = make_match([me], map_name="Bind", red_won=True)
        result = json.loads(compute_map_stats([match], "SayGG", "11111"))
        assert "Bind" in result
        assert result["Bind"]["games"] == 1
        assert result["Bind"]["wins"] == 1
        assert result["Bind"]["win_rate"] == "100%"

    def test_multiple_maps(self):
        me1 = make_player(name="SayGG", tag="11111")
        me2 = make_player(name="SayGG", tag="11111")
        match1 = make_match([me1], map_name="Bind", matchid="m1", red_won=True)
        match2 = make_match([me2], map_name="Haven", matchid="m2", red_won=False)
        result = json.loads(compute_map_stats([match1, match2], "SayGG", "11111"))
        assert result["Bind"]["wins"] == 1
        assert result["Haven"]["wins"] == 0
        assert result["Haven"]["losses"] == 1

    def test_same_map_multiple_games(self):
        me1 = make_player(name="SayGG", tag="11111", kills=20, deaths=10, assists=5)
        me2 = make_player(name="SayGG", tag="11111", kills=10, deaths=15, assists=3)
        match1 = make_match([me1], map_name="Bind", matchid="m1", red_won=True)
        match2 = make_match([me2], map_name="Bind", matchid="m2", red_won=False)
        result = json.loads(compute_map_stats([match1, match2], "SayGG", "11111"))
        assert result["Bind"]["games"] == 2
        assert result["Bind"]["wins"] == 1
        assert result["Bind"]["win_rate"] == "50%"

    def test_empty_when_player_not_found(self):
        other = make_player(name="Other", tag="0000")
        match = make_match([other], map_name="Bind")
        result = json.loads(compute_map_stats([match], "SayGG", "11111"))
        assert result == {}
