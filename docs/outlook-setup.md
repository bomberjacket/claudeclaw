# Outlook Skills for ClaudeClaw

> Read-only Microsoft 365 calendar and email access from Telegram, using a single Azure app registration.

This documents what was built, why, how it works under the hood, and how to set it up yourself. Both skills share the same app registration, Client ID, and Tenant ID.

---

# Part 1: Outlook Calendar

---

## The problem

ClaudeClaw already had a Google Calendar skill for scheduling. But if your organization runs on Microsoft 365 / Outlook, you need a way to check your work calendar too. The constraint: no Azure AD admin access. Someone else manages the tenant.

## The solution

A read-only Outlook Calendar skill that:
- Uses **device-code flow** (no redirect URI, no web server, no client secret)
- Only requests `Calendars.Read` (delegated) -- physically cannot modify your calendar
- Works with regular user app registration (no admin needed in most M365 tenants)
- Follows the same pattern as the existing Google Calendar skill (Python CLI, JSON output)
- Token caching with automatic refresh via MSAL

---

## What was built

### Files created

**1. Python CLI script** -- `~/.config/calendar/outlook_cal.py`

The main workhorse. A ~280-line Python script with four commands:

| Command | Graph API endpoint | What it does |
|---------|-------------------|-------------|
| `auth` | Device code flow | One-time sign-in via browser |
| `list [--days N]` | `/me/calendarView` | Upcoming events (default: 10 days, up to 50 events) |
| `get <event_id>` | `/me/events/{id}` | Full details for one event |
| `freebusy "start" "end"` | `/me/calendar/getSchedule` | Check if a time range is free/busy |

All output is JSON. Errors are also JSON (`{"error": "message"}`), so ClaudeClaw can always parse the result.

**2. Skill definition** -- `skills/outlook-calendar/SKILL.md`

The YAML frontmatter tells Claude Code which Bash patterns this skill is allowed to run:

```yaml
allowed-tools: Bash(CLAUDECLAW_DIR=* python ~/.config/calendar/outlook_cal.py *)
```

The rest of the file documents the commands, datetime formats, and usage patterns so Claude knows how to invoke the script when someone asks about their calendar.

**3. Setup guide** -- this file (`docs/outlook-setup.md`)

### Files modified

**4. `.env`** -- Added two new variables:

```
OUTLOOK_CLIENT_ID=
OUTLOOK_TENANT_ID=
```

**5. `CLAUDE.md`** -- Updated the skill trigger description from generic "schedule, meeting, calendar, availability" to "Outlook calendar, schedule, meeting, availability (read-only)" so it's clear this is the Outlook integration.

**6. `README.md`** -- Added Outlook Calendar to the bundled skills install section and the configuration reference table.

### Dependencies installed

```
pip install msal msal-extensions requests
```

- `msal` -- Microsoft Authentication Library. Handles OAuth2 device-code flow, token acquisition, silent refresh
- `msal-extensions` -- Persistent token cache helpers (we use MSAL's built-in `SerializableTokenCache` with plain file storage)
- `requests` -- HTTP client for Graph API calls

---

## Architecture decisions

### Why device-code flow?

There are several ways to authenticate with Microsoft Graph:

| Flow | Requires | Tradeoff |
|------|----------|----------|
| Authorization code | Redirect URI, web server | Overkill for a CLI tool |
| Client credentials | Admin-granted app-only permissions | Needs admin, gets org-wide access |
| **Device code** | **Nothing extra** | **User signs in via browser, grants their own permissions** |
| ROPC (username/password) | Password in plaintext | Insecure, doesn't work with MFA |

Device-code flow is the right fit because:
- No redirect URI to configure
- No client secret to store or leak
- Works with MFA and conditional access
- The user authenticates themselves -- no admin needs to grant anything
- Works on headless machines (the browser can be on a different device)

### Why read-only?

The Google Calendar skill already handles event creation with Meet links and invites. This skill is specifically for checking your Outlook/work calendar. Keeping it read-only means:
- Simpler permission model (`Calendars.Read` vs `Calendars.ReadWrite`)
- Less risk -- the app literally cannot modify your calendar even if compromised
- No admin consent needed (read-only delegated permissions are user-consentable)

### Why a Python CLI instead of an MCP server?

Following the same pattern as the Google Calendar skill. A Python script that:
- Reads config from `CLAUDECLAW_DIR/.env`
- Outputs JSON to stdout
- Is invoked via Bash tool with the `CLAUDECLAW_DIR` prefix

This keeps all calendar skills consistent and means Claude already knows the pattern.

### Why `~/.config/calendar/` for the script?

Same directory as `gcal.py`. Groups calendar tools together, keeps them out of the repo (tokens and scripts with credential access don't belong in git).

---

## How it works under the hood

```
User (Telegram)
  |
  v
ClaudeClaw (Claude Code session)
  |
  v
Bash: CLAUDECLAW_DIR=... python ~/.config/calendar/outlook_cal.py list
  |
  +--> Reads .env for OUTLOOK_CLIENT_ID + OUTLOOK_TENANT_ID
  +--> Loads token cache from ~/.config/calendar/outlook_token_cache.json
  +--> MSAL acquires token silently (refresh if needed)
  +--> GET https://graph.microsoft.com/v1.0/me/calendarView?...
  +--> Normalizes response to clean JSON
  |
  v
JSON array of events --> Claude formats for Telegram
```

### Token lifecycle

1. **First run** (`auth`): Device-code flow. User gets a URL + code, signs in via browser. MSAL returns access token + refresh token.
2. **Subsequent runs**: MSAL loads the cache, checks if the access token is still valid (~1 hour). If expired, uses the refresh token to get a new one silently.
3. **Refresh token expiry**: After ~90 days of inactivity, the refresh token expires. User needs to re-run `auth`.

### Event normalization

Graph API returns deeply nested objects. The script normalizes them to a flat structure:

```json
{
  "id": "AAMk...",
  "summary": "Weekly Standup",
  "start": "2026-03-10T09:00:00.0000000",
  "end": "2026-03-10T09:30:00.0000000",
  "location": "Conference Room B",
  "organizer": "boss@company.com",
  "attendees": [
    {"email": "you@company.com", "name": "You", "response": "accepted"}
  ],
  "online_meeting_url": "https://teams.microsoft.com/...",
  "is_cancelled": false
}
```

This matches the shape of the Google Calendar skill's output so Claude can handle both consistently.

---

## Setup (for your own fork)

### Step 1 -- Register an Azure app

Most M365 tenants let regular users do this. No admin needed.

1. Go to [https://entra.microsoft.com](https://entra.microsoft.com)
2. **Identity > Applications > App registrations > New registration**
   - Name: `ClaudeClaw Calendar Reader`
   - Supported account types: "Accounts in this organizational directory only"
   - Redirect URI: leave blank
3. Click **Register**

If blocked, ask your M365 admin. They can register it and hand you the IDs.

### Step 2 -- Configure the app

1. **Authentication** (sidebar) > scroll to Advanced settings > **Allow public client flows = Yes** > Save
2. **API permissions** (sidebar) > Add a permission > Microsoft Graph > Delegated > `Calendars.Read` > Add

No admin consent needed for `Calendars.Read`.

### Step 3 -- Copy IDs to .env

From the app's **Overview** page, copy both IDs into your ClaudeClaw `.env`:

```
OUTLOOK_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
OUTLOOK_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Step 4 -- Install dependencies

```bash
pip install msal msal-extensions requests
```

### Step 5 -- Place the script

```bash
mkdir -p ~/.config/calendar
cp skills/outlook-calendar/outlook_cal.py ~/.config/calendar/outlook_cal.py
```

Or if you built from scratch, the script is already at `~/.config/calendar/outlook_cal.py`.

### Step 6 -- Authenticate

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py auth
```

You'll see:

```
To sign in, use a web browser to open the page https://microsoft.com/devicelogin
and enter the code XXXXXXXX to authenticate.
```

Open the URL, enter the code, sign in, approve. Done.

### Step 7 -- Install the skill

```bash
cp -r skills/outlook-calendar ~/.claude/skills/outlook-calendar
```

### Step 8 -- Test

```bash
# CLI test
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/calendar/outlook_cal.py list

# Telegram test
# Send: "what's on my calendar today?"
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID must be set in .env` | Missing env vars | Add them to `.env`, make sure `CLAUDECLAW_DIR` is set |
| `Not authenticated. Run: python outlook_cal.py auth` | No token cache or expired refresh token | Re-run `auth` |
| `App registration blocked by tenant policy` | Admin disabled user registrations | Ask admin to register the app for you |
| `AADSTS50020: User account does not exist in tenant` | Signing in with personal account | Use your work/school account |
| `Insufficient privileges` | `Calendars.Read` needs admin consent in your tenant | Ask admin to grant consent |

---

## Security

- **Read-only by design**: Only `Calendars.Read` (delegated). Cannot modify anything.
- **No client secret**: Public client flow. Nothing to leak.
- **Tokens stored locally**: `~/.config/calendar/outlook_token_cache.json` -- not in the repo.
- **User-scoped**: Only accesses the authenticated user's calendar. No org-wide access.
- `.env` with Client/Tenant IDs should not be committed (it's in `.gitignore`).

---

# Part 2: Outlook Mail

> Read-only Microsoft 365 email access. Same Azure app, separate token cache, separate scope.

Added March 9, 2026.

---

## The problem

ClaudeClaw had a Gmail skill for email but no way to read your Microsoft 365 / Outlook inbox. If your work email is on M365, you need this.

## The solution

A read-only Outlook Mail skill that:
- Reuses the **same Azure app registration** as the Calendar skill (same Client ID + Tenant ID)
- Only requests `Mail.Read` (delegated) -- physically cannot send, reply, forward, move, or delete
- Uses a **separate token cache** (`~/.config/mail/outlook_token_cache.json`) because the scope is different
- Same architecture: Python CLI, JSON output, device-code flow

---

## What was built

### Files created

**1. Python CLI script** -- `~/.config/mail/outlook_mail.py`

A ~280-line Python script with four commands:

| Command | Graph API endpoint | What it does |
|---------|-------------------|-------------|
| `auth` | Device code flow | One-time sign-in via browser (consents to `Mail.Read`) |
| `list [--hours N] [--all] [--folder NAME]` | `/me/mailFolders/{folder}/messages` | Inbox messages (default: last 48h) |
| `read <message_id>` | `/me/messages/{id}` | Full message body, headers, attachment list |
| `search --query "keyword" [--from "sender"] [--subject "text"]` | `/me/messages?$search=...` | Search via Graph API KQL syntax |

All output is JSON. Errors are also JSON (`{"error": "message"}`).

**2. Skill definition** -- `skills/outlook-mail/SKILL.md`

```yaml
allowed-tools: Bash(CLAUDECLAW_DIR=* python ~/.config/mail/outlook_mail.py *)
```

**3. This setup guide** -- appended to the existing calendar doc.

### Files modified

**4. `CLAUDE.md`** -- Changed the `outlook` skill trigger to "Outlook email, inbox, read email (read-only)".

**5. `README.md`** -- Added Outlook Mail to the bundled skills install section.

---

## Architecture decisions

### Why a separate token cache?

MSAL caches tokens per scope. The calendar skill authenticates with `Calendars.Read` and the mail skill with `Mail.Read`. Using the same cache file would work but could cause confusion during token refresh. Separate caches keep things clean:

- Calendar: `~/.config/calendar/outlook_token_cache.json`
- Mail: `~/.config/mail/outlook_token_cache.json`

### Why `~/.config/mail/` for the script?

Mirrors the calendar pattern (`~/.config/calendar/`). Groups mail tools together, keeps tokens out of the repo.

### Why not pre-register Mail.Read in the app manifest?

We tried. In some tenants the Entra portal "Add a permission" button is grayed out for app owners who aren't Global Admins. MSAL's device-code flow supports **dynamic consent** -- it requests the scope at auth time and the user consents in the browser. No manifest change needed. The admin may need to approve the consent request depending on tenant policy.

---

## How it works under the hood

```
User (Telegram)
  |
  v
ClaudeClaw (Claude Code session)
  |
  v
Bash: CLAUDECLAW_DIR=... python ~/.config/mail/outlook_mail.py list
  |
  +--> Reads .env for OUTLOOK_CLIENT_ID + OUTLOOK_TENANT_ID
  +--> Loads token cache from ~/.config/mail/outlook_token_cache.json
  +--> MSAL acquires token silently (refresh if needed)
  +--> GET https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?...
  +--> Normalizes response to clean JSON
  |
  v
JSON array of messages --> Claude formats for Telegram
```

### Message normalization

Graph API returns deeply nested objects. The script normalizes them:

```json
{
  "id": "AAMk...",
  "subject": "Q1 Report",
  "from_name": "John Smith",
  "from_email": "john@example.com",
  "received": "2026-03-09T14:30:00Z",
  "is_read": true,
  "has_attachments": false,
  "importance": "normal",
  "preview": "First 200 chars of the email body...",
  "to": [{"name": "Mike", "email": "mike@company.com"}]
}
```

Full message view (`read`) adds: `body`, `body_type`, `cc`, `attachments` (metadata only), `reply_to`, `conversation_id`.

### Search

Uses Graph API's `$search` parameter with KQL syntax:

- `--query "CMMC"` becomes `$search="CMMC"`
- `--from "john@example.com"` becomes `$search=from:"john@example.com"`
- Combined: `$search="CMMC" AND from:"john@example.com"`

### Folder support

The `--folder` flag maps to Graph's well-known folder names:

| Flag value | Graph folder |
|-----------|-------------|
| `inbox` (default) | Inbox |
| `sentitems` | Sent Items |
| `drafts` | Drafts |
| `deleteditems` | Deleted Items |
| `junkemail` | Junk Email |
| `archive` | Archive |

---

## Setup

### If you already have the Calendar skill working

You already have the app registration, Client ID, Tenant ID, and dependencies. Just:

**Step 1 -- Add `Mail.Read` permission**

Option A: In Entra > App registrations > your app > API permissions > Add a permission > Microsoft Graph > Delegated > `Mail.Read`.

Option B: If the button is grayed out, skip this step. Dynamic consent during device-code flow will handle it. Your tenant admin may need to approve the consent request.

**Step 2 -- Place the script**

```bash
mkdir -p ~/.config/mail
cp skills/outlook-mail/outlook_mail.py ~/.config/mail/outlook_mail.py
```

Or the script is already at `~/.config/mail/outlook_mail.py` if built from scratch.

**Step 3 -- Authenticate**

```bash
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py auth
```

You'll get a device-code prompt. Sign in and approve `Mail.Read`. If your tenant requires admin approval, your Global Admin will need to approve the consent request first.

**Step 4 -- Install the skill**

```bash
cp -r skills/outlook-mail ~/.claude/skills/outlook-mail
```

**Step 5 -- Test**

```bash
# List recent inbox
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py list

# Search
CLAUDECLAW_DIR=/path/to/claudeclaw python ~/.config/mail/outlook_mail.py search --query "CMMC"

# Telegram test
# Send: "check my email"
```

### If you're starting from scratch

Follow Part 1's setup (Steps 1-6) first to register the app and configure the calendar skill. Then come back here for the mail steps.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `OUTLOOK_CLIENT_ID and OUTLOOK_TENANT_ID must be set in .env` | Missing env vars | Add them to `.env`, make sure `CLAUDECLAW_DIR` is set |
| `Not authenticated. Run: python outlook_mail.py auth` | No token cache or expired refresh token | Re-run `auth` |
| `Approval required` during device-code flow | Tenant requires admin consent for `Mail.Read` | Ask Global Admin to approve the consent request in Entra > Enterprise apps > Admin consent requests |
| `Add a permission` button grayed out in Entra | You're not a Global Admin and tenant restricts this | Skip it -- dynamic consent during auth handles it, but admin may need to approve |
| `Graph API error 403` | Token doesn't have `Mail.Read` scope | Re-run `auth` to consent to the scope |

---

## Security

- **Read-only by design**: Only `Mail.Read` (delegated). Cannot send, reply, forward, move, or delete.
- **No client secret**: Public client flow. Nothing to leak.
- **Tokens stored locally**: `~/.config/mail/outlook_token_cache.json` -- not in the repo.
- **User-scoped**: Only accesses the authenticated user's mailbox. No org-wide access.
- **Same app, separate caches**: Calendar and Mail use the same app registration but different token caches and scopes.
