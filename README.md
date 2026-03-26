# Valorant MCP Server

An MCP (Model Context Protocol) server that exposes Valorant match analysis tools. Connect it to Claude (or any MCP-compatible client) to fetch and analyze player stats, match history, agent performance, and more.

Powered by [Henrik's Unofficial Valorant API](https://docs.henrikdev.xyz/valorant/general).

## Tools

| Tool | Description |
|------|-------------|
| `get_player_info` | Fetch basic account info for a Riot ID |
| `get_match_history` | Recent competitive match history with detailed stats for you and teammates |
| `get_match_details` | Full breakdown of a specific match by match ID |
| `get_agent_stats` | Aggregated per-agent stats: win rate, avg KDA, avg score |
| `get_map_stats` | Aggregated per-map stats: win rate, avg score |
| `get_rank_progression` | Current rank, elo, peak rank, and season history |

## Setup

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Henrik API key](https://docs.henrikdev.xyz/valorant/general)

### Install

```bash
git clone https://github.com/SeijiMatsumoto/valorant-mcp.git
cd valorant-mcp
uv sync
```

### Configure

Create a `.env` file in the project root:

```
HENRIK_API_KEY=your-api-key-here
VALORANT_REGION=na
```

Supported regions: `na`, `eu`, `ap`, `kr`

### Add to Claude Code

```bash
claude mcp add valorant-analyzer -- uv run valorant-mcp
```

### Add to Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "valorant-analyzer": {
      "command": "uv",
      "args": ["run", "valorant-mcp"],
      "cwd": "/path/to/valorant-mcp"
    }
  }
}
```

## Development

### Run the server directly

```bash
uv run valorant-mcp
```

### Test with MCP Inspector

```bash
mcp dev src/valorant_mcp/server.py
```

### Run tests

```bash
uv run pytest src/valorant_mcp/tests/ -v
```

## Tech Stack

- [MCP Python SDK (FastMCP)](https://github.com/modelcontextprotocol/python-sdk) — server framework
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [Pydantic](https://docs.pydantic.dev/) — data validation
- [uv](https://docs.astral.sh/uv/) — package management

## License

MIT
