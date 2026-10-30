from valorant_mcp.analysis import (
    analyze_all_players,
    analyze_match,
    analyze_matches,
    wilson,
)
from valorant_mcp.insights import build_benchmarks, build_sites, build_teamplay

from .conftest import BLUE, ME, RED, make_kill, make_match, make_player, make_round


def _rounds(n, winner="Red", **kwargs):
    return [make_round(i, winner, **kwargs) for i in range(n)]


class TestWilson:
    def test_small_sample_is_wide(self):
        lo, hi = wilson(7, 9)  # 78% observed
        assert lo < 50
        assert hi > 90

    def test_bounds(self):
        assert wilson(0, 10)[0] == 0.0
        assert wilson(10, 10)[1] == 100.0
        assert wilson(0, 0) is None


class TestSpacing:
    def test_nearest_teammate_and_isolation(self):
        kills = [make_kill(0, 1000, "b1", ME, at=(0, 0),
                           positions={"r2": (3000, 0), "r3": (4000, 0), "b1": (500, 0)})]
        r = analyze_match(make_match(_rounds(1), kills), ME).rounds[0]
        assert r.nearest_mate_at_death == 3000
        assert r.isolated_death
        assert r.killer_distance == 500

    def test_close_teammate_not_isolated(self):
        kills = [make_kill(0, 1000, "b1", ME, positions={"r2": (800, 0)})]
        r = analyze_match(make_match(_rounds(1), kills), ME).rounds[0]
        assert not r.isolated_death

    def test_trade_chance_taken(self):
        kills = [make_kill(0, 1000, "b1", "r2", at=(0, 0), positions={ME: (1000, 0), "b1": (2000, 0)}),
                 make_kill(0, 3000, ME, "b1", positions={ME: (1000, 0)})]
        r = analyze_match(make_match(_rounds(1), kills), ME).rounds[0]
        assert (r.trade_chances, r.trade_chances_taken) == (1, 1)

    def test_far_teammate_death_is_not_a_chance(self):
        kills = [make_kill(0, 1000, "b1", "r2", at=(0, 0), positions={ME: (5000, 0)})]
        r = analyze_match(make_match(_rounds(1), kills), ME).rounds[0]
        assert r.trade_chances == 0

    def test_kill_distance(self):
        kills = [make_kill(0, 1000, ME, "b1", weapon="Operator", at=(3000, 0), positions={ME: (0, 0)})]
        r = analyze_match(make_match(_rounds(1), kills), ME).rounds[0]
        assert r.kill_distances == [("Operator", 3000.0)]


class TestRoundContext:
    def test_plant_fields(self):
        rounds = [make_round(0, "Red", planter=ME, site="B"), make_round(1, "Red", planter="b1")]
        rec = analyze_match(make_match(rounds), ME)
        assert rec.rounds[0].planted_by_us and rec.rounds[0].i_planted and rec.rounds[0].plant_site == "B"
        assert rec.rounds[1].enemy_planted

    def test_my_buy_vs_team(self):
        rounds = [make_round(0, "Red"), make_round(1, "Red", red_loadout=5000, my_loadout=800)]
        r = analyze_match(make_match(rounds), ME).rounds[1]
        assert (r.buy, r.my_buy) == ("full", "eco")

    def test_role_party_and_lobby(self):
        players = [make_player(p, agent="Sova" if p == ME else "Jett", tier=13 if p in RED else 15,
                               party_id="p" if p in (ME, "r2") else None) for p in RED + BLUE]
        rec = analyze_match(make_match(_rounds(1), players=players), ME)
        assert rec.role == "Initiator"
        assert rec.party_mates == ["r2#NA1"]
        assert rec.enemy_avg_tier == 15


class TestReports:
    def _matches(self):
        out = []
        for i, winner in enumerate(["Red", "Blue", "Red"]):
            kills = [make_kill(12, 1000, "b1", ME, positions={"r2": (500, 0)}),
                     make_kill(12, 2000, "r2", "b1")]
            # Red attacks the first half and plants A; Blue attacks after the swap and plants B.
            rounds = [make_round(0, winner, planter="r2"), make_round(12, winner, planter="b1", site="B")]
            out.append(make_match(rounds, kills, match_id=f"m{i}",
                                  started_at=f"2026-10-0{i + 1}T20:00:00Z"))
        return out

    def test_benchmarks(self):
        matches = self._matches()
        me = analyze_matches(matches, ME)
        everyone = {m.metadata.match_id: analyze_all_players(m) for m in matches}
        out = build_benchmarks(me, everyone)
        assert out["vs_lobby"]["kast_pct"]["you"] is not None
        assert "you_minus_same_role" in out["vs_lobby"]["acs"]
        assert out["avg_place_in_lobby_of_10"]["acs"] is not None
        jett = out["by_agent"]["Jett"]
        assert "Q: Updraft" in jett["utility_per_round"]
        assert jett["other_player_games"] > 0

    def test_teamplay(self):
        out = build_teamplay(analyze_matches(self._matches(), ME))
        assert out["overall"]["deaths_traded_pct"] == 100.0
        assert out["overall"]["by_spacing"]["close (teammate within 15m)"]["deaths"] == 3

    def test_sites(self):
        out = build_sites(analyze_matches(self._matches(), ME))
        attack = out["overall"]["attack"]
        defense = out["overall"]["defense"]
        assert attack["rounds"] == 3 and attack["plant_rate_pct"] == 100.0
        assert defense["by_site"]["B"]["plants"] == 3

    def test_empty(self):
        assert build_teamplay([]) == {"sample": {"matches": 0}}
        assert build_sites([]) == {"sample": {"matches": 0}}
        assert build_benchmarks([], {}) == {"sample": {"matches": 0}}
