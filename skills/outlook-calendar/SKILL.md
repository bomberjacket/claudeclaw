---
name: outlook-calendar
description: Read-only access to your Outlook / Microsoft 365 calendar. List events, check details, and query availability.
allowed-tools: Bash(CLAUDECLAW_DIR=* python ~/.config/calendar/outlook_cal.py *)
---

# Outlook Calendar Skill (Read-Only)

## Purpose

View upcoming meetings, get event details, and check availability on your Microsoft 365 calendar. This skill is **read-only** — it cannot create, update, or delete events.

## Environment

The calendar CLI reads config from environment variables, loaded from ClaudeClaw's `.env` via `CLAUDECLAW_DIR`. Every command MUST use this prefix:

```
CLAUDECLAW_DIR=/path/to/claudeclaw
```

Your `.env` should contain:

```
OUTLOOK_CLIENT_ID=<your Azure app client ID>
OUTLOOK_TENANT_ID=<your Azure AD tenant ID>
```

## Commands

### List upcoming events

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py list
```

Returns next 10 days of events as JSON. Each entry has: `id`, `summary`, `start`, `end`, `location`, `organizer`, `attendees`, `online_meeting_url`.

### List events within N days

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py list --days 7
```

### Get event details

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py get <event_id>
```

Returns full event details including body preview.

### Check free/busy

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py freebusy "2026-03-15 09:00" "2026-03-15 17:00"
```

Shows busy time slots in the given range. If no conflicts, returns `{"status": "free"}`.

### Re-authenticate

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py auth
```

Uses device-code flow — you'll get a URL and code to enter in a browser. One-time setup.

## Datetime Formats

All of these work:
- `2026-03-15 10:00`
- `2026-03-15 2:00PM`
- `2026-03-15T14:00`
- `03/15/2026 10:00`

## Timezone

Defaults to **America/New_York**. To change, edit the `TIMEZONE` constant in `outlook_cal.py`.

## What This Skill Does NOT Do

This is read-only. It cannot:
- Create events
- Update events
- Cancel/delete events
- Send invites

Use the Google Calendar skill for write operations if needed.

## One-Time Setup

### Prerequisites
1. Register an app at https://entra.microsoft.com > App registrations
   - Name: `ClaudeClaw Calendar Reader`
   - Account type: "Accounts in this organizational directory only"
   - Enable "Allow public client flows" under Authentication
   - Add API permission: Microsoft Graph > Delegated > `Calendars.Read`
2. Copy the **Application (client) ID** and **Tenant ID** into `.env`
3. Run `pip install msal msal-extensions requests`
4. Run auth:

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py auth
```

Follow the device-code prompt to sign in via browser.

## Error Handling

- If `OUTLOOK_CLIENT_ID` or `OUTLOOK_TENANT_ID` missing: error tells you to set them in `.env`
- If not authenticated: error tells you to run `auth`
- Token refresh is automatic via MSAL cache
