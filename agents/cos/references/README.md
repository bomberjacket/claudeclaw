# Workflow Definitions

Workflows are JSON files in this directory, named `workflow-<name>.json`.

## Format

```json
{
  "name": "my-workflow",
  "description": "What this workflow does",
  "steps": [
    {
      "step": 1,
      "name": "Step Name",
      "description": "Detailed description of what this step does",
      "agent": "target-agent-id",
      "input": "What to tell the agent / what data to pass",
      "output": "What to expect back from the agent",
      "timeout_minutes": 5,
      "validation": {
        "rules": [
          {
            "check": "output_exists",
            "operator": "==",
            "value": true
          }
        ],
        "on_failure": "stop"
      }
    }
  ]
}
```

## Fields

### Top-level
| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique workflow identifier (lowercase, hyphens) |
| `description` | No | Human-readable description |
| `steps` | Yes | Array of step objects |

### Step object
| Field | Required | Description |
|-------|----------|-------------|
| `step` | Yes | Step number (1-indexed, sequential) |
| `name` | Yes | Short name for the step |
| `description` | No | Detailed description passed to the target agent |
| `agent` | Yes | Agent ID from `agents/` directory |
| `input` | Yes | What to tell/give the agent |
| `output` | No | Expected output description (for validation) |
| `timeout_minutes` | No | Max wait time before timeout (default: 5) |
| `validation` | No | Validation rules for the step output |

### Validation
| Field | Description |
|-------|-------------|
| `rules` | Array of check objects |
| `on_failure` | What to do on failure: `stop` (fail run) or `retry` (retry once) |

### Validation checks
| Check | Description |
|-------|-------------|
| `output_exists` | Agent produced some output |
| `contains` | Output contains a specific string |
| `hive_mind_logged` | Agent logged to hive_mind after dispatch |

## Agent IDs

The `agent` field maps to directory names under `agents/`. List available agents:

```bash
ls agents/ | grep -v _template | grep -v cos
```

## Graduation

- First run of any workflow is always **supervised** (Mike approves each step)
- After one clean supervised run, the workflow **graduates** to autonomous
- Autonomous runs execute without pausing, with notifications per configured cadence
