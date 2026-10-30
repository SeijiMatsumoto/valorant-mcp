"""Single-match views for get_match_details."""

import json

from valorant_mcp.analysis import (
    TRADE_WINDOW_MS,
    analyze_match,
    attacking_team_by_round,
    buy_type,
    half_length,
    side_for,
    summarize_matches,
    team_loadout,
)
from valorant_mcp.callouts import ensure_loaded, resolve
from valorant_mcp.models import Match


def _ms_to_clock(ms: int) -> str:
    total_s = ms // 1000
    return f"{total_s // 60}:{total_s % 60:02d}"


def _team_ids(match: Match) -> list[str]:
    return sorted({p.team_id for p in match.players})


def _round_buys(match: Match, rnd) -> dict[str, str]:
    if rnd.id in (0, half_length(match)):
        return {t: "pistol" for t in _team_ids(match)}
    buys = {}
    for t in _team_ids(match):
        value = team_loadout(rnd, t)
        buys[t] = buy_type(value) if value is not None else "unknown"
    return buys


def _sides(match: Match, round_id: int, attackers: dict[int, str]) -> dict[str, str | None]:
    return {t: side_for(t, round_id, attackers) for t in _team_ids(match)}


async def format_match_details(match: Match) -> str:
    await ensure_loaded()
    attackers = attacking_team_by_round(match)
    teams_out = {}
    for team in match.teams:
        players = []
        for p in sorted((p for p in match.players if p.team_id == team.team_id),
                        key=lambda p: p.stats.score, reverse=True):
            rec = analyze_match(match, p.puuid)
            summary = summarize_matches([rec]) if rec else {}
            s = p.stats
            shots = s.headshots + s.bodyshots + s.legshots
            row = {
                "name": f"{p.name}#{p.tag}",
                "agent": p.agent.name,
                "rank": p.tier.name,
                "kda": f"{s.kills}/{s.deaths}/{s.assists}",
                "acs": round(rec.acs) if rec else None,
                "adr": round(s.damage.dealt / rec.rounds_played) if rec else None,
                "hs_pct": round(100 * s.headshots / shots) if shots else 0,
                "kast_pct": summary.get("kast_pct"),
                "fk_fd": f"{summary.get('first_kills')}/{summary.get('first_deaths')}",
                "deaths_traded_pct": summary.get("trading", {}).get("my_deaths_traded_pct"),
                "multikills": summary.get("multikills"),
                "clutches": summary.get("clutches"),
                "avg_loadout": round(p.economy.loadout_value.average),
                "party": p.party_id[:8] if p.party_id else None,
            }
            if p.performance and p.performance.ratings and p.performance.ratings.grade:
                row["henrik_grade"] = p.performance.ratings.grade
            players.append(row)
        teams_out[team.team_id] = {
            "result": "Win" if team.won else "Loss",
            "rounds": f"{team.rounds.won}-{team.rounds.lost}",
            "started_on": side_for(team.team_id, 0, attackers),
            "players": players,
        }

    rounds = []
    first_bloods: dict[str, int] = {}
    for rnd in sorted(match.rounds, key=lambda r: r.id):
        kills = sorted((k for k in match.kills if k.round == rnd.id), key=lambda k: k.time_in_round_in_ms)
        row = {
            "round": rnd.id + 1,
            "winner": rnd.winning_team,
            "how": rnd.result,
            "sides": _sides(match, rnd.id, attackers),
            "buys": _round_buys(match, rnd),
        }
        if kills:
            fb = kills[0]
            row["first_blood"] = f"{fb.killer.name} > {fb.victim.name} ({_ms_to_clock(fb.time_in_round_in_ms)})"
            first_bloods[fb.killer.team] = first_bloods.get(fb.killer.team, 0) + 1
        if rnd.plant:
            row["plant"] = f"{rnd.plant.site} by {rnd.plant.player.name} at {_ms_to_clock(rnd.plant.round_time_in_ms)}"
        if rnd.defuse:
            row["defuse"] = f"{rnd.defuse.player.name} at {_ms_to_clock(rnd.defuse.round_time_in_ms)}"
        row["kills"] = [
            f"{_ms_to_clock(k.time_in_round_in_ms)} {k.killer.name} > {k.victim.name} ({k.weapon.name or 'Ability'})"
            for k in kills
        ]
        rounds.append(row)

    result = {
        "match_id": match.metadata.match_id,
        "map": match.metadata.map.name,
        "mode": match.metadata.queue.name if match.metadata.queue else None,
        "date": match.metadata.started_at,
        "teams": teams_out,
        "first_bloods_by_team": first_bloods,
        "rounds": rounds,
    }
    if match.metadata.mvp:
        result["match_mvp"] = f"{match.metadata.mvp.name}#{match.metadata.mvp.tag}"
    return json.dumps(result, indent=1, ensure_ascii=False)


async def format_match_narrative(match: Match, focus_puuid: str | None = None,
                                 only_rounds: list[int] | None = None) -> str:
    await ensure_loaded()
    map_name = match.metadata.map.name or ""
    attackers = attacking_team_by_round(match)
    player_agents = {p.puuid: p.agent.name for p in match.players}

    def tag(ref):
        me = " (YOU)" if focus_puuid and ref.puuid == focus_puuid else ""
        return f"{ref.name}#{ref.tag} ({player_agents.get(ref.puuid, '?')}, {ref.team}){me}"

    rounds_out = []
    for r in sorted(match.rounds, key=lambda r: r.id):
        if only_rounds and r.id + 1 not in only_rounds:
            continue
        timeline = []
        rks = sorted((k for k in match.kills if k.round == r.id), key=lambda k: k.time_in_round_in_ms)

        for idx, k in enumerate(rks):
            region, super_region = resolve(map_name, k.location.x, k.location.y)
            tags = ["first_blood"] if idx == 0 else []
            if any(prev.killer.puuid == k.victim.puuid and prev.victim.team == k.killer.team
                   and k.time_in_round_in_ms - prev.time_in_round_in_ms <= TRADE_WINDOW_MS
                   for prev in rks[:idx]):
                tags.append("trade")
            timeline.append({
                "t": _ms_to_clock(k.time_in_round_in_ms),
                "ms": k.time_in_round_in_ms,
                "type": "kill",
                "actor": tag(k.killer),
                "target": tag(k.victim),
                "zone": region,
                "zone_group": super_region,
                "weapon": k.weapon.name or "Ability",
                "tags": tags,
            })

        for event, data in (("plant", r.plant), ("defuse", r.defuse)):
            if not data:
                continue
            region, super_region = resolve(map_name, data.location.x, data.location.y)
            entry = {
                "t": _ms_to_clock(data.round_time_in_ms),
                "ms": data.round_time_in_ms,
                "type": event,
                "actor": tag(data.player),
                "zone": region,
                "zone_group": super_region,
            }
            if event == "plant":
                entry["site"] = data.site
            timeline.append(entry)
        timeline.sort(key=lambda e: e["ms"])
        for e in timeline:
            del e["ms"]

        round_tags = []
        first_kill = next((e for e in timeline if e["type"] == "kill"), None)
        plant_event = next((e for e in timeline if e["type"] == "plant"), None)
        if first_kill and plant_event and first_kill.get("zone_group") \
                and plant_event.get("zone_group") \
                and first_kill["zone_group"] != plant_event["zone_group"]:
            round_tags.append(f"rotation_{first_kill['zone_group']}_to_{plant_event['zone_group']}")

        rounds_out.append({
            "round": r.id + 1,
            "sides": _sides(match, r.id, attackers),
            "buys": _round_buys(match, r),
            "outcome": r.result,
            "winning_team": r.winning_team,
            "tags": round_tags,
            "timeline": timeline,
        })

    teams = {t.team_id: t for t in match.teams}
    result = {
        "match_id": match.metadata.match_id,
        "map": map_name,
        "date": match.metadata.started_at,
        "score": {tid: f"{t.rounds.won}-{t.rounds.lost}" for tid, t in teams.items()},
        "players": {
            tid: [f"{p.name}#{p.tag} ({p.agent.name})" for p in match.players if p.team_id == tid]
            for tid in teams
        },
        "rounds": rounds_out,
    }
    return json.dumps(result, indent=1, ensure_ascii=False)
