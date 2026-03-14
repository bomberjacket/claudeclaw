# Threat Taxonomy

## Architecture: Why ClaudeClaw Is Maximum-Risk

ClaudeClaw satisfies Simon Willison's **Lethal Trifecta** -- all three present simultaneously:

1. **Private data access** -- full filesystem, SQLite DB, credentials, emails, calendar
2. **Untrusted content exposure** -- Telegram messages, web fetches, file reads, MCP tool results
3. **External action capability** -- unrestricted shell, network requests, API calls, file writes

This means: if an attacker gets malicious tokens into the context window, those tokens can trigger real-world actions with full user privileges. The entire security model depends on preventing, detecting, and containing this.

**Multi-provider surface area:** The Token Optimization Framework routes API calls across Anthropic and Google (Gemini). This doubles the API key surface -- both keys are resolved from `.env` at call time via `readEnvFile()`. Neither key enters `process.env` (by design), but both exist in JS heap during calls. Budget-aware downgrade at 95% spend means all traffic can shift to Google, making `GOOGLE_API_KEY` a critical credential.

---

## Threat Tiers

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

---

## OWASP ASI Reference (Agentic Security Initiative)

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

---

## Defense Principles

1. **Deterministic controls over AI-based detection** -- allowlists, sandboxing, parameterized validation beat prompt-based defenses
2. **Progressive privilege** -- start minimal, elevate explicitly, log everything
3. **All Telegram input is untrusted** -- it is the primary injection surface
4. **Tool result sanitization** -- clean all external content before feeding to LLM context
5. **Configuration files are code** -- validate `.claude/`, `.mcp.json`, skills with same rigor as executables
6. **Reduce autonomy where possible** -- the single most effective architectural mitigation
7. **Separation of concerns** -- privileged actions via separate validated pathways, not raw shell
8. **Budget as a security boundary** -- token budget limits blast radius of runaway or hijacked API calls; all model calls MUST go through the token router to maintain tracking
9. **API keys stay out of process.env** -- `readEnvFile()` resolves keys at call time without polluting the environment, reducing exposure to child processes
