#!/usr/bin/env python3
"""Outlook Mail CLI — read-only access to Microsoft 365 mailbox.

Uses MSAL device-code flow for auth. Token is cached persistently.
All output is JSON for easy parsing by ClaudeClaw.

Usage:
    python outlook_mail.py auth                                    # Authenticate (one-time)
    python outlook_mail.py list [--hours N] [--all] [--folder NAME]  # List messages
    python outlook_mail.py read <message_id>                       # Read full message
    python outlook_mail.py search --query "keyword" [--from "sender"] [--subject "text"]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import msal
import requests

from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read"]
TIMEZONE = "America/New_York"

def _env_path():
    """Load env vars from ClaudeClaw .env if CLAUDECLAW_DIR is set."""
    claw_dir = os.environ.get("CLAUDECLAW_DIR")
    if not claw_dir:
        return
    env_file = os.path.join(os.path.expanduser(claw_dir), ".env")
    if not os.path.isfile(env_file):
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if key and val and key not in os.environ:
                os.environ[key] = val

_env_path()

CLIENT_ID = os.environ.get("OUTLOOK_CLIENT_ID", "")
TENANT_ID = os.environ.get("OUTLOOK_TENANT_ID", "")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}" if TENANT_ID else ""

TOKEN_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".config", "mail", "outlook_token_cache.json")

# ---------------------------------------------------------------------------
# Token cache  (plain-file persistence)
# ---------------------------------------------------------------------------

def _build_cache():
    cache = msal.SerializableTokenCache()
    if os.path.isfile(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE) as f:
            cache.deserialize(f.read())
    return cache

def _save_cache(cache):
    if cache.has_state_changed:
        os.makedirs(os.path.dirname(TOKEN_CACHE_FILE), exist_ok=True)
        with open(TOKEN_CACHE_FILE, "w") as f:
            f.write(cache.serialize())

def _build_app(cache=None):
    if not CLIENT_ID or not TENANT_ID:
        _die("OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID must be set in .env")
    return msal.PublicClientApplication(
        CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache,
    )

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _get_token():
    """Return a valid access token, using cache if possible."""
    cache = _build_cache()
    app = _build_app(cache)
    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        _die("Not authenticated. Run: python outlook_mail.py auth")
    _save_cache(cache)
    return result["access_token"]

def _headers():
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Prefer": f'outlook.timezone="{TIMEZONE}"',
    }

def _die(msg):
    print(json.dumps({"error": msg}))
    sys.exit(1)

def _graph_get(path, params=None):
    r = requests.get(f"{GRAPH_BASE}{path}", headers=_headers(), params=params or {})
    if r.status_code != 200:
        _die(f"Graph API error {r.status_code}: {r.text[:300]}")
    return r.json()

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_auth(_args):
    """Authenticate via device-code flow."""
    cache = _build_cache()
    app = _build_app(cache)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        _die(f"Device flow failed: {flow.get('error_description', 'unknown error')}")

    print(flow["message"], file=sys.stderr)
    result = app.acquire_token_by_device_flow(flow)
    _save_cache(cache)

    if "access_token" in result:
        print(json.dumps({"status": "authenticated", "account": result.get("id_token_claims", {}).get("preferred_username", "unknown")}))
    else:
        _die(f"Auth failed: {result.get('error_description', result.get('error', 'unknown'))}")

def cmd_list(args):
    """List inbox messages."""
    local_tz = ZoneInfo(TIMEZONE)
    now = datetime.now(local_tz)

    folder = args.folder or "inbox"
    folder_path = f"/me/mailFolders/{folder}/messages"

    select_fields = "id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview,importance"

    params = {
        "$orderby": "receivedDateTime desc",
        "$top": 50,
        "$select": select_fields,
    }

    if not args.all:
        hours = args.hours or 48
        cutoff = now - timedelta(hours=hours)
        params["$filter"] = f"receivedDateTime ge {cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}"

    data = _graph_get(folder_path, params)
    messages = []
    for msg in data.get("value", []):
        messages.append(_format_message(msg))

    output = {
        "current_time": now.strftime("%A, %B %d, %Y %I:%M %p %Z").replace(" 0", " "),
        "timezone": TIMEZONE,
        "folder": folder,
        "count": len(messages),
        "messages": messages,
    }
    print(json.dumps(output, indent=2))

def cmd_read(args):
    """Read full message by ID."""
    if not args.message_id:
        _die("message_id is required")
    data = _graph_get(f"/me/messages/{args.message_id}")
    print(json.dumps(_format_message(data, full=True), indent=2))

def cmd_search(args):
    """Search messages via Graph API."""
    local_tz = ZoneInfo(TIMEZONE)
    now = datetime.now(local_tz)

    # Build $search query -- Graph API uses KQL syntax
    search_parts = []
    if args.query:
        search_parts.append(f'"{args.query}"')
    if args.sender:
        search_parts.append(f'from:"{args.sender}"')
    if args.subject:
        search_parts.append(f'subject:"{args.subject}"')

    if not search_parts:
        _die("At least --query, --from, or --subject is required")

    search_string = " AND ".join(search_parts)

    params = {
        "$search": search_string,
        "$top": 25,
        "$select": "id,subject,from,toRecipients,receivedDateTime,isRead,hasAttachments,bodyPreview,importance",
    }

    data = _graph_get("/me/messages", params)
    messages = []
    for msg in data.get("value", []):
        messages.append(_format_message(msg))

    output = {
        "current_time": now.strftime("%A, %B %d, %Y %I:%M %p %Z").replace(" 0", " "),
        "timezone": TIMEZONE,
        "search": search_string,
        "count": len(messages),
        "messages": messages,
    }
    print(json.dumps(output, indent=2))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_message(msg, full=False):
    """Normalize a message dict to a clean JSON-friendly shape."""
    from_addr = msg.get("from", {}).get("emailAddress", {})
    out = {
        "id": msg.get("id"),
        "subject": msg.get("subject"),
        "from_name": from_addr.get("name", ""),
        "from_email": from_addr.get("address", ""),
        "received": msg.get("receivedDateTime"),
        "is_read": msg.get("isRead", False),
        "has_attachments": msg.get("hasAttachments", False),
        "importance": msg.get("importance", "normal"),
        "preview": msg.get("bodyPreview", "")[:200],
    }

    to_list = []
    for r in msg.get("toRecipients", []):
        addr = r.get("emailAddress", {})
        to_list.append({
            "name": addr.get("name", ""),
            "email": addr.get("address", ""),
        })
    out["to"] = to_list

    if full:
        body = msg.get("body", {})
        out["body_type"] = body.get("contentType", "text")
        out["body"] = body.get("content", "")

        # CC recipients
        cc_list = []
        for r in msg.get("ccRecipients", []):
            addr = r.get("emailAddress", {})
            cc_list.append({
                "name": addr.get("name", ""),
                "email": addr.get("address", ""),
            })
        if cc_list:
            out["cc"] = cc_list

        # Attachments list (metadata only)
        attachments = msg.get("attachments")
        if attachments is None and msg.get("hasAttachments"):
            # Fetch attachments separately
            try:
                att_data = _graph_get(f"/me/messages/{msg.get('id')}/attachments",
                                       {"$select": "id,name,contentType,size"})
                attachments = att_data.get("value", [])
            except Exception:
                attachments = []
        if attachments:
            out["attachments"] = [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "content_type": a.get("contentType"),
                    "size": a.get("size"),
                }
                for a in attachments
            ]

        # Reply-to
        reply_to = msg.get("replyTo", [])
        if reply_to:
            out["reply_to"] = [
                r.get("emailAddress", {}).get("address", "")
                for r in reply_to
            ]

        # Conversation ID for threading
        out["conversation_id"] = msg.get("conversationId")

    return out

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Outlook Mail CLI (read-only)")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("auth", help="Authenticate via device-code flow")

    p_list = sub.add_parser("list", help="List inbox messages")
    p_list.add_argument("--hours", type=int, default=None, help="Hours to look back (default: 48)")
    p_list.add_argument("--all", action="store_true", help="Show all messages (no time filter)")
    p_list.add_argument("--folder", type=str, default=None, help="Mail folder (default: inbox)")

    p_read = sub.add_parser("read", help="Read full message")
    p_read.add_argument("message_id", help="Message ID")

    p_search = sub.add_parser("search", help="Search messages")
    p_search.add_argument("--query", type=str, default=None, help="Search keyword")
    p_search.add_argument("--from", dest="sender", type=str, default=None, help="Filter by sender")
    p_search.add_argument("--subject", type=str, default=None, help="Filter by subject")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "auth": cmd_auth,
        "list": cmd_list,
        "read": cmd_read,
        "search": cmd_search,
    }
    dispatch[args.command](args)

if __name__ == "__main__":
    main()
