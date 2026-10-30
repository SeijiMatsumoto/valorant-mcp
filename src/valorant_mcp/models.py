from pydantic import BaseModel

# Models mirror Henrik's v4 schema (https://api.henrikdev.xyz/openapi.json).
# Fields added in 4.10 are optional: prod often returns them as null.


class IdName(BaseModel):
    id: str | None = None
    name: str | None = None


class TierRef(BaseModel):
    id: int
    name: str


class SeasonRef(BaseModel):
    id: str
    short: str | None = None


# --- Account (v2) ---

class Account(BaseModel):
    puuid: str
    region: str
    account_level: int
    name: str
    tag: str
    platforms: list[str] = []


# --- Match (v4) ---

class Location(BaseModel):
    x: int
    y: int


class PlayerRef(BaseModel):
    puuid: str
    name: str
    tag: str
    team: str


class PlayerLocation(BaseModel):
    player: PlayerRef
    view_radians: float | None = None
    location: Location


class Weapon(BaseModel):
    id: str | None = None
    name: str | None = None
    type: str | None = None


class Damage(BaseModel):
    dealt: int
    received: int


class PlayerStats(BaseModel):
    score: int
    kills: int
    deaths: int
    assists: int
    headshots: int
    bodyshots: int
    legshots: int
    damage: Damage


class EconomyTotal(BaseModel):
    overall: int
    average: float


class PlayerEconomy(BaseModel):
    spent: EconomyTotal
    loadout_value: EconomyTotal


class AbilityCasts(BaseModel):
    grenade: int | None = None
    ability1: int | None = None
    ability2: int | None = None
    ultimate: int | None = None


class CombatRatings(BaseModel):
    damage: str | None = None
    death_impact: str | None = None
    kill_impact: str | None = None
    trades: str | None = None


class UtilityRatings(BaseModel):
    assists: str | None = None
    defuses: str | None = None
    plants: str | None = None
    utility_usage: str | None = None


class PerformanceRatings(BaseModel):
    grade: str | None = None
    combat: CombatRatings | None = None
    utility: UtilityRatings | None = None


class Performance(BaseModel):
    score: float | None = None
    breakdown: dict[str, float | None] = {}
    ratings: PerformanceRatings | None = None


class MatchPlayer(BaseModel):
    puuid: str
    name: str
    tag: str
    team_id: str
    party_id: str | None = None
    agent: IdName
    stats: PlayerStats
    tier: TierRef
    economy: PlayerEconomy
    ability_casts: AbilityCasts | None = None
    session_playtime_in_ms: int | None = None
    performance: Performance | None = None


class TeamRounds(BaseModel):
    won: int
    lost: int


class Team(BaseModel):
    team_id: str
    rounds: TeamRounds
    won: bool
    mvp: PlayerRef | None = None


class Queue(BaseModel):
    id: str | None = None
    name: str | None = None
    mode_type: str | None = None


class MatchMetadata(BaseModel):
    match_id: str
    map: IdName
    started_at: str
    game_length_in_ms: int | None = None
    is_completed: bool = True
    queue: Queue | None = None
    season: SeasonRef | None = None
    region: str | None = None
    mvp: PlayerRef | None = None


class Kill(BaseModel):
    time_in_round_in_ms: int
    time_in_match_in_ms: int
    round: int
    killer: PlayerRef
    victim: PlayerRef
    assistants: list[PlayerRef] = []
    location: Location
    weapon: Weapon
    secondary_fire_mode: bool = False
    player_locations: list[PlayerLocation] = []


class PlantDefuse(BaseModel):
    round_time_in_ms: int
    site: str | None = None
    location: Location
    player: PlayerRef


class DamageEvent(BaseModel):
    player: PlayerRef
    damage: int
    headshots: int
    bodyshots: int
    legshots: int


class RoundPlayerStatsStats(BaseModel):
    score: int
    kills: int
    headshots: int
    bodyshots: int
    legshots: int


class RoundEconomy(BaseModel):
    loadout_value: int
    remaining: int
    weapon: Weapon | None = None
    armor: IdName | None = None


class RoundPlayerStats(BaseModel):
    player: PlayerRef
    stats: RoundPlayerStatsStats
    economy: RoundEconomy
    damage_events: list[DamageEvent] = []
    was_afk: bool = False
    stayed_in_spawn: bool = False


class Round(BaseModel):
    # Round ids are 0-indexed in v4.
    id: int
    result: str
    ceremony: str | None = None
    winning_team: str
    winning_team_role: str | None = None
    first_blood: PlayerRef | None = None
    plant: PlantDefuse | None = None
    defuse: PlantDefuse | None = None
    stats: list[RoundPlayerStats] = []


class Match(BaseModel):
    metadata: MatchMetadata
    players: list[MatchPlayer]
    teams: list[Team]
    rounds: list[Round]
    kills: list[Kill]


# --- MMR (v3) ---

class MMRAccount(BaseModel):
    puuid: str
    name: str
    tag: str


class MMRCurrent(BaseModel):
    tier: TierRef
    rr: int
    last_change: int
    elo: int
    games_needed_for_rating: int = 0
    rank_protection_shields: int | None = None
    rank_protection_status: str | None = None


class MMRPeak(BaseModel):
    season: SeasonRef
    tier: TierRef
    rr: int


class MMRSeason(BaseModel):
    season: SeasonRef
    wins: int
    games: int
    end_tier: TierRef
    end_rr: int


class MMR(BaseModel):
    account: MMRAccount
    current: MMRCurrent
    peak: MMRPeak | None = None
    seasonal: list[MMRSeason] = []


# --- MMR history (v2) ---

class MMRHistoryEntry(BaseModel):
    match_id: str
    date: str
    map: IdName
    season: SeasonRef
    tier: TierRef
    rr: int
    last_change: int
    elo: int
    rr_before_update: int | None = None
    rr_performance_bonus: int | None = None
    rr_penalty: float | None = None
    afk_penalty: int | None = None
    was_derank_protected: bool = False
    is_placement_match: bool | None = None


class MMRHistory(BaseModel):
    account: MMRAccount
    history: list[MMRHistoryEntry]
