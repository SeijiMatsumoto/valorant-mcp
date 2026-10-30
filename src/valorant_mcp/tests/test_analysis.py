
from valorant_mcp.analysis import (
    analyze_match,
    analyze_matches,
    attacking_team_by_round,
    build_report,
    buy_type,
    compare,
    summarize_matches,
)

from .conftest import BLUE, ME, RED, make_kill, make_match, make_player, make_round


def _rounds(n, winner="Red", **kwargs):
    return [make_round(i, winner, **kwargs) for i in range(n)]


class TestSides:
    def test_plant_sets_first_half_attacker(self):
        rounds = _rounds(26)
        rounds[2] = make_round(2, "Red", planter="b1")
        attackers = attacking_team_by_round(make_match(rounds))
        assert attackers[0] == "Blue"
        assert attackers[11] == "Blue"
        assert attackers[12] == "Red"
        assert attackers[23] == "Red"

    def test_overtime_alternates(self):
        rounds = _rounds(26)
        rounds[0] = make_round(0, "Red", planter="r2")
        attackers = attacking_team_by_round(make_match(rounds))
        assert attackers[24] == "Red"
        assert attackers[25] == "Blue"

    def test_second_half_plant_is_flipped(self):
        rounds = _rounds(14)
        rounds[13] = make_round(13, "Red", planter="r2")
        assert attacking_team_by_round(make_match(rounds))[0] == "Blue"

    def test_winning_team_role_is_used(self):
        rounds = _rounds(3)
        rounds[1] = make_round(1, "Blue", role="Defender")
        assert attacking_team_by_round(make_match(rounds))[0] == "Red"

    def test_unknown_without_plants_or_roles(self):
        assert attacking_team_by_round(make_match(_rounds(5))) == {}

    def test_swiftplay_half_is_four(self):
        rounds = _rounds(6)
        rounds[0] = make_round(0, "Red", planter="r2")
        attackers = attacking_team_by_round(make_match(rounds, queue="swiftplay"))
        assert attackers[3] == "Red"
        assert attackers[4] == "Blue"


class TestBuyType:
    def test_thresholds(self):
        assert buy_type(800) == "eco"
        assert buy_type(2500) == "force"
        assert buy_type(4600) == "full"

    def test_pistol_rounds_and_matchups(self):
        rounds = [make_round(i, "Red", red_loadout=4500, blue_loadout=1000) for i in range(13)]
        rec = analyze_match(make_match(rounds), ME)
        assert rec.rounds[0].buy == "pistol"
        assert rec.rounds[12].buy == "pistol"
        assert rec.rounds[1].buy == "full"
        assert rec.rounds[1].enemy_buy == "eco"


class TestRoundEvents:
    def test_first_kill_and_first_death(self):
        kills = [make_kill(0, 1000, ME, "b1"), make_kill(1, 1000, "b1", ME)]
        rec = analyze_match(make_match(_rounds(2), kills), ME)
        assert rec.rounds[0].first_kill and not rec.rounds[0].first_death
        assert rec.rounds[1].first_death and not rec.rounds[1].first_kill

    def test_traded_death(self):
        kills = [make_kill(0, 1000, "b1", ME), make_kill(0, 4000, "r2", "b1")]
        rec = analyze_match(make_match(_rounds(1), kills), ME)
        assert rec.rounds[0].died
        assert rec.rounds[0].traded_death
        assert rec.rounds[0].kast

    def test_untraded_when_too_slow(self):
        kills = [make_kill(0, 1000, "b1", ME), make_kill(0, 9000, "r2", "b1")]
        rec = analyze_match(make_match(_rounds(1), kills), ME)
        assert not rec.rounds[0].traded_death
        assert not rec.rounds[0].kast

    def test_trade_kill(self):
        kills = [make_kill(0, 1000, "b1", "r2"), make_kill(0, 2500, ME, "b1")]
        rec = analyze_match(make_match(_rounds(1), kills), ME)
        assert rec.rounds[0].trade_kills == 1
        assert rec.rounds[0].kill_weapons == ["Vandal"]

    def test_assist_counts_for_kast(self):
        kills = [make_kill(0, 1000, "r2", "b1", assistants=(ME,)), make_kill(0, 2000, "b2", ME)]
        rec = analyze_match(make_match(_rounds(1), kills), ME)
        assert rec.rounds[0].kast

    def test_clutch_detected(self):
        # All four teammates die first, then I take out all five enemies.
        kills = [make_kill(0, 1000 * i, "b1", mate) for i, mate in enumerate(RED[1:], 1)]
        kills += [make_kill(0, 7000 + i, ME, b) for i, b in enumerate(BLUE)]
        rec = analyze_match(make_match(_rounds(1), kills), ME)
        assert rec.rounds[0].clutch_vs == 5
        assert rec.rounds[0].won

    def test_damage_from_damage_events(self):
        rec = analyze_match(make_match([make_round(0, "Red", my_damage=140)]), ME)
        assert rec.rounds[0].damage == 140

    def test_round_numbers_are_one_indexed(self):
        rec = analyze_match(make_match(_rounds(2)), ME)
        assert [r.round for r in rec.rounds] == [1, 2]


class TestMatchRecord:
    def test_missing_player_returns_none(self):
        assert analyze_match(make_match(_rounds(1)), "nobody") is None

    def test_party_and_acs_rank(self):
        players = [make_player(p, party_id="p1" if p in ("me", "r2") else None,
                               score=5000 if p == "r3" else 4000 if p == ME else 1000)
                   for p in RED + BLUE]
        rec = analyze_match(make_match(_rounds(2), players=players), ME)
        assert rec.party_size == 2
        assert rec.team_acs_rank == 2

    def test_sessions(self):
        matches = [
            make_match(_rounds(1), match_id="a", started_at="2026-10-01T20:00:00Z"),
            make_match(_rounds(1), match_id="b", started_at="2026-10-01T20:45:00Z"),
            make_match(_rounds(1), match_id="c", started_at="2026-10-02T20:00:00Z"),
        ]
        games = {r.match_id: r.session_game for r in analyze_matches(matches, ME)}
        assert games == {"a": 1, "b": 2, "c": 1}


class TestSummaries:
    def _records(self):
        m1 = make_match(_rounds(13, "Red"), [make_kill(0, 1000, ME, "b1")], match_id="w",
                        started_at="2026-10-02T20:00:00Z")
        m2 = make_match(_rounds(13, "Blue"), [make_kill(0, 1000, "b1", ME)], match_id="l",
                        started_at="2026-10-01T20:00:00Z")
        return analyze_matches([m1, m2], ME)

    def test_overview(self):
        s = summarize_matches(self._records())
        assert s["record"] == "1W-1L"
        assert s["opening_duels"]["opening_win_pct"] == 50.0
        assert s["opening_duels"]["round_win_pct_after_my_first_kill"] == 100.0
        assert s["low_sample"] is True

    def test_report_sections(self):
        report = build_report(self._records(), ["overview", "economy"])
        assert report["sample"]["matches"] == 2
        assert "economy" in report and "by_map" not in report

    def test_empty_report(self):
        assert build_report([]) == {"sample": {"matches": 0}}

    def test_compare_deltas(self):
        recs = self._records()
        out = compare(recs[:1], recs[1:], "a", "b")
        row = out["metrics"]["win_pct"]
        assert (row["a"], row["b"], row["delta"]) == (100.0, 0.0, 100.0)
        assert row["a_ci95"][1] == 100.0 and row["b_ci95"][0] == 0.0
