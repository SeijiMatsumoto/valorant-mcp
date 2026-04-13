from typing import Literal

from mcp.server.fastmcp import FastMCP

from valorant_mcp.models import PlayerInfo
from valorant_mcp.henrik import HenrikClient
from valorant_mcp.config import My_Settings
from valorant_mcp.stats import format_match_history, format_match_details, format_match_narrative, compute_agent_stats, compute_map_stats, compute_weapon_stats

mcp = FastMCP(
    "valorant-analyze",
    instructions="""When presenting player stats, focus on each player's strengths and contributions to the team.
Never label anyone as the 'weakest link', 'worst performer', 'liability', or similar negative framing.
Players have different roles — a sentinel with fewer kills is still contributing with site holds and utility.
Present stats objectively and highlight what each player does well.""",
)

settings = My_Settings()
henrik_client = HenrikClient(settings.henrik_api_key)

@mcp.tool(
    name="get_player_info",
    description="Fetch basic account info for a given Riot ID"
)
async def get_player_info(username: str) -> PlayerInfo:
    return await henrik_client.get_player_info(username)

@mcp.tool(
    name="get_match_history",
    description="Fetch recent match history for a player. Returns a readable summary of each match including the player's stats, teammates, and opponents. Mode defaults to competitive but can be changed to unrated, deathmatch, swiftplay, spikerush, or premier."
)
async def get_match_history(username: str, count: int = 5, mode: str = "competitive", region: str = "na") -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 10)
    matches = await henrik_client.get_match_history(username, region, count, mode)
    return format_match_history(matches, name, tag)

@mcp.tool(
    name="get_rank_progression",
    description="Get a player's current rank, elo, MMR change from last game, peak rank, and season-by-season rank history"
)
async def get_rank_progression(username: str, region: str = "na") -> str:
    mmr = await henrik_client.get_mmr(username, region)
    return str(mmr)

@mcp.tool(
    name="get_agent_stats",
    description="Get aggregated per-agent stats from a player's recent matches: games played, wins, losses, win rate, avg kills/deaths/assists/score"
)
async def get_agent_stats(username: str, count: int = 20, mode: str = "competitive", region: str = "na") -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 10)
    matches = await henrik_client.get_match_history(username, region, count, mode)
    return compute_agent_stats(matches, name, tag)

@mcp.tool(
    name="get_map_stats",
    description="Get aggregated per-map stats from a player's recent matches: games played, wins, losses, win rate, avg score"
)
async def get_map_stats(username: str, count: int = 20, mode: str = "competitive", region: str = "na") -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 10)
    matches = await henrik_client.get_match_history(username, region, count, mode)
    return compute_map_stats(matches, name, tag)

@mcp.tool(
    name="get_weapon_stats",
    description="Get weapon usage stats from a player's recent matches: kills per weapon, usage percentage. Shows which guns and abilities a player gets the most kills with."
)
async def get_weapon_stats(username: str, count: int = 5, mode: str = "competitive", region: str = "na") -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 5)
    matches = await henrik_client.get_match_history(username, region, count, mode)
    v4_matches = []
    for match in matches:
        v4 = await henrik_client.get_match(region, match.metadata.matchid)
        v4_matches.append(v4)
    return compute_weapon_stats(v4_matches, name, tag)

@mcp.tool(
    name="get_match_details",
    description=(
        "Get full details of a specific match by match ID. "
        "`view=summary` (default): per-player stats, team totals, kill list, round results, economy — best for stat or aggregate questions. "
        "`view=narrative`: round-by-round event timeline with attack/defense sides labeled, named map zones (A Site, Mid, B Long, etc.), "
        "and event tags (entry, first_blood, trade, rotation) — best for story/spatial questions like 'which round did we rotate from B to A' "
        "or 'where do we usually die on attack'."
    )
)
async def get_match_details(
    match_id: str,
    region: str = "na",
    view: Literal["summary", "narrative"] = "summary",
) -> str:
    match = await henrik_client.get_match(region, match_id)
    if view == "narrative":
        return await format_match_narrative(match)
    return format_match_details(match)

def main():
    mcp.run()

if __name__ == "__main__":
    mcp.run()
