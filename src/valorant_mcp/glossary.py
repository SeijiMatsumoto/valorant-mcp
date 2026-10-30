GLOSSARY = """# Valorant MCP metric glossary

All metrics come from Henrik's v4 match data. Rounds are shown 1-indexed. Distances are metres
(game units / 100). Unless stated otherwise, metrics are for the requested player only.

## Confidence and sample size
- **\\*_ci95**: 95% confidence range (Wilson interval) for a percentage. With 9 games, a 78% win
  rate has a range of roughly 45–94%: overlapping ranges mean a difference may be noise.
- **low_sample**: fewer than 3 matches or 20 rounds in that bucket.

## Core
- **ACS**: combat score per round. **ADR**: damage dealt per round.
- **KAST %**: rounds where the player got a Kill, Assist, Survived, or was Traded.
- **HS %**: headshots / all hits (from Riot's shot counts).
- **avg_team_acs_rank**: average ACS placement on own team (1 = top fragger).

## Opening duels
- **first_kill / first_death**: the player got / was the first kill of the round.
- **opening_win_pct**: first kills / (first kills + first deaths).
- **round_win_pct_after_my_first_kill / ...first_death**: team round win % in those rounds.

## Trading and spacing
- **traded death**: a teammate killed the player's killer within 5 s of the death.
- **trade kill**: the player killed someone within 5 s of that enemy killing a teammate.
- **trade chance**: a teammate died within 15 m of the player while the player was alive.
  **conversion_pct** = chances where the player then killed that killer within 5 s.
- **nearest teammate distance at death**: distance from the death spot to the closest living
  teammate at that moment.
- **isolated death**: no living teammate within 25 m. **loose**: 15–25 m. **close**: within 15 m.
- **early death**: died in the first 25 s of the round.

## Clutches and multikills
- **clutch 1vX**: the player became the last one alive on their team with X enemies alive.
  Shown as won/attempts. 1v3+ includes many unwinnable rounds; weigh 1v1/1v2 more.
- **multikills**: rounds with 2/3/4/5 kills by the player.

## Economy
- **team buy**: average loadout value (weapon + armor + abilities) at round start for the team:
  eco < 2000, force 2000–3899, full ≥ 3900. Rounds 1 and 13 (and swiftplay equivalents) are pistol.
- **anti_eco**: our full buy vs their eco/force. **upsets**: our eco/force vs their full buy.
- **my_buy_vs_team**: rounds where the player's own loadout class differed from the team's
  (saved while the team full-bought, or full-bought while the team saved).

## Damage and weapons
- **damage_per_kill**: total damage dealt / kills.
- **rounds_100dmg_no_kill_pct**: of rounds with 100+ damage dealt, share with zero kills
  (damage that didn't convert).
- **median_kill_distance_m**: median distance from the player to the victim, per weapon.
- **engagement_ranges**: kills and deaths by distance: close < 10 m, mid 10–25 m, long 25 m+.
- **by_primary_weapon_held**: results in rounds by the main weapon the player bought.

## Benchmarks
- **lobby**: all other players in the same matches (both teams) — controls for rank.
- **same_role**: other players in that match whose agent role (Duelist, Initiator, Controller,
  Sentinel) matches the player's role in that match.
- **others_on_agent**: everyone else who played that agent in the player's matches.
- **avg_place_in_lobby_of_10**: average placement among all 10 players (1 = best).
- **utility_casts_per_round**: total ability casts / rounds; per-ability breakdown uses C/Q/E/X.
- **henrik_performance**: Henrik's 4.10 performance model when the API provides it. Ratings
  are labels like down / neutral / up / double_up per category.

## Context
- **party**: solo, duo, trio, 4-stack, 5-stack (from shared party ids).
- **lobby strength**: enemy team's average rank vs the player's rank that match.
- **game in session**: games whose start times are within 100 min of the previous one count as
  the same session.

## Sites (team-level)
- **plant_rate_pct**: attack rounds where our team planted. **post_plant_win_pct**: win % after
  planting on that site.
- **enemy_plant_rate_pct / retake_or_hold_win_pct**: on defense, how often the enemy planted
  each site and how often we still won.
"""
