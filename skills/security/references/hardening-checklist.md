# Hardening Checklist

The security agent evaluates across 8 domains. Each produces scored findings.

## Scan Categories

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
- [ ] `CLAUDE_CODE_OAUTH_TOKEN` if used, has minimum scope
- [ ] `GOOGLE_API_KEY` treated as critical credential (used for Gemini routing and budget fallback)
- [ ] `TOKEN_DAILY_BUDGET_USD` set to a reasonable limit (prevents runaway spend)

### 3. File System Security (FS)
- [ ] `store/` directory: owner-only via `icacls store /inheritance:r /grant:r "%USERNAME%:F"`
- [ ] `store/claudeclaw.db`: owner-only ACL
- [ ] `store/*.pid`, `store/*.txt`: owner-only ACL
- [ ] No files with loose ACLs granting access to `Everyone` or `Users` group
- [ ] `.obsidian/` configs not executable
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
- [ ] Session-level context not carrying stale permissions
- [ ] Memory context gating active (trivial messages skip memory lookup to reduce attack surface)

### 6. Network & API Security (NET)
- [ ] No unexpected listening ports (`netstat -ano | findstr LISTENING`)
- [ ] Telegram bot token not exposed in logs
- [ ] API keys not in any URL parameters (note: Gemini API uses key= in URL -- ensure not logged)
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
- [ ] Token budget (`/tokens` command) shows spend within daily limit
- [ ] No untracked API calls bypassing the token router
- [ ] No compaction events outside heavy operations
- [ ] Message volume within baseline (no flood patterns)
- [ ] No off-hours activity if unexpected
- [ ] Error rate within normal range
- [ ] No repeated failed auth attempts in logs
- [ ] Budget hard-limit (95%) functioning -- all calls downgrade to Gemini when triggered

---

## Severity Scoring

| Severity | Criteria | SLA |
|----------|----------|-----|
| CRITICAL | Active exploit exists, directly affects this system, RCE/data exfil possible | Fix within 24 hours |
| HIGH | Exploit exists or emerging threat, affects this stack, elevated risk | Fix within 72 hours |
| MEDIUM | Known issue, indirect risk, defense-in-depth improvement | Fix within 7 days |
| LOW | Best practice improvement, minimal direct risk | Fix within 30 days |
| INFO | Awareness item, no action required | Track only |

## Scan Frequency

| Domain | Frequency | Method |
|--------|-----------|--------|
| DEP | Daily | `security-scan.sh` + `npm audit` |
| SEC | Daily | `security-scan.sh` secret grep |
| FS | Daily | `security-scan.sh` permission check |
| MCP | Weekly | Manual review or agent-assisted |
| AGT | Weekly | Agent self-audit |
| NET | Daily | Port scan in `security-scan.sh` |
| AITL | Daily | AI web search (8 sources) |
| MON | Continuous | `security-monitor.py` on each scan + `token_budget` table |
