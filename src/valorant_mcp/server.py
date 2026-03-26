from mcp.server.fastmcp import FastMCP

from valorant_mcp.models import PlayerInfo
from valorant_mcp.henrik import HenrikClient
from valorant_mcp.config import My_Settings
from valorant_mcp.stats import format_match_history, format_match_details, compute_agent_stats, compute_map_stats

mcp = FastMCP("valorant-analyze", host="0.0.0.0", port=8080)

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
    description="Fetch recent competitive match history for a player. Returns a readable summary of each match including the player's stats, teammates, and opponents."
)
async def get_match_history(username: str, count: int = 5) -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 10)
    matches = await henrik_client.get_match_history(username, settings.valorant_region, count)
    return format_match_history(matches, name, tag)

@mcp.tool(
    name="get_rank_progression",
    description="Get a player's current rank, elo, MMR change from last game, peak rank, and season-by-season rank history"
)
async def get_rank_progression(username: str) -> str:
    mmr = await henrik_client.get_mmr(username, settings.valorant_region)
    return str(mmr)

@mcp.tool(
    name="get_agent_stats",
    description="Get aggregated per-agent stats from a player's recent matches: games played, wins, losses, win rate, avg kills/deaths/assists/score"
)
async def get_agent_stats(username: str, count: int = 20) -> str:
    name, tag = henrik_client._parse_username(username)
    count = min(count, 10)
    matches = await henrik_client.get_match_history(username, settings.valorant_region, count)
    return compute_agent_stats(matches, name, tag)

@mcp.tool(
    name="get_map_stats",
    description="Get aggregated per-map stats from a player's recent matches: games played, wins, losses, win rate, avg score"
)
async def get_map_stats(username: str, count: int = 20) -> str:
    name, tag = henrik_client._parse_username(username)
    matches = await henrik_client.get_match_history(username, settings.valorant_region, count)
    return compute_map_stats(matches, name, tag)

@mcp.tool(
    name="get_match_details",
    description="Get full details of a specific match by match ID, including all players, stats, and results"
)
async def get_match_details(match_id: str) -> str:
    match = await henrik_client.get_match(settings.valorant_region, match_id)
    return format_match_details(match)

def main():
    mcp.run(transport="sse")

if __name__ == "__main__":
    mcp.run(transport="sse")