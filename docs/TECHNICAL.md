# Technical Documentation — mcp-wacli

## 1. System overview

mcp-wacli is a thin Python MCP server that wraps the [wacli](https://github.com/steipete/wacli) Go binary. It translates MCP tool calls into `wacli --json` subprocess invocations and returns the JSON output to the MCP client.

### 1.1 Component diagram

```
┌─────────────────────────────────────────────────────────┐
│  AI Client Machine (e.g. Mac)                           │
│                                                         │
│  ┌───────────────────┐                                  │
│  │  Claude Code /    │                                  │
│  │  Claude Desktop / │                                  │
│  │  Cursor / Cline   │                                  │
│  └────────┬──────────┘                                  │
│           │ MCP protocol (JSON-RPC 2.0 over stdin/stdout)│
│           │ transported via SSH                          │
└───────────┼─────────────────────────────────────────────┘
            │
            ▼ SSH
┌─────────────────────────────────────────────────────────┐
│  Server Machine (e.g. Linux headless)                   │
│                                                         │
│  ┌───────────────────┐    subprocess     ┌────────────┐ │
│  │  server.py        │ ──────────────▶   │  wacli     │ │
│  │  (Python FastMCP) │    --json         │  (Go bin)  │ │
│  │  27 tools         │ ◀──────────────   │            │ │
│  └───────────────────┘    JSON stdout    └─────┬──────┘ │
│                                                │        │
│                                          ┌─────▼──────┐ │
│                                          │ ~/.wacli/  │ │
│                                          │ session.db │ │
│                                          │ wacli.db   │ │
│                                          │ media/     │ │
│                                          └─────┬──────┘ │
│                                                │        │
│                                          whatsmeow      │
│                                          WebSocket       │
└────────────────────────────────────────────────┼────────┘
                                                 │
                                                 ▼
                                        WhatsApp Servers
```

### 1.2 Data flow

1. **AI client** sends a JSON-RPC `tools/call` message over stdin (via SSH)
2. **server.py** receives it, maps the tool name to a wacli command
3. **subprocess** runs `wacli --json <subcommand> [flags]`
4. **wacli** reads from local SQLite DB or connects to WhatsApp (for live operations)
5. **JSON stdout** from wacli is captured and returned as MCP tool result
6. **AI client** receives the response and incorporates it into the conversation

### 1.3 Transport modes

#### stdio (default) — SSH or local

MCP uses stdio (stdin/stdout) as its default transport. When the server runs on a remote machine, SSH acts as a transparent pipe:

```
Client stdin  →  SSH  →  Remote server.py stdin
Client stdout ←  SSH  ←  Remote server.py stdout
```

No ports, no HTTP, no API keys — SSH handles authentication and encryption.

#### HTTP/SSE — network access with Bearer auth

When started with `--http`, the server runs an HTTP server with SSE (Server-Sent Events) transport:

```
Client  ──HTTP POST──▶  server.py:9800/messages
Client  ◀──SSE stream──  server.py:9800/sse
```

**Authentication:** Every HTTP request must include `Authorization: Bearer <token>`. The token is auto-generated on first run and saved to `~/.mcp-wacli-token` (chmod 600).

**Security model:**
- Token is a 32-character `secrets.token_urlsafe()` — 192 bits of entropy
- Token file is readable only by the owner (mode 0600)
- Requests without a valid token receive HTTP 401
- Bind to Tailscale IP (`MCP_HOST=100.x.x.x`) to restrict network access

**Configuration:**

| Env variable | Default | Description |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `9800` | Listen port |

**Running as a systemd service:**

```ini
[Unit]
Description=mcp-wacli HTTP/SSE server
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/user/mcp-wacli
ExecStart=/home/user/.local/bin/uv run server.py --http
Environment=MCP_HOST=0.0.0.0
Environment=MCP_PORT=9800
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

## 2. File structure

```
mcp-wacli/
├── server.py           # MCP server — all tool definitions
├── pyproject.toml      # Python project metadata & dependencies
├── .python-version     # Python version pin (3.11)
├── README.md           # User-facing documentation
└── docs/
    ├── TECHNICAL.md    # This file
    └── USER_GUIDE.md   # End-user guide
```

## 3. server.py — detailed design

### 3.1 The `_run()` helper

All tools delegate to a single helper function:

```python
def _run(args: list[str], timeout: int = WACLI_TIMEOUT) -> dict[str, Any]:
```

**Behavior:**
- Prepends `wacli --json` to the argument list
- Runs the command via `subprocess.run()` with capture
- Parses stdout as JSON (wacli always returns `{"success": bool, "data": ..., "error": ...}`)
- Handles timeouts, JSON parse errors, and empty output gracefully
- Returns a normalized dict that MCP serializes as the tool result

**Timeout strategy:**
- Default: 30 seconds (sufficient for local DB reads)
- `sync_once`: 120 seconds (network operations)
- `history_backfill`: 60 seconds (network + processing)

### 3.2 Tool categories

| Category     | Count | wacli subcommand  | Network required |
|--------------|-------|-------------------|------------------|
| Chats        | 2     | `chats`           | No (local DB)    |
| Messages     | 4     | `messages`        | No (local DB)    |
| Contacts     | 5     | `contacts`        | No (local DB)    |
| Send         | 2     | `send`            | Yes              |
| Groups       | 9     | `groups`          | Mixed            |
| Media        | 1     | `media`           | Yes              |
| Sync/History | 2     | `sync`, `history` | Yes              |
| Diagnostics  | 2     | `doctor`, `auth`  | No               |
| **Total**    | **27**|                   |                  |

### 3.3 Error handling

The server never crashes on wacli failures. All errors are returned as structured JSON:

```json
{
  "success": false,
  "data": null,
  "error": "description of what went wrong"
}
```

Error sources:
- **Timeout**: `subprocess.TimeoutExpired` — returns timeout error
- **Parse failure**: `json.JSONDecodeError` — returns first 500 chars of raw output
- **wacli error**: wacli's own error JSON is passed through
- **Missing binary**: `FileNotFoundError` — caught by generic exception handler

## 4. wacli internals (relevant for maintainers)

### 4.1 Storage layout

```
~/.wacli/
├── session.db    # whatsmeow session data (auth tokens, device keys)
├── wacli.db      # Messages, contacts, groups (SQLite, optional FTS5)
├── media/        # Downloaded media files
└── LOCK          # PID lock file (prevents concurrent access)
```

### 4.2 LOCK file behavior

wacli uses a file lock to prevent concurrent writes. Important implications:
- If `wacli sync` is running, read-only commands still work
- Two write commands cannot run simultaneously
- The MCP server runs commands sequentially (one subprocess at a time per request)
- If wacli crashes, a stale LOCK file may need manual removal

### 4.3 JID format

WhatsApp identifies entities with JIDs (Jabber IDs):

| Entity     | Format                        | Example                        |
|------------|-------------------------------|--------------------------------|
| Individual | `{countrycode}{number}@s.whatsapp.net` | `573001234567@s.whatsapp.net` |
| Group      | `{groupid}@g.us`              | `120363001234567890@g.us`      |
| Broadcast  | `{id}@broadcast`              | `status@broadcast`             |

### 4.4 JSON output contract

All wacli `--json` commands return:

```json
{
  "success": true | false,
  "data": { ... } | [ ... ] | null,
  "error": "string" | null
}
```

This contract is relied upon by `_run()` for transparent passthrough.

### 4.5 FTS5 vs LIKE search

wacli supports two search modes:
- **FTS5**: Full-text search with SQLite's FTS5 extension. Requires the SQLite build to include FTS5 support. Supports ranking, snippets, and prefix matching.
- **LIKE fallback**: Simple `LIKE '%query%'` when FTS5 is unavailable. Slower on large databases, no ranking.

Check status with `wacli doctor --json` → `data.fts_enabled`.

## 5. Deployment patterns

### 5.1 Remote headless server (recommended)

```
Mac (Claude Code) ──SSH──▶ Linux server (wacli + mcp-wacli)
```

**Pros:** Always on, shared across devices, single WhatsApp session
**Cons:** Requires SSH access, initial QR scan needs terminal access

### 5.2 Local (same machine)

```
Mac (Claude Code) ──stdio──▶ Local (wacli + mcp-wacli)
```

**Pros:** Simplest setup, no SSH
**Cons:** Must have wacli and Go installed locally

### 5.3 Docker (future)

Not yet implemented. Would require mounting `~/.wacli/` as a volume for session persistence.

## 6. Session lifecycle

```
                 ┌──────────┐
                 │ wacli    │
                 │ auth     │◀──── Scan QR with phone
                 └────┬─────┘
                      │ session.db created
                      ▼
                 ┌──────────┐
                 │ wacli    │
                 │ sync     │◀──── Messages flow in
                 └────┬─────┘
                      │ wacli.db populated
                      ▼
                 ┌──────────┐
                 │ mcp-wacli│
                 │ server.py│◀──── AI client queries & sends
                 └────┬─────┘
                      │
              ┌───────┴────────┐
              ▼                ▼
    Read tools (local DB)   Write tools (network)
    - list_chats            - send_message
    - search_messages       - send_file
    - list_groups           - group_rename
    - ...                   - sync_once
                            - ...
```

Session expires after ~20 days. Re-authenticate with `wacli auth`.

## 7. Extending the server

### 7.1 Adding a new tool

1. Identify the wacli command: `wacli <cmd> <subcmd> --help`
2. Add a function in `server.py` with `@mcp.tool()` decorator
3. Map parameters to wacli flags
4. Call `_run([...args...])`

Example:

```python
@mcp.tool()
def my_new_tool(param: str) -> dict:
    """Description for the AI to understand when to use this tool.

    Args:
        param: What this parameter does
    """
    return _run(["subcommand", "action", "--flag", param])
```

### 7.2 Testing a tool manually

```bash
# Initialize + call a tool via stdin
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}\n{"jsonrpc":"2.0","id":2,"method":"notifications/initialized"}\n{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"doctor","arguments":{}}}\n' | uv run server.py
```

### 7.3 Upgrading wacli

```bash
# Check current version
wacli version

# Update (if installed via go install)
go install github.com/steipete/wacli@latest

# Verify
wacli doctor --json
```

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `"error": "timeout after 30s"` | wacli command hung (LOCK or network) | Check if `wacli sync` is holding the lock; kill stale processes |
| `"authenticated": false` | Session expired | Run `wacli auth` and scan QR |
| `"fts_enabled": false` | SQLite without FTS5 | Rebuild SQLite with FTS5 or use LIKE fallback (automatic) |
| `exit code 1` with no output | wacli binary not found or crashed | Verify `which wacli` and check stderr |
| SSH connection refused | Server down or SSH misconfigured | Check SSH config and server uptime |
| `Client Outdated (405)` | WhatsApp rejected protocol version | Update wacli to latest version |
