"""Reports that put a player's numbers in context: lobby benchmarks, teamplay, sites."""

from collections import Counter, defaultdict

from . import agents
from .analysis import (
    ISOLATED_RANGE,
    TRADE_RANGE,
    MatchRecord,
    RoundRecord,
    avg,
    group_by,
    median_m,
    party_label,
    pct,
    sample_info,
    summarize_matches,
    wilson,
)

# --- benchmarks ---

def metric_block(records: list[MatchRecord]) -> dict:
    """Pooled per-round metrics for a set of player-games."""
    rounds = [r for m in records for r in m.rounds]
    rp = sum(m.rounds_played for m in records)
    died = [r for r in rounds if r.died]
    fk = sum(r.first_kill for r in rounds)
    fd = sum(r.first_death for r in rounds)
    chances = sum(r.trade_chances for r in rounds)
    shots = sum(m.headshots + m.bodyshots + m.legshots for m in records)
    with_casts = [m for m in records if m.ability_casts]
    return {
        "player_games": len(records),
        "acs": avg(sum(m.score for m in records), rp, 0),
        "adr": avg(sum(m.damage for m in records), rp, 1),
        "kills_per_round": avg(sum(m.kills for m in records), rp),
        "deaths_per_round": avg(sum(m.deaths for m in records), rp),
        "assists_per_round": avg(sum(m.assists for m in records), rp),
        "kast_pct": pct(sum(r.kast for r in rounds), len(rounds)),
        "hs_pct": pct(sum(m.headshots for m in records), shots),
        "first_kill_rate_pct": pct(fk, len(rounds)),
        "first_death_rate_pct": pct(fd, len(rounds)),
        "opening_win_pct": pct(fk, fk + fd),
        "deaths_traded_pct": pct(sum(r.traded_death for r in died), len(died)),
        "trade_kills_per_round": avg(sum(r.trade_kills for r in rounds), len(rounds)),
        "trade_chance_conversion_pct": pct(sum(r.trade_chances_taken for r in rounds), chances),
        "isolated_death_pct": pct(sum(r.isolated_death for r in died), len(died)),
        "median_teammate_distance_at_death_m": median_m(
            [r.nearest_mate_at_death for r in died if r.nearest_mate_at_death is not None]),
        "survival_pct": pct(len(rounds) - len(died), len(rounds)),
        "utility_casts_per_round": avg(sum(sum(m.ability_casts.values()) for m in with_casts),
                                       sum(m.rounds_played for m in with_casts)),
    }


def _table(columns: dict[str, dict], delta: tuple[str, str]) -> dict:
    """Turn {column: metric_block} into {metric: {column: value, ..., delta}}."""
    keys = [k for k in next(iter(columns.values())) if k != "player_games"]
    table = {}
    for key in keys:
        row = {col: block.get(key) for col, block in columns.items()}
        a, b = row.get(delta[0]), row.get(delta[1])
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            row[f"{delta[0]}_minus_{delta[1]}"] = round(a - b, 2)
        table[key] = row
    return table


def _lobby_ranks(me: list[MatchRecord], everyone: dict[str, list[MatchRecord]]) -> dict:
    """Average place among all 10 players in the match (1 = best)."""
    metrics = {
        "acs": lambda m: m.acs,
        "adr": lambda m: m.damage / m.rounds_played,
        "kast": lambda m: sum(r.kast for r in m.rounds) / max(1, len(m.rounds)),
        "opening_duel_net": lambda m: sum(r.first_kill for r in m.rounds) - sum(r.first_death for r in m.rounds),
    }
    out = {}
    for name, fn in metrics.items():
        places = []
        for rec in me:
            lobby = everyone.get(rec.match_id, [])
            if lobby:
                places.append(1 + sum(fn(o) > fn(rec) for o in lobby if o.puuid != rec.puuid))
        out[name] = avg(sum(places), len(places), 1)
    return out


def _utility(agent: str, mine: list[MatchRecord], others: list[MatchRecord]) -> dict:
    def per_round(records: list[MatchRecord], key: str) -> float | None:
        rs = [m for m in records if key in m.ability_casts]
        return avg(sum(m.ability_casts[key] for m in rs), sum(m.rounds_played for m in rs))

    return {
        agents.ability_label(agent, key): {"you": per_round(mine, key), "others": per_round(others, key)}
        for key in agents.SLOTS
    }


def _henrik(mine: list[MatchRecord], others: list[MatchRecord]) -> dict | None:
    def breakdown(records: list[MatchRecord]) -> dict[str, float]:
        sums: dict[str, list[float]] = defaultdict(list)
        for m in records:
            for k, v in m.perf_breakdown.items():
                sums[k].append(v)
        return {k: round(sum(v) / len(v), 2) for k, v in sums.items()}

    mine_b = breakdown(mine)
    if not mine_b:
        return None
    others_b = breakdown(others)
    ratings: dict[str, Counter] = defaultdict(Counter)
    for m in mine:
        for k, v in m.perf_ratings.items():
            ratings[k][v] += 1
    return {
        "breakdown_avg": {k: {"you": v, "others": others_b.get(k)} for k, v in mine_b.items()},
        "your_ratings": {k: dict(c) for k, c in sorted(ratings.items())},
        "games_with_data": sum(1 for m in mine if m.perf_breakdown),
    }


def build_benchmarks(me: list[MatchRecord], everyone: dict[str, list[MatchRecord]],
                     min_agent_games: int = 2) -> dict:
    """Compare a player with everyone else in their own lobbies.

    `everyone` maps match_id -> records for all players in that match.
    """
    if not me:
        return {"sample": {"matches": 0}}
    my_puuid = me[0].puuid
    others = [o for recs in everyone.values() for o in recs if o.puuid != my_puuid]
    my_roles = {m.match_id: m.role for m in me}
    same_role = [o for o in others if o.role == my_roles.get(o.match_id)]

    by_agent = {}
    for agent, mine in group_by(me, lambda m: m.agent).items():
        if len(mine) < min_agent_games:
            continue
        theirs = [o for o in others if o.agent == agent]
        entry = {
            "your_games": len(mine),
            "other_player_games": len(theirs),
            "metrics": _table({"you": metric_block(mine), "others_on_agent": metric_block(theirs)},
                              ("you", "others_on_agent")),
            "utility_per_round": _utility(agent, mine, theirs),
        }
        if (henrik := _henrik(mine, theirs)):
            entry["henrik_performance"] = henrik
        if len(theirs) < 5:
            entry["low_sample"] = True
        by_agent[agent] = entry

    return {
        "sample": sample_info(me),
        "comparison_groups": {
            "lobby": f"{len(others)} other player-games in your matches (both teams)",
            "same_role": f"{len(same_role)} player-games in the same role as you that match",
        },
        "vs_lobby": _table({"you": metric_block(me), "same_role": metric_block(same_role),
                            "lobby": metric_block(others)}, ("you", "same_role")),
        "avg_place_in_lobby_of_10": _lobby_ranks(me, everyone),
        "by_agent": by_agent,
    }


# --- teamplay ---

def _spacing(rounds: list[RoundRecord]) -> dict:
    died = [r for r in rounds if r.died]

    def bucket(r: RoundRecord) -> str:
        d = r.nearest_mate_at_death
        if d is None or d > ISOLATED_RANGE:
            return "isolated (no teammate within 25m)"
        if d > TRADE_RANGE:
            return "loose (15-25m)"
        return "close (teammate within 15m)"

    groups: dict[str, list[RoundRecord]] = defaultdict(list)
    for r in died:
        groups[bucket(r)].append(r)
    chances = sum(r.trade_chances for r in rounds)
    taken = sum(r.trade_chances_taken for r in rounds)
    traded = sum(r.traded_death for r in died)
    return {
        "deaths": len(died),
        "median_teammate_distance_at_death_m": median_m(
            [r.nearest_mate_at_death for r in died if r.nearest_mate_at_death is not None]),
        "deaths_traded_pct": pct(traded, len(died)),
        "deaths_traded_ci95": wilson(traded, len(died)),
        "by_spacing": {
            k: {"deaths": len(v), "share_pct": pct(len(v), len(died)),
                "traded_pct": pct(sum(r.traded_death for r in v), len(v))}
            for k, v in sorted(groups.items())
        },
        "trade_chances": {
            "definition": "a teammate died within 15m of you while you were alive",
            "chances": chances,
            "converted": taken,
            "conversion_pct": pct(taken, chances),
            "conversion_ci95": wilson(taken, chances),
        },
        "trade_kills_per_round": avg(sum(r.trade_kills for r in rounds), len(rounds)),
    }


def build_teamplay(records: list[MatchRecord], top_zones: int = 6) -> dict:
    if not records:
        return {"sample": {"matches": 0}}
    rounds = [r for m in records for r in m.rounds]
    isolated_zones = Counter(
        f"{r.map} {r.side or '?'}: {r.death_zone or 'unknown'}"
        for r in rounds if r.isolated_death and not r.traded_death
    )
    partners: dict[str, list[MatchRecord]] = defaultdict(list)
    for m in records:
        for mate in m.party_mates:
            partners[mate].append(m)

    return {
        "sample": sample_info(records),
        "overall": _spacing(rounds),
        "by_side": {s: _spacing([r for r in rounds if r.side == s]) for s in ("attack", "defense")},
        "isolated_untraded_death_spots": dict(isolated_zones.most_common(top_zones)),
        "party": {
            "by_size": {p: summarize_matches(g, compact=True)
                        for p, g in group_by(records, lambda m: party_label(m.party_size)).items()},
            "partners": {
                name: {"games": len(g), "record": f"{sum(m.won for m in g)}W-{sum(not m.won for m in g)}L",
                       "win_pct": pct(sum(m.won for m in g), len(g)),
                       "win_ci95": wilson(sum(m.won for m in g), len(g))}
                for name, g in sorted(partners.items(), key=lambda kv: -len(kv[1]))
            },
        },
    }


# --- sites ---

def _site_block(rounds: list[RoundRecord], side: str) -> dict:
    side_rounds = [r for r in rounds if r.side == side]
    planted = [r for r in side_rounds if (r.planted_by_us if side == "attack" else r.enemy_planted)]
    no_plant = [r for r in side_rounds if not r.planted_by_us and not r.enemy_planted]
    by_site: dict[str, list[RoundRecord]] = defaultdict(list)
    for r in planted:
        by_site[r.plant_site or "?"].append(r)
    label = "post_plant_win_pct" if side == "attack" else "retake_or_hold_win_pct"
    out = {
        "rounds": len(side_rounds),
        ("plant_rate_pct" if side == "attack" else "enemy_plant_rate_pct"): pct(len(planted), len(side_rounds)),
        "by_site": {
            site: {"plants": len(v), "share_pct": pct(len(v), len(planted)),
                   label: pct(sum(r.won for r in v), len(v)),
                   f"{label.removesuffix('_pct')}_ci95": wilson(sum(r.won for r in v), len(v))}
            for site, v in sorted(by_site.items())
        },
        "no_plant_rounds": {"rounds": len(no_plant), "round_win_pct": pct(sum(r.won for r in no_plant),
                                                                          len(no_plant))},
    }
    if side == "attack":
        out["you_planted"] = sum(r.i_planted for r in side_rounds)
    return out


def build_sites(records: list[MatchRecord]) -> dict:
    if not records:
        return {"sample": {"matches": 0}}
    rounds = [r for m in records for r in m.rounds]
    by_map: dict[str, list[RoundRecord]] = defaultdict(list)
    for r in rounds:
        by_map[r.map].append(r)
    return {
        "sample": sample_info(records),
        "note": "Team-level: site choice and post-plant/retake results for your team.",
        "overall": {s: _site_block(rounds, s) for s in ("attack", "defense")},
        "by_map": {
            name: {"matches": len({r.match_id for r in rs}),
                   **{s: _site_block(rs, s) for s in ("attack", "defense")}}
            for name, rs in sorted(by_map.items(), key=lambda kv: -len(kv[1]))
        },
    }
