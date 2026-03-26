import pytest
from valorant_mcp.models import (
    MatchData, MatchMetadata, MatchPlayer, PlayerStats, PlayerEconomy,
    EconomySpent, EconomyLoadout, TeamResult,
    V4MatchData, V4MatchMetadata, V4MatchPlayer, V4PlayerStats,
    V4Map, V4Agent, V4Tier, V4Team, V4Rounds, V4Damage,
)


def make_player(name="SayGG", tag="11111", character="Jett", team="Red",
                rank="Gold 2", kills=20, deaths=15, assists=5,
                headshots=10, bodyshots=30, legshots=2,
                damage_made=3000, damage_received=2500,
                spent=50000, avg_spent=2500.0,
                loadout=70000, avg_loadout=3500.0):
    return MatchPlayer(
        name=name,
        tag=tag,
        character=character,
        team=team,
        currenttier_patched=rank,
        stats=PlayerStats(
            score=(kills * 200 + assists * 50),
            kills=kills,
            deaths=deaths,
            assists=assists,
            headshots=headshots,
            bodyshots=bodyshots,
            legshots=legshots,
        ),
        economy=PlayerEconomy(
            spent=EconomySpent(overall=spent, average=avg_spent),
            loadout_value=EconomyLoadout(overall=loadout, average=avg_loadout),
        ),
        damage_made=damage_made,
        damage_received=damage_received,
    )


def make_match(players_all, red_won=True, rounds_won=13, rounds_lost=9,
               map_name="Bind", matchid="match-001",
               date="Wednesday, March 25, 2026 03:34 AM"):
    red_players = [p for p in players_all if p.team == "Red"]
    blue_players = [p for p in players_all if p.team == "Blue"]
    return MatchData(
        metadata=MatchMetadata(
            map=map_name,
            game_start_patched=date,
            matchid=matchid,
        ),
        players={
            "all_players": players_all,
            "red": red_players,
            "blue": blue_players,
        },
        teams={
            "red": TeamResult(has_won=red_won, rounds_won=rounds_won, rounds_lost=rounds_lost),
            "blue": TeamResult(has_won=not red_won, rounds_won=rounds_lost, rounds_lost=rounds_won),
        },
    )


def make_v4_player(name="SayGG", tag="11111", team_id="Red",
                   agent_name="Jett", agent_id="add6443a-41bd-e414-f6ad-e58d267f4e95",
                   rank="Gold 2", tier_id=13,
                   kills=20, deaths=15, assists=5,
                   headshots=10, bodyshots=30, legshots=2,
                   damage_dealt=3000, damage_received=2500,
                   spent=50000, avg_spent=2500.0,
                   loadout=70000, avg_loadout=3500.0):
    return V4MatchPlayer(
        name=name,
        tag=tag,
        team_id=team_id,
        agent=V4Agent(id=agent_id, name=agent_name),
        stats=V4PlayerStats(
            score=(kills * 200 + assists * 50),
            kills=kills,
            deaths=deaths,
            assists=assists,
            headshots=headshots,
            bodyshots=bodyshots,
            legshots=legshots,
            damage=V4Damage(dealt=damage_dealt, received=damage_received),
        ),
        tier=V4Tier(id=tier_id, name=rank),
        economy=PlayerEconomy(
            spent=EconomySpent(overall=spent, average=avg_spent),
            loadout_value=EconomyLoadout(overall=loadout, average=avg_loadout),
        ),
    )


def make_v4_match(players, red_won=True, rounds_won=13, rounds_lost=9,
                  map_name="Bind", match_id="match-v4-001",
                  started_at="2026-03-25T03:34:00Z", region="na"):
    return V4MatchData(
        metadata=V4MatchMetadata(
            match_id=match_id,
            map=V4Map(id="map-001", name=map_name),
            started_at=started_at,
            region=region,
        ),
        players=players,
        teams=[
            V4Team(team_id="Red", rounds=V4Rounds(won=rounds_won, lost=rounds_lost), won=red_won),
            V4Team(team_id="Blue", rounds=V4Rounds(won=rounds_lost, lost=rounds_won), won=not red_won),
        ],
    )
