from datetime import date
from pydantic import BaseModel

class PlayerInfo(BaseModel):
    puuid: str
    region: str
    account_level: int
    name: str
    tag: str

class PlayerStats(BaseModel):
    score: int
    kills: int
    deaths: int
    assists: int
    headshots: int
    bodyshots: int
    legshots: int

class EconomySpent(BaseModel):
    overall: int
    average: float

class EconomyLoadout(BaseModel):
    overall: int
    average: float

class PlayerEconomy(BaseModel):
    spent: EconomySpent
    loadout_value: EconomyLoadout

class MatchPlayer(BaseModel):
    name: str
    tag: str
    character: str
    team: str
    currenttier_patched: str
    stats: PlayerStats
    economy: PlayerEconomy
    damage_made: int
    damage_received: int

class TeamResult(BaseModel):
    has_won: bool
    rounds_won: int
    rounds_lost: int

class MatchMetadata(BaseModel):
    map: str
    game_start_patched: str
    matchid: str

class MatchData(BaseModel):
    metadata: MatchMetadata
    players: dict[str, list[MatchPlayer]]
    teams: dict[str, TeamResult]

class V4Map(BaseModel):
    id: str
    name: str

class V4Agent(BaseModel):
    id: str
    name: str

class V4Tier(BaseModel):
    id: int
    name: str

class V4Damage(BaseModel):
    dealt: int
    received: int

class V4PlayerStats(BaseModel):
    score: int
    kills: int
    deaths: int
    assists: int
    headshots: int
    bodyshots: int
    legshots: int
    damage: V4Damage

class V4MatchPlayer(BaseModel):
    name: str
    tag: str
    team_id: str
    agent: V4Agent
    stats: V4PlayerStats
    tier: V4Tier
    economy: PlayerEconomy

class V4Rounds(BaseModel):
    won: int
    lost: int

class V4Team(BaseModel):
    team_id: str
    rounds: V4Rounds
    won: bool

class V4MatchMetadata(BaseModel):
    match_id: str
    map: V4Map
    started_at: str
    region: str

class V4Location(BaseModel):
    x: int
    y: int

class V4PlayerRef(BaseModel):
    puuid: str
    name: str
    tag: str
    team: str

class V4Weapon(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None

class V4Kill(BaseModel):
    time_in_round_in_ms: int
    time_in_match_in_ms: int
    round: int
    killer: V4PlayerRef
    victim: V4PlayerRef
    assistants: list[V4PlayerRef]
    location: V4Location
    weapon: V4Weapon
    secondary_fire_mode: bool

class V4PlantDefuse(BaseModel):
    round_time_in_ms: int
    site: str | None = None
    location: V4Location
    player: V4PlayerRef

class V4RoundPlayerStats(BaseModel):
    score: int
    kills: int
    headshots: int
    bodyshots: int
    legshots: int

class V4Armor(BaseModel):
    id: str
    name: str

class V4RoundEconomy(BaseModel):
    loadout_value: int
    remaining: int
    weapon: V4Weapon | None = None
    armor: V4Armor | None = None

class V4RoundStat(BaseModel):
    player: V4PlayerRef
    stats: V4RoundPlayerStats
    economy: V4RoundEconomy
    was_afk: bool
    stayed_in_spawn: bool

class V4Round(BaseModel):
    id: int
    result: str
    ceremony: str
    winning_team: str
    plant: V4PlantDefuse | None = None
    defuse: V4PlantDefuse | None = None
    stats: list[V4RoundStat]

class V4MatchData(BaseModel):
    metadata: V4MatchMetadata
    players: list[V4MatchPlayer]
    teams: list[V4Team]
    kills: list[V4Kill]
    rounds: list[V4Round]

class CurrentMMR(BaseModel):                                                                        
    currenttierpatched: str
    ranking_in_tier: int                                                                            
    mmr_change_to_last_game: int                                
    elo: int                                                                                        
                                                                
class SeasonData(BaseModel):                                    
    wins: int
    number_of_games: int
    final_rank_patched: str                                                                         

class MMRData(BaseModel):                                                                         
    name: str                                                                                       
    tag: str                                                                                      
    current_data: CurrentMMR
    highest_rank: dict
    by_season: dict[str, SeasonData | dict]