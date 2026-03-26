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

## Quick Start (Remote)

The server is hosted remotely — no Python or API key needed on your end.

### Claude Code

```bash
claude mcp add valorant-analyzer --transport sse https://valorant-mcp.fly.dev/sse
```

### Claude Desktop

Requires [Node.js](https://nodejs.org/) for the `mcp-remote` bridge.

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "valorant-analyzer": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://valorant-mcp.fly.dev/sse"]
    }
  }
}
```

## Self-Hosted Setup

If you'd prefer to run the server yourself with your own API key:

### Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager
- A [Henrik API key](https://docs.henrikdev.xyz/valorant/general)

### Claude Code

```bash
claude mcp add valorant-analyzer -e HENRIK_API_KEY=your-key-here -e VALORANT_REGION=na -- uvx valorant-mcp
```

### Claude Desktop

```json
{
  "mcpServers": {
    "valorant-analyzer": {
      "command": "uvx",
      "args": ["valorant-mcp"],
      "env": {
        "HENRIK_API_KEY": "your-key-here",
        "VALORANT_REGION": "na"
      }
    }
  }
}
```

Supported regions: `na`, `eu`, `ap`, `kr`

## Local Development

```bash
git clone https://github.com/SeijiMatsumoto/valorant-mcp.git
cd valorant-mcp
uv sync
```

Create a `.env` file in the project root:

```
HENRIK_API_KEY=your-api-key-here
VALORANT_REGION=na
```

### Run the server

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
- [Fly.io](https://fly.io/) — remote hosting

## License

MIT
