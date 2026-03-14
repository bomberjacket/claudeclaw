---
name: outlook-mail
description: Read-only access to your Outlook / Microsoft 365 mailbox. List inbox messages, read full emails, and search mail.
allowed-tools: Bash(CLAUDECLAW_DIR=* python ~/.config/mail/outlook_mail.py *)
---

# Outlook Mail Skill (Read-Only)

## Purpose

Read inbox messages, view full email content, and search your Microsoft 365 mailbox. This skill is **read-only** -- it cannot send, reply, forward, move, or delete messages.

## Environment

The mail CLI reads config from environment variables, loaded from ClaudeClaw's `.env` via `CLAUDECLAW_DIR`. Every command MUST use this prefix:

```
CLAUDECLAW_DIR=/path/to/claudeclaw
```

Your `.env` should contain:

```
OUTLOOK_CLIENT_ID=<your Azure app client ID>
OUTLOOK_TENANT_ID=<your Azure AD tenant ID>
```

## Commands

### List recent inbox messages

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py list
```

Returns last 48 hours of inbox messages as JSON. Each entry has: `id`, `subject`, `from_name`, `from_email`, `received`, `is_read`, `has_attachments`, `importance`, `preview`, `to`.

### List messages within N hours

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py list --hours 24
```

### List all messages (no time filter)

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py list --all
```

### List messages from a specific folder

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py list --folder sentitems
```

Common folder names: `inbox`, `sentitems`, `drafts`, `deleteditems`, `junkemail`, `archive`.

### Read full message

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py read <message_id>
```

Returns full message including body, CC recipients, attachment list, conversation ID, and reply-to.

### Search messages

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py search --query "CMMC"
```

Search by keyword, sender, subject, or combine them:

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py search --query "proposal" --from "john@example.com"
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py search --subject "invoice"
```

### Re-authenticate

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py auth
```

Uses device-code flow -- you'll get a URL and code to enter in a browser. One-time setup.

## Display Format

When presenting emails to the user, use a compact table:

```
| # | From | Subject | Date | Read |
|---|------|---------|------|------|
| 1 | John Smith | Q1 Report | Mar 9, 2:30 PM | Yes |
| 2 | Lisa Chen | Invoice #4521 | Mar 9, 11:15 AM | No |
```

For full message view, show headers then body content.

## Timezone

Defaults to **America/New_York**. To change, edit the `TIMEZONE` constant in `outlook_mail.py`.

## What This Skill Does NOT Do

This is read-only. It cannot:
- Send emails
- Reply to or forward emails
- Move or delete messages
- Mark messages as read/unread
- Manage folders or rules

## One-Time Setup

### Prerequisites
1. Use the same Azure app registration as Outlook Calendar (or create a new one at https://entra.microsoft.com > App registrations)
2. Add API permission: Microsoft Graph > Delegated > `Mail.Read`
3. Grant admin consent if required by your tenant
4. Ensure `OUTLOOK_CLIENT_ID` and `OUTLOOK_TENANT_ID` are in `.env` (should already be there from calendar setup)
5. Dependencies are the same: `pip install msal requests`
6. Run auth:

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py auth
```

Follow the device-code prompt to sign in via browser. This creates a separate token cache from the calendar skill since it uses the `Mail.Read` scope.

## Error Handling

- If `OUTLOOK_CLIENT_ID` or `OUTLOOK_TENANT_ID` missing: error tells you to set them in `.env`
- If not authenticated: error tells you to run `auth`
- Token refresh is automatic via MSAL cache
