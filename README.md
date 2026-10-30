# Valorant MCP Server

An MCP (Model Context Protocol) server that exposes Valorant match analysis tools. Connect it to Claude (or any MCP-compatible client) to fetch and analyze player stats, match history, agent performance, and more.

Powered by [Henrik's Unofficial Valorant API](https://docs.henrikdev.xyz/valorant/general).

## Tools

| Tool | Use it for |
|------|-------------|
| `get_performance_report` | The broad picture across up to 50 matches: opening duels, trading, KAST/ADR, damage conversion, clutches, attack vs defense, economy (incl. your buy vs your team's), per-role/agent/map results, death positions by callout, weapons and engagement ranges, solo vs party, lobby strength, game number in session |
| `get_benchmarks` | Whether those numbers are good: you vs the other 9 players in the same lobbies, vs the same role, and vs others on the same agent (incl. utility casts per ability and Henrik's performance ratings) |
| `get_teamplay_report` | Spacing and trading from player positions: isolated deaths, trade chances you converted, where you die alone, win rate with each party member |
| `get_site_report` | Team site choice per map, post-plant and retake win rates |
| `compare_periods` | Last N matches vs the N before, with deltas and confidence ranges |
| `get_rr_history` | RR gained/lost per match, joined with how you played in each |
| `get_player_profile` | Account, current rank/RR, peak, rank protection, season history |
| `get_match_history` | One compact row per recent match (filter by mode, map, agent) |
| `get_match_details` | One match in depth. `summary`: per-player stats, per-round sides, buys, first blood. `narrative`: round-by-round timeline with named map zones and tags; filter with `rounds` |

Also exposed:
- **Prompt** `coach_review`: runs the tools and writes a **keep / change / experiment** review.
- **Resource** `valorant://glossary`: definitions of every metric (trade chance, isolated death, buy thresholds, confidence ranges, ...).

Percentages that depend on sample size come with `*_ci95` 95% confidence ranges so small samples aren't over-read.

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) package manager:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  (Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`)
- A [Henrik API key](https://api.henrikdev.xyz/dashboard/)

### Claude Code

```bash
claude mcp add valorant-analyzer -e HENRIK_API_KEY=your-key-here -- uvx valorant-mcp
```

### Claude Desktop

Add to your Claude Desktop config:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "valorant-analyzer": {
      "command": "uvx",
      "args": ["valorant-mcp"],
      "env": {
        "HENRIK_API_KEY": "your-key-here"
      }
    }
  }
}
```

## Local Development

```bash
git clone https://github.com/SeijiMatsumoto/valorant-mcp.git
cd valorant-mcp
uv sync
```

Create a `.env` file in the project root:

```
HENRIK_API_KEY=your-api-key-here
```

Optional settings (env vars or `.env`):

| Variable | Default | Notes |
|---|---|---|
| `VALORANT_REGION` | `na` | `na`, `eu`, `ap`, `kr`, `latam`, `br` |
| `VALORANT_PLATFORM` | `pc` | `pc` or `console` |
| `HENRIK_BASE_URL` | `https://api.henrikdev.xyz/valorant` | Set to `https://beta.api.henrikdev.xyz/valorant` for 4.10 beta fields (Henrik performance grades, MVPs). Analysis doesn't depend on them. |
| `CACHE_DIR` | `~/.cache/valorant-mcp` | Completed matches are cached here permanently |

### Run the server

```bash
uv run valorant-mcp
```

### Test with MCP Inspector

```bash
mcp dev src/valorant_mcp/server.py
```

### Run tests

Live tests need `HENRIK_API_KEY` and `VALORANT_SMOKE_PLAYER=name#TAG` in your `.env`.

```bash
uv run pytest                 # offline unit tests (HTTP is mocked)
uv run pytest -m live         # smoke tests against the real Henrik API (~13 of your 30 requests/min)
```

## Tech Stack

- [MCP Python SDK (FastMCP)](https://github.com/modelcontextprotocol/python-sdk) — server framework
- [httpx](https://www.python-httpx.org/) — async HTTP client
- [Pydantic](https://docs.pydantic.dev/) — data validation
- [uv](https://docs.astral.sh/uv/) — package management

## License

MIT
