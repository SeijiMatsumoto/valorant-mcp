import json
from valorant_mcp.models import MatchData, V4MatchData
from valorant_mcp.callouts import ensure_loaded, resolve


def format_match_history(matches: list[MatchData], name: str, tag: str) -> str:
    summaries = []
    for match in matches:
        player = _find_player(match, name, tag)
        if not player:
            continue
        team = player.team.lower()
        opponent_team = "blue" if team == "red" else "red"
        won = match.teams[team].has_won
        s = player.stats

        teammates = []
        for p in match.players.get(team, []):
            if not (p.name.lower() == name.lower() and p.tag.lower() == tag.lower()):
                ps = p.stats
                teammates.append(f"{p.character} ({p.name}#{p.tag}): {ps.kills}/{ps.deaths}/{ps.assists}")

        opponents = []
        for p in match.players.get(opponent_team, []):
            opponents.append(f"{p.character} ({p.name}#{p.tag}): {p.stats.kills}/{p.stats.deaths}/{p.stats.assists}")

        summaries.append({
            "match_id": match.metadata.matchid,
            "map": match.metadata.map,
            "date": match.metadata.game_start_patched,
            "result": "Win" if won else "Loss",
            "rounds": f"{match.teams[team].rounds_won}-{match.teams[team].rounds_lost}",
            "player": {
                "agent": player.character,
                "rank": player.currenttier_patched,
                "kda": f"{s.kills}/{s.deaths}/{s.assists}",
                "score": s.score,
                "headshot_pct": f"{(s.headshots / (s.headshots + s.bodyshots + s.legshots)) * 100:.0f}%" if (s.headshots + s.bodyshots + s.legshots) > 0 else "0%",
                "damage_made": player.damage_made,
                "damage_received": player.damage_received,
            },
            "teammates": teammates,
            "opponents": opponents,
        })
    return json.dumps(summaries, indent=2)


def format_match_details(match: V4MatchData) -> str:
    red_team = [p for p in match.players if p.team_id == "Red"]
    blue_team = [p for p in match.players if p.team_id == "Blue"]

    red_result = next(t for t in match.teams if t.team_id == "Red")
    blue_result = next(t for t in match.teams if t.team_id == "Blue")

    def format_player(p):
        s = p.stats
        total_shots = s.headshots + s.bodyshots + s.legshots
        hs_pct = f"{(s.headshots / total_shots) * 100:.0f}%" if total_shots > 0 else "0%"
        return {
            "agent": p.agent.name,
            "name": f"{p.name}#{p.tag}",
            "rank": p.tier.name,
            "kda": f"{s.kills}/{s.deaths}/{s.assists}",
            "score": s.score,
            "headshot_pct": hs_pct,
            "damage_dealt": s.damage.dealt,
            "damage_received": s.damage.received,
            "economy": {
                "spent": p.economy.spent.overall,
                "avg_spent": p.economy.spent.average,
                "loadout": p.economy.loadout_value.overall,
                "avg_loadout": p.economy.loadout_value.average,
            },
        }

    kills = []
    for k in match.kills:
        kills.append({
            "round": k.round,
            "time_in_round_ms": k.time_in_round_in_ms,
            "killer": f"{k.killer.name}#{k.killer.tag} ({k.killer.team})",
            "victim": f"{k.victim.name}#{k.victim.tag} ({k.victim.team})",
            "weapon": k.weapon.name or "Ability",
            "location": {"x": k.location.x, "y": k.location.y},
            "assistants": [f"{a.name}#{a.tag}" for a in k.assistants],
        })

    rounds = []
    for r in match.rounds:
        round_data = {
            "round": r.id,
            "result": r.result,
            "winning_team": r.winning_team,
        }
        if r.plant:
            round_data["plant"] = {
                "site": r.plant.site,
                "time_ms": r.plant.round_time_in_ms,
                "player": f"{r.plant.player.name}#{r.plant.player.tag}",
                "location": {"x": r.plant.location.x, "y": r.plant.location.y},
            }
        if r.defuse:
            round_data["defuse"] = {
                "time_ms": r.defuse.round_time_in_ms,
                "player": f"{r.defuse.player.name}#{r.defuse.player.tag}",
                "location": {"x": r.defuse.location.x, "y": r.defuse.location.y},
            }
        round_data["player_economy"] = [
            {
                "player": f"{rs.player.name}#{rs.player.tag}",
                "team": rs.player.team,
                "loadout_value": rs.economy.loadout_value,
                "remaining": rs.economy.remaining,
                "weapon": rs.economy.weapon.name if rs.economy.weapon else None,
                "armor": rs.economy.armor.name if rs.economy.armor else None,
            }
            for rs in r.stats
        ]
        rounds.append(round_data)

    # Compute first bloods
    first_bloods = {}
    first_deaths = {}
    for k in match.kills:
        r = k.round
        if r not in first_bloods:
            first_bloods[r] = f"{k.killer.name}#{k.killer.tag}"
            first_deaths[r] = f"{k.victim.name}#{k.victim.tag}"

    fb_counts = {}
    fd_counts = {}
    for name in first_bloods.values():
        fb_counts[name] = fb_counts.get(name, 0) + 1
    for name in first_deaths.values():
        fd_counts[name] = fd_counts.get(name, 0) + 1

    result = {
        "match_id": match.metadata.match_id,
        "map": match.metadata.map.name,
        "date": match.metadata.started_at,
        "region": match.metadata.region,
        "red_team": {
            "result": "Win" if red_result.won else "Loss",
            "rounds": f"{red_result.rounds.won}-{red_result.rounds.lost}",
            "players": [format_player(p) for p in red_team],
        },
        "blue_team": {
            "result": "Win" if blue_result.won else "Loss",
            "rounds": f"{blue_result.rounds.won}-{blue_result.rounds.lost}",
            "players": [format_player(p) for p in blue_team],
        },
        "first_blood_counts": fb_counts,
        "first_death_counts": fd_counts,
        "kills": kills,
        "rounds": rounds,
    }
    return json.dumps(result, indent=2)


def _derive_sides(match: V4MatchData) -> dict[int, dict[str, str]]:
    attacker_r1 = None
    for r in sorted(match.rounds, key=lambda r: r.id):
        if r.id > 12:
            break
        if r.plant:
            attacker_r1 = r.plant.player.team
            break
    if attacker_r1 is None:
        return {}
    defender_r1 = "Blue" if attacker_r1 == "Red" else "Red"
    sides: dict[int, dict[str, str]] = {}
    for r in match.rounds:
        if r.id <= 12:
            sides[r.id] = {attacker_r1.lower(): "attack", defender_r1.lower(): "defense"}
        elif r.id <= 24:
            sides[r.id] = {attacker_r1.lower(): "defense", defender_r1.lower(): "attack"}
        else:
            sides[r.id] = {"red": "overtime", "blue": "overtime"}
    return sides


def _ms_to_clock(ms: int) -> str:
    total_s = ms // 1000
    return f"{total_s // 60}:{total_s % 60:02d}"


async def format_match_narrative(match: V4MatchData) -> str:
    await ensure_loaded()
    map_name = match.metadata.map.name
    sides = _derive_sides(match)

    player_agents = {p.name + "#" + p.tag: p.agent.name for p in match.players}

    def tag(ref):
        key = f"{ref.name}#{ref.tag}"
        agent = player_agents.get(key, "?")
        return f"{ref.name}#{ref.tag} ({agent}, {ref.team})"

    kills_by_round: dict[int, list] = {}
    for k in match.kills:
        kills_by_round.setdefault(k.round, []).append(k)

    rounds_out = []
    for r in sorted(match.rounds, key=lambda r: r.id):
        timeline = []
        rks = sorted(kills_by_round.get(r.id, []), key=lambda k: k.time_in_round_in_ms)

        for idx, k in enumerate(rks):
            region, super_region = resolve(map_name, k.location.x, k.location.y)
            tags = []
            if idx == 0:
                tags.extend(["entry", "first_blood"])
            for prev in rks[:idx]:
                if (k.time_in_round_in_ms - prev.time_in_round_in_ms) <= 5000 \
                        and prev.victim.team == k.killer.team:
                    prev_region, _ = resolve(map_name, prev.location.x, prev.location.y)
                    if prev_region == region:
                        tags.append("trade")
                        break
            timeline.append({
                "t": _ms_to_clock(k.time_in_round_in_ms),
                "type": "kill",
                "actor": tag(k.killer),
                "target": tag(k.victim),
                "zone": region,
                "zone_group": super_region,
                "weapon": k.weapon.name or "Ability",
                "tags": tags,
            })

        if r.plant:
            region, super_region = resolve(map_name, r.plant.location.x, r.plant.location.y)
            timeline.append({
                "t": _ms_to_clock(r.plant.round_time_in_ms),
                "type": "plant",
                "actor": tag(r.plant.player),
                "site": r.plant.site,
                "zone": region,
                "zone_group": super_region,
            })
        if r.defuse:
            region, super_region = resolve(map_name, r.defuse.location.x, r.defuse.location.y)
            timeline.append({
                "t": _ms_to_clock(r.defuse.round_time_in_ms),
                "type": "defuse",
                "actor": tag(r.defuse.player),
                "zone": region,
                "zone_group": super_region,
            })
        timeline.sort(key=lambda e: e["t"])

        round_tags = []
        first_kill = next((e for e in timeline if e["type"] == "kill"), None)
        plant_event = next((e for e in timeline if e["type"] == "plant"), None)
        if first_kill and plant_event and first_kill.get("zone_group") \
                and plant_event.get("zone_group") \
                and first_kill["zone_group"] != plant_event["zone_group"]:
            round_tags.append(f"rotation_{first_kill['zone_group']}_to_{plant_event['zone_group']}")

        rounds_out.append({
            "round": r.id,
            "side": sides.get(r.id, {}),
            "outcome": r.result,
            "winning_team": r.winning_team,
            "tags": round_tags,
            "timeline": timeline,
        })

    red_team = next((t for t in match.teams if t.team_id == "Red"), None)
    blue_team = next((t for t in match.teams if t.team_id == "Blue"), None)

    result = {
        "match_id": match.metadata.match_id,
        "map": map_name,
        "date": match.metadata.started_at,
        "sides_first_half": {
            "red": sides.get(1, {}).get("red"),
            "blue": sides.get(1, {}).get("blue"),
        },
        "score": {
            "red": f"{red_team.rounds.won}-{red_team.rounds.lost}" if red_team else None,
            "blue": f"{blue_team.rounds.won}-{blue_team.rounds.lost}" if blue_team else None,
        },
        "players": {
            "red": [f"{p.name}#{p.tag} ({p.agent.name})" for p in match.players if p.team_id == "Red"],
            "blue": [f"{p.name}#{p.tag} ({p.agent.name})" for p in match.players if p.team_id == "Blue"],
        },
        "rounds": rounds_out,
    }
    return json.dumps(result, indent=2)


def _find_player(match: MatchData, name: str, tag: str):
    for player in match.players["all_players"]:
        if player.name.lower() == name.lower() and player.tag.lower() == tag.lower():
            return player
    return None


def compute_agent_stats(matches: list[MatchData], name: str, tag: str) -> str:
    agent_stats = {}
    for match in matches:
        player = _find_player(match, name, tag)                                                         
        if not player:
            continue
        agent = player.character
        team = player.team.lower()
        won = match.teams[team].has_won

        if agent not in agent_stats:
            agent_stats[agent] = {"games": 0, "wins": 0, "kills": 0, "deaths": 0, "assists": 0, "score": 0}

        agent_stats[agent]["games"] += 1
        agent_stats[agent]["wins"] += 1 if won else 0
        agent_stats[agent]["kills"] += player.stats.kills
        agent_stats[agent]["deaths"] += player.stats.deaths
        agent_stats[agent]["assists"] += player.stats.assists
        agent_stats[agent]["score"] += player.stats.score

    result = {}
    for agent, stats in agent_stats.items():
        g = stats["games"]
        result[agent] = {
            "games": g,
            "wins": stats["wins"],
            "losses": g - stats["wins"],
            "win_rate": f"{(stats['wins'] / g) * 100:.0f}%",
            "avg_kills": round(stats["kills"] / g, 1),
            "avg_deaths": round(stats["deaths"] / g, 1),
            "avg_assists": round(stats["assists"] / g, 1),
            "avg_score": round(stats["score"] / g, 0),
        }
    return json.dumps(result, indent=2)


def compute_map_stats(matches: list[MatchData], name: str, tag: str) -> str:
    map_stats = {}
    for match in matches:
        player = _find_player(match, name, tag)
        if not player:
            continue
        map_name = match.metadata.map
        team = player.team.lower()
        won = match.teams[team].has_won

        if map_name not in map_stats:
            map_stats[map_name] = {"games": 0, "wins": 0, "score": 0}

        map_stats[map_name]["games"] += 1
        map_stats[map_name]["wins"] += 1 if won else 0
        map_stats[map_name]["score"] += player.stats.score

    result = {}
    for map_name, stats in map_stats.items():
        g = stats["games"]
        result[map_name] = {
            "games": g,
            "wins": stats["wins"],
            "losses": g - stats["wins"],
            "win_rate": f"{(stats['wins'] / g) * 100:.0f}%",
            "avg_score": round(stats["score"] / g, 0),
        }
    return json.dumps(result, indent=2)


def compute_weapon_stats(matches: list[V4MatchData], name: str, tag: str) -> str:
    weapon_stats = {}
    full_name = f"{name}#{tag}".lower()

    for match in matches:
        for kill in match.kills:
            killer_name = f"{kill.killer.name}#{kill.killer.tag}".lower()
            if killer_name != full_name:
                continue

            weapon_name = kill.weapon.name or "Ability"
            if weapon_name not in weapon_stats:
                weapon_stats[weapon_name] = {"kills": 0}

            weapon_stats[weapon_name]["kills"] += 1

    sorted_weapons = dict(sorted(weapon_stats.items(), key=lambda x: x[1]["kills"], reverse=True))

    total_kills = sum(w["kills"] for w in sorted_weapons.values())
    result = {"total_kills": total_kills, "matches_analyzed": len(matches), "weapons": {}}
    for weapon, stats in sorted_weapons.items():
        result["weapons"][weapon] = {
            "kills": stats["kills"],
            "usage_pct": f"{(stats['kills'] / total_kills) * 100:.0f}%" if total_kills > 0 else "0%",
        }
    return json.dumps(result, indent=2)
