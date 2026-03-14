# CSO Agent & Security Skill -- Complete Guide

**Project:** ClaudeClaw (multi-agent Telegram bot framework)
**Platform:** Windows 11 (adapted from macOS)
**Last updated:** 2026-03-14

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [File Structure](#file-structure)
4. [8-Domain Scan Framework](#8-domain-scan-framework)
5. [Threat Taxonomy](#threat-taxonomy)
6. [Hardening Checklist](#hardening-checklist)
7. [Runtime Monitor](#runtime-monitor)
8. [Dependency & Secrets Scanner](#dependency--secrets-scanner)
9. [Incident Response Playbooks](#incident-response-playbooks)
10. [Token Budget Security](#token-budget-security)
11. [CSO Agent Configuration](#cso-agent-configuration)
12. [Using CSO (Scheduled & On-Demand)](#using-cso)
13. [PM2 Process Management](#pm2-process-management)
14. [macOS to Windows Conversion Guide](#macos-to-windows-conversion-guide)

---

## Overview

ClaudeClaw has a dedicated security framework consisting of two parts:

1. **Security skill** (`skills/security/`) -- the knowledge base: threat taxonomy, hardening checklists, incident response playbooks, runtime monitor script
2. **CSO agent** (`agents/cso/`) -- the operator: a standalone agent that runs the security skill, monitors the system, and reports findings

The CSO (Chief Security Officer) agent has a single skill: `security`. If it identifies a need for additional capabilities, it escalates through Cos (Chief of Staff), who relays the request to Mike for approval. CSO never self-assigns skills.

---

## Architecture

```
Mike (Telegram)
  |
  +-- @CC_CSO_bot (CSO agent)
  |     |
  |     +-- Runs 8-domain security scans
  |     +-- Executes security-monitor.py
  |     +-- Runs security-scan.sh
  |     +-- Tracks findings in security_findings table
  |     +-- Responds to incident playbooks (P0-P3)
  |     |
  |     +-- Needs a new capability?
  |           |
  |           v
  |     Logs capability_request to hive_mind
  |           |
  |           v
  |     Cos relays request to Mike
  |           |
  |           v
  |     Mike approves/denies
  |
  +-- @CC_Cos_bot (Cos agent -- orchestration)
  +-- @CC_CMO_bot (CMO agent -- marketing)
  +-- @bnixobot   (PA -- personal assistant)
```

### Why ClaudeClaw is Maximum-Risk

ClaudeClaw satisfies Simon Willison's **Lethal Trifecta** -- all three present simultaneously:

1. **Private data access** -- full filesystem, SQLite DB, credentials, emails, calendar
2. **Untrusted content exposure** -- Telegram messages, web fetches, file reads, MCP tool results
3. **External action capability** -- unrestricted shell, network requests, API calls, file writes

This means: if an attacker gets malicious tokens into the context window, those tokens can trigger real-world actions with full user privileges. The entire security model depends on preventing, detecting, and containing this.

---

## File Structure

### Security Skill

```
skills/security/
+-- SKILL.md                              # Entry point: frontmatter, 8-domain framework,
|                                         #   daily workflow, finding lifecycle, rules
+-- references/
|   +-- threat-taxonomy.md                # T1-T4 threat tiers, OWASP ASI, defense principles
|   +-- hardening-checklist.md            # 8-domain checklists, severity scoring, frequency
|   +-- incident-response.md              # P0-P3 playbooks, credential rotation, anomaly indicators
|   +-- token-budget-security.md          # Budget architecture, multi-provider routing, monitoring
+-- scripts/
    +-- security-monitor.py               # Runtime monitor (Windows: icacls, netstat)
```

### CSO Agent

```
agents/cso/
+-- agent.yaml          # name, bot token env var, model, skills list
+-- CLAUDE.md           # Role, procedures, scope boundaries, escalation chain
```

### Supporting Scripts

```
scripts/
+-- security-scan.sh    # Dependency scanner: npm audit, outdated, secrets, ACLs, ports
+-- notify.sh           # Telegram alert helper
```

---

## 8-Domain Scan Framework

Every security scan evaluates across all 8 domains:

| Domain | Code | What It Covers |
|--------|------|----------------|
| Dependency Security | DEP | npm audit, outdated packages, SBOM |
| Secret Management | SEC | .env permissions, hardcoded secrets, git history, token rotation |
| File System Security | FS | ACLs on store/, .env, project files (Windows: `icacls`) |
| MCP & Tool Security | MCP | Server configs, tool descriptions, scope review |
| Agent Configuration | AGT | Settings hooks, skills review, CLAUDE.md, respin safety |
| Network & API | NET | Open ports (`netstat`), API key exposure, HTTPS enforcement |
| AI Threat Intelligence | AITL | CVEs, prompt injection, jailbreaks, supply chain, research |
| Runtime Monitoring | MON | Token usage, cost spikes, message floods, budget alerts |

### Scan Frequency

| Domain | Frequency | Method |
|--------|-----------|--------|
| DEP | Daily | `security-scan.sh` + `npm audit` |
| SEC | Daily | `security-scan.sh` secret grep |
| FS | Daily | `security-scan.sh` permission check |
| MCP | Weekly | Manual review or agent-assisted |
| AGT | Weekly | Agent self-audit |
| NET | Daily | Port scan in `security-scan.sh` |
| AITL | Daily | AI web search (8 sources) |
| MON | Continuous | `security-monitor.py` + `token_budget` table |

---

## Threat Taxonomy

Organized by OWASP ASI (Agentic Security Initiative):

### Tier 1: CRITICAL -- Full System Compromise

| ID | Threat | OWASP ASI | Attack Vector | Impact |
|----|--------|-----------|---------------|--------|
| T1.1 | Direct prompt injection | ASI01 | Crafted Telegram message bypasses instructions | RCE, data exfil, credential theft |
| T1.2 | Shell command injection | ASI05 | Injected payload reaches `bash` via agent | Full host compromise |
| T1.3 | MCP supply chain attack | ASI04 | Malicious `.mcp.json` or compromised MCP server | Silent persistent backdoor |
| T1.4 | Configuration-as-code | CVE-2025-59536 | Malicious `.claude/settings.json` hooks | Auto-execute on session start |
| T1.5 | Credential/token theft | ASI03 | Agent accesses `.env`, OAuth tokens, API keys | Full account takeover |
| T1.6 | Auth bypass (Telegram) | ASI03 | Compromised Telegram account or session hijack | Full agent control |

### Tier 2: HIGH -- Data Exfiltration / Persistent Compromise

| ID | Threat | OWASP ASI | Attack Vector | Impact |
|----|--------|-----------|---------------|--------|
| T2.1 | Indirect prompt injection | ASI01/06 | Malicious content in fetched web pages, files, emails | Goal hijack via ingested content |
| T2.2 | Memory/context poisoning | ASI06 | Poisoned conversation history, `/respin` replay | Persistent behavioral manipulation |
| T2.3 | Tool confusion / hijacking | ASI02 | ToolHijacker pattern manipulates tool selection | Wrong tool called with wrong params |
| T2.4 | Log-to-leak exfiltration | ASI02 | Agent tricked into logging sensitive data to attacker-controlled tool | Silent data exfil via MCP |
| T2.5 | Data exfil via tool chaining | ASI02/03 | Shell + curl = trivial exfil channel | Sensitive data sent to attacker |
| T2.6 | Privilege escalation via chaining | ASI03 | Multi-step plan accumulates privileges | Escalation beyond intended scope |
| T2.7 | API key exposure via routing | ASI03 | Multi-provider routing resolves both Anthropic + Google keys; error messages or logs could leak them | Account takeover on either provider |

### Tier 3: MEDIUM -- Degraded Security Posture

| ID | Threat | OWASP ASI | Attack Vector | Impact |
|----|--------|-----------|---------------|--------|
| T3.1 | Human-agent trust exploitation | ASI09 | Agent presents attacker's content as its own analysis | User acts on manipulated info |
| T3.2 | Cascading failures | ASI08 | Error in step 1 propagates through multi-step plan | Unintended destructive actions |
| T3.3 | Rogue agent behavior | ASI10 | Misaligned behavior over long sessions | Subtle incorrect actions |
| T3.4 | Dependency vulnerabilities | ASI04 | Known CVEs in npm packages | Varies by CVE |
| T3.5 | Resource exhaustion | ASI08 | Infinite loops, massive file operations, untracked API calls | DoS, API credit drain |
| T3.6 | Secrets in git history | ASI03 | Accidentally committed credentials | Credential exposure |
| T3.7 | Budget bypass | ASI08 | API calls outside the token router skip budget tracking | Uncontrolled spend |
| T3.8 | Gemini response injection | ASI01/06 | Gemini reviewer in code pipeline returns crafted JSON that manipulates arbiter decisions | Pipeline verdict manipulation |

### Tier 4: LOW -- Awareness Items

| ID | Threat | Attack Vector | Impact |
|----|--------|---------------|--------|
| T4.1 | Outdated packages | Stale dependencies | Exposure window |
| T4.2 | Overly permissive file ACLs | Loose ACLs on store/ files | Local info disclosure |
| T4.3 | Log data leakage | PII/secrets in log files | Local info disclosure |
| T4.4 | Session persistence | No timeout on agent sessions | Stale auth context |

### OWASP ASI Reference

| Code | Name | ClaudeClaw Relevance |
|------|------|---------------------|
| ASI01 | Agent Goal Hijack | PRIMARY RISK - Telegram input is the main injection surface |
| ASI02 | Tool Misuse & Exploitation | Shell access = maximum tool risk |
| ASI03 | Identity & Privilege Abuse | Runs as full Windows user with multi-provider API access |
| ASI04 | Supply Chain Vulnerabilities | MCP servers, npm packages, skills |
| ASI05 | Unexpected Code Execution | `bypassPermissions` = unrestricted execution |
| ASI06 | Memory & Context Poisoning | Conversation log, /respin, SQLite memories |
| ASI07 | Insecure Inter-Agent Communication | Sub-agent spawning via Task tool |
| ASI08 | Cascading Failures | Multi-step plans with no circuit breakers; budget bypass |
| ASI09 | Human-Agent Trust Exploitation | User trusts Telegram output implicitly |
| ASI10 | Rogue Agents | Long-running sessions with no behavioral baseline |

### Defense Principles

1. **Deterministic controls over AI-based detection** -- allowlists, sandboxing, parameterized validation beat prompt-based defenses
2. **Progressive privilege** -- start minimal, elevate explicitly, log everything
3. **All Telegram input is untrusted** -- it is the primary injection surface
4. **Tool result sanitization** -- clean all external content before feeding to LLM context
5. **Configuration files are code** -- validate `.claude/`, `.mcp.json`, skills with same rigor as executables
6. **Reduce autonomy where possible** -- the single most effective architectural mitigation
7. **Separation of concerns** -- privileged actions via separate validated pathways, not raw shell
8. **Budget as a security boundary** -- token budget limits blast radius of runaway or hijacked API calls
9. **API keys stay out of process.env** -- `readEnvFile()` resolves keys at call time without polluting the environment

---

## Hardening Checklist

### 1. Dependency Security (DEP)
- [ ] `npm audit` shows zero critical/high vulnerabilities
- [ ] All packages within 1 minor version of latest
- [ ] No packages with known supply chain compromises
- [ ] `package-lock.json` integrity verified
- [ ] No deprecated packages in dependency tree

### 2. Secret Management (SEC)
- [ ] `.env` permissions: owner-only via `icacls .env /inheritance:r /grant:r "%USERNAME%:F"`
- [ ] No secrets in source code (grep for token patterns)
- [ ] No secrets in git history (`git log -p | grep -i` for key patterns)
- [ ] No `.env.bak`, `.env.local`, `.env.*.local` files exist
- [ ] API keys rotated within last 90 days
- [ ] Slack, Gmail, Calendar tokens scoped to minimum permissions
- [ ] `GOOGLE_API_KEY` treated as critical credential (used for Gemini routing and budget fallback)
- [ ] `TOKEN_DAILY_BUDGET_USD` set to a reasonable limit

### 3. File System Security (FS)
- [ ] `store/` directory: owner-only via `icacls store /inheritance:r /grant:r "%USERNAME%:F"`
- [ ] `store/claudeclaw.db`: owner-only ACL
- [ ] No files with loose ACLs granting access to `Everyone` or `Users` group
- [ ] No stale upload files in `workspace/uploads/`
- [ ] `.gitignore` covers: `.env*`, `*.pem`, `*.key`, `*.cert`, `*.sqlite`, `*.db`

### 4. MCP & Tool Security (MCP)
- [ ] All configured MCP servers are from trusted sources
- [ ] No `enableAllProjectMcpServers` in `.claude/settings.json`
- [ ] MCP server tool descriptions reviewed for injection payloads
- [ ] No MCP servers with overly broad scopes
- [ ] `.mcp.json` files in project roots reviewed for malicious commands
- [ ] MCP servers pinned to specific versions (no `latest` tags)

### 5. Agent Configuration (AGT)
- [ ] `.claude/settings.json` hooks reviewed (no auto-execute of untrusted code)
- [ ] Skills directory contents reviewed for hidden unicode/injection
- [ ] CLAUDE.md does not contain injection-vulnerable patterns
- [ ] `/respin` history marked as untrusted data
- [ ] Memory context gating active (trivial messages skip memory lookup)

### 6. Network & API Security (NET)
- [ ] No unexpected listening ports (`netstat -ano | findstr LISTENING`)
- [ ] Telegram bot token not exposed in logs
- [ ] API keys not in any URL parameters (Gemini API uses `?key=` in URL -- ensure not logged)
- [ ] No hardcoded IPs or credentials in source
- [ ] HTTPS enforced for all external API calls
- [ ] Token router error messages do not leak API keys (truncated to 500 chars)

### 7. AI Threat Intelligence (AITL)
- [ ] Anthropic security advisories checked (last 7 days)
- [ ] Claude Code / Agent SDK CVEs checked
- [ ] MCP protocol vulnerabilities checked
- [ ] OWASP LLM/Agentic top 10 updates checked
- [ ] Prompt injection/jailbreak research checked
- [ ] Supply chain attacks on AI tooling checked

### 8. Runtime Monitoring (MON)
- [ ] Token usage within expected bounds (no cost spikes)
- [ ] Token budget shows spend within daily limit
- [ ] No untracked API calls bypassing the token router
- [ ] No compaction events outside heavy operations
- [ ] Message volume within baseline (no flood patterns)
- [ ] No off-hours activity if unexpected
- [ ] Error rate within normal range
- [ ] Budget hard-limit (95%) functioning -- all calls downgrade to Gemini when triggered

### Severity Scoring

| Severity | Criteria | SLA |
|----------|----------|-----|
| CRITICAL | Active exploit exists, directly affects this system, RCE/data exfil possible | Fix within 24 hours |
| HIGH | Exploit exists or emerging threat, affects this stack, elevated risk | Fix within 72 hours |
| MEDIUM | Known issue, indirect risk, defense-in-depth improvement | Fix within 7 days |
| LOW | Best practice improvement, minimal direct risk | Fix within 30 days |
| INFO | Awareness item, no action required | Track only |

---

## Runtime Monitor

**File:** `skills/security/scripts/security-monitor.py`

Python script using only stdlib (no pip installs). Checks token usage, message patterns, file permissions, open ports, MCP configs, and hardcoded secrets.

### Usage

```bash
cd claudeclaw
python skills/security/scripts/security-monitor.py              # Full report (pretty-printed)
python skills/security/scripts/security-monitor.py --json       # JSON output
python skills/security/scripts/security-monitor.py --all        # Include file + port checks
python skills/security/scripts/security-monitor.py --check-files  # File ACL checks only
python skills/security/scripts/security-monitor.py --check-ports  # Port scan only
```

### What It Checks

| Check | Category | Method |
|-------|----------|--------|
| Token usage anomalies | MON | Queries `token_usage` table, compares to session averages |
| Token budget status | MON | Queries `token_budget` table, checks 75%/95% thresholds |
| Message flood detection | MON | Counts messages in `conversation_log` (last hour) |
| Off-hours activity | MON | Checks message timestamps against 00:00-06:00 window |
| File permissions | FS | Runs `icacls` on .env, store/, store/* |
| Environment backup files | SEC | Looks for .env.bak, .env.local, etc. |
| Secrets in git history | SEC | Checks recent git commits for .env file additions |
| Open ports | NET | Runs `netstat -ano`, resolves PIDs to process names |
| MCP configs | MCP | Checks `enableAllProjectMcpServers`, .mcp.json review |
| Hardcoded secrets | SEC | Regex scan of src/, scripts/ for API key patterns |

### Configuration

Edit constants at the top of the script:

| Constant | Default | Purpose |
|----------|---------|---------|
| `CLAUDECLAW_DIR` | `~/bni-agents/claudeclaw` | Project root (or set env var) |
| `COST_SPIKE_THRESHOLD` | `$5/session` | Alert if session cost exceeds this |
| `MSG_FLOOD_THRESHOLD` | `50/hour` | Alert if message volume exceeds this |
| `COMPACTION_THRESHOLD` | `3/session` | Alert on frequent context compactions |
| `DAILY_BUDGET_USD` | `$10` | Maps to `TOKEN_DAILY_BUDGET_USD` |
| `TOKEN_SPIKE_MULTIPLIER` | `3x` | Alert if cost exceeds 3x average |

---

## Dependency & Secrets Scanner

**File:** `scripts/security-scan.sh`

Bash script that covers DEP, SEC, FS, and NET domains. Outputs JSON to stdout, progress to stderr.

### What It Scans

| Domain | Check | Method |
|--------|-------|--------|
| DEP | npm vulnerabilities | `npm audit --json` |
| DEP | Outdated packages | `npm outdated --json` |
| SEC | .env backup files | Checks for .env.bak, .env.local, .env.backup, .env.old, .env.copy |
| SEC | Hardcoded secrets | Regex grep of src/, scripts/, agents/, skills/ for API key patterns |
| FS | File ACLs | `icacls` on .env, store/, store/claudeclaw.db |
| NET | Intel AMT port | `netstat` check for port 16992 |

### Usage

```bash
cd claudeclaw
bash scripts/security-scan.sh              # JSON output to stdout
bash scripts/security-scan.sh 2>/dev/null  # JSON only, suppress progress
```

---

## Incident Response Playbooks

### Severity Classification

| Level | Definition | Examples | Response Time |
|-------|-----------|----------|---------------|
| P0 | Active exploitation or confirmed breach | Unauthorized commands executed, data exfiltrated, credentials leaked | Immediate |
| P1 | Critical vulnerability with known exploit | RCE CVE affecting installed version, compromised MCP server | < 24 hours |
| P2 | High-severity vulnerability or suspicious activity | Emerging threat targeting this stack, unusual token usage, budget spike | < 72 hours |
| P3 | Medium-severity or hardening gap | Outdated dependency, permission misconfiguration | < 7 days |

### P0: Active Incident Playbook

**Step 1. Contain**
```bash
# Stop the bot immediately
pm2 stop claudeclaw 2>/dev/null

# Kill any running node processes related to claudeclaw
taskkill /F /IM node.exe /FI "WINDOWTITLE eq claudeclaw" 2>nul

# Kill any running Claude Code processes
taskkill /F /IM claude.exe 2>nul

# Block network if needed (requires elevated shell)
netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound
```

**Step 2. Preserve Evidence**
```bash
# Snapshot logs
pm2 logs claudeclaw --nostream --lines 1000 > "$HOME/incident-$(date +%Y%m%d-%H%M%S).log"

# Snapshot database
cp "$CLAUDECLAW_DIR/store/claudeclaw.db" "$HOME/incident-db-$(date +%Y%m%d-%H%M%S).sqlite"

# Capture running processes and network state
tasklist /V > "$HOME/incident-ps-$(date +%Y%m%d-%H%M%S).txt"
netstat -ano > "$HOME/incident-net-$(date +%Y%m%d-%H%M%S).txt"

# Snapshot token budget for forensics
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "SELECT * FROM token_budget ORDER BY created_at DESC LIMIT 50;" > "$HOME/incident-budget-$(date +%Y%m%d-%H%M%S).txt"
```

**Step 3. Assess**
```bash
# Check conversation log for suspicious commands
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT created_at, role, substr(content, 1, 200)
  FROM conversation_log ORDER BY created_at DESC LIMIT 50;"

# Check for unusual API spend
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT date_key, model, provider, cost_usd, input_tokens, output_tokens
  FROM token_budget ORDER BY created_at DESC LIMIT 20;"

# Check for unauthorized file modifications (PowerShell)
powershell -Command "Get-ChildItem -Path '$CLAUDECLAW_DIR' -Recurse -File | Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-24) } | Select-Object -First 50 FullName, LastWriteTime"

# Check for scheduled tasks referencing claude
schtasks /query /fo LIST | findstr -i claude
```

**Step 4. Remediate**
- Rotate ALL API keys and tokens (Telegram, Anthropic, Google, Slack)
- Revoke OAuth tokens
- Review and clean `.claude/settings.json` hooks
- Review MCP server configs (`.mcp.json`)
- Audit recent git commits for injected code
- Re-run security scan after remediation

**Step 5. Recover**
```bash
# Restore network if blocked
netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound

# Restart with fresh session
pm2 start claudeclaw 2>/dev/null || npm start
```

**Step 6. Post-Incident**
- Document what happened, how it was detected, and how it was resolved
- Save to security_scans table as a manual entry
- Update threat taxonomy if this was a new attack vector
- Adjust scan rules to detect similar attacks

### P1: Critical Vulnerability Response
1. Assess applicability -- is this CVE in our installed version?
2. Check for patches
3. Apply fix
4. Verify with relevant scan
5. Mark fixed in security_findings table

### Remediation Workflow (for any finding)
1. **Always query the DB first** -- never rely on conversation memory
2. **Show the finding** with ID, severity, title, and proposed fix
3. **Wait for approval** -- never auto-fix security issues
4. **Execute the fix**
5. **Verify** -- re-run the relevant check
6. **Mark fixed** -- update all matching open findings
7. **Rebuild if needed** -- `npm run build` + restart service

### Credential Rotation Schedule

| Credential | Rotation | How |
|-----------|----------|-----|
| `TELEGRAM_BOT_TOKEN` | On compromise or annually | BotFather > Revoke Token |
| `ANTHROPIC_API_KEY` | On compromise or quarterly | console.anthropic.com > API Keys |
| `GOOGLE_API_KEY` | On compromise or quarterly | console.cloud.google.com > Credentials |
| `SLACK_USER_TOKEN` | On compromise or annually | Slack App > OAuth & Permissions > Reinstall |
| Gmail/Calendar OAuth | Auto-refresh; revoke on compromise | Google Account > Security > Third-party apps |
| Agent bot tokens | On compromise or annually | BotFather > Revoke Token |

### Anomaly Indicators

| Indicator | What It Means | Where to Check |
|-----------|--------------|----------------|
| Token usage spike > 3x baseline | Possible unauthorized usage or loops | `token_usage` table |
| Daily budget > 95% before midday | Abnormal spend rate | `token_budget` table |
| Messages outside 06:00-00:00 | Unexpected off-hours activity | `conversation_log` table |
| > 50 messages in 1 hour | Possible automated abuse | `conversation_log` table |
| Repeated compaction events | Context stuffing or very long operation | `token_usage.did_compact` |
| Cost > $5 in single session | Abnormally expensive session | `token_usage.cost_usd` |
| Gemini-only spend when both keys available | Budget hard-limit triggered unexpectedly | `token_budget` table |
| New files in `.claude/` or project root | Possible injected configuration | PowerShell `Get-ChildItem` |

---

## Token Budget Security

### Architecture

ClaudeClaw uses a Token Optimization Framework to route API calls across providers and track spend.

**Components:**
- `src/token-router.ts` -- centralized routing, picks cheapest capable model per task
- `src/token-budget.ts` -- budget tracking with threshold alerts
- `src/db.ts` -- `token_budget` table for persistent spend tracking

**Route Table:**

| Task Type | Provider | Model | Rationale |
|-----------|----------|-------|-----------|
| `pipeline-reviewer` | Google | gemini-2.0-flash | Junior review, structured JSON |
| `pipeline-arbiter` | Anthropic | claude-sonnet-4 | Strong reasoning for adjudication |
| `scheduled-simple` | Google | gemini-2.0-flash | Datetime sync, simple lookups |
| `scheduled-complex` | Anthropic | claude-sonnet-4 | Security scans, analysis |
| `general` | Anthropic | claude-sonnet-4 | Fallback |

**Budget Thresholds:**
- **75%** -- Warning (advisory, no action)
- **95%** -- Hard-limit: ALL calls forced to Gemini Flash

**Env var:** `TOKEN_DAILY_BUDGET_USD` (default: 10, currently set to 25)

### Multi-Provider Security Considerations

1. **API key isolation**: Keys read from `.env` via `readEnvFile()` at call time, never in `process.env`
2. **Error message truncation**: API errors truncated to 500 chars to prevent key leakage
3. **Fallback behavior**: Missing key falls back to other provider (feature, not vulnerability)
4. **Budget as blast radius control**: 95% hard-limit caps financial damage
5. **Gemini URL key parameter**: Gemini passes key as URL param (`?key=...`) -- ensure HTTP logging doesn't capture full URLs
6. **Pipeline trust boundary**: Gemini reviewers could craft responses to influence Claude arbiter

### Budget Queries

```bash
# Today's spend
sqlite3 store/claudeclaw.db "
  SELECT model, provider, input_tokens, output_tokens, cost_usd
  FROM token_budget WHERE date_key = date('now') ORDER BY cost_usd DESC;"

# 7-day history
sqlite3 store/claudeclaw.db "
  SELECT date_key, SUM(cost_usd) as daily_cost
  FROM token_budget WHERE date_key >= date('now', '-7 days')
  GROUP BY date_key ORDER BY date_key DESC;"

# Detect anomalies (2x budget)
sqlite3 store/claudeclaw.db "
  SELECT date_key, SUM(cost_usd) as total FROM token_budget
  GROUP BY date_key HAVING total > 50 ORDER BY date_key DESC;"
```

---

## CSO Agent Configuration

### agent.yaml

```yaml
name: CSO
description: Security -- 8-domain scanning, threat detection, incident response, runtime monitoring
telegram_bot_token_env: CSO_BOT_TOKEN
model: claude-sonnet-4-6

skills:
  - security
```

### CSO CLAUDE.md (Summary)

The CSO agent's CLAUDE.md defines:
- **Role**: Run 8-domain scans, detect threats, execute incident response, monitor runtime
- **Single skill**: `security` -- everything else requires escalation
- **Escalation chain**: CSO -> hive_mind capability_request -> Cos -> Mike
- **Daily scan workflow**: 8-step sequence at 09:00
- **Rules**: Never auto-fix, always query DB, no duplicates, rotate credentials on exposure
- **Hive mind logging**: scan_completed, finding_created, finding_fixed, incident_detected, capability_request, threat_intel

### Finding Lifecycle

```
  [NEW] --> [OPEN] --> [FIXED]       (remediated)
                   --> [IGNORED]     (accepted risk, with justification)
                   --> [SUPERSEDED]  (replaced by newer finding)
```

### Intelligence Sources

| Source | What to Look For |
|--------|-----------------|
| Anthropic advisories | Claude Code CVEs, Agent SDK security patches |
| GitHub anthropics/* | Issues, PRs mentioning security |
| MCP protocol | Server vulnerabilities, protocol exploits |
| OWASP LLM/Agentic | Top 10 updates, new attack categories |
| Prompt injection research | New jailbreak techniques, defense bypasses |
| Simon Willison's blog | LLM security analysis, real-world incidents |
| Embrace The Red | AI red team research, agent exploits |
| ArXiv | Academic papers on LLM/agent security |

---

## Using CSO

### Scheduled

A daily scan runs automatically at 9:00 AM (task `eed725b9`). CSO follows the full Daily Scan Workflow and reports results via Telegram.

```bash
cd claudeclaw
node dist/schedule-cli.js list --agent cso          # list tasks
node dist/schedule-cli.js pause eed725b9             # pause daily scan
node dist/schedule-cli.js resume eed725b9            # resume daily scan
node dist/schedule-cli.js delete eed725b9            # delete daily scan
```

### On-Demand (Telegram)

Message `@CC_CSO_bot` directly:

| Message | What CSO Does |
|---------|--------------|
| `run a scan` | Full 8-domain security scan |
| `check dependencies` | DEP domain only |
| `check secrets` | SEC domain |
| `check permissions` | FS domain |
| `check ports` | NET domain |
| `check mcp` | MCP domain |
| `check budget` | MON domain |
| `what's open?` | Query open findings |
| `fix <package>` | Start remediation workflow (shows finding, waits for approval) |
| `threat intel` | Search intelligence sources |
| `run security-monitor.py` | Execute runtime monitor |
| `status` | Summary of last scan, open findings, budget |

CSO also responds to natural language -- "are there any critical findings?", "when was the last scan?", "rotate the Anthropic key", etc.

### CSO Reporting Chain

```
CSO detects issue
  |
  +-- P3/P2 finding --> Logs to security_findings table, reports to Mike
  |
  +-- P1 critical vuln --> Logs finding + alerts Mike immediately
  |
  +-- P0 active breach --> Stops bot, preserves evidence, alerts Mike
  |
  +-- Needs new capability --> Logs capability_request to hive_mind
                                Asks Cos to relay to Mike
```

---

## PM2 Process Management

All agents run as PM2 processes for auto-restart and centralized management.

### Ecosystem File

`ecosystem.config.js` defines all processes:

```js
module.exports = {
  apps: [
    { name: 'claudeclaw-pa',  script: 'dist/index.js' },
    { name: 'claudeclaw-cos', script: 'dist/index.js', args: '--agent cos' },
    { name: 'claudeclaw-cso', script: 'dist/index.js', args: '--agent cso' },
    { name: 'claudeclaw-cmo', script: 'dist/index.js', args: '--agent cmo' },
  ],
};
```

### Common Commands

| Command | What It Does |
|---------|-------------|
| `pm2 list` | Show status of all processes |
| `pm2 restart all` | Restart all running processes |
| `pm2 stop all` | Stop all processes |
| `pm2 logs claudeclaw-cso` | Tail CSO logs |
| `pm2 logs claudeclaw-cso --nostream --lines 50` | Last 50 lines |
| `pm2 save` | Save current process list (for resurrect) |
| `pm2 resurrect` | Restore saved process list after reboot |

### Adding a New Agent

1. Create: `agents/<name>/agent.yaml` + `agents/<name>/CLAUDE.md`
2. Add bot token to `.env`: `<NAME>_BOT_TOKEN=...`
3. Add entry to `ecosystem.config.js`
4. Start: `pm2 start dist/index.js --name claudeclaw-<name> -- --agent <name>`
5. Save: `pm2 save`

### Log Locations

PM2 logs are at `C:\Users\shopp\.pm2\logs\`:
- `claudeclaw-cso-out.log` -- stdout
- `claudeclaw-cso-error.log` -- stderr

---

## macOS to Windows Conversion Guide

The security skill was originally written for macOS. This section documents every platform adaptation made, serving as a reference for converting other macOS-oriented skills to Windows.

### Command Substitutions

| Task | macOS | Windows |
|------|-------|---------|
| Check file permissions | `ls -la <path>` or `stat -f '%A' <path>` | `icacls <path>` |
| Restrict file to owner | `chmod 600 <path>` | `icacls <path> /inheritance:r /grant:r "%USERNAME%:F"` |
| Restrict directory to owner | `chmod 700 <path>` | `icacls <path> /inheritance:r /grant:r "%USERNAME%:F"` |
| Add SYSTEM access | N/A | `icacls <path> /grant:r "SYSTEM:F"` (often needed alongside user) |
| List listening ports | `lsof -i -P -n \| grep LISTEN` | `netstat -ano \| findstr LISTENING` |
| Resolve PID to process | `ps -p <PID> -o comm=` | `tasklist /FI "PID eq <PID>" /FO CSV /NH` |
| Kill process by name | `pkill -f claudeclaw` | `taskkill /F /IM node.exe /FI "WINDOWTITLE eq claudeclaw"` |
| Kill process by PID | `kill -9 <PID>` | `taskkill /F /PID <PID>` |
| Block all network | `pfctl -e && pfctl -f /etc/pf.conf` | `netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound` |
| Restore network | `pfctl -d` | `netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound` |
| Check scheduled tasks | `crontab -l` | `schtasks /query /fo LIST \| findstr -i claude` |
| Find recently modified files | `find . -mtime -1` | PowerShell: `Get-ChildItem -Recurse \| Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-24) }` |
| Temp directory | `/tmp/` | `%TEMP%` or `os.tmpdir()` in Node |
| Home directory | `~` or `$HOME` | `%USERPROFILE%` or `os.homedir()` in Node |
| Null device | `/dev/null` | `NUL` (cmd) or `/dev/null` (Git Bash) |
| Path separator | `/` | `\` (cmd/PowerShell) or `/` (Git Bash, Node `path.join`) |

### ACL Concepts: chmod vs icacls

macOS/Linux uses numeric permission bits (owner/group/other):
```bash
chmod 600 .env    # owner read+write, no group, no other
chmod 700 store/  # owner read+write+execute, no group, no other
```

Windows uses Access Control Lists with named principals:
```bash
# Remove inherited permissions, grant only to current user
icacls .env /inheritance:r /grant:r "%USERNAME%:F"

# Common principals to watch for:
# - Everyone           -> world-readable (BAD)
# - BUILTIN\Users      -> all local users (BAD for sensitive files)
# - NT AUTHORITY\Authenticated Users -> all authenticated (BAD)
# - SYSTEM             -> Windows OS (usually OK)
# - Administrators     -> admin group (usually OK)
# - %USERNAME%         -> current user (GOOD for owner-only)
```

**Key difference:** On macOS, `chmod 600` is one command. On Windows, you need `/inheritance:r` first (strip inherited permissions), then `/grant:r` (replace with explicit grant). Without `/inheritance:r`, the file inherits parent directory permissions and your explicit grant is additive.

### Python Script Adaptations

The `security-monitor.py` was adapted as follows:

1. **File permission checks**: Replaced `os.stat()` + `stat.S_IMODE()` with `subprocess.run(['icacls', path])` + custom parser
2. **ACL parsing**: Added `_parse_icacls_output()` to extract `(principal, permissions)` tuples from icacls output
3. **Loose ACL detection**: Added `_has_loose_acl()` checking for Everyone, BUILTIN\Users, Authenticated Users
4. **Port scanning**: Replaced `lsof -i -P -n` with `netstat -ano` + `tasklist` PID resolution
5. **Process names**: `tasklist /FI "PID eq X" /FO CSV /NH` instead of `ps -p X -o comm=`

### Bash Script Adaptations

The `security-scan.sh` was adapted:

1. **ACL checks**: `icacls.exe` instead of `ls -la` with permission parsing
2. **Broad ACL grep**: `grep -iE "(Everyone|BUILTIN\\\\Users)"` to find loose principals
3. **Port check**: `netstat -ano | grep ":16992"` instead of `lsof` for Intel AMT detection
4. **Command availability**: `command -v icacls.exe` guard before ACL checks

### Shell Environment Notes

ClaudeClaw runs in Git Bash on Windows. This means:
- Unix shell syntax works (`/dev/null`, forward slashes, `$(...)`)
- But Windows executables are available (`icacls.exe`, `netstat`, `tasklist`, `schtasks`)
- Paths can use forward slashes in most contexts
- Environment variables: `$HOME` works, `%USERPROFILE%` works in cmd-passthrough
- `subprocess.run()` in Python uses Windows executables directly

### Checklist for Converting Any Skill to Windows

1. **Grep for platform-specific commands**: `chmod`, `chown`, `lsof`, `pkill`, `kill -9`, `stat`, `crontab`, `pfctl`
2. **Replace with Windows equivalents** per the table above
3. **Test `icacls` output parsing** -- format differs from `ls -la`, needs custom parser
4. **Check path handling** -- forward slashes generally work in Git Bash and Node, but `icacls` and other Windows tools may need backslashes
5. **Check temp file paths** -- `/tmp/` doesn't exist on Windows, use `os.tmpdir()` or `%TEMP%`
6. **Test subprocess calls** -- `subprocess.run()` in Python on Windows may need `shell=True` for some commands, or use `.exe` suffix
7. **Verify `.sh` scripts work in Git Bash** -- most do, but watch for `declare -A` (associative arrays need Bash 4+, Git Bash usually has it)
8. **Test the full skill** by running the agent and triggering each check manually via Telegram

---

## Component References

| Component | Path | Status |
|-----------|------|--------|
| Token router | `src/token-router.ts` | Active |
| Budget tracker | `src/token-budget.ts` | Active |
| Dependency scanner | `scripts/security-scan.sh` | Active |
| Runtime monitor | `skills/security/scripts/security-monitor.py` | Active |
| Security findings DB | `store/claudeclaw.db` (table: `security_findings`) | Active |
| Token budget DB | `store/claudeclaw.db` (table: `token_budget`) | Active |
