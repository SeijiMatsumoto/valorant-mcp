import os

import pytest
from pydantic import ValidationError

from valorant_mcp import agents, callouts
from valorant_mcp.config import Settings

# server.py builds Settings at import time. Without a real key (env or .env), use a dummy so the
# offline tests can import it; they mock all HTTP. A real key is left alone for the live tests.
try:
    Settings()
except ValidationError:
    os.environ["HENRIK_API_KEY"] = "test-key"
from valorant_mcp.models import (
    AbilityCasts,
    Damage,
    EconomyTotal,
    IdName,
    Kill,
    Location,
    Match,
    MatchMetadata,
    MatchPlayer,
    PlantDefuse,
    PlayerEconomy,
    PlayerLocation,
    PlayerRef,
    PlayerStats,
    Queue,
    Round,
    RoundEconomy,
    RoundPlayerStats,
    RoundPlayerStatsStats,
    SeasonRef,
    Team,
    TeamRounds,
    TierRef,
    Weapon,
)

ME = "me"
RED = ["me", "r2", "r3", "r4", "r5"]
BLUE = ["b1", "b2", "b3", "b4", "b5"]


@pytest.fixture(autouse=True)
def no_content_download(monkeypatch):
    # Empty callout table (zones resolve to None) and a tiny agent table; nothing is fetched.
    monkeypatch.setattr(callouts, "_cache", {})
    monkeypatch.setattr(callouts, "_refreshed", True)
    monkeypatch.setattr(agents, "_cache", {
        "jett": {"role": "Duelist", "abilities": {"grenade": "Cloudburst", "ability1": "Updraft",
                                                   "ability2": "Tailwind", "ultimate": "Blade Storm"}},
        "sova": {"role": "Initiator", "abilities": {}},
    })
    monkeypatch.setattr(agents, "_refreshed", True)


def team_of(puuid: str) -> str:
    return "Red" if puuid in RED else "Blue"


def ref(puuid: str) -> PlayerRef:
    return PlayerRef(puuid=puuid, name=puuid, tag="NA1", team=team_of(puuid))


def make_player(puuid: str, agent="Jett", party_id=None, score=4000, kills=15, deaths=15,
                assists=5, headshots=10, bodyshots=30, legshots=2, dealt=3000, tier=13, casts=None):
    return MatchPlayer(
        puuid=puuid, name=puuid, tag="NA1", team_id=team_of(puuid),
        party_id=party_id or f"party-{puuid}",
        agent=IdName(id=agent.lower(), name=agent),
        stats=PlayerStats(score=score, kills=kills, deaths=deaths, assists=assists,
                          headshots=headshots, bodyshots=bodyshots, legshots=legshots,
                          damage=Damage(dealt=dealt, received=2500)),
        tier=TierRef(id=tier, name=f"Tier {tier}"),
        ability_casts=AbilityCasts(**(casts or {"grenade": 10, "ability1": 5, "ability2": 5, "ultimate": 1})),
        economy=PlayerEconomy(spent=EconomyTotal(overall=50000, average=2500.0),
                              loadout_value=EconomyTotal(overall=70000, average=3500.0)),
    )


def make_kill(round_id: int, t_ms: int, killer: str, victim: str, weapon="Vandal",
              assistants: tuple[str, ...] = (), at: tuple[int, int] = (0, 0),
              positions: dict[str, tuple[int, int]] | None = None):
    """`at` is where the victim died; `positions` are living players' (x, y) at that moment."""
    return Kill(
        time_in_round_in_ms=t_ms, time_in_match_in_ms=round_id * 100000 + t_ms, round=round_id,
        killer=ref(killer), victim=ref(victim), assistants=[ref(a) for a in assistants],
        location=Location(x=at[0], y=at[1]), weapon=Weapon(name=weapon),
        player_locations=[PlayerLocation(player=ref(pid), location=Location(x=x, y=y))
                          for pid, (x, y) in (positions or {}).items()],
    )


def make_round(round_id: int, winner: str, planter: str | None = None, role: str | None = None,
               red_loadout=4500, blue_loadout=4500, my_damage=0, my_loadout=None, site="A"):
    stats = []
    for pid in RED + BLUE:
        stats.append(RoundPlayerStats(
            player=ref(pid),
            stats=RoundPlayerStatsStats(score=0, kills=0, headshots=1, bodyshots=2, legshots=0),
            economy=RoundEconomy(loadout_value=(my_loadout if pid == ME and my_loadout is not None
                                                else red_loadout if pid in RED else blue_loadout),
                                 remaining=0, weapon=Weapon(name="Vandal")),
            damage_events=[{"player": ref("b1"), "damage": my_damage, "headshots": 0,
                            "bodyshots": 1, "legshots": 0}] if pid == ME and my_damage else [],
        ))
    plant = PlantDefuse(round_time_in_ms=30000, site=site, location=Location(x=0, y=0),
                        player=ref(planter)) if planter else None
    return Round(id=round_id, result="Elimination", winning_team=winner,
                 winning_team_role=role, plant=plant, stats=stats)


def make_match(rounds: list[Round], kills: list[Kill] | None = None, players=None,
               match_id="m1", started_at="2026-10-01T20:00:00Z", map_name="Ascent",
               queue="competitive", season="e11a6"):
    players = players or [make_player(p) for p in RED + BLUE]
    red_won = sum(r.winning_team == "Red" for r in rounds)
    blue_won = len(rounds) - red_won
    return Match(
        metadata=MatchMetadata(match_id=match_id, map=IdName(id="map", name=map_name),
                               started_at=started_at, queue=Queue(id=queue),
                               season=SeasonRef(id=season, short=season)),
        players=players,
        teams=[Team(team_id="Red", rounds=TeamRounds(won=red_won, lost=blue_won), won=red_won > blue_won),
               Team(team_id="Blue", rounds=TeamRounds(won=blue_won, lost=red_won), won=blue_won > red_won)],
        rounds=rounds,
        kills=kills or [],
    )
