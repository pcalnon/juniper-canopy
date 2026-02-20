# Setup MCP server for AlphaVantage

## Configuration

### Remote server setup

```bash
claude mcp add -t http alphavantage https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY
```

### Local server setup

**Maybe not the curl pipe to shell crazyness**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
claude mcp add alphavantage -- uvx av-mcp YOUR_API_KEY
```

## Examples:

### Remote Connection Example

```bash
https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY
```

### Local Connection Example

```bash
uvx av-mcp YOUR_API_KEY
```

---
