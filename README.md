# mcp-wacli

MCP (Model Context Protocol) server that wraps [wacli](https://github.com/steipete/wacli) — a WhatsApp CLI built on [whatsmeow](https://github.com/tulir/whatsmeow). Lets any MCP-compatible AI client (Claude Code, Claude Desktop, Cursor, Cline, etc.) read, search, and send WhatsApp messages through your personal account.

## Why a wrapper?

Instead of reimplementing the WhatsApp Web protocol, mcp-wacli delegates everything to wacli's `--json` mode. This means:

- **Zero duplicate sessions** — uses the same authenticated session as your existing wacli install
- **Zero data duplication** — one SQLite DB, shared with wacli
- **Full feature parity** — any wacli command becomes an MCP tool
- **Tiny codebase** — ~300 lines of Python glue

## Architecture

```
AI Client (Claude Code / Desktop / Cursor)
  │  MCP protocol (stdin/stdout over SSH)
  ▼
server.py (Python — FastMCP)
  │  subprocess calls
  ▼
wacli --json (Go binary, locally installed)
  │  whatsmeow protocol
  ▼
WhatsApp Web Multi-Device API
  │
  ▼
Your WhatsApp account
```

All data stays local. Messages are only sent to the AI when it explicitly invokes a tool.

## Prerequisites

| Dependency | Version  | Notes                          |
|------------|----------|--------------------------------|
| wacli      | dev+     | Must be authenticated (`wacli auth`) |
| Python     | >= 3.11  | Managed by uv                  |
| uv         | >= 0.10  | Python package manager         |

## Quick start

```bash
# 1. Clone
git clone https://github.com/user/mcp-wacli.git
cd mcp-wacli

# 2. Install dependencies
uv sync

# 3. Verify wacli is authenticated
wacli doctor --json

# 4. Test the MCP server
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run server.py
```

## Configure your AI client

### Claude Code (global — all projects)

Edit `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "ssh",
      "args": [
        "your-server",
        "PATH=$HOME/.local/bin:$PATH cd ~/mcp-wacli && uv run server.py"
      ]
    }
  }
}
```

### Claude Code (project-only)

Edit `.claude/settings.json` in your project root with the same structure.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "ssh",
      "args": [
        "your-server",
        "PATH=$HOME/.local/bin:$PATH cd ~/mcp-wacli && uv run server.py"
      ]
    }
  }
}
```

### Local (no SSH)

If wacli and mcp-wacli are on the same machine:

```json
{
  "mcpServers": {
    "whatsapp": {
      "command": "uv",
      "args": ["run", "server.py"],
      "cwd": "/path/to/mcp-wacli"
    }
  }
}
```

## Available tools (27)

### Chats (2)

| Tool | Description |
|------|-------------|
| `list_chats` | List chats with optional name search |
| `show_chat` | Show details of a single chat by JID |

### Messages (4)

| Tool | Description |
|------|-------------|
| `list_messages` | List recent messages with date/chat filters |
| `search_messages` | Full-text search (FTS5 or LIKE fallback) |
| `show_message` | Show a single message by ID |
| `message_context` | Show surrounding messages for context |

### Contacts (5)

| Tool | Description |
|------|-------------|
| `search_contacts` | Search contacts by name or phone |
| `show_contact` | Show contact details by JID |
| `set_contact_alias` | Set a local nickname for a contact |
| `remove_contact_alias` | Remove a local nickname |
| `refresh_contacts` | Re-import contacts from session store |

### Send (2)

| Tool | Description |
|------|-------------|
| `send_message` | Send a text message |
| `send_file` | Send image, video, audio, or document |

### Groups (9)

| Tool | Description |
|------|-------------|
| `list_groups` | List groups with optional search |
| `group_info` | Fetch live group info |
| `group_rename` | Rename a group |
| `group_leave` | Leave a group |
| `group_join` | Join a group by invite code |
| `group_participants_add` | Add members to a group |
| `group_participants_remove` | Remove members from a group |
| `group_participants_promote` | Promote members to admin |
| `group_participants_demote` | Demote admins |

### Media (1)

| Tool | Description |
|------|-------------|
| `download_media` | Download media from a message |

### Sync & History (2)

| Tool | Description |
|------|-------------|
| `sync_once` | Sync new messages (connect, fetch, exit) |
| `history_backfill` | Request older messages from primary device |

### Diagnostics (2)

| Tool | Description |
|------|-------------|
| `doctor` | Check store, auth, and search status |
| `auth_status` | Show authentication status |

## Usage examples

Once configured, you can ask your AI client things like:

- *"Show me my recent WhatsApp chats"*
- *"Search my messages for 'invoice' from last week"*
- *"Send Aurora a message saying I'll be 10 minutes late"*
- *"List all my WhatsApp groups"*
- *"Who are the participants in the family group?"*
- *"Download the image from that last message"*

## JID format reference

| Type | Format | Example |
|------|--------|---------|
| Individual | `{country}{number}@s.whatsapp.net` | `573001234567@s.whatsapp.net` |
| Group | `{id}@g.us` | `120363001234567890@g.us` |
| Phone number | `{country}{number}` | `573001234567` |

## Security considerations

- All messages are stored locally in `~/.wacli/`
- Data is only sent to the AI model when a tool is explicitly invoked
- No data leaves the machine except through WhatsApp's own protocol and MCP tool calls
- The `send_message` and `send_file` tools require the AI client to request permission before execution
- wacli uses the unofficial WhatsApp Web API — use at your own risk

## Known limitations

- **Re-authentication**: WhatsApp sessions expire every ~20 days. Re-scan QR with `wacli auth`
- **Client outdated errors**: WhatsApp updates protocol versions. Keep wacli updated
- **FTS5**: Full-text search requires SQLite compiled with FTS5 support. Falls back to LIKE
- **No real-time events**: This is a pull-based model (query when asked), not push-based
- **wacli sync must run**: For fresh messages, `wacli sync` should be running or `sync_once` must be called

## License

MIT
