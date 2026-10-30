import json
import logging
from dataclasses import dataclass
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from valorant_mcp import agents, callouts
from valorant_mcp.analysis import (
    SECTIONS,
    MatchRecord,
    analyze_all_players,
    analyze_matches,
    build_report,
    compare,
    match_line,
)
from valorant_mcp.cache import MatchCache
from valorant_mcp.config import Settings
from valorant_mcp.glossary import GLOSSARY
from valorant_mcp.henrik import HenrikClient, parse_username
from valorant_mcp.insights import build_benchmarks, build_sites, build_teamplay
from valorant_mcp.models import Match
from valorant_mcp.stats import format_match_details, format_match_narrative

mcp = FastMCP(
    "valorant-analyze",
    instructions="""Tools for analyzing a Valorant player's matches via Henrik's API.
Usernames are Riot IDs like name#TAG.

Which tool to use:
- get_performance_report: the broad picture — what the player's numbers are and where the patterns are.
- get_benchmarks: whether those numbers are good or bad, compared with the other players in the
  same lobbies (same rank), the same role, and others on the same agent (incl. utility usage).
- get_teamplay_report: spacing and trading — isolated deaths, missed trade chances, duo partners.
- get_site_report: team site choices, post-plant and retake results per map.
- compare_periods: what changed recently. get_rr_history: which games gained/lost RR.
- get_match_history / get_match_details: find and drill into specific games as evidence.
Metric definitions are in the resource valorant://glossary.

Interpreting data:
- *_ci95 fields are 95% confidence ranges. If two ranges overlap heavily, the difference may be
  noise — say so. Buckets marked low_sample are anecdotes, not patterns.
- Prefer benchmarks over absolute numbers when judging good vs bad.
- Round numbers in outputs are 1-indexed. Distances are in metres.

Tone: when presenting stats, focus on each player's strengths and contributions.
Never label anyone as the 'weakest link', 'worst performer', 'liability', or similar.
Players have different roles — a sentinel with fewer kills is still contributing with site holds and utility.
Present stats objectively and make improvement advice specific and actionable.""",
)

logging.getLogger("httpx").setLevel(logging.WARNING)

settings = Settings()
henrik_client = HenrikClient(
    settings.henrik_api_key,
    base_url=settings.henrik_base_url,
    region=settings.valorant_region,
    platform=settings.valorant_platform,
    cache=MatchCache(settings.cache_dir),
)

MAX_MATCHES = 50

Username = Annotated[str, Field(description="Riot ID as name#TAG, e.g. 'player#NA1'")]
Count = Annotated[int, Field(description="Number of recent matches to analyze (max 50)", ge=1, le=MAX_MATCHES)]
Mode = Annotated[Literal["competitive", "unrated", "premier", "swiftplay", "spikerush"],
                 Field(description="Queue to analyze")]
MapFilter = Annotated[str | None, Field(description="Only matches on this map, e.g. 'Ascent'")]
AgentFilter = Annotated[str | None, Field(
    description="Only matches on this agent, e.g. 'Sova'. Fetches extra history to fill `count`.")]
Region = Annotated[str | None, Field(description="na, eu, ap, kr, latam or br. Defaults to the server setting.")]


def _dump(data) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False)


def _puuid_from_matches(matches: list[Match], username: str) -> str | None:
    name, tag = parse_username(username)
    target = (name.casefold(), tag.casefold())
    for match in matches:
        for p in match.players:
            if (p.name.casefold(), p.tag.casefold()) == target:
                return p.puuid
    return None


@dataclass
class Loaded:
    matches: list[Match]
    records: list[MatchRecord]


async def _load(username: str, count: int, mode: str, map_name: str | None,
                agent: str | None, region: str | None) -> Loaded:
    count = max(1, min(count, MAX_MATCHES))
    # Agent filtering happens after fetching, so pull extra history to fill `count`.
    fetch = min(MAX_MATCHES, count * 3) if agent else count
    matches = await henrik_client.get_matches(username, fetch, mode, map_name, region)
    if not matches:
        return Loaded([], [])
    puuid = _puuid_from_matches(matches, username) or (await henrik_client.get_account(username)).puuid
    await callouts.ensure_loaded({m.metadata.map.name for m in matches})
    await agents.ensure_loaded({p.agent.name for m in matches for p in m.players})
    records = analyze_matches(matches, puuid)
    if agent:
        records = [r for r in records if r.agent.casefold() == agent.casefold()]
    records = sorted(records, key=lambda r: r.started_at, reverse=True)[:count]
    keep = {r.match_id for r in records}
    return Loaded([m for m in matches if m.metadata.match_id in keep], records)


async def _player_records(username: str, count: int, mode: str, map_name: str | None,
                          agent: str | None, region: str | None) -> list[MatchRecord]:
    return (await _load(username, count, mode, map_name, agent, region)).records


@mcp.tool()
async def get_player_profile(username: Username, region: Region = None) -> str:
    """Account info plus ranked state: current rank/RR/elo, last RR change, peak rank,
    rank protection, and season-by-season results."""
    account = await henrik_client.get_account(username)
    mmr = await henrik_client.get_mmr(username, region)
    return _dump({
        "name": f"{account.name}#{account.tag}",
        "puuid": account.puuid,
        "region": account.region,
        "account_level": account.account_level,
        "current": {
            "rank": mmr.current.tier.name,
            "rr": mmr.current.rr,
            "elo": mmr.current.elo,
            "last_change": mmr.current.last_change,
            "rank_protection": mmr.current.rank_protection_status,
            "games_needed_for_rating": mmr.current.games_needed_for_rating,
        },
        "peak": {"rank": mmr.peak.tier.name, "season": mmr.peak.season.short} if mmr.peak else None,
        "seasons": [
            {"season": s.season.short, "games": s.games, "wins": s.wins,
             "win_pct": round(100 * s.wins / s.games, 1) if s.games else None,
             "end_rank": s.end_tier.name}
            for s in mmr.seasonal[-8:] if s.games
        ],
    })


@mcp.tool()
async def get_performance_report(
    username: Username,
    count: Count = 20,
    mode: Mode = "competitive",
    map: MapFilter = None,
    agent: AgentFilter = None,
    sections: Annotated[list[Literal["overview", "sides", "economy", "agents", "maps",
                                     "positioning", "weapons", "context"]] | None,
                        Field(description="Subset of sections to return; omit for all")] = None,
    region: Region = None,
) -> str:
    """Broad analysis of a player's recent matches. Start here for "how am I doing / what are my
    patterns". Sections:
    - overview: win rate (with 95% range), ACS, K/D, ADR, HS%, KAST, opening duels (first kill/death
      rates, round win % after each), trading (deaths traded, isolated/early deaths), damage
      conversion, clutches (1v1, 1v2, 1v3+), multikills, and personal stats in wins vs losses
    - sides: attack vs defense round win %, KAST, survival
    - economy: round win % by team buy (pistol/eco/force/full), anti-eco, upsets, and rounds where
      your own buy didn't match the team's
    - agents / maps: per-role, per-agent and per-map results incl. attack/defense round win %
    - positioning: where you die per map and side (named callouts), first-death zones, isolated %
    - weapons: kills by weapon, median kill distance, K/D by engagement range, results by weapon held
    - context: solo vs party, lobby strength (enemy rank vs yours), game number within a session
    Numbers are absolute; use get_benchmarks to judge them against same-rank players."""
    records = await _player_records(username, count, mode, map, agent, region)
    report = {"player": username, "filters": {"mode": mode, "map": map, "agent": agent}}
    report.update(build_report(records, list(sections) if sections else list(SECTIONS)))
    return _dump(report)


@mcp.tool()
async def compare_periods(
    username: Username,
    recent: Annotated[int, Field(description="Size of the recent block", ge=1, le=25)] = 10,
    previous: Annotated[int, Field(description="Size of the block before it", ge=1, le=25)] = 10,
    mode: Mode = "competitive",
    agent: AgentFilter = None,
    region: Region = None,
) -> str:
    """Compare the most recent `recent` matches against the `previous` block before them.
    Shows key metrics side by side with deltas — use it to answer "what changed?" or
    "am I improving?". Also lists the agents/maps played in each block. Check the win_pct
    confidence ranges before calling a change real."""
    records = await _player_records(username, recent + previous, mode, None, agent, region)
    return _dump(compare(records[:recent], records[recent:recent + previous],
                         f"last_{recent}", f"previous_{previous}"))


@mcp.tool()
async def get_rr_history(username: Username, count: Count = 20, region: Region = None) -> str:
    """Competitive RR change per match, joined with how the player performed in that match
    (agent, KDA, ACS, KAST, first kills/deaths). Use it to see which kinds of games
    gain or lose RR, and RR performance bonuses/penalties."""
    count = max(1, min(count, MAX_MATCHES))
    history = await henrik_client.get_mmr_history(username, count, region)
    records = {r.match_id: r for r in await _player_records(username, count, "competitive",
                                                             None, None, region)}
    rows = []
    for e in history:
        row = {
            "date": e.date[:10],
            "map": e.map.name,
            "rr_change": e.last_change,
            "rank_after": f"{e.tier.name} {e.rr}RR",
        }
        if e.rr_performance_bonus:
            row["performance_bonus"] = e.rr_performance_bonus
        if e.was_derank_protected:
            row["derank_protected"] = True
        if (rec := records.get(e.match_id)):
            line = match_line(rec)
            row.update({k: line[k] for k in ("agent", "result", "score", "kda", "acs", "kast_pct",
                                             "fk_fd", "team_acs_rank", "party")})
        rows.append(row)
    total = sum(e.last_change for e in history)
    return _dump({"net_rr": total, "matches": len(history), "history": rows})


@mcp.tool()
async def get_match_history(
    username: Username,
    count: Count = 10,
    mode: Mode = "competitive",
    map: MapFilter = None,
    agent: AgentFilter = None,
    region: Region = None,
) -> str:
    """List recent matches (max 50), one compact row each: map, agent, result, score, KDA,
    ACS, ADR, HS%, KAST, first kills/deaths, ACS rank on team, party size. Use the
    match_id with get_match_details to drill in."""
    records = await _player_records(username, count, mode, map, agent, region)
    return _dump([match_line(r) for r in records])


@mcp.tool()
async def get_match_details(
    match_id: Annotated[str, Field(description="match_id from get_match_history or other tools")],
    view: Literal["summary", "narrative"] = "summary",
    focus_username: Annotated[str | None, Field(description="Riot ID to mark as (YOU) in the narrative")] = None,
    rounds: Annotated[list[int] | None, Field(description="1-indexed rounds to include in the narrative")] = None,
    region: Region = None,
) -> str:
    """Full details of one match.
    `summary` (default): per-player stats (ACS, ADR, KAST, first kills/deaths, trades,
    multikills, clutches), plus per-round sides, team buys, first blood, plant/defuse and kills.
    `narrative`: round-by-round timeline with named map zones (A Site, Mid, B Long, ...) and
    tags (first_blood, trade, rotation) — best for spatial/story questions like "where do
    we die on attack". Pass `focus_username` to mark that player as (YOU) in the narrative,
    and `rounds` (1-indexed) to limit the narrative to specific rounds — it is long otherwise."""
    match = await henrik_client.get_match(match_id, region)
    if view == "narrative":
        focus = _puuid_from_matches([match], focus_username) if focus_username else None
        return await format_match_narrative(match, focus, rounds)
    return await format_match_details(match)


@mcp.tool()
async def get_benchmarks(
    username: Username,
    count: Count = 20,
    mode: Mode = "competitive",
    map: MapFilter = None,
    agent: AgentFilter = None,
    region: Region = None,
) -> str:
    """Judge whether the player's numbers are good or bad by comparing them with the other 9
    players in the same matches (so rank is controlled for):
    - vs_lobby: per-round metrics for you vs players in the same role that match vs the whole lobby
      (ACS, ADR, KAST, opening duels, deaths traded, trade-chance conversion, isolated deaths,
      teammate distance at death, survival, utility casts per round)
    - avg_place_in_lobby_of_10: your average placement among all 10 players (1 = best)
    - by_agent: for each agent played 2+ times, you vs everyone else on that agent in your lobbies,
      incl. casts per round of each ability and Henrik's performance breakdown/ratings when available"""
    loaded = await _load(username, count, mode, map, agent, region)
    everyone = {m.metadata.match_id: analyze_all_players(m) for m in loaded.matches}
    return _dump({"player": username, **build_benchmarks(loaded.records, everyone)})


@mcp.tool()
async def get_teamplay_report(
    username: Username,
    count: Count = 20,
    mode: Mode = "competitive",
    map: MapFilter = None,
    agent: AgentFilter = None,
    region: Region = None,
) -> str:
    """Spacing and trading, from every player's position at each kill:
    - how far your nearest teammate was when you died; deaths split into close (<15m), loose
      (15-25m) and isolated (>25m), with how often each got traded
    - trade chances: teammate died within 15m of you while you were alive, and how often you
      killed their killer within 5s
    - the map/side/callout spots where you most often die isolated and untraded
    - results by party size and win rate with each party member
    Use for "why do I die alone", "am I trading my teammates", "who should I queue with"."""
    records = await _player_records(username, count, mode, map, agent, region)
    return _dump({"player": username, **build_teamplay(records)})


@mcp.tool()
async def get_site_report(
    username: Username,
    count: Count = 20,
    mode: Mode = "competitive",
    map: MapFilter = None,
    region: Region = None,
) -> str:
    """Team-level site play per map: on attack, plant rate, which site you plant and the
    post-plant win % on each; on defense, which site the enemy plants and your retake/hold win %;
    plus win % in rounds with no plant. Use for "which site should we hit on Bind" or
    "are we bad at retakes"."""
    records = await _player_records(username, count, mode, map, None, region)
    return _dump({"player": username, **build_sites(records)})


@mcp.resource("valorant://glossary", mime_type="text/markdown")
def glossary() -> str:
    """Definitions of every metric these tools return."""
    return GLOSSARY


@mcp.prompt()
def coach_review(username: str, count: str = "20") -> str:
    """Structured coaching review of a player's recent games: what to keep, change, and try."""
    return f"""Act as a Valorant coach reviewing {username}'s recent games.

1. Call get_player_profile for rank context.
2. Call get_performance_report for {username} with count={count}.
3. Call get_benchmarks to see which numbers are actually above or below same-rank players.
4. Call get_teamplay_report, and get_site_report if site play looks like a factor.
5. Call compare_periods to see the recent trend.
6. If a pattern needs evidence, pull one or two representative matches with
   get_match_details (narrative view, focus_username={username}, only the relevant rounds).

Then write the review with these sections:
- **Keep doing**: 2-3 strengths backed by specific numbers.
- **Change**: the 2-3 highest-impact problems. For each: the evidence (numbers, sample size),
  why it costs rounds, and one concrete in-game habit to fix it.
- **Experiment**: 1-2 things to try next session (agent, role, buy discipline, positioning)
  with how to tell if it's working.

Judge good vs bad from the benchmarks, not gut feel. Ignore buckets marked low_sample unless
several point the same way, and use the *_ci95 ranges to avoid overstating small differences."""


def main():
    mcp.run()


if __name__ == "__main__":
    main()
