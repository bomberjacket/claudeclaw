# References Directory

This directory contains domain knowledge and workflow configs that the agent loads on demand.

## File Types

### Domain Knowledge (.md)

Deep expertise files the agent reads before responding to domain-specific tasks.
The agent's CLAUDE.md maps task types to these files.

Structure:
```markdown
# [Domain Area]

## Core Frameworks

### [Framework Name]
**What it is:** [1-2 sentences]
**When to use:** [trigger conditions]
**How to apply:**
1. [Step]
2. [Step]
3. [Step]
**Watch out for:** [common mistakes]
```

Keep each file focused on one domain area. 150-300 lines is the sweet spot --
enough depth to be useful, small enough to not flood the context window.

### Workflow Configs (.json)

Multi-step process definitions with validation between stages.
The agent executes these one step at a time.

Structure:
```json
{
  "name": "workflow-name",
  "steps": [
    {
      "step": 1,
      "name": "Step Name",
      "description": "What this step does",
      "input": "what it needs",
      "output": "what it produces",
      "validation": {
        "rules": [
          {"check": "output_exists", "operator": "==", "value": true}
        ],
        "on_failure": "stop | pause | warn_and_continue"
      }
    }
  ],
  "settings": {
    "auto_continue_on_success": true,
    "pause_between_steps": false
  }
}
```

### Anti-Patterns (.md)

Common mistakes this agent should avoid. Loaded after drafting deliverables
as a self-check.

Structure:
```markdown
# Anti-Patterns for [Domain]

## [Mistake Category]
- **What it looks like:** [description]
- **Why it's wrong:** [explanation]
- **Do this instead:** [correct approach]
```

## Naming Convention

- `domain-knowledge.md` -- primary expertise file
- `[specific-topic].md` -- additional deep-dives (e.g., `pricing.md`, `negotiation.md`)
- `workflow-[name].json` -- process definitions
- `anti-patterns.md` -- things to avoid

## Learning Pipeline Integration (Future)

The learning pipeline may auto-generate or update reference files over time
based on what the agent learns from conversations. High-value memories get
consolidated into reference files, so the agent builds its own playbook.
