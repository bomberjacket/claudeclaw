#!/usr/bin/env python3
"""
ClaudeClaw Runtime Security Monitor (Windows)
Analyzes token usage, message patterns, and system state for anomalies.
Stdlib only - no pip installs required.

Usage: python security-monitor.py [--json] [--check-files] [--check-ports] [--all]

Configuration: Update the path constants below to match your installation.
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── CONFIGURATION -- Update these paths for your installation ──
# Set CLAUDECLAW_DIR env var or edit these defaults
_BASE = os.environ.get(
    "CLAUDECLAW_DIR",
    os.path.join(os.path.expanduser("~"), "bni-agents", "claudeclaw"),
)
DB_PATH = os.path.join(_BASE, "store", "claudeclaw.db")
ENV_PATH = os.path.join(_BASE, ".env")
STORE_PATH = os.path.join(_BASE, "store")
PROJECT_ROOT = _BASE

# Thresholds
COST_SPIKE_THRESHOLD = 5.0       # $ per session
MSG_FLOOD_THRESHOLD = 50         # messages per hour
COMPACTION_THRESHOLD = 3         # compactions per session
OFF_HOURS_START = 0              # midnight
OFF_HOURS_END = 6                # 6 AM
TOKEN_SPIKE_MULTIPLIER = 3.0     # 3x average = spike
DAILY_BUDGET_USD = 10.0          # matches TOKEN_DAILY_BUDGET_USD default


def get_db():
    return sqlite3.connect(DB_PATH)


def check_token_usage(db):
    """Detect token usage anomalies."""
    alerts = []
    cursor = db.cursor()

    # Get average cost per session
    cursor.execute("""
        SELECT session_id, SUM(cost_usd) as total_cost, COUNT(*) as turns,
               SUM(did_compact) as compactions
        FROM token_usage
        WHERE session_id IS NOT NULL
        GROUP BY session_id
        ORDER BY MAX(created_at) DESC
        LIMIT 20
    """)
    sessions = cursor.fetchall()

    if not sessions:
        return alerts

    costs = [s[1] for s in sessions if s[1]]
    avg_cost = sum(costs) / len(costs) if costs else 0

    # Check most recent session
    if sessions:
        latest = sessions[0]
        session_id, cost, turns, compactions = latest

        if cost and cost > COST_SPIKE_THRESHOLD:
            alerts.append({
                'severity': 'high',
                'category': 'MON',
                'title': f'Cost spike: ${cost:.2f} in session (threshold: ${COST_SPIKE_THRESHOLD})',
                'detail': f'Session {session_id[:8]}... | {turns} turns | avg: ${avg_cost:.2f}',
            })

        if cost and avg_cost > 0 and cost > avg_cost * TOKEN_SPIKE_MULTIPLIER:
            alerts.append({
                'severity': 'medium',
                'category': 'MON',
                'title': f'Cost {cost/avg_cost:.1f}x above average',
                'detail': f'Session cost: ${cost:.2f} vs avg: ${avg_cost:.2f}',
            })

        if compactions and compactions > COMPACTION_THRESHOLD:
            alerts.append({
                'severity': 'medium',
                'category': 'MON',
                'title': f'{compactions} compaction events in session',
                'detail': 'Possible context stuffing or very long operation',
            })

    return alerts


def check_token_budget(db):
    """Detect token budget anomalies across providers."""
    alerts = []
    cursor = db.cursor()

    # Check if token_budget table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='token_budget'")
    if not cursor.fetchone():
        return alerts

    # Today's total spend
    cursor.execute("""
        SELECT SUM(total_cost_usd) as total_cost,
               COUNT(DISTINCT provider) as model_count
        FROM token_budget
        WHERE date = date('now')
    """)
    row = cursor.fetchone()
    if row and row[0]:
        today_cost = row[0]
        pct = today_cost / DAILY_BUDGET_USD if DAILY_BUDGET_USD > 0 else 0

        if pct >= 0.95:
            alerts.append({
                'severity': 'high',
                'category': 'MON',
                'title': f'Token budget at {pct*100:.0f}% (${today_cost:.2f} / ${DAILY_BUDGET_USD:.2f})',
                'detail': 'Hard-limit active: all calls routed to Gemini Flash',
            })
        elif pct >= 0.75:
            alerts.append({
                'severity': 'medium',
                'category': 'MON',
                'title': f'Token budget at {pct*100:.0f}% (${today_cost:.2f} / ${DAILY_BUDGET_USD:.2f})',
                'detail': 'Approaching daily limit',
            })

    # Check for spend anomaly vs 7-day average
    cursor.execute("""
        SELECT date, SUM(total_cost_usd) as daily_cost
        FROM token_budget
        WHERE date >= date('now', '-7 days')
        GROUP BY date
        ORDER BY date DESC
    """)
    daily_costs = cursor.fetchall()
    if len(daily_costs) >= 3:
        today_entry = daily_costs[0] if daily_costs else None
        past_costs = [d[1] for d in daily_costs[1:] if d[1]]
        avg_past = sum(past_costs) / len(past_costs) if past_costs else 0
        if today_entry and today_entry[1] and avg_past > 0:
            ratio = today_entry[1] / avg_past
            if ratio > TOKEN_SPIKE_MULTIPLIER:
                alerts.append({
                    'severity': 'high',
                    'category': 'MON',
                    'title': f'Daily spend {ratio:.1f}x above 7-day average',
                    'detail': f'Today: ${today_entry[1]:.2f} | Avg: ${avg_past:.2f}',
                })

    return alerts


def check_message_patterns(db):
    """Detect suspicious message volume and timing."""
    alerts = []
    cursor = db.cursor()

    now = int(datetime.now().timestamp())
    one_hour_ago = now - 3600
    one_day_ago = now - 86400

    # Messages in last hour
    cursor.execute("""
        SELECT COUNT(*) FROM conversation_log
        WHERE created_at > ? AND role = 'user'
    """, (one_hour_ago,))
    hourly = cursor.fetchone()[0]

    if hourly > MSG_FLOOD_THRESHOLD:
        alerts.append({
            'severity': 'high',
            'category': 'MON',
            'title': f'Message flood: {hourly} messages in last hour',
            'detail': f'Threshold: {MSG_FLOOD_THRESHOLD}. Possible automated abuse.',
        })

    # Off-hours activity
    cursor.execute("""
        SELECT COUNT(*), MIN(created_at), MAX(created_at)
        FROM conversation_log
        WHERE created_at > ? AND role = 'user'
    """, (one_day_ago,))
    day_count, first_msg, last_msg = cursor.fetchone()

    if first_msg:
        first_hour = datetime.fromtimestamp(first_msg).hour
        if OFF_HOURS_START <= first_hour < OFF_HOURS_END:
            alerts.append({
                'severity': 'medium',
                'category': 'MON',
                'title': f'Off-hours activity detected at {first_hour}:00',
                'detail': f'{day_count} messages in last 24h',
            })

    # Daily volume for baseline
    cursor.execute("""
        SELECT date(created_at, 'unixepoch') as day, COUNT(*) as cnt
        FROM conversation_log
        WHERE role = 'user'
        GROUP BY day
        ORDER BY day DESC
        LIMIT 7
    """)
    daily_volumes = cursor.fetchall()
    if len(daily_volumes) >= 3:
        avg_daily = sum(d[1] for d in daily_volumes[1:]) / (len(daily_volumes) - 1)
        today_count = daily_volumes[0][1] if daily_volumes else 0
        if avg_daily > 0 and today_count > avg_daily * TOKEN_SPIKE_MULTIPLIER:
            alerts.append({
                'severity': 'medium',
                'category': 'MON',
                'title': f'Message volume {today_count/avg_daily:.1f}x above daily average',
                'detail': f'Today: {today_count} | Avg: {avg_daily:.0f}',
            })

    return alerts


def _parse_icacls_output(output):
    """Parse icacls output and return list of (principal, permissions) tuples."""
    entries = []
    for line in output.strip().splitlines():
        line = line.strip()
        # icacls lines look like: "DOMAIN\User:(F)" or "BUILTIN\Users:(R)"
        match = re.match(r'^(.+?):\(([^)]+)\)$', line)
        if match:
            entries.append((match.group(1), match.group(2)))
    return entries


def _has_loose_acl(acl_entries):
    """Check if ACL entries grant access to Everyone, Users, or Authenticated Users."""
    loose_principals = {'everyone', 'builtin\\users', 'nt authority\\authenticated users'}
    for principal, perms in acl_entries:
        if principal.lower() in loose_principals:
            return True, principal, perms
    return False, None, None


def check_file_permissions():
    """Check file system security using Windows ACLs (icacls)."""
    alerts = []

    # .env permissions -- should be restricted to owner only
    if os.path.exists(ENV_PATH):
        try:
            result = subprocess.run(
                ['icacls', ENV_PATH],
                capture_output=True, text=True, timeout=10
            )
            acl_entries = _parse_icacls_output(result.stdout)
            is_loose, principal, perms = _has_loose_acl(acl_entries)
            if is_loose:
                alerts.append({
                    'severity': 'high',
                    'category': 'FS',
                    'title': f'.env has loose ACL: {principal} has ({perms})',
                    'fix': f'icacls "{ENV_PATH}" /inheritance:r /grant:r "%USERNAME%:F"',
                })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # store/ permissions -- should be restricted to owner only
    if os.path.exists(STORE_PATH):
        try:
            result = subprocess.run(
                ['icacls', STORE_PATH],
                capture_output=True, text=True, timeout=10
            )
            acl_entries = _parse_icacls_output(result.stdout)
            is_loose, principal, perms = _has_loose_acl(acl_entries)
            if is_loose:
                alerts.append({
                    'severity': 'medium',
                    'category': 'FS',
                    'title': f'store/ has loose ACL: {principal} has ({perms})',
                    'fix': f'icacls "{STORE_PATH}" /inheritance:r /grant:r "%USERNAME%:F"',
                })
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Check for loose ACLs on files in store/
    if os.path.exists(STORE_PATH):
        for f in os.listdir(STORE_PATH):
            fp = os.path.join(STORE_PATH, f)
            if os.path.isfile(fp):
                try:
                    result = subprocess.run(
                        ['icacls', fp],
                        capture_output=True, text=True, timeout=10
                    )
                    acl_entries = _parse_icacls_output(result.stdout)
                    is_loose, principal, perms = _has_loose_acl(acl_entries)
                    if is_loose:
                        alerts.append({
                            'severity': 'low',
                            'category': 'FS',
                            'title': f'store/{f} has loose ACL: {principal} has ({perms})',
                            'fix': f'icacls "{fp}" /inheritance:r /grant:r "%USERNAME%:F"',
                        })
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

    # Check for env backup files
    for pattern in ['.env.bak', '.env.local', '.env.development', '.env.production']:
        fp = os.path.join(PROJECT_ROOT, pattern)
        if os.path.exists(fp):
            alerts.append({
                'severity': 'high',
                'category': 'SEC',
                'title': f'Environment backup file found: {pattern}',
                'fix': f'del "{fp}"',
            })

    # Check for secrets in git history
    try:
        result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'log', '--diff-filter=A', '--name-only',
             '--pretty=format:', '-n', '50'],
            capture_output=True, text=True, timeout=10
        )
        added_files = result.stdout.strip().split('\n')
        env_in_history = [f for f in added_files if '.env' in f and f.strip()]
        if env_in_history:
            alerts.append({
                'severity': 'high',
                'category': 'SEC',
                'title': f'.env files found in git history: {", ".join(env_in_history)}',
                'detail': 'Secrets may be exposed in git log',
            })
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return alerts


def check_open_ports():
    """Check for unexpected listening ports using netstat (Windows)."""
    alerts = []
    try:
        result = subprocess.run(
            ['netstat', '-ano'],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')
        listening_lines = [l for l in lines if 'LISTENING' in l]

        for line in listening_lines:
            parts = line.split()
            if len(parts) >= 5:
                local_addr = parts[1]
                pid = parts[4]

                # Try to resolve PID to process name
                try:
                    pid_result = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {pid}', '/FO', 'CSV', '/NH'],
                        capture_output=True, text=True, timeout=5
                    )
                    pid_output = pid_result.stdout.strip()
                    if 'node' in pid_output.lower():
                        alerts.append({
                            'severity': 'medium',
                            'category': 'NET',
                            'title': f'Node process listening: {local_addr}',
                            'detail': f'PID: {pid} | {pid_output.split(",")[0].strip(chr(34))}',
                        })
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return alerts


def check_mcp_configs():
    """Check MCP server configurations for risks."""
    alerts = []

    # Check .claude/settings.json for risky settings
    settings_path = os.path.join(os.path.expanduser('~'), '.claude', 'settings.json')
    if os.path.exists(settings_path):
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            if settings.get('enableAllProjectMcpServers'):
                alerts.append({
                    'severity': 'critical',
                    'category': 'MCP',
                    'title': 'enableAllProjectMcpServers is ON',
                    'detail': 'Any .mcp.json in a project can auto-load MCP servers',
                    'fix': 'Set enableAllProjectMcpServers: false in ~/.claude/settings.json',
                })
        except (json.JSONDecodeError, KeyError):
            pass

    # Check for .mcp.json files in project
    mcp_file = os.path.join(PROJECT_ROOT, '.mcp.json')
    if os.path.exists(mcp_file):
        try:
            with open(mcp_file) as f:
                mcp_config = json.load(f)
            server_count = len(mcp_config.get('mcpServers', {}))
            alerts.append({
                'severity': 'info',
                'category': 'MCP',
                'title': f'.mcp.json found with {server_count} server(s)',
                'detail': 'Review server commands for malicious payloads',
            })
        except (json.JSONDecodeError, KeyError):
            pass

    return alerts


def check_secrets_in_source():
    """Scan source files for hardcoded secrets."""
    alerts = []
    secret_patterns = [
        r'TELEGRAM_BOT_TOKEN\s*=\s*["\'][^"\']+',
        r'ANTHROPIC_API_KEY\s*=\s*["\'][^"\']+',
        r'SLACK_USER_TOKEN\s*=\s*["\'][^"\']+',
        r'GOOGLE_API_KEY\s*=\s*["\'][^"\']+',
        r'xoxp-[0-9]+-[0-9]+-[0-9]+-[a-f0-9]+',
        r'sk-ant-[a-zA-Z0-9-]+',
        r'AIza[0-9A-Za-z_-]{35}',
    ]

    src_dirs = [
        os.path.join(PROJECT_ROOT, 'src'),
        os.path.join(PROJECT_ROOT, 'scripts'),
    ]

    for src_dir in src_dirs:
        if not os.path.exists(src_dir):
            continue
        for root, _, files in os.walk(src_dir):
            for f in files:
                if not f.endswith(('.ts', '.js', '.sh', '.py')):
                    continue
                fp = os.path.join(root, f)
                try:
                    with open(fp, encoding='utf-8', errors='ignore') as fh:
                        content = fh.read()
                    for pattern in secret_patterns:
                        if re.search(pattern, content):
                            alerts.append({
                                'severity': 'high',
                                'category': 'SEC',
                                'title': f'Possible secret in {os.path.relpath(fp, PROJECT_ROOT)}',
                                'detail': f'Pattern: {pattern[:30]}...',
                            })
                            break
                except IOError:
                    pass

    return alerts


def generate_report(output_json=False, check_files=True, check_ports=True):
    """Generate full security monitor report."""
    all_alerts = []

    # DB-dependent checks -- only run if DB exists
    if os.path.exists(DB_PATH):
        db = get_db()
        all_alerts.extend(check_token_usage(db))
        all_alerts.extend(check_token_budget(db))
        all_alerts.extend(check_message_patterns(db))
        db.close()
    else:
        all_alerts.append({
            'severity': 'info',
            'category': 'MON',
            'title': f'Database not found at {DB_PATH}',
            'detail': 'Token usage and message pattern checks skipped',
        })

    # Always run these
    all_alerts.extend(check_mcp_configs())
    all_alerts.extend(check_secrets_in_source())

    # Optional checks
    if check_files:
        all_alerts.extend(check_file_permissions())
    if check_ports:
        all_alerts.extend(check_open_ports())

    # Sort by severity
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    all_alerts.sort(key=lambda a: severity_order.get(a.get('severity', 'info'), 5))

    # Summary
    summary = {
        'timestamp': datetime.now().isoformat(),
        'total_alerts': len(all_alerts),
        'critical': sum(1 for a in all_alerts if a['severity'] == 'critical'),
        'high': sum(1 for a in all_alerts if a['severity'] == 'high'),
        'medium': sum(1 for a in all_alerts if a['severity'] == 'medium'),
        'low': sum(1 for a in all_alerts if a['severity'] == 'low'),
        'info': sum(1 for a in all_alerts if a.get('severity') == 'info'),
    }

    report = {'summary': summary, 'alerts': all_alerts}

    if output_json:
        print(json.dumps(report, indent=2))
        return

    # Pretty print
    print("=" * 60)
    print("  SECURITY MONITOR REPORT")
    print(f"  {summary['timestamp']}")
    print("=" * 60)

    if summary['total_alerts'] == 0:
        print("\n  All clear. No anomalies detected.\n")
        return

    print(f"\n  {summary['total_alerts']} alert(s): "
          f"{summary['critical']} critical, {summary['high']} high, "
          f"{summary['medium']} medium, {summary['low']} low\n")

    for alert in all_alerts:
        icon = {'critical': '!!!', 'high': '!!', 'medium': '!', 'low': '.', 'info': 'i'}
        sev = alert['severity'].upper()
        cat = alert.get('category', '???')
        print(f"  [{icon.get(alert['severity'], '?')}] [{cat}] [{sev}] {alert['title']}")
        if 'detail' in alert:
            print(f"      {alert['detail']}")
        if 'fix' in alert:
            print(f"      Fix: {alert['fix']}")
        print()

    print("=" * 60)


def main():
    output_json = '--json' in sys.argv
    check_files = '--check-files' in sys.argv or '--all' in sys.argv or len(sys.argv) == 1
    check_ports = '--check-ports' in sys.argv or '--all' in sys.argv or len(sys.argv) == 1
    generate_report(output_json, check_files, check_ports)


if __name__ == '__main__':
    main()
