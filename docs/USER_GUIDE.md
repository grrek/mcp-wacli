# User Guide — mcp-wacli

This guide explains how to use the WhatsApp MCP integration from your AI assistant (Claude Code, Claude Desktop, Cursor, or any MCP-compatible client).

## Getting started

Once configured, you can interact with WhatsApp using natural language. The AI assistant has access to 27 tools organized into 8 categories.

## What you can do

### Read your messages

Ask the AI to show you recent messages or search for specific content:

```
> Show me my WhatsApp chats

> What messages did I get today?

> Search my WhatsApp for messages about "meeting" from last week

> Show me the last 10 messages from the family group

> Find all audio messages from Maria
```

### Send messages

The AI will always ask for your confirmation before sending:

```
> Send Aurora a message saying "I'm running 10 minutes late"

> Send a message to +573001234567: "The report is ready"

> Send the file /tmp/report.pdf to the work group with caption "Q4 Report"
```

### Manage contacts

```
> Search for contacts named "Carlos"

> Show me the details of contact 573001234567

> Set an alias "Boss" for contact 573009876543@s.whatsapp.net

> Refresh my contacts list
```

### Work with groups

```
> List all my WhatsApp groups

> Show me info about the "Project Alpha" group

> Who are the members of the family group?

> Add +573001234567 to the work group

> Promote Maria to admin in the team group

> Rename the group to "Q1 Planning"
```

### Download media

```
> Download the image from the last message in Aurora's chat

> Get the document that was sent in the work group yesterday
```

### Sync & diagnostics

```
> Sync my WhatsApp messages

> Run WhatsApp diagnostics

> Check if my WhatsApp session is still authenticated

> Backfill history for Aurora's chat
```

## Understanding JIDs

WhatsApp uses JIDs (Jabber IDs) internally to identify chats. You don't usually need to know these — the AI will resolve names for you. But if you see them:

| What you see | What it means |
|---|---|
| `573001234567@s.whatsapp.net` | Individual chat with +57 300 123 4567 |
| `120363001234567890@g.us` | A group chat |
| Phone number like `573001234567` | Can be used directly for sending |

## Tips for effective use

### Be specific with dates

```
# Good
> Messages from Aurora after 2026-03-01

# Better
> Messages from Aurora between 2026-03-01 and 2026-03-07
```

### Search efficiently

```
# Good — uses full-text search
> Search messages for "invoice"

# Better — narrowed to a specific chat and date range
> Search messages for "invoice" in the work group from last month
```

### Group management

```
# Use phone numbers with country code (no + sign, no spaces)
> Add 573001234567 to the project group

# Or ask the AI to look up contacts first
> Find Carlos's number and add him to the project group
```

## How syncing works

The WhatsApp data on the server comes from `wacli sync`. For the most recent messages:

1. If `wacli sync` is running in the background, data is always fresh
2. If not, use the `sync_once` tool: *"Sync my WhatsApp messages"*
3. The sync connects to WhatsApp, fetches new messages, and disconnects

**Important:** `sync_once` requires that `wacli sync` is not already running (they share a lock file).

## Privacy & security

- **All data is local**: Messages are stored in `~/.wacli/` on your server
- **On-demand access**: The AI only sees messages when you ask it to use a WhatsApp tool
- **No cloud storage**: Nothing is uploaded to third-party services
- **Send confirmation**: The AI should always confirm before sending messages
- **Your session**: Uses the same WhatsApp session as your existing wacli setup
- **Bearer token**: HTTP mode requires a 192-bit token for every request. The token is stored locally with owner-only permissions
- **Network isolation**: Recommended to run behind a VPN (e.g. Tailscale) rather than on the public internet

## Connection modes

### HTTP/SSE (recommended)

The MCP server runs as a persistent service on your server. Your AI client connects over the network with a Bearer token. Best for:
- Always-on access without SSH
- Connecting from multiple AI clients
- Non-Anthropic LLMs (GPT, Gemini, etc.)

### SSH (stdio)

Claude Code opens an SSH connection and runs the MCP server on-demand. Best for:
- Simple setup (no systemd, no tokens)
- Single-user access with existing SSH keys

### Local (stdio)

If wacli and mcp-wacli are on the same machine, they communicate directly via stdio. Best for:
- Development and testing
- Local-only setups

## Server management (HTTP mode)

If the MCP server runs as a systemd service:

```bash
# Check if the server is running
ssh your-server "systemctl --user status mcp-wacli"

# View recent logs
ssh your-server "journalctl --user -u mcp-wacli --since '1 hour ago'"

# Restart after updates
ssh your-server "systemctl --user restart mcp-wacli"

# Read the Bearer token
ssh your-server "cat ~/.mcp-wacli-token"
```

## Session expiration

WhatsApp sessions expire approximately every 20 days. When this happens:

1. You'll see authentication errors in tool responses
2. SSH into the server: `ssh your-server`
3. Re-authenticate: `wacli auth`
4. Scan the QR code with your phone (WhatsApp > Linked Devices > Link Device)
5. Wait for sync to complete
6. You're back in business

## Troubleshooting

### "The tool returned an error"

Run diagnostics:
```
> Run WhatsApp diagnostics
```

This calls `wacli doctor` and shows:
- Whether the store directory exists
- Whether you're authenticated
- Whether full-text search is available

### "No messages found"

Messages might not be synced yet:
```
> Sync my WhatsApp messages
```

### "Timeout" errors

Some operations take longer (sync, media download). The server has generous timeouts, but if the WhatsApp connection is slow, it may still time out. Try again.

### Messages seem stale

If you're not running `wacli sync` in the background, messages in the local DB may be old. Either:
- Start a background sync: `wacli sync --follow` on the server
- Or ask the AI to sync: *"Sync my WhatsApp messages"*

### MCP not connecting (HTTP mode)

1. Verify the server is running: `systemctl --user status mcp-wacli`
2. Test connectivity: `curl -H "Authorization: Bearer YOUR_TOKEN" http://YOUR_SERVER:9800/sse`
3. Check the token matches: compare `~/.mcp-wacli-token` on the server with your client config
4. Ensure VPN (Tailscale) is connected if the server is behind one

### MCP not connecting (SSH mode)

1. Test SSH manually: `ssh your-server "echo ok"`
2. Check for stderr noise: `ssh -o LogLevel=ERROR -o ClearAllForwardings=yes your-server "echo ok" 2>&1`
3. Verify uv is in PATH: `ssh your-server "export PATH=\$HOME/.local/bin:\$PATH && which uv"`

## Limitations

1. **Not real-time**: This is query-based, not push-based. You ask, it checks.
2. **Text messages only for send**: You can send text and files, but not reactions, polls, or status updates.
3. **No call support**: Voice and video calls are not supported.
4. **No message editing/deletion**: Once sent, messages cannot be edited or deleted through this interface.
5. **Unofficial API**: wacli uses the unofficial WhatsApp Web protocol. WhatsApp could change it at any time.
