# Token Optimization & Budget Security

## Token Budget Architecture

ClaudeClaw uses a Token Optimization Framework to route API calls across providers and track spend.

**Components:**
- `src/token-router.ts` -- Centralized routing: picks cheapest capable model per task type
- `src/token-budget.ts` -- Budget tracking with threshold alerts
- `src/db.ts` -- `token_budget` table for persistent spend tracking

**Database schema:**
```sql
CREATE TABLE IF NOT EXISTS token_budget (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  date_key      TEXT NOT NULL,        -- YYYY-MM-DD
  model         TEXT NOT NULL,        -- e.g. 'claude-sonnet-4', 'gemini-2.0-flash'
  provider      TEXT NOT NULL,        -- 'anthropic' or 'google'
  input_tokens  INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd      REAL NOT NULL DEFAULT 0,
  created_at    INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_token_budget_date_model ON token_budget(date_key, model);
```

**Route table:**

| Task Type | Provider | Model | Rationale |
|-----------|----------|-------|-----------|
| `pipeline-reviewer` | Google | `gemini-2.0-flash` | Junior review work, structured JSON output |
| `pipeline-arbiter` | Anthropic | `claude-sonnet-4` | Needs strong reasoning to adjudicate |
| `scheduled-simple` | Google | `gemini-2.0-flash` | Datetime sync, simple lookups |
| `scheduled-complex` | Anthropic | `claude-sonnet-4` | Security scans, analysis |
| `consensus-claude` | Anthropic | `claude-sonnet-4` | Multi-model validation |
| `consensus-gemini` | Google | `gemini-2.0-flash` | Multi-model validation |
| `general` | Anthropic | `claude-sonnet-4` | Fallback |

**Budget thresholds:**
- **75%** -- Warning (advisory, no action)
- **95%** -- Hard-limit: ALL calls forced to Gemini Flash regardless of route table

**Env var:** `TOKEN_DAILY_BUDGET_USD` (default: `10`)

**Telegram command:** `/tokens` -- shows daily spend, per-model breakdown, 7-day history

## Multi-Provider Routing Security

Security considerations for the multi-provider architecture:

1. **API key isolation**: Keys are read from `.env` via `readEnvFile()` at call time, never stored in `process.env`. This prevents leakage to child processes (sandboxed code, MCP servers).

2. **Error message truncation**: All API error responses are truncated to 500 characters before being thrown as exceptions. This prevents full error bodies (which may echo request headers containing API keys) from reaching logs or Telegram.

3. **Fallback behavior**: If the preferred provider's key is missing, the router falls back to the other provider. This is a feature, not a vulnerability -- but it means a single key deletion doesn't disable the system.

4. **Budget as blast radius control**: The 95% hard-limit forces all traffic to the cheapest provider. This limits financial damage from runaway loops or hijacked sessions.

5. **Gemini URL key parameter**: The Gemini API passes the key as a URL query parameter (`?key=...`). Ensure HTTP request logging does NOT capture full URLs. The token router uses `fetch()` directly -- verify no middleware or proxy logs the request URL.

6. **Pipeline reviewer trust boundary**: Code pipeline reviewers are now routed to Gemini Flash. Gemini's structured JSON output flows into the arbiter (still Claude). A malicious reviewer response could attempt to influence the arbiter. The arbiter's system prompt is designed to independently evaluate findings, but this is a trust boundary worth monitoring.

## Budget Monitoring

### Query current day's spend
```bash
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT model, provider, input_tokens, output_tokens, cost_usd
  FROM token_budget
  WHERE date_key = date('now')
  ORDER BY cost_usd DESC;
"
```

### Query 7-day history
```bash
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT date_key, SUM(cost_usd) as daily_cost,
         SUM(input_tokens) as total_in, SUM(output_tokens) as total_out
  FROM token_budget
  WHERE date_key >= date('now', '-7 days')
  GROUP BY date_key ORDER BY date_key DESC;
"
```

### Detect budget anomalies
```bash
# Check if any single day exceeded 2x the configured budget
sqlite3 "$CLAUDECLAW_DIR/store/claudeclaw.db" "
  SELECT date_key, SUM(cost_usd) as total
  FROM token_budget
  GROUP BY date_key
  HAVING total > 20  -- 2x default budget
  ORDER BY date_key DESC;
"
```
