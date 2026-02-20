# Exa API Setup Guide

## Configuration

| Setting | Value |
|---------|-------|
| Coding Tool | Claude |
| Framework | MCP |
| Use Case | Research platform for investigating dynamic neural networks and novel learning architectures |
| Search Type | Auto - Balanced relevance and speed (~1 second) |
| Content | Full text |

## API Key Setup

### Environment Variable

```bash
export EXA_API_KEY="YOUR_API_KEY"
```

### .env File

```env
EXA_API_KEY=YOUR_API_KEY
```

## MCP Server Configuration

### Claude Code (user-level)

```bash
claude mcp add --transport http exa "https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}"
```

### Project-level (.mcp.json)

```json
{
  "mcpServers": {
    "exa": {
      "type": "http",
      "url": "https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}",
      "headers": {}
    }
  }
}
```

### Available Tools

- `web_search_exa` - Real-time web search
- `get_code_context_exa` - Code snippets, docs, and examples
- `company_research_exa` - Company information and research
- `crawling_exa` - Extract content from any URL
- `linkedin_search_exa` - Find people on LinkedIn
- `deep_researcher_start` - AI-powered deep research

## Search Type Reference

| Type | Best For | Speed | Depth |
|------|----------|-------|-------|
| `fast` | Real-time apps, autocomplete, quick lookups | Fastest | Basic |
| `auto` | Most queries - balanced relevance & speed | Medium | Smart |

## Content Configuration

| Type | Config | Best For |
|------|--------|----------|
| Text | `"text": {"max_characters": 20000}` | Full content extraction, RAG |
| Highlights | `"highlights": {"max_characters": 2000}` | Snippets, summaries, lower cost |

**Token usage warning:** Using `text: true` (full page text) can significantly increase token count. Mitigate with:
- `max_characters` limit: `"text": {"max_characters": 10000}`
- Use `highlights` instead if you don't need contiguous text

## Category Filters

| Category | Use Case |
|----------|----------|
| `people` | Find people by role/expertise |
| `company` | Find companies by industry/attributes |
| `news` | News articles |
| `research paper` | Academic papers (arxiv, etc.) |
| `tweet` | Twitter/X posts |

## Quick Start (cURL)

```bash
curl -X POST 'https://api.exa.ai/search' \
  -H 'x-api-key: YOUR_API_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
  "query": "your search query here",
  "type": "auto",
  "num_results": 10,
  "contents": {
    "text": {
      "max_characters": 20000
    }
  }
}'
```

## Domain Filtering (Optional)

```json
{
  "includeDomains": ["arxiv.org", "github.com"],
  "excludeDomains": ["pinterest.com"]
}
```

Note: `includeDomains` and `excludeDomains` cannot be used together.

## Content Freshness (maxAgeHours)

| Value | Behavior | Best For |
|-------|----------|----------|
| 24 | Cache if < 24h old, else livecrawl | Daily-fresh content |
| 1 | Cache if < 1h old, else livecrawl | Near real-time data |
| 0 | Always livecrawl | Real-time data |
| -1 | Never livecrawl (cache only) | Maximum speed, static content |
| *(omit)* | Default (livecrawl as fallback) | Recommended |

## Other Endpoints

| Endpoint | Description | Docs |
|----------|-------------|------|
| `/search` | Search the web | [Docs](https://exa.ai/docs/reference/search) |
| `/contents` | Get contents for known URLs | [Docs](https://exa.ai/docs/reference/get-contents) |
| `/answer` | Q&A with citations | [Docs](https://exa.ai/docs/reference/answer) |

## Function Calling / Tool Use

### Anthropic Tool Use

```python
import anthropic
from exa_py import Exa

client = anthropic.Anthropic()
exa = Exa()

tools = [{
    "name": "exa_search",
    "description": "Search the web for current information.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"]
    }
}]

def exa_search(query: str) -> str:
    results = exa.search(query=query, type="auto", num_results=10, contents={"text": {"max_characters": 20000}})
    return "\n".join([f"{r.title}: {r.url}" for r in results.results])

messages = [{"role": "user", "content": "Latest quantum computing developments?"}]
response = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096, tools=tools, messages=messages)

if response.stop_reason == "tool_use":
    tool_use = next(b for b in response.content if b.type == "tool_use")
    tool_result = exa_search(tool_use.input["query"])
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": tool_use.id, "content": tool_result}]})
    final = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096, tools=tools, messages=messages)
    print(final.content[0].text)
```

## Resources

- Docs: https://exa.ai/docs
- Dashboard: https://dashboard.exa.ai
- API Status: https://status.exa.ai
- Full MCP docs: https://docs.exa.ai/reference/exa-mcp
