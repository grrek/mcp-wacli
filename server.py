"""
mcp-wacli — MCP server wrapper for wacli (WhatsApp CLI).

Exposes wacli commands as MCP tools so any MCP-compatible LLM client
(Claude Code, Claude Desktop, Cursor, etc.) can interact with WhatsApp
through a locally authenticated wacli session.

Repository: https://github.com/user/mcp-wacli
Upstream:   https://github.com/steipete/wacli
"""

import json
import subprocess
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

WACLI_BIN = "wacli"
WACLI_TIMEOUT = 30  # seconds per command

mcp = FastMCP("whatsapp-wacli")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run(args: list[str], timeout: int = WACLI_TIMEOUT) -> dict[str, Any]:
    """Run a wacli command with --json and return parsed output."""
    cmd = [WACLI_BIN, "--json"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # wacli --json always returns {"success":bool,"data":...,"error":...}
        if result.stdout.strip():
            return json.loads(result.stdout)
        if result.stderr.strip():
            return {"success": False, "data": None, "error": result.stderr.strip()}
        return {"success": False, "data": None, "error": f"exit code {result.returncode}"}
    except subprocess.TimeoutExpired:
        return {"success": False, "data": None, "error": f"timeout after {timeout}s"}
    except json.JSONDecodeError as e:
        return {"success": False, "data": result.stdout[:500], "error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"success": False, "data": None, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# CHATS (2 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_chats(query: Optional[str] = None, limit: int = 50) -> dict:
    """List WhatsApp chats from local DB.

    Args:
        query: Optional search string to filter chats by name
        limit: Max number of chats to return (default 50)
    """
    args = ["chats", "list", "--limit", str(limit)]
    if query:
        args += ["--query", query]
    return _run(args)


@mcp.tool()
def show_chat(jid: str) -> dict:
    """Show details of a single chat.

    Args:
        jid: Chat JID (e.g. '573001234567@s.whatsapp.net' or '...@g.us' for groups)
    """
    return _run(["chats", "show", "--jid", jid])


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGES (4 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_messages(
    chat: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """List recent WhatsApp messages with optional filters.

    Args:
        chat: Optional chat JID to filter by
        after: Only messages after this date (YYYY-MM-DD or RFC3339)
        before: Only messages before this date (YYYY-MM-DD or RFC3339)
        limit: Max results (default 50)
    """
    args = ["messages", "list", "--limit", str(limit)]
    if chat:
        args += ["--chat", chat]
    if after:
        args += ["--after", after]
    if before:
        args += ["--before", before]
    return _run(args)


@mcp.tool()
def search_messages(
    query: str,
    chat: Optional[str] = None,
    sender: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    media_type: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Full-text search across WhatsApp messages (FTS5 if available, LIKE fallback).

    Args:
        query: Search text
        chat: Optional chat JID filter
        sender: Optional sender JID filter
        after: Only after this date (YYYY-MM-DD or RFC3339)
        before: Only before this date (YYYY-MM-DD or RFC3339)
        media_type: Filter by media type (image|video|audio|document)
        limit: Max results (default 50)
    """
    args = ["messages", "search", query, "--limit", str(limit)]
    if chat:
        args += ["--chat", chat]
    if sender:
        args += ["--from", sender]
    if after:
        args += ["--after", after]
    if before:
        args += ["--before", before]
    if media_type:
        args += ["--type", media_type]
    return _run(args)


@mcp.tool()
def show_message(message_id: str, chat: str) -> dict:
    """Show details of a single message.

    Args:
        message_id: The message ID
        chat: Chat JID where the message is
    """
    return _run(["messages", "show", "--id", message_id, "--chat", chat])


@mcp.tool()
def message_context(
    message_id: str,
    chat: str,
    before: int = 5,
    after: int = 5,
) -> dict:
    """Show surrounding messages around a specific message ID for context.

    Args:
        message_id: The message ID to center on
        chat: Chat JID where the message is
        before: Number of messages before (default 5)
        after: Number of messages after (default 5)
    """
    return _run([
        "messages", "context",
        "--id", message_id,
        "--chat", chat,
        "--before", str(before),
        "--after", str(after),
    ])


# ═══════════════════════════════════════════════════════════════════════════
# CONTACTS (5 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def search_contacts(query: str, limit: int = 50) -> dict:
    """Search WhatsApp contacts by name or phone number.

    Args:
        query: Search term
        limit: Max results (default 50)
    """
    return _run(["contacts", "search", query, "--limit", str(limit)])


@mcp.tool()
def show_contact(jid: str) -> dict:
    """Show details of a single contact.

    Args:
        jid: Contact JID (e.g. '573001234567@s.whatsapp.net')
    """
    return _run(["contacts", "show", "--jid", jid])


@mcp.tool()
def set_contact_alias(jid: str, alias: str) -> dict:
    """Set a local alias (nickname) for a contact.

    Args:
        jid: Contact JID
        alias: Alias to set
    """
    return _run(["contacts", "alias", "set", "--jid", jid, "--alias", alias])


@mcp.tool()
def remove_contact_alias(jid: str) -> dict:
    """Remove a local alias from a contact.

    Args:
        jid: Contact JID
    """
    return _run(["contacts", "alias", "rm", "--jid", jid])


@mcp.tool()
def refresh_contacts() -> dict:
    """Import/refresh contacts from the WhatsApp session store into local DB."""
    return _run(["contacts", "refresh"])


# ═══════════════════════════════════════════════════════════════════════════
# SEND (2 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def send_message(to: str, message: str) -> dict:
    """Send a text message via WhatsApp.

    Args:
        to: Recipient phone number (e.g. '573001234567') or JID
        message: Text message to send
    """
    return _run(["send", "text", "--to", to, "--message", message])


@mcp.tool()
def send_file(
    to: str,
    file_path: str,
    caption: Optional[str] = None,
    filename: Optional[str] = None,
    mime: Optional[str] = None,
) -> dict:
    """Send a file (image, video, audio, document) via WhatsApp.

    Args:
        to: Recipient phone number or JID
        file_path: Path to the file on the server
        caption: Optional caption for the file
        filename: Optional display name (defaults to file basename)
        mime: Optional MIME type override
    """
    args = ["send", "file", "--to", to, "--file", file_path]
    if caption:
        args += ["--caption", caption]
    if filename:
        args += ["--filename", filename]
    if mime:
        args += ["--mime", mime]
    return _run(args)


# ═══════════════════════════════════════════════════════════════════════════
# GROUPS (9 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def list_groups(query: Optional[str] = None, limit: int = 50) -> dict:
    """List WhatsApp groups from local DB.

    Args:
        query: Optional search string to filter groups
        limit: Max results (default 50)
    """
    args = ["groups", "list", "--limit", str(limit)]
    if query:
        args += ["--query", query]
    return _run(args)


@mcp.tool()
def group_info(jid: str) -> dict:
    """Fetch live group info from WhatsApp and update local DB.

    Args:
        jid: Group JID (e.g. '120363001234567890@g.us')
    """
    return _run(["groups", "info", "--jid", jid])


@mcp.tool()
def group_rename(jid: str, name: str) -> dict:
    """Rename a WhatsApp group.

    Args:
        jid: Group JID
        name: New group name
    """
    return _run(["groups", "rename", "--jid", jid, "--name", name])


@mcp.tool()
def group_leave(jid: str) -> dict:
    """Leave a WhatsApp group.

    Args:
        jid: Group JID
    """
    return _run(["groups", "leave", "--jid", jid])


@mcp.tool()
def group_join(code: str) -> dict:
    """Join a WhatsApp group by invite code.

    Args:
        code: Invite code from a group link (the part after https://chat.whatsapp.com/)
    """
    return _run(["groups", "join", "--code", code])


@mcp.tool()
def group_participants_add(jid: str, users: list[str]) -> dict:
    """Add participants to a WhatsApp group.

    Args:
        jid: Group JID
        users: List of phone numbers or JIDs to add
    """
    args = ["groups", "participants", "add", "--jid", jid]
    for user in users:
        args += ["--user", user]
    return _run(args)


@mcp.tool()
def group_participants_remove(jid: str, users: list[str]) -> dict:
    """Remove participants from a WhatsApp group.

    Args:
        jid: Group JID
        users: List of phone numbers or JIDs to remove
    """
    args = ["groups", "participants", "remove", "--jid", jid]
    for user in users:
        args += ["--user", user]
    return _run(args)


@mcp.tool()
def group_participants_promote(jid: str, users: list[str]) -> dict:
    """Promote participants to admin in a WhatsApp group.

    Args:
        jid: Group JID
        users: List of phone numbers or JIDs to promote
    """
    args = ["groups", "participants", "promote", "--jid", jid]
    for user in users:
        args += ["--user", user]
    return _run(args)


@mcp.tool()
def group_participants_demote(jid: str, users: list[str]) -> dict:
    """Demote admin participants in a WhatsApp group.

    Args:
        jid: Group JID
        users: List of phone numbers or JIDs to demote
    """
    args = ["groups", "participants", "demote", "--jid", jid]
    for user in users:
        args += ["--user", user]
    return _run(args)


# ═══════════════════════════════════════════════════════════════════════════
# MEDIA (1 tool)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def download_media(message_id: str, chat: str, output: Optional[str] = None) -> dict:
    """Download media from a WhatsApp message.

    Args:
        message_id: The message ID containing media
        chat: Chat JID where the message is
        output: Optional output file or directory (defaults to wacli media dir)
    """
    args = ["media", "download", "--id", message_id, "--chat", chat]
    if output:
        args += ["--output", output]
    return _run(args)


# ═══════════════════════════════════════════════════════════════════════════
# SYNC & HISTORY (2 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def sync_once(
    refresh_contacts: bool = False,
    refresh_groups: bool = False,
    download_media: bool = False,
) -> dict:
    """Sync messages once (connect, fetch new messages, then exit).

    Args:
        refresh_contacts: Also refresh contacts from session store
        refresh_groups: Also refresh joined groups (live)
        download_media: Download media in the background during sync
    """
    args = ["sync", "--once"]
    if refresh_contacts:
        args.append("--refresh-contacts")
    if refresh_groups:
        args.append("--refresh-groups")
    if download_media:
        args.append("--download-media")
    return _run(args, timeout=120)


@mcp.tool()
def history_backfill(chat: str) -> dict:
    """Request older messages for a chat from your primary device (best-effort).

    Args:
        chat: Chat JID to backfill history for
    """
    return _run(["history", "backfill", "--chat", chat], timeout=60)


# ═══════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS (2 tools)
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
def doctor() -> dict:
    """Run wacli diagnostics — check store, authentication, and search capabilities."""
    return _run(["doctor"])


@mcp.tool()
def auth_status() -> dict:
    """Show authentication status of the current wacli session."""
    return _run(["auth", "status"])


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mcp.run()
