---
name: new-agent
description: "Interactive wizard to create a fully configured ClaudeClaw agent with CLAUDE.md, references, and optional skills. Use when: Mike says /new-agent, 'create an agent', 'new agent', or 'set up an agent'."
allowed-tools:
  - AskUserQuestion
  - Read
  - Write
  - Glob
  - Bash(npm run build*)
  - Bash(ls *)
  - Bash(grep * .env)
  - Bash(echo * >> *)
  - Bash(cat *)
  - Bash(mkdir *)
  - Bash(node *)
  - Bash(unzip *)
  - Bash(cp *)
---

# New Agent Wizard

Create a fully configured ClaudeClaw agent through a structured interview. You will collect all the information needed, then generate every file at once.

## Important

- Use `AskUserQuestion` for EVERY section -- do not skip or assume answers.
- Generate real content based on answers -- never leave placeholder text like `[describe X here]`.
- Use forward slashes in all file paths.
- The project root is the directory containing this skill's parent `CLAUDE.md`. Find it with the claudeclaw dir (where `package.json` and `agents/` live).

## Interview Flow

Run these 9 sections in order. Each section uses one `AskUserQuestion` call (some sections may need a follow-up). Collect all answers before generating any files.

---

### Section 1: Identity

First, list existing agents so you know what's taken:

```bash
ls agents/ | grep -v _template
```

Then ask:

**Question:** "What should this agent be called?"
- Header: "Identity"
- Options:
  - Label: "I have a name in mind" / Description: "You'll type the agent ID, display name, and a one-sentence description"
  - Label: "Help me brainstorm" / Description: "Describe what the agent will do and I'll suggest names"

If they pick "I have a name in mind", ask a follow-up for:
- **Agent ID** (lowercase, hyphens ok, no spaces -- this becomes the directory name)
- **Display name** (human-friendly, used in agent.yaml `name:`)
- **Description** (1 sentence -- used for team awareness and handoff context)

If they pick "Help me brainstorm", ask what the agent does, then suggest 3 ID/name combos and let them pick or modify.

**Validation:** Check `agents/<id>/` doesn't already exist. If it does, ask whether to overwrite or pick a new name.

---

### Section 2: Role & Domain

**Question:** "What kind of agent is this?"
- Header: "Role"
- Options:
  - Label: "Research" / Description: "Deep research, competitive intel, academic analysis, trend tracking"
  - Label: "Communications" / Description: "Email, Slack, social media, customer engagement"
  - Label: "Operations" / Description: "Calendar, billing, admin, project management, automation"
  - Label: "Content" / Description: "Writing, editing, social posts, video scripts, creative work"
- (User can also pick "Other" for custom)

Then ask a follow-up: "Describe this agent's role in 2-3 sentences. Be specific about what it does, not generic."

Store the role description for CLAUDE.md.

---

### Section 3: Model Selection

**Question:** "Which model should this agent use by default?"
- Header: "Model"
- Options:
  - Label: "Sonnet 4.6 (Recommended)" / Description: "Balanced speed and capability. Best for most agents. ~$3/MTok input."
  - Label: "Opus 4.6" / Description: "Most capable. Use for complex reasoning, coding, research. ~$15/MTok input."
  - Label: "Haiku 4.5" / Description: "Fastest and cheapest. Good for simple tasks, triage, routing. ~$0.80/MTok input."

Default selection: Sonnet.

---

### Section 4: Telegram Bot

**Question:** "Does this agent have a Telegram bot yet?"
- Header: "Telegram"
- Options:
  - Label: "I have a token ready" / Description: "You already created the bot via @BotFather and have the token"
  - Label: "Walk me through it" / Description: "I'll guide you through creating a bot with @BotFather"
  - Label: "Skip for now" / Description: "You'll add the bot token to .env later"

If "I have a token ready": ask them to paste it.
If "Walk me through it": show these steps, then ask them to paste the token:

```
1. Open Telegram and message @BotFather
2. Send /newbot
3. Give it a display name (e.g., "ClaudeClaw <AgentName>")
4. Give it a username (e.g., "<agent_id>_claw_bot")
5. Copy the token BotFather gives you
```

If "Skip for now": note that they'll need to add `<AGENT_ID>_BOT_TOKEN=<token>` to `.env` before starting.

The env var name is always: `<AGENT_ID uppercased with hyphens as underscores>_BOT_TOKEN`
Example: agent ID `my-research` -> env var `MY_RESEARCH_BOT_TOKEN`

---

### Section 5: Skills

First, list available skills:

```bash
ls skills/
```

**Question:** "Which skills should this agent have access to?"
- Header: "Skills"
- multiSelect: true
- Options: Build dynamically from the `ls skills/` output. Each option:
  - Label: the skill directory name
  - Description: read the first line of each skill's SKILL.md `description:` field
- Always include one extra option:
  - Label: "All skills" / Description: "Don't restrict -- agent can use any available skill"

If "All skills" is selected, omit the `skills:` key from agent.yaml entirely.

Then ask: "Want to add more skills?"
- Header: "More skills"
- Options:
  - Label: "Import a skill from disk" / Description: "Copy an existing skill from a folder or zip file on your machine"
  - Label: "Create a new skill" / Description: "Generate a starter SKILL.md from scratch for this agent"
  - Label: "No, I'm done with skills" / Description: "Move on to the next section"

#### Import a skill from disk

If "Import a skill from disk" is selected:

1. Ask: "What's the path to the skill? (folder or zip file)"
   - Accept either a directory path or a `.zip` file path

2. **If it's a directory** containing `SKILL.md` at the top level:
   - That directory IS the skill. Copy it directly into `skills/<dirname>/`.
   - Example: `/path/to/my-skill/SKILL.md` -> copy whole folder to `skills/my-skill/`

3. **If it's a directory** that does NOT have `SKILL.md` at the top level:
   - Look for a `.zip` file inside it, OR look one level down for a subfolder with `SKILL.md`.
   - Common pattern (like advisory-board downloads): the download folder contains a `.zip`, and inside the zip is the actual skill folder with `SKILL.md`.
   - Example: `Downloads/JamesPasmantier-Advisory-Board-Skill/` contains `advisory-board.zip` which contains `advisory-board/SKILL.md` + `advisory-board/references/`

4. **If it's a `.zip` file**:
   - List contents first: `unzip -l <path>`
   - Find the folder containing `SKILL.md`
   - Extract that folder into `skills/`: `unzip <path> -d skills/`
   - If the zip extracts with a wrapper folder (e.g., `advisory-board/SKILL.md`), that's fine -- the skill name becomes the folder name.

5. After copying/extracting:
   - Read the imported `SKILL.md` frontmatter to get the skill name and description
   - Show Mike what was imported: skill name, description, any bundled reference files
   - Confirm: "Skill '<name>' imported to skills/<name>/. Add it to this agent's skill list?"
   - If yes, add it to the selected skills list

6. Ask again: "Import another skill, create a new one, or move on?"

#### Create a new skill

If "Create a new skill" is selected:
- Collect skill name, one-sentence description, and what it does
- Generate a starter SKILL.md in `skills/<name>/SKILL.md`
- Add it to the agent's selected skills list
- Ask again: "Import another, create another, or move on?"

---

### Section 6: Reference Knowledge

**Question:** "Does this agent need specialized knowledge files?"
- Header: "References"
- Options:
  - Label: "Yes, domain expertise" / Description: "Frameworks, procedures, and deep knowledge the agent loads on demand"
  - Label: "Yes, workflows" / Description: "Multi-step processes with validation between stages"
  - Label: "Yes, both" / Description: "Domain expertise files AND workflow configs"
  - Label: "No, skip" / Description: "Agent works from general knowledge only"

If they want domain expertise:
- Ask: "What topic areas? (list 1-3 topics, e.g., 'pricing strategy', 'client onboarding')"
- For each topic, ask for 2-3 key frameworks or knowledge areas
- Generate a `references/<topic>.md` file from the domain-knowledge template

If they want workflows:
- Ask: "What workflows? (e.g., 'client onboarding', 'content review')"
- For each workflow, ask for the main steps (3-5)
- Generate a `references/workflow-<name>.json` file from the workflow template

Then ask: "Any common mistakes this agent should watch for?"
- If yes: collect 2-3 anti-patterns with what-it-looks-like / why-wrong / do-instead
- Generate `references/anti-patterns.md`

---

### Section 7: Obsidian Integration

**Question:** "Does this agent need access to the Obsidian vault?"
- Header: "Obsidian"
- Options:
  - Label: "Yes, read-write" / Description: "Agent can read and create/edit notes in specific folders"
  - Label: "Yes, read-only" / Description: "Agent can read notes but not modify the vault"
  - Label: "No" / Description: "No Obsidian access needed"

If yes (either mode):
- Ask: "Which vault folders? (comma-separated, e.g., 'Projects/, Clients/, Daily Notes/')"
- If read-write was picked, also ask which of those folders should be read-only

The vault path is: `C:/Users/shopp/ObsidianVault`

---

### Section 8: Team Awareness

First, list existing agents:

```bash
ls agents/ | grep -v _template
```

**Question:** "Which agents might this one work with?"
- Header: "Team"
- multiSelect: true
- Options: Build dynamically from existing agents. Each option:
  - Label: agent directory name
  - Description: read the agent's `agent.yaml` and use its `description:` field

This populates the Handoffs section of CLAUDE.md with the list of available agents.

---

### Section 9: Communication Style

**Question:** "How should this agent communicate?"
- Header: "Style"
- Options:
  - Label: "Concise & direct" / Description: "Short answers, bullet points, no fluff. Best for ops and triage agents."
  - Label: "Detailed & thorough" / Description: "Full explanations, examples, context. Best for research and analysis."
  - Label: "Casual & friendly" / Description: "Conversational tone, personality. Best for comms-facing agents."
  - Label: "Formal & precise" / Description: "Professional tone, structured output. Best for client-facing work."

Then ask: "Any additional style notes? (or 'none')"

---

## File Generation

After ALL 9 sections are complete, generate files in this order. Tell Mike "Generating agent files..." before starting.

### 1. Create directories

```bash
mkdir -p agents/<id>/references
```

### 2. Write `agents/<id>/agent.yaml`

```yaml
name: <display_name>
description: <description>
telegram_bot_token_env: <ENV_VAR_NAME>
model: <model>
```

Add `skills:` list only if specific skills were selected (not "All skills").
Add `obsidian:` block only if Obsidian was configured.

Example with all optional sections:
```yaml
name: Research Lead
description: Deep research, competitive intel, and trend analysis for strategic decisions
telegram_bot_token_env: RESEARCH_LEAD_BOT_TOKEN
model: claude-sonnet-4-6
skills:
  - agent-browser
  - outlook-mail
obsidian:
  vault: C:/Users/shopp/ObsidianVault
  folders:
    - Research/
    - Projects/
  read_only:
    - Daily Notes/
```

### 3. Write `agents/<id>/CLAUDE.md`

Use the template from `agents/_template/CLAUDE.md` but fill in EVERY section with real content from the interview. No placeholders.

Key sections to populate:
- **Title**: Use the display name
- **Your role**: The 2-3 sentence role description from Section 2
- **Your Obsidian folders**: List folders or remove section if none
- **Reference knowledge**: Build the task-type-to-file mapping table from the reference files created
- **Workflows**: Describe workflow configs if any, or remove section
- **Team awareness**: Keep the standard team awareness text as-is
- **Hive mind**: Keep standard -- replace `[AGENT_ID]` with the actual agent ID
- **Handoffs**: Replace `[AGENT_ID]` with actual ID, list the agents from Section 8 as available handoff targets
- **Anti-patterns**: Use the anti-patterns from Section 6 if provided, plus standard ones (don't load all refs at once, stay in your lane, hand off out-of-domain tasks)
- **Style**: Use the style choice and notes from Section 9
- **Rules**: Keep the standard rules list

### 4. Write `agents/<id>/references/README.md`

Copy the content from `agents/_template/references/README.md` exactly.

### 5. Write reference files (if any)

For each domain knowledge topic: generate `agents/<id>/references/<topic-slug>.md` using the domain-knowledge.md.example structure, filled with the frameworks the user described.

For each workflow: generate `agents/<id>/references/workflow-<name-slug>.json` using the workflow-example.json structure, filled with the steps the user described.

For anti-patterns: generate `agents/<id>/references/anti-patterns.md` with the structure from the README.

### 6. Write new skill (if requested)

If a new skill was requested in Section 5, generate `skills/<skill-name>/SKILL.md`:

```yaml
---
name: <skill-name>
description: "<one-sentence description>"
allowed-tools: []
---
```

Then add a markdown body with Purpose, When to Use, When NOT to Use, and Commands/Instructions sections based on what the user described.

### 7. Update `.env` (if token provided)

Only if a bot token was collected in Section 4:

```bash
echo "" >> .env
echo "# Agent: <id>" >> .env
echo "<ENV_VAR>=<token>" >> .env
```

First check if the env var already exists:
```bash
grep "^<ENV_VAR>=" .env
```
If it exists, tell Mike it's already set and skip.

### 8. Build

```bash
npm run build
```

If the build fails, show the error and suggest fixes. Don't stop the wizard -- the agent files are already created.

### 9. Summary

Show a summary of everything created:

```
Agent "<display_name>" created!

Files:
  agents/<id>/agent.yaml
  agents/<id>/CLAUDE.md
  agents/<id>/references/README.md
  [any additional reference files]
  [any new skill files]

To start: npm start -- --agent <id>
```

### 10. Offer to start

**Question:** "Want to test-start the agent now?"
- Header: "Launch"
- Options:
  - Label: "Yes, start it" / Description: "Runs npm start -- --agent <id> (Ctrl+C to stop)"
  - Label: "No, I'll start it later" / Description: "You can run: npm start -- --agent <id>"

If yes:
```bash
node dist/index.js --agent <id>
```
