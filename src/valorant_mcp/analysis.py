"""Per-round and per-match analysis of players across v4 matches.

Everything here is derived from raw match data so it works whether or not the
API fills in the 4.10 fields (first_blood, winning_team_role, performance).

Distances are in game units (≈ centimetres), reported in metres.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import agents
from .callouts import zone_label
from .models import Location, Match, MatchPlayer, Round

TRADE_WINDOW_MS = 5000
EARLY_DEATH_MS = 25000
# A teammate dying within this distance of you is a trade chance.
TRADE_RANGE = 1500
# Dying with no teammate within this distance counts as an isolated death.
ISOLATED_RANGE = 2500
# Engagement range buckets for kills/deaths.
CLOSE_RANGE = 1000
LONG_RANGE = 2500
# Start-to-start gap that still counts as the same play session (~40m game + 1h break).
SESSION_GAP = timedelta(minutes=100)
HALF_LENGTH = {"swiftplay": 4, "spikerush": 3}

# Average loadout value (weapon + armor + abilities) at round start.
ECO_MAX = 2000
FULL_MIN = 3900

LOW_SAMPLE_MATCHES = 3
LOW_SAMPLE_ROUNDS = 20


# --- sides & round structure ---

def half_length(match: Match) -> int:
    queue = (match.metadata.queue.id if match.metadata.queue else "") or ""
    return HALF_LENGTH.get(queue.lower(), 12)


def _parity(round_id: int, half: int) -> int:
    """0 = same sides as round 1, 1 = swapped. Overtime alternates every round."""
    if round_id < half:
        return 0
    if round_id < 2 * half:
        return 1
    return (round_id - 2 * half) % 2


def _other(team: str, teams: list[str]) -> str:
    return teams[1] if team == teams[0] else teams[0]


def attacking_team_by_round(match: Match) -> dict[int, str]:
    """Map round id -> attacking team id. Empty if sides can't be determined."""
    teams = sorted({p.team_id for p in match.players})
    if len(teams) != 2:
        return {}
    half = half_length(match)
    votes: Counter[str] = Counter()
    for r in match.rounds:
        attacker = None
        if r.winning_team_role in ("Attacker", "Defender") and r.winning_team in teams:
            attacker = r.winning_team if r.winning_team_role == "Attacker" else _other(r.winning_team, teams)
        elif r.plant and r.plant.player.team in teams:
            attacker = r.plant.player.team
        if attacker:
            votes[attacker if _parity(r.id, half) == 0 else _other(attacker, teams)] += 1
    if not votes:
        return {}
    first = votes.most_common(1)[0][0]
    return {r.id: first if _parity(r.id, half) == 0 else _other(first, teams) for r in match.rounds}


def side_for(team: str, round_id: int, attackers: dict[int, str]) -> str | None:
    attacker = attackers.get(round_id)
    if attacker is None:
        return None
    return "attack" if attacker == team else "defense"


def buy_type(avg_loadout: float) -> str:
    if avg_loadout < ECO_MAX:
        return "eco"
    if avg_loadout < FULL_MIN:
        return "force"
    return "full"


def team_loadout(rnd: Round, team: str) -> float | None:
    values = [s.economy.loadout_value for s in rnd.stats if s.player.team == team]
    return sum(values) / len(values) if values else None


def _dist(a: Location, b: Location) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def range_bucket(units: float) -> str:
    if units < CLOSE_RANGE:
        return "close (<10m)"
    if units < LONG_RANGE:
        return "mid (10-25m)"
    return "long (25m+)"


# --- records ---

@dataclass
class RoundRecord:
    match_id: str
    map: str
    agent: str
    round: int  # 1-indexed for display
    side: str | None
    won: bool
    buy: str  # team buy: pistol / eco / force / full
    enemy_buy: str
    my_buy: str = "unknown"  # own loadout class
    kills: int = 0
    died: bool = False
    assisted: bool = False
    traded_death: bool = False
    trade_kills: int = 0
    trade_chances: int = 0  # teammate died within TRADE_RANGE of me while I was alive
    trade_chances_taken: int = 0  # ...and I killed their killer within the trade window
    first_kill: bool = False
    first_death: bool = False
    clutch_vs: int | None = None  # X in a 1vX the player was left in
    damage: int = 0
    death_time_ms: int | None = None
    death_zone: str | None = None
    nearest_mate_at_death: float | None = None
    killer_distance: float | None = None
    weapon: str | None = None  # primary weapon held this round
    kill_weapons: list[str] = field(default_factory=list)
    kill_distances: list[tuple[str, float]] = field(default_factory=list)
    headshots: int = 0
    bodyshots: int = 0
    legshots: int = 0
    planted_by_us: bool = False
    enemy_planted: bool = False
    plant_site: str | None = None
    i_planted: bool = False

    @property
    def kast(self) -> bool:
        return self.kills > 0 or self.assisted or not self.died or self.traded_death

    @property
    def isolated_death(self) -> bool:
        return self.died and (self.nearest_mate_at_death is None
                              or self.nearest_mate_at_death > ISOLATED_RANGE)


@dataclass
class MatchRecord:
    match_id: str
    puuid: str
    name: str
    started_at: datetime
    map: str
    agent: str
    role: str
    rank: str
    tier_id: int
    won: bool
    draw: bool
    rounds_won: int
    rounds_lost: int
    score: int
    kills: int
    deaths: int
    assists: int
    damage: int
    headshots: int
    bodyshots: int
    legshots: int
    party_size: int
    party_mates: list[str]
    team_acs_rank: int  # 1 = top ACS on own team
    enemy_avg_tier: float | None
    ability_casts: dict[str, int]
    grade: str | None
    perf_breakdown: dict[str, float]
    perf_ratings: dict[str, str]
    is_match_mvp: bool
    rounds: list[RoundRecord]
    session_game: int = 1  # filled in by annotate_sessions

    @property
    def rounds_played(self) -> int:
        return max(1, self.rounds_won + self.rounds_lost)

    @property
    def acs(self) -> float:
        return self.score / self.rounds_played

    @property
    def result(self) -> str:
        return "Draw" if self.draw else ("Win" if self.won else "Loss")


def find_player(match: Match, puuid: str) -> MatchPlayer | None:
    return next((p for p in match.players if p.puuid == puuid), None)


def _performance(me: MatchPlayer) -> tuple[str | None, dict[str, float], dict[str, str]]:
    perf = me.performance
    if not perf:
        return None, {}, {}
    breakdown = {k: v for k, v in perf.breakdown.items() if v is not None}
    ratings: dict[str, str] = {}
    if perf.ratings:
        for group in ("combat", "utility"):
            values = getattr(perf.ratings, group)
            if values:
                ratings.update({f"{group}.{k}": v for k, v in values.model_dump().items() if v})
    return (perf.ratings.grade if perf.ratings else None), breakdown, ratings


def analyze_match(match: Match, puuid: str) -> MatchRecord | None:
    me = find_player(match, puuid)
    if me is None:
        return None
    team = me.team_id
    teams = sorted({p.team_id for p in match.players})
    if len(teams) != 2:
        return None  # deathmatch etc.
    enemy = _other(team, teams)
    half = half_length(match)
    attackers = attacking_team_by_round(match)
    map_name = match.metadata.map.name or "Unknown"
    agent = me.agent.name or "Unknown"

    roster = {p.puuid: p.team_id for p in match.players}
    kills_by_round: dict[int, list] = defaultdict(list)
    for k in match.kills:
        kills_by_round[k.round].append(k)

    rounds: list[RoundRecord] = []
    for rnd in sorted(match.rounds, key=lambda r: r.id):
        kills = sorted(kills_by_round.get(rnd.id, []), key=lambda k: k.time_in_round_in_ms)
        my_stats = next((s for s in rnd.stats if s.player.puuid == puuid), None)
        if rnd.id in (0, half):
            own_buy = enemy_buy = my_buy = "pistol"
        else:
            own, theirs = team_loadout(rnd, team), team_loadout(rnd, enemy)
            own_buy = buy_type(own) if own is not None else "unknown"
            enemy_buy = buy_type(theirs) if theirs is not None else "unknown"
            my_buy = buy_type(my_stats.economy.loadout_value) if my_stats else "unknown"

        rec = RoundRecord(
            match_id=match.metadata.match_id, map=map_name, agent=agent,
            round=rnd.id + 1, side=side_for(team, rnd.id, attackers),
            won=rnd.winning_team == team, buy=own_buy, enemy_buy=enemy_buy, my_buy=my_buy,
        )
        if rnd.plant:
            rec.planted_by_us = rnd.plant.player.team == team
            rec.enemy_planted = not rec.planted_by_us
            rec.plant_site = rnd.plant.site
            rec.i_planted = rnd.plant.player.puuid == puuid

        if my_stats:
            rec.damage = sum(e.damage for e in my_stats.damage_events)
            rec.weapon = my_stats.economy.weapon.name if my_stats.economy.weapon else None
            rec.headshots = my_stats.stats.headshots
            rec.bodyshots = my_stats.stats.bodyshots
            rec.legshots = my_stats.stats.legshots

        if kills:
            rec.first_kill = kills[0].killer.puuid == puuid
            rec.first_death = kills[0].victim.puuid == puuid

        alive = set(roster)
        for i, k in enumerate(kills):
            positions = {pl.player.puuid: pl.location for pl in k.player_locations}
            alive.discard(k.victim.puuid)
            if k.killer.puuid == puuid and k.victim.team != team:
                rec.kills += 1
                weapon = k.weapon.name or "Ability"
                rec.kill_weapons.append(weapon)
                if puuid in positions:
                    rec.kill_distances.append((weapon, _dist(positions[puuid], k.location)))
                # Trade: I killed someone who killed a teammate in the last few seconds.
                if any(prev.killer.puuid == k.victim.puuid and prev.victim.team == team
                       and k.time_in_round_in_ms - prev.time_in_round_in_ms <= TRADE_WINDOW_MS
                       for prev in kills[:i]):
                    rec.trade_kills += 1
            if any(a.puuid == puuid for a in k.assistants):
                rec.assisted = True
            if k.victim.puuid == puuid:
                rec.died = True
                rec.death_time_ms = k.time_in_round_in_ms
                rec.death_zone = zone_label(map_name, k.location.x, k.location.y)
                mates = [_dist(loc, k.location) for pid, loc in positions.items()
                         if pid != puuid and roster.get(pid) == team]
                rec.nearest_mate_at_death = min(mates) if mates else None
                if k.killer.puuid in positions:
                    rec.killer_distance = _dist(positions[k.killer.puuid], k.location)
                rec.traded_death = any(
                    later.victim.puuid == k.killer.puuid and later.killer.team == team
                    and later.time_in_round_in_ms - k.time_in_round_in_ms <= TRADE_WINDOW_MS
                    for later in kills[i + 1:]
                )
            elif (k.victim.team == team and puuid in alive and puuid in positions
                  and _dist(positions[puuid], k.location) <= TRADE_RANGE):
                rec.trade_chances += 1
                if any(later.killer.puuid == puuid and later.victim.puuid == k.killer.puuid
                       and later.time_in_round_in_ms - k.time_in_round_in_ms <= TRADE_WINDOW_MS
                       for later in kills[i + 1:]):
                    rec.trade_chances_taken += 1
            # Clutch: I'm the last one alive on my team with enemies still up.
            if rec.clutch_vs is None and puuid in alive and k.victim.team == team:
                mates_alive = [pid for pid in alive if roster[pid] == team]
                enemies = [pid for pid in alive if roster[pid] == enemy]
                if mates_alive == [puuid] and enemies:
                    rec.clutch_vs = len(enemies)
        rounds.append(rec)

    my_team = next((t for t in match.teams if t.team_id == team), None)
    other_team = next((t for t in match.teams if t.team_id != team), None)
    rounds_won = my_team.rounds.won if my_team else sum(r.won for r in rounds)
    rounds_lost = my_team.rounds.lost if my_team else len(rounds) - rounds_won
    draw = bool(my_team and other_team and not my_team.won and not other_team.won)

    teammates = sorted((p for p in match.players if p.team_id == team),
                       key=lambda p: p.stats.score, reverse=True)
    party_mates = [f"{p.name}#{p.tag}" for p in teammates
                   if me.party_id and p.party_id == me.party_id and p.puuid != puuid]
    enemy_tiers = [p.tier.id for p in match.players if p.team_id == enemy and p.tier.id >= 3]
    casts = me.ability_casts.model_dump() if me.ability_casts else {}
    grade, breakdown, ratings = _performance(me)
    s = me.stats
    return MatchRecord(
        match_id=match.metadata.match_id,
        puuid=puuid,
        name=f"{me.name}#{me.tag}",
        started_at=_parse_time(match.metadata.started_at),
        map=map_name,
        agent=agent,
        role=agents.role(agent),
        rank=me.tier.name,
        tier_id=me.tier.id,
        won=bool(my_team and my_team.won),
        draw=draw,
        rounds_won=rounds_won,
        rounds_lost=rounds_lost,
        score=s.score, kills=s.kills, deaths=s.deaths, assists=s.assists,
        damage=s.damage.dealt,
        headshots=s.headshots, bodyshots=s.bodyshots, legshots=s.legshots,
        party_size=len(party_mates) + 1,
        party_mates=party_mates,
        team_acs_rank=next(i for i, p in enumerate(teammates, 1) if p.puuid == puuid),
        enemy_avg_tier=sum(enemy_tiers) / len(enemy_tiers) if enemy_tiers else None,
        ability_casts={k: v for k, v in casts.items() if v is not None},
        grade=grade,
        perf_breakdown=breakdown,
        perf_ratings=ratings,
        is_match_mvp=bool(match.metadata.mvp and match.metadata.mvp.puuid == puuid),
        rounds=rounds,
    )


def analyze_all_players(match: Match) -> list[MatchRecord]:
    """Records for all ten players — used to benchmark against the lobby."""
    return [r for p in match.players if (r := analyze_match(match, p.puuid))]


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value)


def annotate_sessions(records: list[MatchRecord]) -> None:
    """Number games within a play session, based on gaps between match start times."""
    ordered = sorted(records, key=lambda r: r.started_at)
    prev = None
    for rec in ordered:
        if prev and rec.started_at - prev.started_at <= SESSION_GAP:
            rec.session_game = prev.session_game + 1
        else:
            rec.session_game = 1
        prev = rec


def analyze_matches(matches: list[Match], puuid: str) -> list[MatchRecord]:
    records = [r for m in matches if (r := analyze_match(m, puuid))]
    annotate_sessions(records)
    return records


# --- aggregation helpers ---

def pct(num: float, den: float) -> float | None:
    return round(100 * num / den, 1) if den else None


def avg(num: float, den: float, digits: int = 2) -> float | None:
    return round(num / den, digits) if den else None


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% confidence range for a rate, in percent. Honest about small samples."""
    if not n:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(100 * max(0.0, centre - margin), 1), round(100 * min(1.0, centre + margin), 1)]


def median_m(values: list[float]) -> float | None:
    """Median distance in metres."""
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    value = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return round(value / 100, 1)


def summarize_rounds(rounds: list[RoundRecord]) -> dict:
    n = len(rounds)
    won = sum(r.won for r in rounds)
    deaths = sum(r.died for r in rounds)
    out = {
        "rounds": n,
        "round_win_pct": pct(won, n),
        "round_win_ci95": wilson(won, n),
        "kast_pct": pct(sum(r.kast for r in rounds), n),
        "kills_per_round": avg(sum(r.kills for r in rounds), n),
        "survival_pct": pct(n - deaths, n),
        "adr": avg(sum(r.damage for r in rounds), n, 1),
        "first_kills": sum(r.first_kill for r in rounds),
        "first_deaths": sum(r.first_death for r in rounds),
    }
    if n < LOW_SAMPLE_ROUNDS:
        out["low_sample"] = True
    return out


def _clutch_buckets(rounds: list[RoundRecord]) -> dict[str, str]:
    buckets: dict[str, list[RoundRecord]] = defaultdict(list)
    for r in rounds:
        if r.clutch_vs:
            buckets["1v3+" if r.clutch_vs >= 3 else f"1v{r.clutch_vs}"].append(r)
    return {k: f"{sum(r.won for r in v)}/{len(v)}" for k, v in sorted(buckets.items())}


def summarize_matches(records: list[MatchRecord], compact: bool = False) -> dict:
    n = len(records)
    rounds = [r for m in records for r in m.rounds]
    rp = sum(m.rounds_played for m in records)
    shots = sum(m.headshots + m.bodyshots + m.legshots for m in records)
    deaths = sum(m.deaths for m in records)
    kills = sum(m.kills for m in records)
    wins = sum(m.won for m in records)

    out = {
        "matches": n,
        "record": f"{wins}W-{sum(not m.won and not m.draw for m in records)}L"
                  + (f"-{sum(m.draw for m in records)}D" if any(m.draw for m in records) else ""),
        "win_pct": pct(wins, n),
        "win_ci95": wilson(wins, n),
        "acs": avg(sum(m.score for m in records), rp, 0),
        "kd": avg(kills, deaths),
        "adr": avg(sum(m.damage for m in records), rp, 1),
        "hs_pct": pct(sum(m.headshots for m in records), shots),
        "kast_pct": pct(sum(r.kast for r in rounds), len(rounds)),
    }
    fk = sum(r.first_kill for r in rounds)
    fd = sum(r.first_death for r in rounds)
    out["first_kills"] = fk
    out["first_deaths"] = fd
    if compact:
        sides = {s: [r for r in rounds if r.side == s] for s in ("attack", "defense")}
        out["attack_round_win_pct"] = pct(sum(r.won for r in sides["attack"]), len(sides["attack"]))
        out["defense_round_win_pct"] = pct(sum(r.won for r in sides["defense"]), len(sides["defense"]))
    else:
        died = [r for r in rounds if r.died]
        traded = sum(r.traded_death for r in died)
        multi = Counter(min(r.kills, 5) for r in rounds if r.kills >= 2)
        dmg_rounds = [r for r in rounds if r.damage >= 100]
        out.update({
            "avg_kda": f"{avg(kills, n, 1)}/{avg(deaths, n, 1)}/{avg(sum(m.assists for m in records), n, 1)}",
            "rounds": len(rounds),
            "opening_duels": {
                "first_kill_rate_pct": pct(fk, len(rounds)),
                "first_death_rate_pct": pct(fd, len(rounds)),
                "opening_win_pct": pct(fk, fk + fd),
                "opening_win_ci95": wilson(fk, fk + fd),
                "round_win_pct_after_my_first_kill": pct(sum(r.won for r in rounds if r.first_kill), fk),
                "round_win_pct_after_my_first_death": pct(sum(r.won for r in rounds if r.first_death), fd),
            },
            "trading": {
                "my_deaths_traded_pct": pct(traded, len(died)),
                "my_deaths_traded_ci95": wilson(traded, len(died)),
                "trade_kills_per_round": avg(sum(r.trade_kills for r in rounds), len(rounds)),
                "early_death_pct": pct(
                    sum(r.death_time_ms is not None and r.death_time_ms <= EARLY_DEATH_MS for r in died),
                    len(died)),
                "isolated_death_pct": pct(sum(r.isolated_death for r in died), len(died)),
            },
            "damage_conversion": {
                "damage_per_kill": avg(sum(r.damage for r in rounds), kills, 0),
                "rounds_100dmg_no_kill_pct": pct(sum(r.kills == 0 for r in dmg_rounds), len(dmg_rounds)),
            },
            "clutches": _clutch_buckets(rounds),
            "multikills": {f"{k}k": multi[k] for k in sorted(multi)},
            "avg_team_acs_rank": avg(sum(m.team_acs_rank for m in records), n, 1),
        })
        grades = Counter(m.grade for m in records if m.grade)
        if grades:
            out["henrik_grades"] = dict(grades)
    if n < LOW_SAMPLE_MATCHES:
        out["low_sample"] = True
    return out


def group_by(records: list[MatchRecord], key) -> dict[str, list[MatchRecord]]:
    groups: dict[str, list[MatchRecord]] = defaultdict(list)
    for r in records:
        groups[key(r)].append(r)
    return dict(sorted(groups.items(), key=lambda kv: -len(kv[1])))


def party_label(size: int) -> str:
    return {1: "solo", 2: "duo", 3: "trio", 4: "4-stack", 5: "5-stack"}.get(size, f"{size}-stack")


def lobby_label(m: MatchRecord) -> str:
    if m.enemy_avg_tier is None or m.tier_id < 3:
        return "unknown"
    diff = m.enemy_avg_tier - m.tier_id
    if diff >= 1:
        return "tougher enemies (avg ≥1 rank above you)"
    if diff <= -1:
        return "easier enemies (avg ≥1 rank below you)"
    return "even enemies"


def _win_rate(rounds: list[RoundRecord]) -> dict:
    won = sum(r.won for r in rounds)
    return {"rounds": len(rounds), "round_win_pct": pct(won, len(rounds)),
            "round_win_ci95": wilson(won, len(rounds))}


def economy_section(rounds: list[RoundRecord]) -> dict:
    by_buy = {b: summarize_rounds([r for r in rounds if r.buy == b])
              for b in ("pistol", "eco", "force", "full")}
    by_buy = {b: s for b, s in by_buy.items() if s["rounds"]}

    def matchup(own: set[str], theirs: set[str]) -> dict:
        return _win_rate([r for r in rounds if r.buy in own and r.enemy_buy in theirs])

    return {
        "by_team_buy": by_buy,
        "anti_eco": matchup({"full"}, {"eco", "force"}),
        "full_vs_full": matchup({"full"}, {"full"}),
        "upsets": matchup({"eco", "force"}, {"full"}),
        "my_buy_vs_team": {
            "i_saved_team_bought": _win_rate([r for r in rounds if r.buy == "full" and r.my_buy == "eco"]),
            "i_bought_team_saved": _win_rate([r for r in rounds if r.buy == "eco" and r.my_buy == "full"]),
            "in_sync": _win_rate([r for r in rounds if r.buy == r.my_buy and r.buy in ("eco", "force", "full")]),
        },
        "thresholds": f"avg loadout: eco <{ECO_MAX}, force <{FULL_MIN}, full ≥{FULL_MIN} (includes abilities)",
    }


def positioning_section(rounds: list[RoundRecord], top: int = 4) -> dict:
    """Where the player dies, per map and side."""
    out: dict[str, dict] = {}
    groups: dict[tuple, list[RoundRecord]] = defaultdict(list)
    for r in rounds:
        groups[(r.map, r.side)].append(r)
    for (map_name, side), subset in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        deaths = [r for r in subset if r.died]
        if not deaths or side is None:
            continue
        zones = Counter(r.death_zone or "unknown" for r in deaths)
        first = Counter(r.death_zone or "unknown" for r in deaths if r.first_death)
        out.setdefault(map_name, {})[side] = {
            "rounds": len(subset),
            "deaths": len(deaths),
            "top_death_zones": {z: f"{c} ({pct(c, len(deaths)):.0f}%)" for z, c in zones.most_common(top)},
            "first_death_zones": dict(first.most_common(3)),
            "untraded_pct": pct(sum(not r.traded_death for r in deaths), len(deaths)),
            "isolated_pct": pct(sum(r.isolated_death for r in deaths), len(deaths)),
        }
    return out


def weapons_section(rounds: list[RoundRecord], top: int = 8) -> dict:
    kills = Counter(w for r in rounds for w in r.kill_weapons)
    total = sum(kills.values())
    held: dict[str, list[RoundRecord]] = defaultdict(list)
    for r in rounds:
        if r.weapon:
            held[r.weapon].append(r)
    by_held = {}
    for weapon, subset in sorted(held.items(), key=lambda kv: -len(kv[1]))[:top]:
        shots = sum(r.headshots + r.bodyshots + r.legshots for r in subset)
        by_held[weapon] = {
            "rounds": len(subset),
            "round_win_pct": pct(sum(r.won for r in subset), len(subset)),
            "kills_per_round": avg(sum(r.kills for r in subset), len(subset)),
            "hs_pct": pct(sum(r.headshots for r in subset), shots),
        }
    distances: dict[str, list[float]] = defaultdict(list)
    for r in rounds:
        for weapon, d in r.kill_distances:
            distances[weapon].append(d)
    kill_ranges = Counter(range_bucket(d) for r in rounds for _, d in r.kill_distances)
    death_ranges = Counter(range_bucket(r.killer_distance) for r in rounds if r.killer_distance is not None)
    return {
        "kills_by_weapon": {w: f"{c} ({pct(c, total):.0f}%)" for w, c in kills.most_common(top)},
        "median_kill_distance_m": {w: median_m(distances[w]) for w, _ in kills.most_common(top)
                                   if distances[w]},
        "engagement_ranges": {
            bucket: {"kills": kill_ranges[bucket], "deaths": death_ranges[bucket],
                     "kd": avg(kill_ranges[bucket], death_ranges[bucket])}
            for bucket in ("close (<10m)", "mid (10-25m)", "long (25m+)")
        },
        "by_primary_weapon_held": by_held,
    }


SECTIONS = ("overview", "sides", "economy", "agents", "maps", "positioning", "weapons", "context")


def build_report(records: list[MatchRecord], sections: list[str] | None = None) -> dict:
    sections = sections or list(SECTIONS)
    rounds = [r for m in records for r in m.rounds]
    report: dict = {}
    if not records:
        report["sample"] = {"matches": 0}
        return report
    report["sample"] = sample_info(records)

    if "overview" in sections:
        report["overview"] = summarize_matches(records)
        report["wins_vs_losses"] = {
            "wins": summarize_matches([m for m in records if m.won], compact=True),
            "losses": summarize_matches([m for m in records if not m.won and not m.draw], compact=True),
        }
    if "sides" in sections:
        report["by_side"] = {s: summarize_rounds([r for r in rounds if r.side == s])
                             for s in ("attack", "defense")}
    if "economy" in sections:
        report["economy"] = economy_section(rounds)
    if "agents" in sections:
        report["by_role"] = {a: summarize_matches(g, compact=True)
                             for a, g in group_by(records, lambda m: m.role).items()}
        report["by_agent"] = {a: summarize_matches(g, compact=True)
                              for a, g in group_by(records, lambda m: m.agent).items()}
    if "maps" in sections:
        report["by_map"] = {a: summarize_matches(g, compact=True)
                            for a, g in group_by(records, lambda m: m.map).items()}
    if "positioning" in sections:
        report["death_positions"] = positioning_section(rounds)
    if "weapons" in sections:
        report["weapons"] = weapons_section(rounds)
    if "context" in sections:
        report["by_party"] = {p: summarize_matches(g, compact=True)
                              for p, g in group_by(records, lambda m: party_label(m.party_size)).items()}
        report["by_lobby_strength"] = {k: summarize_matches(g, compact=True)
                                       for k, g in group_by(records, lobby_label).items()}
        report["by_game_in_session"] = {
            k: summarize_matches(g, compact=True)
            for k, g in sorted(group_by(records, lambda m: _session_bucket(m.session_game)).items())
        }
    return report


def sample_info(records: list[MatchRecord]) -> dict:
    return {
        "matches": len(records),
        "rounds": sum(len(m.rounds) for m in records),
        "from": min(m.started_at for m in records).date().isoformat(),
        "to": max(m.started_at for m in records).date().isoformat(),
        "ranks_seen": sorted({m.rank for m in records}),
    }


def _session_bucket(n: int) -> str:
    return "game 1-2" if n <= 2 else ("game 3-4" if n <= 4 else "game 5+")


COMPARE_KEYS = ("win_pct", "acs", "kd", "adr", "hs_pct", "kast_pct")


def compare(a: list[MatchRecord], b: list[MatchRecord], label_a: str, label_b: str) -> dict:
    ra = [r for m in a for r in m.rounds]
    rb = [r for m in b for r in m.rounds]
    sa, sb = summarize_matches(a), summarize_matches(b)
    rows: dict[str, dict] = {}
    for key in COMPARE_KEYS:
        rows[key] = {label_a: sa.get(key), label_b: sb.get(key)}
    rows["win_pct"].update({f"{label_a}_ci95": sa.get("win_ci95"), f"{label_b}_ci95": sb.get("win_ci95")})
    for group, sub in (("opening_duels", ("first_kill_rate_pct", "first_death_rate_pct", "opening_win_pct")),
                       ("trading", ("my_deaths_traded_pct", "isolated_death_pct", "early_death_pct"))):
        for key in sub:
            rows[key] = {label_a: sa[group][key] if group in sa else None,
                         label_b: sb[group][key] if group in sb else None}
    for side in ("attack", "defense"):
        rows[f"{side}_round_win_pct"] = {
            label_a: summarize_rounds([r for r in ra if r.side == side])["round_win_pct"],
            label_b: summarize_rounds([r for r in rb if r.side == side])["round_win_pct"],
        }
    for row in rows.values():
        va, vb = row[label_a], row[label_b]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            row["delta"] = round(va - vb, 2)
    return {
        label_a: {"matches": len(a), "agents": dict(Counter(m.agent for m in a).most_common(3)),
                  "maps": dict(Counter(m.map for m in a).most_common(3))},
        label_b: {"matches": len(b), "agents": dict(Counter(m.agent for m in b).most_common(3)),
                  "maps": dict(Counter(m.map for m in b).most_common(3))},
        "metrics": rows,
        "note": "win_pct ranges are 95% confidence intervals; overlapping ranges mean the change may be noise.",
    }


def match_line(m: MatchRecord) -> dict:
    """One compact row per match for history listings."""
    rounds = m.rounds
    shots = m.headshots + m.bodyshots + m.legshots
    return {
        "match_id": m.match_id,
        "date": m.started_at.strftime("%Y-%m-%d %H:%M UTC"),
        "map": m.map,
        "agent": m.agent,
        "result": m.result,
        "score": f"{m.rounds_won}-{m.rounds_lost}",
        "kda": f"{m.kills}/{m.deaths}/{m.assists}",
        "acs": round(m.acs),
        "adr": round(m.damage / m.rounds_played),
        "hs_pct": pct(m.headshots, shots),
        "kast_pct": pct(sum(r.kast for r in rounds), len(rounds)),
        "fk_fd": f"{sum(r.first_kill for r in rounds)}/{sum(r.first_death for r in rounds)}",
        "team_acs_rank": m.team_acs_rank,
        "party": party_label(m.party_size),
        "rank": m.rank,
        **({"grade": m.grade} if m.grade else {}),
    }
