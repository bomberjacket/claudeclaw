# Security Skill & CSO Agent -- Operations Guide

**Date:** 2026-03-12
**Status:** Deployed and running

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
  │
  ├── @CC_CSO_bot (CSO agent)
  │     │
  │     ├── Runs 8-domain security scans
  │     ├── Executes security-monitor.py
  │     ├── Tracks findings in security_findings table
  │     ├── Responds to incident playbooks (P0-P3)
  │     │
  │     └── Needs a new capability?
  │           │
  │           ▼
  │     Logs capability_request to hive_mind
  │           │
  │           ▼
  │     Cos relays request to Mike
  │           │
  │           ▼
  │     Mike approves/denies
  │
  ├── @CC_Cos_bot (Cos agent)
  │     └── Orchestrates workflows, relays CSO capability requests
  │
  └── @CC_XO_bot (main bot)
```

---

## File Structure

### Security Skill

```
skills/security/
├── SKILL.md                              # Entry point: frontmatter, 8-domain framework,
│                                         #   daily workflow, finding lifecycle, rules
├── references/
│   ├── threat-taxonomy.md                # T1-T4 threat tiers, OWASP ASI, defense principles
│   ├── hardening-checklist.md            # 8-domain checklists, severity scoring, frequency
│   ├── incident-response.md              # P0-P3 playbooks, credential rotation, anomaly indicators
│   └── token-budget-security.md          # Budget architecture, multi-provider routing, monitoring
└── scripts/
    └── security-monitor.py               # Runtime monitor (Windows: icacls, netstat)
```

### CSO Agent

```
agents/cso/
├── agent.yaml          # name, bot token env var, model
└── CLAUDE.md           # Role, procedures, scope boundaries, escalation chain
```

---

## 8-Domain Scan Framework

Every security scan evaluates across all 8 domains:

| Domain | Code | What It Covers |
|--------|------|----------------|
| Dependency Security | DEP | npm audit, outdated packages, SBOM |
| Secret Management | SEC | .env permissions, hardcoded secrets, git history, token rotation |
| File System Security | FS | ACLs on store/, .env, project files (Windows icacls) |
| MCP & Tool Security | MCP | Server configs, tool descriptions, scope review |
| Agent Configuration | AGT | Settings hooks, skills review, CLAUDE.md, respin safety |
| Network & API | NET | Open ports (netstat), API key exposure, HTTPS enforcement |
| AI Threat Intelligence | AITL | CVEs, prompt injection, jailbreaks, supply chain, research |
| Runtime Monitoring | MON | Token usage, cost spikes, message floods, budget alerts |

---

## Runtime Monitor

The Python script at `skills/security/scripts/security-monitor.py` uses only stdlib (no pip installs).

**Run manually:**
```bash
cd claudeclaw
python skills/security/scripts/security-monitor.py --json       # JSON output
python skills/security/scripts/security-monitor.py              # Pretty-printed
python skills/security/scripts/security-monitor.py --all        # Include file + port checks
python skills/security/scripts/security-monitor.py --check-files  # File ACL checks only
python skills/security/scripts/security-monitor.py --check-ports  # Port scan only
```

**What it checks:**
- Token usage anomalies (cost spikes, compaction events)
- Token budget status across providers (75%/95% thresholds)
- Message patterns (flood detection, off-hours activity)
- File permissions via `icacls` (loose ACLs on .env, store/)
- Open ports via `netstat -ano` (node processes listening)
- MCP configs (enableAllProjectMcpServers, .mcp.json review)
- Hardcoded secrets in source files

**Configuration:** Edit the constants at the top of the script. Key settings:
- `CLAUDECLAW_DIR` env var or `_BASE` default path
- `COST_SPIKE_THRESHOLD` (default: $5/session)
- `MSG_FLOOD_THRESHOLD` (default: 50/hour)
- `DAILY_BUDGET_USD` (default: $10)

---

## Windows-Specific Details

This skill was adapted from macOS. All platform-specific commands use Windows equivalents:

| Task | Command |
|------|---------|
| Check file permissions | `icacls <path>` |
| Restrict file to owner | `icacls <path> /inheritance:r /grant:r "%USERNAME%:F"` |
| List listening ports | `netstat -ano \| findstr LISTENING` |
| Kill bot process | `taskkill /F /IM node.exe /FI "WINDOWTITLE eq claudeclaw"` |
| Kill Claude processes | `taskkill /F /IM claude.exe 2>nul` |
| Block all network | `netsh advfirewall set allprofiles firewallpolicy blockinbound,blockoutbound` |
| Restore network | `netsh advfirewall set allprofiles firewallpolicy blockinbound,allowoutbound` |
| Check scheduled tasks | `schtasks /query /fo LIST \| findstr -i claude` |
| Find recently modified files | PowerShell `Get-ChildItem -Recurse \| Where-Object { $_.LastWriteTime -gt (Get-Date).AddHours(-24) }` |

---

## Using CSO

### Scheduled

A daily scan runs automatically at 9:00 AM (task `eed725b9`). CSO follows the full Daily Scan Workflow and reports results to Mike via Telegram.

Manage the schedule:
```bash
cd claudeclaw
node dist/schedule-cli.js list --agent cso          # list tasks
node dist/schedule-cli.js pause eed725b9             # pause daily scan
node dist/schedule-cli.js resume eed725b9            # resume daily scan
node dist/schedule-cli.js delete eed725b9            # delete daily scan
```

### On-Demand (Telegram)

Message `@CC_CSO_bot` directly with any of these:

| Message | What CSO Does |
|---------|--------------|
| `run a scan` | Full 8-domain security scan |
| `check dependencies` | DEP domain only -- npm audit, outdated packages |
| `check secrets` | SEC domain -- .env permissions, hardcoded secrets, git history |
| `check permissions` | FS domain -- file ACLs on store/, .env |
| `check ports` | NET domain -- listening ports, unexpected services |
| `check mcp` | MCP domain -- server configs, enableAllProjectMcpServers |
| `check budget` | MON domain -- token budget status, spend anomalies |
| `what's open?` | Query open findings from security_findings table |
| `fix <package>` | Start remediation workflow (shows finding, waits for approval) |
| `threat intel` | Search intelligence sources for emerging AI agent threats |
| `run security-monitor.py` | Execute runtime monitor and report results |
| `status` | Summary of last scan, open findings count, budget status |

CSO also responds to natural language -- "are there any critical findings?", "when was the last scan?", "rotate the Anthropic key", etc. It will always query the DB first, never rely on conversation memory.

### Incident Triggers

CSO follows severity-based playbooks automatically:

| Severity | CSO Behavior |
|----------|-------------|
| P0 (active breach) | Stops bot, preserves evidence, alerts Mike immediately |
| P1 (critical vuln) | Alerts Mike immediately, proposes fix, waits for approval |
| P2 (high severity) | Logs finding, includes in next report, flags for attention |
| P3 (medium/hardening) | Logs finding, tracks in DB, reports in daily scan |

---

## PM2 Process Management

All agents run as PM2 processes for auto-restart and centralized management.

### Ecosystem File

`ecosystem.config.js` defines all processes:

```js
module.exports = {
  apps: [
    { name: 'claudeclaw',     script: 'dist/index.js' },
    { name: 'claudeclaw-cos', script: 'dist/index.js', args: '--agent cos' },
    { name: 'claudeclaw-cso', script: 'dist/index.js', args: '--agent cso' },
  ],
};
```

### Common Commands

| Command | What It Does |
|---------|-------------|
| `pm2 list` | Show status of all processes |
| `pm2 start ecosystem.config.js` | Start all processes from scratch |
| `pm2 restart all` | Restart all running processes |
| `pm2 stop all` | Stop all processes |
| `pm2 logs claudeclaw-cso` | Tail CSO logs |
| `pm2 logs claudeclaw-cso --nostream --lines 50` | Last 50 lines of CSO logs |
| `pm2 save` | Save current process list (for resurrect) |
| `pm2 resurrect` | Restore saved process list after reboot |
| `pm2 startup` | Generate auto-start script for Windows boot |

### Adding a New Agent

1. Create the agent: `agents/<name>/agent.yaml` + `agents/<name>/CLAUDE.md`
2. Add bot token to `.env`: `<NAME>_BOT_TOKEN=...`
3. Add entry to `ecosystem.config.js`:
   ```js
   { name: 'claudeclaw-<name>', script: 'dist/index.js', args: '--agent <name>' },
   ```
4. Start it: `pm2 start dist/index.js --name claudeclaw-<name> -- --agent <name>`
5. Save: `pm2 save`

After step 5, `pm2 restart all` will include the new agent going forward.

**Important:** `pm2 restart all` only restarts processes PM2 already knows about. You must `pm2 start` a new agent first, then `pm2 save`, before it becomes part of `restart all`.

### Logs

PM2 logs are stored at `C:\Users\shopp\.pm2\logs\`:
- `claudeclaw-cso-out.log` -- stdout
- `claudeclaw-cso-error.log` -- stderr

---

## CSO Reporting Chain

```
CSO detects issue
  │
  ├── P3/P2 finding ──▶ Logs to security_findings table
  │                      Reports to Mike via Telegram
  │
  ├── P1 critical vuln ──▶ Logs finding + alerts Mike immediately
  │
  ├── P0 active breach ──▶ Stops bot, preserves evidence, alerts Mike
  │
  └── Needs new capability ──▶ Logs capability_request to hive_mind
                                Asks Cos to relay to Mike
```

CSO logs all actions to `hive_mind` so other agents (especially Cos) have visibility:
- `scan_completed`, `finding_created`, `finding_fixed`
- `incident_detected`, `incident_resolved`
- `capability_request`, `threat_intel`

---

## Credential Rotation Schedule

| Credential | Rotation | How |
|-----------|----------|-----|
| `TELEGRAM_BOT_TOKEN` | On compromise or annually | BotFather > Revoke Token |
| `ANTHROPIC_API_KEY` | On compromise or quarterly | console.anthropic.com > API Keys |
| `GOOGLE_API_KEY` | On compromise or quarterly | console.cloud.google.com > Credentials |
| `SLACK_USER_TOKEN` | On compromise or annually | Slack App > OAuth & Permissions |
| `CSO_BOT_TOKEN` | On compromise or annually | BotFather > Revoke Token |
| `COS_BOT_TOKEN` | On compromise or annually | BotFather > Revoke Token |

---

## Component References (Not Yet Verified)

These components are referenced in the security skill but may not exist yet:

| Component | Path | Status |
|-----------|------|--------|
| Token router | `src/token-router.ts` | Verify after install |
| Budget tracker | `src/token-budget.ts` | Verify after install |
| Dependency scanner | `scripts/security-scan.sh` | Verify after install |
| `/tokens` command | Telegram slash command | Verify after install |
| `/respin` command | Telegram slash command | Verify after install |

These are referenced for completeness. The security skill and CSO agent function independently of them.
