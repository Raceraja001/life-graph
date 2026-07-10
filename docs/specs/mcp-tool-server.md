# MCP Tool Server — Feature Spec

> **Purpose**: Expose the uzhavu AI engine's tools via the Model Context Protocol (MCP) standard. Any MCP-compatible AI client (Claude Desktop, Cursor, Windsurf, custom agents) can discover and use uzhavu's tools — Gmail, calendar, web search, knowledge base, business data queries — all scoped to the authenticated org.
>
> **Architecture ref**: `APP_ARCHITECTURE.md` — follows manifest + module config pattern
>
> **AI Engine ref**: `ai-engine-improvements.md` — uses existing `@tool` decorator registry
>
> **Multi-tenant**: Each MCP connection is authenticated via API key, scoped to an org. Tools only access that org's data.

---

## Requirements

### Story 1: MCP Server Implementation

As a **developer or AI power user**, I want to connect my MCP-compatible AI client to uzhavu's tool server so that I can use uzhavu's tools (Gmail, calendar, knowledge base) from any AI interface.

#### Acceptance Criteria

- GIVEN I have a valid API key for my org WHEN I configure my AI client with the MCP server URL `https://mcp.uzhavu.com/org/{orgId}` (or `http://localhost:8001/mcp/v1` for local) THEN the client connects successfully and discovers available tools
- GIVEN the MCP server is running WHEN a client sends an `initialize` JSON-RPC request THEN the server responds with its capabilities: `{"tools": {"listChanged": true}, "resources": {"listChanged": false}}`
- GIVEN the connection is initialized WHEN a client sends `tools/list` THEN the server returns all available tools for the org with their names, descriptions, and input schemas
- GIVEN a tool is available WHEN a client sends `tools/call` with valid tool name and input THEN the server executes the tool and returns the result
- GIVEN the server supports SSE transport WHEN a client connects via `GET /mcp/v1/sse` THEN the server maintains an SSE connection for streaming responses and server-initiated notifications
- GIVEN the MCP server is running WHEN any client requests `GET /.well-known/mcp.json` THEN the server returns the MCP manifest with server name, version, and endpoint URLs

---

### Story 2: Tool Discovery & Schema

As a **developer**, I want my AI client to discover available tools with full JSON Schema descriptions so that the AI model knows exactly how to call each tool.

#### Acceptance Criteria

- GIVEN I call `tools/list` WHEN tools are available THEN each tool includes: `name` (e.g., `gmail_send`), `description` (human-readable), and `inputSchema` (JSON Schema object with required/optional properties)
- GIVEN a tool has required parameters WHEN the AI model generates a `tools/call` with missing required params THEN the server returns a JSON-RPC error: `{"code": -32602, "message": "Missing required parameter: 'to_email'"}` 
- GIVEN tools change at runtime (custom tool added/removed) WHEN the server detects the change THEN it sends a `notifications/tools/list_changed` notification to connected SSE clients
- GIVEN a tool has complex output WHEN the tool executes successfully THEN the response includes structured `content` array with `type` (text, image, resource) per MCP spec
- GIVEN the org is on the free plan WHEN `tools/list` is called THEN only read-only tools are returned (knowledge base query, business data read) — write tools (Gmail send, calendar create) are excluded

---

### Story 3: Authentication & Multi-Tenant Scoping

As a **platform admin**, I want MCP connections authenticated via API keys so that each connection is scoped to the correct org and unauthorized access is prevented.

#### Acceptance Criteria

- GIVEN an MCP client connects WHEN it includes `Authorization: Bearer <api_key>` in the HTTP header THEN the server validates the key against the `api_keys` table, resolves the `org_id`, and scopes all tool executions to that org
- GIVEN an MCP client connects WHEN the API key is missing or invalid THEN the server returns HTTP 401: `{"error": "Invalid or missing API key"}`
- GIVEN an MCP client connects with a valid API key WHEN the API key has been revoked THEN the server returns HTTP 401: `{"error": "API key has been revoked"}`
- GIVEN an MCP client is connected WHEN it calls `gmail_send` THEN the tool only accesses the org's connected Gmail account — not any other org's
- GIVEN a connection is established WHEN the server stores the connection THEN `mcp_connections` records: api_key_id, client_name (from `initialize` request), client_version, and last_connected_at
- GIVEN the API key has a `scope` field WHEN it restricts to `["tools:read"]` THEN write tools return permission denied errors

---

### Story 4: Custom Tool Builder

As an **org admin**, I want to create custom tools without code so that I can expose external APIs, database queries, or AI prompt chains as MCP tools.

#### Acceptance Criteria

- GIVEN I navigate to AI → Custom Tools WHEN I click "Create Tool" THEN I see a form with: tool name, description, input fields (JSON Schema builder), and action type (HTTP request, database query, or AI prompt)
- GIVEN I create an HTTP action tool WHEN I configure it with URL, method, headers, and body template THEN the tool executes the HTTP request when called via MCP, mapping input parameters to the request
- GIVEN I create a database query tool WHEN I configure it with a parameterized SQL query THEN the tool executes the query against the org's data (read-only, scoped by org_id) and returns results
- GIVEN I create an AI prompt tool WHEN I configure it with a prompt template and model THEN the tool sends the rendered prompt to the AI engine and returns the response
- GIVEN I create a custom tool WHEN it is saved and marked active THEN it appears in `tools/list` for MCP clients connected to my org
- GIVEN I deactivate a custom tool WHEN MCP clients call `tools/list` THEN the deactivated tool is no longer listed
- GIVEN I am on the free or starter plan WHEN I try to create a custom tool THEN I see an upgrade prompt: "Custom tool builder requires Pro plan. Create up to 10 custom tools."
- GIVEN I am on the Pro plan WHEN I have 10 custom tools and try to create another THEN I see: "Pro plan supports up to 10 custom tools. Upgrade to Enterprise for unlimited."

---

### Story 5: Tool Usage Analytics

As a **platform admin**, I want to track which tools are called, by whom, how often, and their success rate so that I can monitor usage and identify issues.

#### Acceptance Criteria

- GIVEN MCP tools are being used WHEN I navigate to AI → Tool Analytics THEN I see a dashboard with: total tool calls (today/week/month), success rate, avg latency, most-used tools, and most-active connections
- GIVEN a tool call completes WHEN the result is recorded THEN the system stores: tool_name, connection_id, input (sanitized), output preview (truncated to 500 chars), status (success/error), and latency_ms in `tool_usage_logs`
- GIVEN I click on a specific tool WHEN usage data exists THEN I see: total calls, success rate, avg latency, error breakdown, and a time-series chart of calls over the last 30 days
- GIVEN the LLM trace viewer module is active WHEN a tool is called during an AI conversation THEN the tool call is linked to the conversation trace for end-to-end visibility
- GIVEN a tool has a high error rate (>20% failures in the last hour) WHEN the system detects it THEN an alert is created for the admin: "Tool 'gmail_send' has a 35% error rate in the last hour"

---

### Story 6: Rate Limiting

As a **platform admin**, I want per-tool rate limits so that external API tools (Gmail, calendar) aren't abused and quotas aren't exhausted.

#### Acceptance Criteria

- GIVEN rate limits are configured WHEN a tool call exceeds the rate limit THEN the server returns a JSON-RPC error: `{"code": -32000, "message": "Rate limit exceeded for tool 'gmail_send'. Limit: 100 calls/hour. Retry after: 45 seconds"}`
- GIVEN default rate limits exist WHEN no custom limits are configured for a tool THEN the system uses defaults: 100 calls/hour for external API tools, 1000 calls/hour for internal tools
- GIVEN I am an org admin WHEN I navigate to tool settings THEN I can configure per-tool rate limits for my org
- GIVEN a rate limit is hit WHEN the tool is called again after the limit window resets THEN the call succeeds
- GIVEN rate limiting is implemented WHEN the system tracks calls THEN it uses a sliding window counter (Redis-backed or in-memory) keyed by `org_id:tool_name`

---

### Story 7: Remote MCP Server Hosting

As a **developer**, I want a publicly accessible MCP server URL so that I can connect my AI client from anywhere — not just my local network.

#### Acceptance Criteria

- GIVEN my org has a valid subscription WHEN I configure my AI client with `https://mcp.uzhavu.com/org/{orgId}` THEN the client connects to the remote MCP server via HTTP+SSE transport
- GIVEN the remote server is running WHEN multiple AI clients connect simultaneously THEN each connection is isolated and independently authenticated
- GIVEN I am using Claude Desktop WHEN I add the MCP server URL to my MCP config THEN Claude Desktop discovers and can use all available tools
- GIVEN I am using Cursor IDE WHEN I add the MCP server URL to Cursor's MCP settings THEN Cursor's AI agent can use the tools during code generation
- GIVEN the remote server is behind HTTPS WHEN a client connects THEN all communication is encrypted via TLS
- GIVEN my org is on the free plan WHEN I try to use the remote MCP server THEN I see: "Remote MCP server access requires Starter plan or above. Use local stdio transport for free."

---

### Story 8: MCP Resources (Read-Only Data)

As a **developer**, I want MCP resources to expose read-only data (knowledge base articles, business configs, recent conversations) so that AI clients have context without calling tools.

#### Acceptance Criteria

- GIVEN an MCP client is connected WHEN it sends `resources/list` THEN the server returns available resources: recent conversations, knowledge base articles, org settings
- GIVEN a resource exists WHEN the client sends `resources/read` with a resource URI THEN the server returns the resource content as structured text
- GIVEN the knowledge base module is active WHEN `resources/list` is called THEN knowledge base articles appear as resources with URIs like `uzhavu://knowledge/{article_id}`
- GIVEN a resource is updated server-side WHEN the change occurs THEN the server sends `notifications/resources/list_changed` to connected SSE clients
- GIVEN I am on the free plan WHEN I call `resources/list` THEN only basic resources are returned (no knowledge base or conversation history)

---

## Design

### Architecture Overview

```
┌────────────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  MCP Clients       │     │  FastAPI MCP Server   │     │  PostgreSQL  │
│  ┌───────────────┐ │     │  /mcp/v1              │     │              │
│  │ Claude Desktop│ │────▶│  ┌─────────────────┐  │────▶│ mcp_*        │
│  │ Cursor IDE    │ │     │  │ JSON-RPC Handler │  │     │ custom_tools │
│  │ Windsurf      │ │     │  │ SSE Transport    │  │     │ tool_usage   │
│  │ Custom Agents │ │     │  │ Auth Middleware   │  │     │ tables       │
│  └───────────────┘ │     │  └────────┬────────┘  │     └──────────────┘
└────────────────────┘     │           │           │
                           │  ┌────────▼────────┐  │
                           │  │  Tool Registry   │  │
                           │  │  @tool decorator  │  │
                           │  │  + Custom Tools   │  │
                           │  └────────┬────────┘  │
                           │           │           │
                           │  ┌────────▼────────┐  │
                           │  │  Existing Tools  │  │
                           │  │  Gmail, Calendar │  │
                           │  │  Web Search, KB  │  │
                           │  │  Business Data   │  │
                           │  └─────────────────┘  │
                           └──────────────────────┘
                                       │
                           ┌───────────┼───────────┐
                           │           │           │
                           ▼           ▼           ▼
                    ┌────────────┐ ┌──────────┐ ┌────────────┐
                    │ NestJS API │ │ API Key  │ │ LLM Trace  │
                    │ (custom    │ │ Mgmt     │ │ Viewer     │
                    │  tool CRUD)│ │ Module   │ │            │
                    └────────────┘ └──────────┘ └────────────┘
```

**Key flows:**
1. **MCP Protocol**: Client → JSON-RPC over HTTP/SSE → FastAPI MCP Server → Tool Registry → Execute Tool
2. **Custom Tool CRUD**: Next.js → NestJS API → PostgreSQL (tool definitions stored in DB)
3. **Tool Execution**: MCP Server loads built-in tools from `@tool` registry + custom tools from DB → executes → logs → returns
4. **Analytics**: Every tool call logged to `tool_usage_logs` → NestJS serves analytics dashboard

---

### Data Models

```sql
-- ============================================================
-- MCP connections — tracks active and historical client connections
-- ============================================================
CREATE TABLE mcp_connections (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id                TEXT NOT NULL,
  api_key_id            TEXT NOT NULL,                     -- FK to api_keys table
  client_name           TEXT,                              -- "Claude Desktop", "Cursor", etc.
  client_version        TEXT,                              -- Client version string
  protocol_version      TEXT DEFAULT '2024-11-05',         -- MCP protocol version
  transport             TEXT DEFAULT 'http_sse',           -- http_sse|stdio
  capabilities          JSONB DEFAULT '{}',                -- Client capabilities from initialize
  is_active             BOOLEAN DEFAULT true,
  last_connected_at     TIMESTAMPTZ DEFAULT NOW(),
  last_request_at       TIMESTAMPTZ,
  total_requests        INT DEFAULT 0,
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mcp_conn_org ON mcp_connections(org_id, last_connected_at DESC);
CREATE INDEX idx_mcp_conn_api_key ON mcp_connections(api_key_id);
CREATE INDEX idx_mcp_conn_active ON mcp_connections(org_id, is_active) WHERE is_active = true;

-- ============================================================
-- Custom tools — user-defined tools (no-code tool builder)
-- ============================================================
CREATE TABLE custom_tools (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id                TEXT NOT NULL,
  name                  TEXT NOT NULL,                     -- Tool name (snake_case, unique per org)
  display_name          TEXT,                              -- Human-readable: "Send Slack Message"
  description           TEXT NOT NULL,                     -- Shown to AI models for tool selection
  input_schema          JSONB NOT NULL DEFAULT '{}',       -- JSON Schema for input parameters
  output_description    TEXT,                              -- What the tool returns
  action_type           TEXT NOT NULL,                     -- http|query|prompt
  action_config         JSONB NOT NULL DEFAULT '{}',       -- Config depends on action_type (see below)
  is_active             BOOLEAN DEFAULT true,
  timeout_ms            INT DEFAULT 30000,                 -- Max execution time
  rate_limit            INT DEFAULT 100,                   -- Calls per hour (0 = unlimited)
  tags                  TEXT[] DEFAULT '{}',               -- Categorization tags
  use_count             INT DEFAULT 0,
  last_used_at          TIMESTAMPTZ,
  created_by            TEXT,                              -- User ID
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_custom_tool_name ON custom_tools(org_id, name);
CREATE INDEX idx_custom_tool_org ON custom_tools(org_id, is_active);
CREATE INDEX idx_custom_tool_type ON custom_tools(org_id, action_type);

-- action_config examples:
-- HTTP: {"method": "POST", "url": "https://api.slack.com/chat.postMessage", "headers": {"Authorization": "Bearer {{slack_token}}"}, "body_template": {"channel": "{{channel}}", "text": "{{message}}"}}
-- Query: {"query": "SELECT * FROM invoices WHERE org_id = $1 AND status = $2", "params": ["org_id", "status"], "read_only": true}
-- Prompt: {"prompt_name": "summarize_document", "model": "gemini/gemini-2.5-flash", "max_tokens": 500}

-- ============================================================
-- Tool usage logs — per-call tracking for analytics
-- ============================================================
CREATE TABLE tool_usage_logs (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id                TEXT NOT NULL,
  connection_id         TEXT REFERENCES mcp_connections(id),
  tool_name             TEXT NOT NULL,                     -- Built-in or custom tool name
  tool_type             TEXT NOT NULL DEFAULT 'builtin',   -- builtin|custom
  input_preview         TEXT,                              -- Sanitized input (truncated, no secrets)
  output_preview        TEXT,                              -- Truncated output (max 500 chars)
  status                TEXT NOT NULL DEFAULT 'success',   -- success|error|timeout|rate_limited
  error_message         TEXT,                              -- Error details if status != success
  latency_ms            INT NOT NULL DEFAULT 0,
  tokens_used           INT,                               -- If the tool used LLM tokens
  trace_id              TEXT,                              -- Link to LLM trace viewer
  user_id               TEXT,                              -- User who initiated (if known)
  created_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tool_log_org ON tool_usage_logs(org_id, created_at DESC);
CREATE INDEX idx_tool_log_tool ON tool_usage_logs(org_id, tool_name, created_at DESC);
CREATE INDEX idx_tool_log_conn ON tool_usage_logs(connection_id, created_at DESC);
CREATE INDEX idx_tool_log_status ON tool_usage_logs(org_id, status, created_at DESC)
  WHERE status != 'success';
-- Consider retention: keep 90 days of logs, archive older data

-- ============================================================
-- Tool rate limits — configurable per org per tool
-- ============================================================
CREATE TABLE tool_rate_limits (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id                TEXT NOT NULL,
  tool_name             TEXT NOT NULL,                     -- '*' for default org-wide limit
  max_calls_per_hour    INT NOT NULL DEFAULT 100,
  max_calls_per_day     INT DEFAULT 0,                    -- 0 = unlimited
  current_hour_count    INT DEFAULT 0,
  current_day_count     INT DEFAULT 0,
  hour_reset_at         TIMESTAMPTZ,
  day_reset_at          TIMESTAMPTZ,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_rate_limit_org_tool ON tool_rate_limits(org_id, tool_name);

-- ============================================================
-- Tool secrets — encrypted secrets for custom tool HTTP actions
-- ============================================================
CREATE TABLE tool_secrets (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  org_id                TEXT NOT NULL,
  name                  TEXT NOT NULL,                     -- "slack_token", "notion_api_key"
  value_encrypted       TEXT NOT NULL,                     -- AES-256 encrypted
  created_by            TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_tool_secret_name ON tool_secrets(org_id, name);
CREATE INDEX idx_tool_secret_org ON tool_secrets(org_id);
```

---

### API Contracts

#### Module Structure

```
# FastAPI MCP Server (alongside AI engine)
ai-engine/app/mcp/
├── server.py                       # MCP server main — JSON-RPC router
├── transport.py                    # HTTP + SSE transport layer
├── auth.py                         # API key validation + org resolution
├── handlers/
│   ├── initialize.py               # initialize / initialized handlers
│   ├── tools.py                    # tools/list, tools/call handlers
│   ├── resources.py                # resources/list, resources/read handlers
│   └── notifications.py           # Server-side notification emission
├── tools/
│   ├── registry.py                 # Unified tool registry (built-in + custom)
│   ├── custom_executor.py          # Execute custom tools (HTTP, query, prompt)
│   └── schema_builder.py          # Build JSON Schema from @tool decorators
├── rate_limiter.py                 # Sliding window rate limiter
├── metrics.py                      # Tool usage logging
└── discovery.py                    # .well-known/mcp.json manifest

# NestJS — Custom tool CRUD + Analytics dashboard
apps/api/src/modules/mcp-tools/
├── mcp-tools.module.ts
├── mcp-tools.controller.ts         # Custom tool CRUD
├── mcp-tools.analytics.controller.ts # Usage analytics
├── mcp-tools.connections.controller.ts # Connection management
├── mcp-tools.service.ts            # Custom tool business logic
├── mcp-tools.analytics.service.ts  # Analytics aggregation
├── mcp-tools.secrets.service.ts    # Encrypted secret management
├── dto/
│   ├── create-custom-tool.dto.ts
│   ├── update-custom-tool.dto.ts
│   ├── create-tool-secret.dto.ts
│   └── configure-rate-limit.dto.ts
├── interfaces/
│   └── mcp-protocol.interface.ts
└── mcp-tools.service.spec.ts
```

---

#### MCP Protocol Endpoints (FastAPI)

##### JSON-RPC Endpoint

```
POST /mcp/v1
Authorization: Bearer <api_key>
Content-Type: application/json
```

All MCP operations use this single endpoint with JSON-RPC 2.0 format.

**Request — Initialize:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "roots": { "listChanged": true }
    },
    "clientInfo": {
      "name": "Claude Desktop",
      "version": "1.2.0"
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": { "listChanged": true },
      "resources": { "listChanged": false }
    },
    "serverInfo": {
      "name": "uzhavu-mcp-server",
      "version": "1.0.0"
    }
  }
}
```

**Request — tools/list:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "gmail_send",
        "description": "Send an email via Gmail. Requires the org's Gmail integration to be connected.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "to": { "type": "string", "description": "Recipient email address" },
            "subject": { "type": "string", "description": "Email subject line" },
            "body": { "type": "string", "description": "Email body (plain text or HTML)" },
            "cc": { "type": "array", "items": { "type": "string" }, "description": "CC recipients" }
          },
          "required": ["to", "subject", "body"]
        }
      },
      {
        "name": "calendar_create_event",
        "description": "Create a Google Calendar event. Returns the event link.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "title": { "type": "string", "description": "Event title" },
            "start_time": { "type": "string", "format": "date-time", "description": "Event start (ISO 8601)" },
            "end_time": { "type": "string", "format": "date-time", "description": "Event end (ISO 8601)" },
            "description": { "type": "string" },
            "attendees": { "type": "array", "items": { "type": "string" } }
          },
          "required": ["title", "start_time", "end_time"]
        }
      },
      {
        "name": "knowledge_search",
        "description": "Search the org's knowledge base for relevant articles and documents.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": { "type": "string", "description": "Search query" },
            "limit": { "type": "integer", "default": 5, "description": "Max results" }
          },
          "required": ["query"]
        }
      },
      {
        "name": "business_data_query",
        "description": "Query business data — invoices, customers, orders, payments. Supports natural language or structured filters.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": { "type": "string", "description": "Natural language query, e.g. 'show unpaid invoices from last month'" },
            "entity": { "type": "string", "enum": ["invoices", "customers", "orders", "payments"], "description": "Entity type to query" },
            "filters": { "type": "object", "description": "Structured filters (optional)" }
          },
          "required": ["query"]
        }
      },
      {
        "name": "slack_post_message",
        "description": "[Custom] Post a message to a Slack channel.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "channel": { "type": "string", "description": "Slack channel name or ID" },
            "message": { "type": "string", "description": "Message text" }
          },
          "required": ["channel", "message"]
        }
      }
    ]
  }
}
```

**Request — tools/call:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "gmail_send",
    "arguments": {
      "to": "customer@example.com",
      "subject": "Invoice #INV-1042",
      "body": "Please find your invoice attached. Payment is due by July 15."
    }
  }
}
```

**Response (success):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Email sent successfully to customer@example.com. Message ID: msg_abc123"
      }
    ]
  }
}
```

**Response (error):**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Error: Gmail integration not connected for this org. Please connect Gmail in Settings → Integrations."
      }
    ],
    "isError": true
  }
}
```

**Request — resources/list:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "resources/list",
  "params": {}
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "resources": [
      {
        "uri": "uzhavu://knowledge/kb_001",
        "name": "Product FAQ",
        "description": "Frequently asked questions about our products",
        "mimeType": "text/plain"
      },
      {
        "uri": "uzhavu://conversations/recent",
        "name": "Recent Conversations",
        "description": "Last 10 AI conversations for this org",
        "mimeType": "application/json"
      },
      {
        "uri": "uzhavu://org/settings",
        "name": "Organization Settings",
        "description": "Current org configuration and preferences",
        "mimeType": "application/json"
      }
    ]
  }
}
```

**JSON-RPC Errors:**

| Code | Message | When |
|:-----|:--------|:-----|
| `-32700` | Parse error | Malformed JSON |
| `-32600` | Invalid request | Missing jsonrpc/method fields |
| `-32601` | Method not found | Unknown method (e.g., `tools/fly`) |
| `-32602` | Invalid params | Missing required tool params |
| `-32603` | Internal error | Unhandled server error |
| `-32000` | Rate limit exceeded | Tool call rate limited |
| `-32001` | Tool execution failed | Tool returned an error |
| `-32002` | Permission denied | Tool not available on current plan |

---

##### SSE Transport

```
GET /mcp/v1/sse
Authorization: Bearer <api_key>
```

Establishes a Server-Sent Events connection. The server sends:
- `message` events with JSON-RPC responses
- `endpoint` event with the POST URL for sending requests
- `notification` events for `notifications/tools/list_changed`, `notifications/resources/list_changed`

**SSE Stream Example:**
```
event: endpoint
data: /mcp/v1/messages?session_id=sess_abc123

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05",...}}

event: notification
data: {"jsonrpc":"2.0","method":"notifications/tools/list_changed"}
```

---

##### MCP Discovery Manifest

```
GET /.well-known/mcp.json
```

No auth required.

**Response:**
```json
{
  "name": "uzhavu-mcp-server",
  "version": "1.0.0",
  "description": "MCP server for uzhavu.race platform — Gmail, Calendar, Knowledge Base, Business Data, and custom tools",
  "transport": {
    "type": "http+sse",
    "url": "https://mcp.uzhavu.com/mcp/v1",
    "sse_url": "https://mcp.uzhavu.com/mcp/v1/sse"
  },
  "authentication": {
    "type": "bearer",
    "description": "Use an API key from your uzhavu organization settings"
  },
  "capabilities": {
    "tools": true,
    "resources": true
  }
}
```

---

#### Custom Tool CRUD (NestJS)

```
POST /business/:orgId/mcp/tools
Authorization: Bearer <token>
```

**Request (HTTP action):**
```json
{
  "name": "slack_post_message",
  "displayName": "Send Slack Message",
  "description": "Post a message to a Slack channel using the Slack API.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "channel": { "type": "string", "description": "Slack channel name or ID" },
      "message": { "type": "string", "description": "Message text" }
    },
    "required": ["channel", "message"]
  },
  "actionType": "http",
  "actionConfig": {
    "method": "POST",
    "url": "https://slack.com/api/chat.postMessage",
    "headers": {
      "Authorization": "Bearer {{slack_token}}",
      "Content-Type": "application/json"
    },
    "bodyTemplate": {
      "channel": "{{channel}}",
      "text": "{{message}}"
    }
  },
  "timeoutMs": 10000,
  "rateLimit": 50,
  "tags": ["communication", "slack"]
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "ct_001",
    "orgId": "org_xyz",
    "name": "slack_post_message",
    "displayName": "Send Slack Message",
    "description": "Post a message to a Slack channel using the Slack API.",
    "actionType": "http",
    "isActive": true,
    "rateLimit": 50,
    "useCount": 0,
    "createdAt": "2026-07-05T12:00:00Z"
  }
}
```

**Request (Database query action):**
```json
{
  "name": "get_unpaid_invoices",
  "displayName": "Get Unpaid Invoices",
  "description": "Retrieve all unpaid invoices for the organization, optionally filtered by date range.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "from_date": { "type": "string", "format": "date", "description": "Start date filter" },
      "to_date": { "type": "string", "format": "date", "description": "End date filter" }
    },
    "required": []
  },
  "actionType": "query",
  "actionConfig": {
    "query": "SELECT id, invoice_number, customer_name, total_amount, due_date FROM invoices WHERE org_id = $1 AND status = 'unpaid' AND due_date BETWEEN COALESCE($2, '2020-01-01') AND COALESCE($3, '2099-12-31') ORDER BY due_date ASC LIMIT 50",
    "params": ["org_id", "from_date", "to_date"],
    "readOnly": true
  }
}
```

**Request (AI prompt action):**
```json
{
  "name": "summarize_document",
  "displayName": "Summarize Document",
  "description": "Generate a concise summary of a given document or text.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "text": { "type": "string", "description": "The text to summarize" },
      "max_length": { "type": "integer", "default": 200, "description": "Max summary length in words" }
    },
    "required": ["text"]
  },
  "actionType": "prompt",
  "actionConfig": {
    "promptTemplate": "Summarize the following text in {{max_length}} words or fewer:\n\n{{text}}",
    "model": "gemini/gemini-2.5-flash",
    "maxTokens": 500
  }
}
```

**Errors:**
- `400` — Invalid input schema or action config
- `409` — Tool with this name already exists
- `429` — Custom tool quota exceeded for current plan

```
GET /business/:orgId/mcp/tools?type=http&active=true&page=1&limit=20
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "ct_001",
      "name": "slack_post_message",
      "displayName": "Send Slack Message",
      "description": "Post a message to a Slack channel...",
      "actionType": "http",
      "isActive": true,
      "useCount": 342,
      "lastUsedAt": "2026-07-05T11:45:00Z",
      "rateLimit": 50,
      "tags": ["communication", "slack"]
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 5 }
}
```

```
GET /business/:orgId/mcp/tools/:toolId
```

```
PATCH /business/:orgId/mcp/tools/:toolId
Authorization: Bearer <token>
```

```
DELETE /business/:orgId/mcp/tools/:toolId
Authorization: Bearer <token>
```

Soft-delete: sets `is_active = false`.

---

#### Tool Secrets Management

```
POST /business/:orgId/mcp/secrets
Authorization: Bearer <token>
```

**Request:**
```json
{
  "name": "slack_token",
  "value": "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "sec_001",
    "name": "slack_token",
    "createdAt": "2026-07-05T12:00:00Z"
  }
}
```

Secret value is AES-256 encrypted at rest, never returned in GET responses.

```
GET /business/:orgId/mcp/secrets
```

Returns secret names only (no values):
```json
{
  "success": true,
  "data": [
    { "id": "sec_001", "name": "slack_token", "createdAt": "2026-07-05T12:00:00Z" },
    { "id": "sec_002", "name": "notion_api_key", "createdAt": "2026-07-05T12:01:00Z" }
  ]
}
```

```
DELETE /business/:orgId/mcp/secrets/:secretId
```

---

#### Connection Management

```
GET /business/:orgId/mcp/connections?active=true&page=1&limit=20
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "conn_001",
      "clientName": "Claude Desktop",
      "clientVersion": "1.2.0",
      "protocolVersion": "2024-11-05",
      "transport": "http_sse",
      "isActive": true,
      "totalRequests": 1247,
      "lastConnectedAt": "2026-07-05T11:00:00Z",
      "lastRequestAt": "2026-07-05T13:45:00Z"
    }
  ],
  "pagination": { "page": 1, "limit": 20, "total": 3 }
}
```

```
DELETE /business/:orgId/mcp/connections/:connectionId
```

Terminates the connection and invalidates the session.

---

#### Tool Usage Analytics

```
GET /business/:orgId/mcp/analytics?period=30d&sortBy=total_calls&order=desc
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "summary": {
      "totalCalls": 8450,
      "successRate": 96.2,
      "avgLatencyMs": 890,
      "activeConnections": 3,
      "uniqueTools": 8
    },
    "tools": [
      {
        "toolName": "knowledge_search",
        "toolType": "builtin",
        "totalCalls": 3200,
        "successRate": 99.1,
        "avgLatencyMs": 450,
        "errorCount": 29,
        "lastUsedAt": "2026-07-05T13:45:00Z"
      },
      {
        "toolName": "gmail_send",
        "toolType": "builtin",
        "totalCalls": 1850,
        "successRate": 94.3,
        "avgLatencyMs": 1200,
        "errorCount": 106,
        "lastUsedAt": "2026-07-05T13:30:00Z"
      },
      {
        "toolName": "slack_post_message",
        "toolType": "custom",
        "totalCalls": 342,
        "successRate": 97.7,
        "avgLatencyMs": 680,
        "errorCount": 8,
        "lastUsedAt": "2026-07-05T11:45:00Z"
      }
    ],
    "dailyTrend": [
      { "date": "2026-07-01", "calls": 280, "errors": 12 },
      { "date": "2026-07-02", "calls": 310, "errors": 8 }
    ]
  }
}
```

```
GET /business/:orgId/mcp/analytics/tools/:toolName?period=7d
```

Returns per-tool detail with hourly breakdown.

---

#### Rate Limit Configuration

```
PUT /business/:orgId/mcp/rate-limits/:toolName
Authorization: Bearer <token>
```

**Request:**
```json
{
  "maxCallsPerHour": 50,
  "maxCallsPerDay": 500
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "toolName": "gmail_send",
    "maxCallsPerHour": 50,
    "maxCallsPerDay": 500,
    "currentHourCount": 12,
    "currentDayCount": 87
  }
}
```

```
GET /business/:orgId/mcp/rate-limits
```

Returns all configured rate limits.

---

### Sequence Diagrams

#### MCP Client Connection & Tool Call

```mermaid
sequenceDiagram
    participant Client as MCP Client (Claude Desktop)
    participant MCP as FastAPI MCP Server
    participant Auth as Auth Middleware
    participant DB as PostgreSQL
    participant Registry as Tool Registry
    participant Tool as Gmail Tool

    Client->>MCP: POST /mcp/v1 {initialize}
    MCP->>Auth: Validate Bearer token
    Auth->>DB: SELECT api_key WHERE key = ?
    DB-->>Auth: {org_id, scopes, is_active}
    Auth-->>MCP: org_id = org_xyz

    MCP->>DB: UPSERT mcp_connections (client_name, version)
    MCP-->>Client: {serverInfo, capabilities}

    Client->>MCP: POST /mcp/v1 {tools/list}
    MCP->>Registry: Get all tools for org_xyz
    Registry->>Registry: Load built-in tools (@tool decorators)
    Registry->>DB: SELECT custom_tools WHERE org_id = org_xyz AND is_active = true
    Registry-->>MCP: Combined tool list
    MCP->>MCP: Filter by plan (free = read-only tools only)
    MCP-->>Client: {tools: [...]}

    Client->>MCP: POST /mcp/v1 {tools/call: gmail_send}
    MCP->>Auth: Validate Bearer token
    MCP->>MCP: Check rate limit (org_id:gmail_send)
    alt Rate limit OK
        MCP->>Registry: Resolve tool "gmail_send"
        Registry-->>MCP: Built-in Gmail tool
        MCP->>Tool: Execute gmail_send({to, subject, body}, org_id)
        Tool-->>MCP: {success: true, message_id: "msg_abc"}
        MCP->>DB: INSERT tool_usage_logs (success, latency)
        MCP->>DB: UPDATE mcp_connections SET total_requests++
        MCP-->>Client: {content: [{type: "text", text: "Email sent..."}]}
    else Rate limit exceeded
        MCP-->>Client: {error: {code: -32000, message: "Rate limit exceeded..."}}
        MCP->>DB: INSERT tool_usage_logs (status: rate_limited)
    end
```

#### Custom Tool Execution (HTTP Action)

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant MCP as FastAPI MCP Server
    participant DB as PostgreSQL
    participant Executor as Custom Tool Executor
    participant Ext as External API (Slack)

    Client->>MCP: POST /mcp/v1 {tools/call: slack_post_message}
    MCP->>DB: SELECT custom_tools WHERE org_id = ? AND name = 'slack_post_message'
    DB-->>MCP: {action_type: "http", action_config: {...}}

    MCP->>DB: SELECT tool_secrets WHERE org_id = ? AND name = 'slack_token'
    DB-->>MCP: {value_encrypted: "..."}
    MCP->>MCP: Decrypt secret (AES-256)

    MCP->>Executor: Execute HTTP action
    Executor->>Executor: Render URL + headers + body (replace {{variables}})
    Executor->>Ext: POST https://slack.com/api/chat.postMessage
    Ext-->>Executor: {ok: true, ts: "1234567890.123456"}
    Executor-->>MCP: {success: true, data: {...}}

    MCP->>DB: INSERT tool_usage_logs (tool: slack_post_message, status: success)
    MCP->>DB: UPDATE custom_tools SET use_count++, last_used_at = NOW()
    MCP-->>Client: {content: [{type: "text", text: "Message posted to #general"}]}
```

#### Custom Tool Execution (Database Query)

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant MCP as FastAPI MCP Server
    participant DB as PostgreSQL
    participant Executor as Custom Tool Executor

    Client->>MCP: POST /mcp/v1 {tools/call: get_unpaid_invoices, args: {from_date: "2026-06-01"}}
    MCP->>DB: SELECT custom_tools WHERE name = 'get_unpaid_invoices'
    DB-->>MCP: {action_type: "query", action_config: {query: "SELECT...", readOnly: true}}

    MCP->>Executor: Execute query action
    Executor->>Executor: Validate read_only = true (prevent writes)
    Executor->>Executor: Bind params: $1=org_id, $2=from_date, $3=null
    Executor->>DB: SELECT id, invoice_number, ... FROM invoices WHERE org_id = $1 AND ...
    DB-->>Executor: [{invoice_number: "INV-1042", ...}, ...]

    Executor-->>MCP: Query results (rows)
    MCP->>MCP: Format as text table or JSON
    MCP->>DB: INSERT tool_usage_logs
    MCP-->>Client: {content: [{type: "text", text: "Found 7 unpaid invoices:\n| # | Customer | Amount | Due |\n..."}]}
```

#### SSE Connection Lifecycle

```mermaid
sequenceDiagram
    participant Client as MCP Client
    participant SSE as SSE Transport
    participant MCP as MCP Server
    participant Admin as Org Admin

    Client->>SSE: GET /mcp/v1/sse (Authorization: Bearer xxx)
    SSE->>MCP: Validate auth, create session
    SSE-->>Client: event: endpoint\ndata: /mcp/v1/messages?session_id=sess_abc

    Note over Client,SSE: SSE connection stays open

    Client->>MCP: POST /mcp/v1/messages?session_id=sess_abc {tools/list}
    MCP-->>SSE: Push response
    SSE-->>Client: event: message\ndata: {tools: [...]}

    Note over Admin: Admin creates a new custom tool

    Admin->>MCP: Custom tool created (via NestJS → event bus)
    MCP->>SSE: Push notification
    SSE-->>Client: event: notification\ndata: {method: "notifications/tools/list_changed"}

    Client->>MCP: POST /mcp/v1/messages {tools/list}
    Note over Client: Client refreshes tool list after notification
    MCP-->>Client: Updated tools list (includes new custom tool)
```

---

### Frontend Structure

```
apps/web/src/apps/mcp-tools/
├── manifest.ts
├── modules/
│   ├── tools.ts                 # Custom tool CRUD config
│   ├── connections.ts           # Connection management config
│   ├── analytics.ts             # Usage analytics config
│   ├── secrets.ts               # Secret management config
│   └── rate-limits.ts           # Rate limit config
├── pages/
│   ├── McpOverviewPage.tsx      # Overview — connections, quick stats, setup guide
│   ├── CustomToolListPage.tsx   # Custom tool list with CRUD
│   ├── CustomToolEditorPage.tsx # Full-screen tool builder (schema + action config)
│   ├── ToolTestPage.tsx         # Test a tool with sample input
│   ├── ConnectionsPage.tsx      # Active/historical connections
│   ├── AnalyticsPage.tsx        # Tool usage analytics dashboard
│   ├── SecretsPage.tsx          # Manage encrypted secrets
│   └── RateLimitsPage.tsx       # Configure per-tool rate limits
├── components/
│   ├── JsonSchemaBuilder.tsx    # Visual JSON Schema editor for input params
│   ├── ActionConfigForm.tsx     # HTTP/Query/Prompt action config form
│   ├── ToolTestRunner.tsx       # Input fields + "Run" button + output display
│   ├── ConnectionCard.tsx       # Client name, version, status, last active
│   ├── UsageChart.tsx           # Time-series chart for tool calls
│   ├── ToolTypeBadge.tsx        # builtin/custom type badge
│   ├── StatusBadge.tsx          # success/error/rate_limited badge
│   ├── McpSetupGuide.tsx        # Instructions for connecting Claude/Cursor/etc.
│   └── RateLimitBar.tsx         # Visual rate limit usage bar
├── actions/
│   └── mcp-tools.ts             # Server actions with withAction()
└── styles/
    ├── McpOverview.module.css
    ├── CustomToolEditor.module.css
    ├── Analytics.module.css
    └── Connections.module.css
```

**Manifest:**
```typescript
export const manifest: AppManifest = {
  id: 'mcp-tools',
  name: 'MCP Tool Server',
  description: 'Expose AI tools via MCP — connect Claude Desktop, Cursor, and any MCP client',
  icon: 'plug-2',
  version: '1.0.0',
  plans: ['free', 'starter', 'pro', 'enterprise'],
  dependencies: [],
  models: ['McpConnection', 'CustomTool', 'ToolUsageLog', 'ToolSecret', 'ToolRateLimit'],
  nav: { section: 'ai', order: 2 },
  routes: [
    { path: '/mcp/overview', label: 'Overview', icon: 'plug-2' },
    { path: '/mcp/tools', label: 'Custom Tools', icon: 'wrench' },
    { path: '/mcp/connections', label: 'Connections', icon: 'link-2' },
    { path: '/mcp/analytics', label: 'Analytics', icon: 'bar-chart-3' },
    { path: '/mcp/secrets', label: 'Secrets', icon: 'key' },
    { path: '/mcp/rate-limits', label: 'Rate Limits', icon: 'gauge' },
  ],
};
```

---

### Plan Gating Matrix

| Feature | Free | Starter (₹499) | Pro (₹1,499) | Enterprise (₹4,999) |
|:--------|:-----|:----------------|:--------------|:---------------------|
| **MCP Access** | Local stdio only | Remote HTTP+SSE | Remote HTTP+SSE | Remote + dedicated |
| **Built-in Tools** | Read-only only | All built-in | All built-in | All built-in |
| **Tool Calls/month** | 100 | 5,000 | 50,000 | Unlimited |
| **Custom Tools** | ✗ | ✗ | 10 tools | Unlimited |
| **Custom Tool Types** | ✗ | ✗ | HTTP + Prompt | HTTP + Query + Prompt |
| **Tool Secrets** | ✗ | ✗ | 5 secrets | Unlimited |
| **Connections** | 1 concurrent | 3 concurrent | 10 concurrent | Unlimited |
| **Analytics** | ✗ | Basic (7d) | Full (30d) | Full + export |
| **Rate Limit Config** | Fixed defaults | Fixed defaults | Configurable | Configurable |
| **Tool Marketplace** | ✗ | ✗ | ✗ | ✓ (future) |
| **Resources (MCP)** | Basic only | All resources | All resources | All + custom |

---

### Dependencies & Integrations

| Dependency | Purpose | Notes |
|:-----------|:--------|:------|
| **API Key Management** | Authenticate MCP connections | API key → org_id resolution, scope enforcement |
| **Tool Registry (`@tool` decorator)** | Built-in tool discovery | Existing AI engine tools auto-exposed via MCP |
| **Gmail/Calendar Integration** | Tool execution | Uses org's connected OAuth tokens |
| **Knowledge Base Module** | Knowledge search tool + resources | Read-only access to org's KB |
| **LLM Trace Viewer** | Link tool calls to conversation traces | `trace_id` in `tool_usage_logs` |
| **Prompt Registry** | AI prompt action tools | Custom tools can reference managed prompts |
| **Encryption Service** | AES-256 for tool secrets | Existing `EncryptionService` from NestJS |
| **EventBusService** | Tool list change notifications | Emit `mcp.tool_added` / `mcp.tool_removed` events |
| **httpx** | Custom HTTP tool execution | Async HTTP client for external API calls |
| **asyncpg** | Custom query tool execution | Direct DB queries (read-only, parameterized) |

### Error Handling

| Scenario | Action |
|:---------|:-------|
| Invalid API key | Return HTTP 401, do not create connection record |
| Revoked API key | Return HTTP 401 with "API key has been revoked" |
| API key scope insufficient | Return JSON-RPC error -32002: "Permission denied: tool requires 'tools:write' scope" |
| Tool not found | Return JSON-RPC error -32601: "Unknown tool: 'nonexistent_tool'" |
| Missing required tool params | Return JSON-RPC error -32602 with specific missing field names |
| Tool execution timeout | Return JSON-RPC error -32001 after `timeout_ms`, log as status=timeout |
| Rate limit exceeded | Return JSON-RPC error -32000 with retry-after seconds |
| Custom tool HTTP action fails | Return JSON-RPC error -32001 with sanitized error (don't expose external API details) |
| Custom tool SQL injection attempt | Parameterized queries only — never string concatenation. `readOnly` enforced via `SET TRANSACTION READ ONLY` |
| Custom tool secret not found | Return JSON-RPC error -32001: "Secret 'slack_token' not configured. Add it in Settings → MCP → Secrets" |
| Malformed JSON-RPC request | Return JSON-RPC error -32700 (parse error) or -32600 (invalid request) |
| SSE connection dropped | Client reconnects automatically (MCP protocol handles reconnection) |
| Concurrent write from multiple MCP clients | Each tool call is isolated — no shared state between calls |
| Monthly tool call quota exceeded | Return JSON-RPC error -32002: "Monthly tool call quota exceeded (5,000/5,000). Upgrade plan." |

### Security Considerations

| Concern | Mitigation |
|:--------|:-----------|
| IDOR (accessing another org's data) | All tool calls scoped by `org_id` from API key. Custom queries auto-inject `org_id` |
| SQL injection in custom query tools | Parameterized queries only (`$1, $2`). No raw SQL from user input. `READ ONLY` transactions |
| Secret exposure in logs | Tool secrets never logged. Input/output previews sanitized — mask API keys, tokens, passwords |
| Custom tool SSRF | Validate custom tool URLs against allowlist/denylist (no `localhost`, `10.x`, `192.168.x` targets) |
| API key in MCP config files | Document best practices: use environment variables, not plaintext in configs |
| Denial of service via tool calls | Rate limiting per org per tool + global rate limit. Timeout enforcement on all tool calls |
| Custom tool data exfiltration | Query tools are read-only. HTTP tools — audit log all outbound requests. Enterprise: approve tools before activation |
| MCP protocol tampering | All HTTP transport over TLS. JSON-RPC request validation before processing |
| Token leakage via error messages | Never include raw errors from external APIs in MCP responses. Sanitize all error messages |

---

## Tasks

### Phase 1: MCP Protocol Foundation (~4 days)

- [ ] Set up MCP server skeleton in FastAPI: `ai-engine/app/mcp/` directory with `server.py`, `transport.py` (~2h)
- [ ] Implement JSON-RPC 2.0 message parser and router: parse `method`, `params`, `id`, route to handlers (~4h)
- [ ] Implement `initialize` handler: return server capabilities and info per MCP spec (~2h)
- [ ] Implement `initialized` notification handler (client confirms initialization) (~30m)
- [ ] Implement HTTP POST transport: `POST /mcp/v1` receives JSON-RPC, returns JSON-RPC response (~3h)
- [ ] Implement SSE transport: `GET /mcp/v1/sse` with session management and message routing (~4h)
- [ ] Implement `/.well-known/mcp.json` discovery manifest endpoint (~1h)
- [ ] Implement JSON-RPC error codes: -32700, -32600, -32601, -32602, -32603, -32000, -32001, -32002 (~2h)
- [ ] Write unit tests for JSON-RPC parsing, routing, and error handling (~3h)

### Phase 2: Authentication & Connection Management (~3 days)

- [ ] Implement auth middleware: extract `Authorization: Bearer <key>`, validate against `api_keys` table, resolve `org_id` (~3h)
- [ ] Create Prisma schema for `mcp_connections`, `custom_tools`, `tool_usage_logs`, `tool_rate_limits`, `tool_secrets` tables (~3h)
- [ ] Run migration, verify tables, indexes, and unique constraints in PostgreSQL (~30m)
- [ ] Implement connection tracking: upsert `mcp_connections` on `initialize`, update `last_request_at` on each request (~2h)
- [ ] Implement scope-based authorization: check API key scopes (`tools:read`, `tools:write`) before tool execution (~2h)
- [ ] Create NestJS module skeleton: `mcp-tools.module.ts` with service/controller registrations (~1h)
- [ ] Implement connection management endpoints: `GET /connections`, `DELETE /connections/:id` in NestJS (~2h)
- [ ] Add plan-based tool filtering: free=read-only tools, starter=all built-in, pro+=custom tools (~2h)
- [ ] Write unit tests for auth, connection tracking, scope enforcement, and plan gating (~3h)

### Phase 3: Tool Discovery & Execution (~4 days)

- [ ] Implement unified tool registry: combine `@tool` decorator registry + custom tools from DB into single tool list (~4h)
- [ ] Implement `tools/list` handler: return all available tools with JSON Schema input descriptions (~3h)
- [ ] Implement JSON Schema auto-generation from `@tool` decorated functions (parse type hints + docstrings) (~4h)
- [ ] Implement `tools/call` handler: resolve tool by name, validate input against schema, execute, return result (~4h)
- [ ] Implement MCP content format: wrap tool results in `{content: [{type: "text", text: "..."}]}` per spec (~2h)
- [ ] Implement `resources/list` and `resources/read` handlers for knowledge base and org data (~3h)
- [ ] Implement `notifications/tools/list_changed` emission via SSE when tools are added/removed (~2h)
- [ ] Write unit tests for tool discovery, schema generation, execution, and resource access (~3h)

### Phase 4: Custom Tool Builder (~4 days)

- [ ] Implement `McpToolsService` in NestJS — custom tool CRUD (create, list, get, update, soft-delete) (~3h)
- [ ] Implement `McpToolsController` — endpoints: `POST/GET/PATCH/DELETE /business/:orgId/mcp/tools` (~3h)
- [ ] Implement custom tool executor — HTTP action: render URL/headers/body templates, execute via httpx (~4h)
- [ ] Implement custom tool executor — Database query action: parameterized query, read-only enforcement, org_id injection (~4h)
- [ ] Implement custom tool executor — AI prompt action: render prompt template, call LLM via litellm (~3h)
- [ ] Implement tool secrets CRUD: `POST/GET/DELETE /business/:orgId/mcp/secrets` with AES-256 encryption (~3h)
- [ ] Implement secret resolution: replace `{{secret_name}}` in action configs with decrypted values at execution time (~2h)
- [ ] Implement SSRF protection: validate custom tool URLs against denylist (no internal IPs, localhost, metadata endpoints) (~2h)
- [ ] Add plan-based quota: free=no custom tools, pro=10, enterprise=unlimited (~1h)
- [ ] Write unit tests for custom tool CRUD, all three executor types, secret handling, and SSRF validation (~3h)

### Phase 5: Rate Limiting (~2 days)

- [ ] Implement sliding window rate limiter: in-memory counter keyed by `org_id:tool_name` with hourly/daily windows (~4h)
- [ ] Implement rate limit check in `tools/call` handler: check before execution, return -32000 error if exceeded (~2h)
- [ ] Implement rate limit configuration endpoints: `PUT/GET /business/:orgId/mcp/rate-limits/:toolName` in NestJS (~2h)
- [ ] Implement default rate limits: 100/hour for external tools, 1000/hour for internal tools, configurable per org (~2h)
- [ ] Implement monthly tool call quota tracking: increment counter per org, reset on 1st of month (~2h)
- [ ] Write unit tests for rate limiter accuracy, window reset, and quota enforcement (~2h)

### Phase 6: Tool Usage Analytics (~2 days)

- [ ] Implement tool usage logging: `INSERT tool_usage_logs` after every tool call (async, non-blocking) (~2h)
- [ ] Implement input/output sanitization: truncate output to 500 chars, mask secrets in input preview (~2h)
- [ ] Implement analytics aggregation endpoint: total calls, success rate, avg latency, per-tool breakdown (~3h)
- [ ] Implement time-series analytics: daily call counts for the last 30 days, per-tool drill-down (~3h)
- [ ] Implement high error rate alerting: check hourly, create admin notification if >20% failure rate (~2h)
- [ ] Link to LLM trace viewer: pass `trace_id` from AI engine context through to tool usage logs (~1h)
- [ ] Write unit tests for logging, sanitization, aggregation, and alerting (~2h)

### Phase 7: Frontend (~6 days)

- [ ] Create app manifest and register in app registry (~1h)
- [ ] Build MCP Overview Page: connection status cards, setup guide for Claude/Cursor/Windsurf, quick stats (~4h)
- [ ] Build McpSetupGuide component: step-by-step instructions with copy-pasteable config snippets for each client (~3h)
- [ ] Build Custom Tool List Page: CRUD table with action type badges, use counts, active/inactive toggle (~4h)
- [ ] Build Custom Tool Editor Page: name/description form + JsonSchemaBuilder for inputs + ActionConfigForm for action (~6h)
- [ ] Build JsonSchemaBuilder component: visual field editor (add field, set type, set required, set description) (~5h)
- [ ] Build ActionConfigForm component: tab-switched forms for HTTP/Query/Prompt action types (~4h)
- [ ] Build Tool Test Page: input form from schema → "Execute" button → output display panel (~3h)
- [ ] Build Connections Page: connection list with client info, last active, request count, terminate button (~3h)
- [ ] Build Analytics Page: summary cards + per-tool table + time-series chart + error breakdown (~5h)
- [ ] Build Secrets Page: secret list (name only, no values), add/delete functionality (~2h)
- [ ] Build Rate Limits Page: per-tool rate limit configuration form with current usage bars (~3h)
- [ ] Build ToolTypeBadge, StatusBadge, RateLimitBar shared components (~2h)
- [ ] Create server actions with `withAction()` wrapper for all MCP tool operations (~3h)
- [ ] CSS Modules for all components (McpOverview, CustomToolEditor, Analytics, Connections) (~3h)
- [ ] Write component tests for JsonSchemaBuilder, ActionConfigForm, ToolTestRunner, ConnectionCard (~2h)

### Phase 8: Testing & Polish (~3 days)

- [ ] End-to-end test: connect Claude Desktop → initialize → tools/list → tools/call (gmail_send) → verify execution (~3h)
- [ ] End-to-end test: create custom HTTP tool → call via MCP → verify external API called with correct params (~3h)
- [ ] End-to-end test: create custom query tool → call via MCP → verify read-only DB query returns correct data (~2h)
- [ ] End-to-end test: create custom prompt tool → call via MCP → verify LLM response returned (~2h)
- [ ] End-to-end test: SSE transport → connect → receive notifications → send requests via POST (~3h)
- [ ] Test auth: valid key succeeds, invalid key returns 401, revoked key returns 401, insufficient scope returns -32002 (~2h)
- [ ] Test rate limiting: exceed limit → get -32000 error → wait for window reset → succeed again (~2h)
- [ ] Test plan gating: free=read-only tools only, starter=all built-in, pro=custom tools, enterprise=unlimited (~2h)
- [ ] Test SSRF protection: custom tool targeting localhost/internal IPs → blocked, external URL → allowed (~1h)
- [ ] Test concurrent connections: 10 simultaneous MCP clients → verify isolation and no cross-org data leakage (~2h)
- [ ] Load test: 100 concurrent tool calls → verify no request loss, rate limiter accuracy, log completeness (~2h)
- [ ] Test custom tool secrets: create secret → use in HTTP tool → verify secret resolved → verify never logged (~2h)
- [ ] Documentation: MCP setup guides for Claude Desktop/Cursor/Windsurf, custom tool authoring guide, API reference (~3h)

**Total estimated effort: ~28 days**

---

*Generated: 05 Jul 2026*
*Ref: APP_ARCHITECTURE.md, ai-engine-improvements.md, product-factory-implementation.md*
