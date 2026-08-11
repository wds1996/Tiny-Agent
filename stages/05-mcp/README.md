# Stage 05 — MCP: Standardized Tools & Context

## Why this stage exists

Function calling teaches how a model proposes an action. MCP introduces a standard protocol for discovering and consuming tools and contextual resources across process or service boundaries.

This stage treats MCP as an engineering protocol, not a magic plugin system.

## Planned topics

- MCP architecture;
- host, client, and server roles;
- tools, resources, and prompts;
- capability discovery;
- local and remote servers;
- exposing custom tools through MCP;
- consuming MCP tools inside Tiny-Agent;
- schema normalization;
- authentication and trust boundaries;
- permissions and unsafe servers.

## Planned code artifacts

```text
code/
├── minimal_mcp_server.py
├── minimal_mcp_client.py
├── custom_tool_server.py
└── tiny_agent_mcp_bridge.py
```

## Planned theory

```text
theory/
├── 01-mcp-mental-model.md
├── 02-tools-resources-prompts.md
├── 03-client-server-lifecycle.md
└── 04-mcp-security-boundaries.md
```

## Milestone

Implement a custom MCP server, discover its capabilities from a client, and make Tiny-Agent consume those capabilities through a clean adapter.

## Key question

> How is standardized tool discovery through MCP different from hard-coding local functions into an Agent process?
