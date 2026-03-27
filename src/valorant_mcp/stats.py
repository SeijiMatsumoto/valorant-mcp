import json
from valorant_mcp.models import MatchData, V4MatchData


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
                total_shots = ps.headshots + ps.bodyshots + ps.legshots
                hs_pct = f"{(ps.headshots / total_shots) * 100:.0f}%" if total_shots > 0 else "0%"
                teammates.append({
                    "agent": p.character,
                    "name": f"{p.name}#{p.tag}",
                    "rank": p.currenttier_patched,
                    "kda": f"{ps.kills}/{ps.deaths}/{ps.assists}",
                    "score": ps.score,
                    "headshot_pct": hs_pct,
                    "damage_made": p.damage_made,
                    "damage_received": p.damage_received,
                    "economy": {
                        "spent": p.economy.spent.overall,
                        "avg_spent": p.economy.spent.average,
                        "loadout": p.economy.loadout_value.overall,
                        "avg_loadout": p.economy.loadout_value.average,
                    },
                })

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
                "economy": {
                    "spent": player.economy.spent.overall,
                    "avg_spent": player.economy.spent.average,
                    "loadout": player.economy.loadout_value.overall,
                    "avg_loadout": player.economy.loadout_value.average,
                },
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
            }
        if r.defuse:
            round_data["defuse"] = {
                "time_ms": r.defuse.round_time_in_ms,
                "player": f"{r.defuse.player.name}#{r.defuse.player.tag}",
            }
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
