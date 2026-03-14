# Agent Collaboration System -- Design Document

**Date:** 2026-03-11
**Status:** Implemented (pending live testing)

---

## Problem

ClaudeClaw's multi-agent system runs agents as isolated silos. Each agent has its own Telegram bot, its own session, and shares a SQLite DB (WAL mode). A `hive_mind` table exists and agents are told (via CLAUDE.md) to log actions there, but nothing auto-reads hive_mind entries -- agents can't see what teammates have done unless they manually run SQL.

Goal: agents that are aware of each other's work, can hand off tasks, have focused skill sets, and improve at their specialty over time.

---

## What Was Built

Three features added to the core system:

### 1. Team Awareness

Agents automatically see what their teammates have been doing. On every message, `buildTeamContext()` in `src/memory.ts` queries hive_mind for:
- **Pending handoffs** targeted at this agent (marked as `accepted` once injected)
- **Recent team activity** (last 8 entries from other agents, with relative timestamps)

This context block is injected alongside memory and obsidian context before each agent response. The main bot (`AGENT_ID === 'main'`) is excluded -- it doesn't need team context.

**Token cost:** ~500-800 tokens per message (well under 1% of 1M context window).

### 2. Cross-Agent Handoffs

Agents can delegate tasks to specific teammates via hive_mind. The flow:

1. Agent A inserts a row with `target_agent = 'agent-b'` and `status = 'pending'`
2. Next time Agent B processes a message, `buildTeamContext()` picks up the handoff
3. The handoff appears in Agent B's context as `[Pending handoffs for you]`
4. The row is marked `status = 'accepted'` so it doesn't repeat

Agents can create handoffs via SQL (instructions in their CLAUDE.md) or programmatically via `logHandoff()` in `src/db.ts`.

### 3. Per-Agent Skill Scoping

Each agent's `agent.yaml` can list specific skills from `~/.claude/skills/`. At startup, `src/index.ts` creates an `agents/<id>/.skills/` directory with Windows-compatible junction symlinks to only the allowed global skills.

This is currently a **soft scope** -- the SDK still loads global skills, but the agent's CLAUDE.md and the `.skills/` directory focus the agent on its designated skills. Future SDK versions may support per-directory skill loading, at which point `.skills/` becomes a hard scope.

---

## Files Changed

| File | What |
|------|------|
| `src/db.ts` | Migration: `target_agent` + `status` columns on hive_mind. New functions: `getTeamActivity()`, `getPendingHandoffs()`, `updateHandoffStatus()`, `logHandoff()`. Updated `HiveMindEntry` interface. |
| `src/memory.ts` | New `buildTeamContext()` function. Wired into `buildMemoryContext()` as third block after memory + obsidian. |
| `src/agent-config.ts` | Added `skills?: string[]` to `AgentConfig` interface. Parsed from YAML. |
| `src/index.ts` | Creates `.skills/` with junction symlinks at agent startup. |
| `src/bot.ts` | Auto-logs 150-char response snippet to hive_mind after every agent response (skips main). |
| `agents/_template/agent.yaml.example` | Added `skills` field documentation. |
| `agents/_template/CLAUDE.md` | Added Team Awareness, Handoffs sections. |
| `agents/comms/agent.yaml` | Added skills list. |
| `agents/research/agent.yaml` | Added skills list. |
| `agents/ops/agent.yaml` | Added skills list. |
| `agents/content/agent.yaml` | Added skills list. |
| `agents/*/CLAUDE.md` | All four agents updated with Team Awareness + Handoffs sections. |

---

## Reference Patterns (for future agent design)

Two external skill structures were analyzed and should inform how specialized agents are built. Both use the same Claude Skills convention: a `SKILL.md` entry point with a `references/` directory for lazy-loaded content.

### Visual Comparison

```
┌─────────────────────────────────┐  ┌─────────────────────────────────┐
│   PATTERN 1: ADVISORY BOARD    │  │  PATTERN 2: CHECKLIST ORCH.     │
│   (Domain Expertise)            │  │  (Stateful Workflow Execution)  │
├─────────────────────────────────┤  ├─────────────────────────────────┤
│                                 │  │                                 │
│  advisory-board/                │  │  checklist-orchestrator/        │
│  ├── SKILL.md (router)          │  │  ├── SKILL.md (sequencer)       │
│  └── references/                │  │  └── references/                │
│      ├── strategist.md          │  │      └── checklist_config.json  │
│      ├── product.md             │  │                                 │
│      ├── finance.md             │  │  + checklist_state.json         │
│      ├── sales.md               │  │    (crash recovery)             │
│      ├── marketing.md           │  │                                 │
│      ├── technical.md           │  ├─────────────────────────────────┤
│      └── founder-coach.md       │  │  EXECUTION MODEL                │
│                                 │  │                                 │
├─────────────────────────────────┤  │  Step 1 ──▶ Validate ──▶ Gate  │
│  EXECUTION MODEL                │  │    │         ✓ pass     stop│   │
│                                 │  │    ▼                   pause│   │
│  Question ──▶ Route to expert   │  │  Step 2 ──▶ Validate   warn │   │
│                 │                │  │    │         ✓ pass          │
│                 ▼                │  │    ▼                         │
│          Load reference .md     │  │  Step N ──▶ Complete         │
│                 │                │  │                                 │
│                 ▼                │  ├─────────────────────────────────┤
│          Synthesize response    │  │  KEY TRAITS                     │
│          (single voice)         │  │  · Pipeline = JSON data         │
│                                 │  │  · One skill per step           │
├─────────────────────────────────┤  │  · State file for resume        │
│  KEY TRAITS                     │  │  · Validation gates (3 modes)   │
│  · Lazy-load refs on demand     │  │  · DOES execute (tools, files)  │
│  · Stage calibration first      │  │  · Structured progress output   │
│  · Anti-pattern lists           │  │                                 │
│  · Single voice synthesis       │  │                                 │
│  · DOES NOT execute (advisory)  │  │                                 │
└─────────────────────────────────┘  └─────────────────────────────────┘

                         │                        │
                         └───────────┬────────────┘
                                     ▼

          ┌───────────────────────────────────────────────┐
          │      COMBINED: CLAUDECLAW AGENT STRUCTURE     │
          ├───────────────────────────────────────────────┤
          │                                               │
          │  agents/your-agent/                           │
          │  ├── agent.yaml          (config + skills)    │
          │  ├── CLAUDE.md           (brain)              │
          │  │   ├─ Role & routing logic    ◀── Pat.1     │
          │  │   ├─ Execution rules         ◀── Pat.2     │
          │  │   ├─ Anti-patterns           ◀── Pat.1     │
          │  │   ├─ Team awareness          ◀── NEW       │
          │  │   └─ Handoff instructions    ◀── NEW       │
          │  └── references/                              │
          │      ├── domain-knowledge.md   ◀── Pat.1      │
          │      │   (deep expertise, lazy-loaded)        │
          │      ├── frameworks.md         ◀── Pat.1      │
          │      │   (named methods + "how to apply")     │
          │      ├── workflow-config.json   ◀── Pat.2     │
          │      │   (repeatable processes as data)       │
          │      └── anti-patterns.md      ◀── Pat.1      │
          │          (what NOT to do)                      │
          │                                               │
          ├───────────────────────────────────────────────┤
          │  WHAT IT KNOWS (Pat.1)  │ HOW IT ACTS (Pat.2) │
          │  · Domain expertise     │ · Step-by-step exec │
          │  · Frameworks           │ · Validate per step │
          │  · Stage awareness      │ · Resume on crash   │
          │  · Anti-patterns        │ · Progress reports  │
          ├─────────────────────────┴─────────────────────┤
          │  WHAT'S NEW (ClaudeClaw additions)            │
          │  · Team context injection (hive_mind)         │
          │  · Cross-agent handoffs (pending → accepted)  │
          │  · Per-agent skill scoping (.skills/ junctions)│
          │  · Learning pipeline → auto-updates refs      │
          └───────────────────────────────────────────────┘
```

### Pattern 1: Advisory Board (Domain Expertise)

**Source:** NimbleDraft Advisory Board Skill
**Purpose:** Route questions to the right expert, return framework-driven advice.

```
advisory-board/
├── SKILL.md              (entry point -- routing logic, response formats, anti-patterns)
└── references/           (loaded on demand per advisor)
    ├── strategist.md     (184 lines of frameworks: Thiel, PG, Naval, Pieter Levels...)
    ├── product.md        (175 lines)
    ├── finance.md        (300 lines)
    ├── sales.md          (195 lines)
    ├── marketing.md      (189 lines)
    ├── technical.md      (218 lines)
    ├── founder-coach.md  (177 lines)
    └── ROUTING.md        (61 lines -- redundant, subset of SKILL.md)
```

**Key design decisions:**
- **Lazy loading** -- reference files only read when that advisor is triggered. Keeps token cost low.
- **Single voice synthesis** -- when multiple advisors contribute, output is woven into one unified response. Never separate sections per advisor.
- **Stage calibration** -- diagnoses user's stage first (idea / pre-PMF / PMF / growth), then gates advice to that stage. Prevents recommending growth tactics to someone who hasn't found PMF.
- **Structured output templates** -- three formats: Standard (recommendation + action plan + decision points + success metrics), Quick Verdict (yes/no with reasoning), Founder Coach (reflection + one action).
- **Anti-pattern lists** -- explicit "what NOT to do" sections. These shape behavior better than positive instructions alone.
- **Thinking only** -- explicitly refuses to execute (no tool calls, no file creation). All execution is the user's responsibility. This constraint would be FLIPPED for ClaudeClaw agents that need to act.

**How this maps to ClaudeClaw agents:**
- Each agent gets `references/*.md` files containing deep domain knowledge for its specialty.
- The agent's CLAUDE.md contains routing logic: "when you encounter X type of task, read `references/X.md` first."
- The learning pipeline can generate/update these reference files over time as the agent discovers what works.
- Anti-pattern lists in CLAUDE.md prevent the agent from drifting outside its specialty.

### Pattern 2: Checklist Orchestrator (Stateful Workflow Execution)

**Source:** CMMC/NIST 800-171 Checklist Orchestrator Skill
**Purpose:** Run a multi-step pipeline with state tracking and validation between stages.

```
checklist-orchestrator/
├── SKILL.md              (entry point -- step sequence, execution rules, progress format)
└── references/
    └── checklist_config.json   (pipeline definition as data)
```

**Key design decisions:**
- **One skill per step, loaded and unloaded** -- context window management. Each pipeline step references a separate skill, so the agent never has all steps' logic loaded simultaneously.
- **JSON config for pipeline definition** -- steps, validation rules, and failure behavior are data, not prose. Pipeline can be changed without rewriting the SKILL.md.
- **State file for crash recovery** -- `checklist_state.json` tracks completed steps. `resume checklist` picks up where it left off after a session dies.
- **Validation gates with three behaviors:**
  - `stop` -- hard fail, checklist halts
  - `pause` -- ask user for instruction (retry / skip / abort)
  - `warn_and_continue` -- log the issue, keep going
- **Structured progress reporting** -- every step outputs a formatted status block with results, validation pass/fail, and what's next.
- **Execution focused** -- unlike the Advisory Board, this skill DOES things. Each step invokes tools, creates files, queries databases.

**How this maps to ClaudeClaw agents:**
- Agents that run repeatable multi-step processes (audits, onboarding, content publishing pipelines) should define their workflows as JSON configs in `references/`.
- The agent's CLAUDE.md contains execution rules (one step at a time, validate before proceeding).
- State tracking via a JSON file means the agent can resume workflows across sessions.
- Validation gates prevent the agent from plowing through broken pipelines.

### Combined Pattern for Specialized Agents

A well-designed ClaudeClaw agent should blend both patterns:

```
agents/your-agent/
├── agent.yaml                 (config: name, bot token, model, skills)
├── CLAUDE.md                  (role, routing logic, execution rules, anti-patterns,
│                               team awareness, handoff instructions)
└── references/
    ├── domain-knowledge.md    (Advisory Board pattern -- deep expertise)
    ├── frameworks.md          (named frameworks with "how to apply" steps)
    ├── workflow-config.json   (Orchestrator pattern -- repeatable processes)
    └── anti-patterns.md       (what NOT to do -- common mistakes in this domain)
```

The agent knows WHAT to do (domain knowledge from reference files) and HOW to execute it (workflow configs), and gets better at both over time through the learning pipeline.

**Learning pipeline integration (future):**
- The existing learning pipeline extracts knowledge from conversations and stores it as memories in SQLite.
- A natural extension: periodically consolidate high-value memories into `references/` files.
- This means the agent literally writes its own playbook. The more it does a task, the richer the reference files become.

---

## Data Flow

```
User message -> Agent bot
  |
  v
[INBOUND GATE] sanitizeInbound()
  |
  v
buildMemoryContext()
  |-- recalled memories (sanitized)
  |-- obsidian context
  |-- buildTeamContext()
  |     |-- getPendingHandoffs(AGENT_ID) -> inject + mark accepted
  |     |-- getTeamActivity(exclude self) -> recent teammate actions
  |
  v
runAgent() [Claude Code SDK]
  |
  v
rawResponse
  |
  v
[OUTBOUND GATE] sanitizeOutbound()
  |
  v
saveConversationTurn() -> learning pipeline (fire-and-forget)
  |
  v
logToHiveMind() -> other agents see this next turn
  |
  v
Send to Telegram
```

---

## DB Schema Changes

### hive_mind table (new columns)

```sql
-- Added by migration in runMigrations()
ALTER TABLE hive_mind ADD COLUMN target_agent TEXT DEFAULT NULL;
ALTER TABLE hive_mind ADD COLUMN status TEXT NOT NULL DEFAULT 'logged';
```

**status values:**
- `logged` -- normal hive_mind entry (team awareness)
- `pending` -- handoff waiting for target agent to pick up
- `accepted` -- handoff was injected into target agent's context
- `completed` -- (future) target agent finished the handoff task

### New functions in src/db.ts

```typescript
getTeamActivity(excludeAgentId: string, limit = 10): HiveMindEntry[]
getPendingHandoffs(targetAgent: string): HiveMindEntry[]
updateHandoffStatus(id: number, status: string): void
logHandoff(fromAgent: string, chatId: string, targetAgent: string, summary: string, artifacts?: string): void
```

---

## Verification Checklist

1. [ ] `npm run build` compiles clean (DONE -- verified 2026-03-11)
2. [ ] Start two agents (e.g., comms + research). Send a message to comms. Check that comms logs to hive_mind.
3. [ ] Send a message to research. Verify it sees comms' recent activity in `[Recent team activity]` block.
4. [ ] Test handoff: from comms, insert a handoff row targeting research. Send a message to research and verify it gets the `[Pending handoffs for you]` block.
5. [ ] Verify skill scoping: check that `agents/<id>/.skills/` contains symlinks only to the skills listed in agent.yaml.
6. [ ] Verify main bot is unaffected (no team context injected for `AGENT_ID === 'main'`).
7. [ ] Test crash recovery: kill an agent mid-conversation, restart, verify hive_mind state is intact.

---

## Known Limitations

- **Skill scoping is soft** -- the Claude Code SDK loads skills from `~/.claude/skills/` globally. The `.skills/` directory and CLAUDE.md instructions focus the agent, but don't technically prevent it from using other skills if prompted.
- **Handoff delivery is pull-based** -- the target agent only sees the handoff on its next message. There's no push notification. If the target agent is idle, the handoff sits until someone messages it.
- **Auto-logging is noisy** -- every agent response logs a 150-char snippet to hive_mind. For high-volume agents, this could flood the team activity feed. May need to add filtering (e.g., only log substantive actions, skip simple replies).
- **No handoff completion tracking** -- handoffs move from `pending` to `accepted` but there's no mechanism yet for the target agent to mark a handoff as `completed` and report back to the originating agent.

---

## Agent Roster

Current agents in the system:

| Agent | Directory | Role |
|-------|-----------|------|
| Comms | `agents/comms/` | Email, Slack, WhatsApp, YouTube comments, Skool, LinkedIn |
| Content | `agents/content/` | YouTube, LinkedIn, writing, trend research |
| Ops | `agents/ops/` | Calendar, billing, Stripe, Gumroad, admin |
| Research | `agents/research/` | Deep research, academic, competitive intel |
| Cos | `agents/cos/` | Workflow orchestration -- multi-step workflows with supervised-to-autonomous graduation |
| CSO | `agents/cso/` | Chief Security Officer -- cybersecurity scanning, threat detection, incident response, runtime monitoring. Reports to Cos for capability requests. |

The `_template` directory is excluded from runtime (`listAgentIds()` skips `_` prefixed dirs).

---

## Agent Creation

**Primary method:** `/new-agent` skill (`skills/new-agent/SKILL.md`)

Interactive 9-section wizard that walks through identity, role, model, Telegram bot, skills (select existing, import from disk, or create new), reference knowledge, Obsidian integration, team awareness, and communication style. Generates all files: `agent.yaml`, `CLAUDE.md`, `references/`, optional new skills, `.env` token.

**Legacy method:** `scripts/agent-create.sh` (`npm run agent:create`)

Basic bash wizard -- pick a template, name, paste bot token. Does not create CLAUDE.md content, reference files, or skills. Superseded by `/new-agent` but kept for quick scaffolding.

---

## Architecture Vision: Department Heads + Sub-Agents

**Date:** 2026-03-14
**Status:** Planned

### Overview

The agent structure is evolving toward a department-based hierarchy. Each department has a **head agent** responsible for strategic decisions, routing, and quality control within its domain. Under each head, **sub-agents** handle specialized, repetitive execution tasks.

This structure maximizes the self-learning pipeline: narrow-scope agents accumulate domain-specific memories faster, building deep expertise over time. A generalist dilutes learning across everything; a specialist gets sharper with every interaction.

### Structure

```
Mike (human)
  |
  v
XO (main bot / personal assistant)
  |
  v
Cos (Chief of Staff -- workflow orchestration, advisory board)
  |
  |-- CMO (Marketing) ............. first department to stand up
  |   |-- Content sub-agent
  |   |-- SEO/GEO sub-agent
  |   |-- Social sub-agent
  |   └-- (future sub-agents as needed)
  |
  |-- CRO (Revenue/Sales)
  |   |-- Outreach sub-agent
  |   |-- Proposals sub-agent
  |   └-- Pipeline sub-agent
  |
  |-- CTO (Technical)
  |   |-- DevOps sub-agent
  |   |-- Code review sub-agent
  |   └-- Architecture sub-agent
  |
  |-- CFO (Finance)
  |   |-- Invoicing sub-agent
  |   |-- Forecasting sub-agent
  |   └-- Metrics sub-agent
  |
  |-- CSO (Security) .............. already running
  |   |-- Scanner sub-agent
  |   └-- Incident response sub-agent
  |
  |-- Comms ........................ existing, may fold under a dept
  |-- Ops .......................... existing, may fold under a dept
  └-- Research ..................... existing, cross-cutting resource
```

### Design Principles

1. **Start lean.** Stand up department heads first. Only spin up sub-agents when a specific task is repeating enough to justify specialization. Organic growth over upfront over-engineering.

2. **Heads think, sub-agents execute.** Department heads run on high-capability models (Opus/Sonnet) for strategic routing and quality control. Sub-agents handle volume work.

3. **Local LLMs for repetitive sub-agents.** High-volume, lower-complexity tasks (content drafting, social post generation, email templating) will run on local models once hardware supports it (pending GPU + PSU upgrade). The department head pattern makes this clean -- the head routes work to sub-agents regardless of whether they hit Anthropic's API or a local endpoint. Same handoff pattern either way.

4. **Self-learning compounds at specialization boundaries.** Each sub-agent's memory pipeline focuses on its narrow domain. A content sub-agent learns what messaging works, what tone lands, what gets engagement. That learning stays concentrated, not diluted across unrelated tasks.

5. **Department heads own the advisory board domain.** The advisory-board skill's domains map directly to department heads:
   - CMO <-> Marketing advisor
   - CRO <-> Sales advisor
   - CTO <-> Technical advisor
   - CFO <-> Finance advisor
   - Cos <-> Strategist + Chief of Staff synthesis

6. **Uniform handoff protocol.** All agents (heads and sub-agents) use the same hive_mind handoff mechanism. A department head dispatches to its sub-agents the same way Cos dispatches to department heads.

### Model Assignment Strategy

| Role | Model | Rationale |
|------|-------|-----------|
| Department heads | Opus 4.6 or Sonnet 4.6 | Strategic routing, quality control, complex reasoning |
| Sub-agents (API) | Sonnet 4.6 or Haiku 4.5 | Execution speed, cost efficiency |
| Sub-agents (local) | TBD (pending hardware) | Zero API cost for high-volume repetitive tasks |

### Rollout Plan

1. **Phase 1 (now):** Cos upgraded to Opus 4.6 with advisory-board skill. Architecture documented.
2. **Phase 2 (next):** Stand up CMO (Marketing department head). Migrate existing content agent under it.
3. **Phase 3 (after hardware):** Install local LLM, create first local sub-agent under CMO for content drafting.
4. **Phase 4 (ongoing):** Stand up additional departments as workload justifies them.
