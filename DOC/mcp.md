# PrismRAG MCP Server

## What is MCP?

Model Context Protocol (MCP) is an open standard that lets AI agents (Claude, GPT, LangChain, AutoGen, and others) call external services as tools using a structured interface.

With PrismRAG's MCP server, an AI agent can:
- Search your custom knowledge graph with a single tool call
- Check ingest job status without writing any integration code
- Create bridge vectors between domain clusters
- List available communities and workspaces

## Why this matters for enterprise

Without MCP, a customer building a RAG pipeline must write code to call your REST API, handle auth, parse responses, and integrate results into their LLM workflow.

With MCP, they connect Claude Desktop (or any MCP host) to your server once, and the AI agent figures out how to use PrismRAG on its own. Zero integration code.

## Transport options

| Mode | Use case |
|---|---|
| `stdio` | Local: Claude Desktop, direct agent subprocess |
| `http` (SSE) | Remote: deployed as a sidecar on the API container |

## Tools exposed

| Tool | Description | Plan required |
|---|---|---|
| `search` | Query the knowledge graph | Starter+ |
| `list_workspaces` | List tenant workspaces | Any |
| `get_job_status` | Poll an ingest job | Any |
| `list_communities` | List community summaries for a workspace | Any |
| `create_bridge` | Create a bridge vector between communities | Professional+ |
| `submit_job` | Submit a new ingest job with rules | Any |

## Claude Desktop setup

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "prismrag": {
      "command": "python",
      "args": ["-m", "prismrag.mcp.server"],
      "env": {
        "PRISMRAG_API_BASE": "https://api.prismrag.io",
        "PRISMRAG_API_KEY": "prk_your_key_here",
        "PRISMRAG_TENANT_ID": "your-default-tenant-uuid"
      }
    }
  }
}
```

After restarting Claude Desktop, the tools appear in the tool picker.

## HTTP/SSE mode (for remote agents)

```bash
PRISMRAG_MCP_TRANSPORT=http python -m prismrag.mcp.server --port 8002
```

Agent connects to `http://your-server:8002/mcp`.
