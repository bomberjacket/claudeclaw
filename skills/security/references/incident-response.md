# Incident Response Procedures

## Severity Classification

| Level | Definition | Examples | Response Time |
|-------|-----------|----------|---------------|
| P0 | Active exploitation or confirmed breach | Unauthorized commands executed, data exfiltrated, credentials leaked | Immediate |
| P1 | Critical vulnerability with known exploit | RCE CVE affecting installed version, compromised MCP server | < 24 hours |
| P2 | High-severity vulnerability or suspicious activity | Emerging threat targeting this stack, unusual token usage pattern, budget spike | < 72 hours |
| P3 | Medium-severity or hardening gap | Outdated dependency, permission misconfiguration | < 7 days |

## P0: Active Incident Playbook

### Step 1. Contain
```bash
# Stop the bot immediately
# If running via PM2:
pm2 stop claudeclaw 2>/dev/null

# Kill any running node processes related to claudeclaw
taskkill /F /IM node.exe /FI "WINDOWTITLE eq claudeclaw" 2>nul

# Kill any running Claude Code processes
taskkill /F /IM claude.exe 2>nul

# Block network if needed (Windows Firewall -- requires elevated shell)
netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound
```

### Step 2. Preserve Evidence
```bash
# Snapshot logs before they rotate
# If using PM2:
pm2 logs claudeclaw --nostream --lines 1000 > "$HOME/incident-$(date +%Y%m%d-%H%M%S).log"

# Or copy from store/ if logging there:
cp "$CLAUDECLAW_DIR/store/claudeclaw.log" "$HOME/incident-$(date +%Y%m%d-%H%M%S).log" 2>/dev/null

# Snapshot database
cp "$CLAUDECLAW_DIR/store/claudeclaw.db" "$HOME/incident-db-$(date +%Y%m%d-%H%M%S).sqlite"

# Capture running processes and network state
tasklist /V > "$HOME/incident-ps-$(date +%Y%m%d-%H%M%S).txt"
netstat -ano > "$HOME/incident-net-$(date +%Y%m%d-%H%M%S).txt"

# Snapshot token budget for forensics
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT * FROM token_budget ORDER BY created_at DESC LIMIT 50;
" > "$HOME/incident-budget-$(date +%Y%m%d-%H%M%S).txt"
```

### Step 3. Assess
```bash
# Check conversation log for suspicious commands
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT created_at, role, substr(content, 1, 200)
  FROM conversation_log
  ORDER BY created_at DESC LIMIT 50;
"

# Check for unusual API spend (possible exfiltration via API calls)
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT date_key, model, provider, cost_usd, input_tokens, output_tokens
  FROM token_budget
  ORDER BY created_at DESC LIMIT 20;
"

# Check for unauthorized file modifications (PowerShell)
powershell -Command "Get-ChildItem -Path '$CLAUDECLAW_DIR' -Recurse -File | Where-Object { \$_.LastWriteTime -gt (Get-Date).AddHours(-24) } | Select-Object -First 50 FullName, LastWriteTime"

# Check for scheduled tasks referencing claude
schtasks /query /fo LIST | findstr -i claude

# Check PM2 process list
pm2 list 2>/dev/null
```

### Step 4. Remediate
- Rotate ALL API keys and tokens (Telegram, Anthropic, Google, Slack)
- Revoke OAuth tokens
- Review and clean `.claude/settings.json` hooks
- Review MCP server configs (`.mcp.json`)
- Audit recent git commits for injected code
- Re-run security scan after remediation
- Verify token budget table for unauthorized spend patterns

### Step 5. Recover
```bash
# Restore network if blocked
netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound

# Restart with fresh session
pm2 start claudeclaw 2>/dev/null || npm start
```

### Step 6. Post-Incident
- Document what happened, how it was detected, and how it was resolved
- Save to security_scans table as a manual entry
- Update threat taxonomy if this was a new attack vector
- Adjust scan rules to detect similar attacks

## P1: Critical Vulnerability Response

1. **Assess applicability**: Is this CVE/vulnerability in our installed version? Does the attack vector apply to our configuration?
2. **Check for patches**: Is there an updated version available?
3. **Apply fix**: Update package, apply patch, or implement workaround
4. **Verify**: Re-run the relevant scan to confirm the fix
5. **Mark fixed**: Update security_findings table

## Credential Rotation Schedule

| Credential | Rotation Frequency | How to Rotate |
|-----------|-------------------|---------------|
| `TELEGRAM_BOT_TOKEN` | On compromise or annually | BotFather > Revoke Token |
| `ANTHROPIC_API_KEY` | On compromise or quarterly | console.anthropic.com > API Keys |
| `GOOGLE_API_KEY` | On compromise or quarterly | console.cloud.google.com > Credentials |
| `SLACK_USER_TOKEN` | On compromise or annually | Slack App > OAuth & Permissions > Reinstall |
| Gmail OAuth tokens | Auto-refresh; revoke on compromise | Google Account > Security > Third-party apps |
| Calendar OAuth tokens | Auto-refresh; revoke on compromise | Google Account > Security > Third-party apps |

## Anomaly Indicators

Watch for these patterns that may indicate compromise or misuse:

| Indicator | What It Means | Check |
|-----------|--------------|-------|
| Token usage spike > 3x baseline | Possible unauthorized usage or recursive loops | `token_usage` table |
| Daily budget > 95% before midday | Abnormal spend rate, possible automated abuse | `token_budget` table, `/tokens` command |
| Messages outside 06:00-00:00 CET | Unexpected off-hours activity | `conversation_log` table |
| > 50 messages in 1 hour | Possible automated abuse | `conversation_log` table |
| Repeated compaction events | Context being pushed to limits, possible context stuffing | `token_usage.did_compact` |
| Cost > $5 in single session | Abnormally expensive session | `token_usage.cost_usd` |
| Gemini-only spend when both keys available | Budget hard-limit triggered unexpectedly | `token_budget` table |
| New files in `.claude/` or project root | Possible injected configuration | PowerShell `Get-ChildItem` |
| Failed auth attempts in logs | Unauthorized access attempts | pino logs |
