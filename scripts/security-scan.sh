#!/usr/bin/env bash
# security-scan.sh -- ClaudeClaw dependency & secrets scanner
# Domains: DEP, SEC, FS
# Outputs JSON to stdout; progress to stderr

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
OUT_FILE=$(mktemp)
FINDING_COUNT=0

add_finding() {
  # Usage: add_finding DOMAIN SEVERITY TITLE DESCRIPTION FIX
  local domain="$1" sev="$2" title="$3" desc="$4" fix="${5:-}"
  FINDING_COUNT=$((FINDING_COUNT + 1))
  node --input-type=commonjs <<EOF >> "$OUT_FILE"
process.stdout.write(JSON.stringify({domain:"$domain",severity:"$sev",title:${title@Q},description:${desc@Q},fix:${fix@Q}}) + '\n');
EOF
}

# ── DEP: npm audit ─────────────────────────────────────────────────────────────
echo "[DEP] npm audit..." >&2

AUDIT_OUT=$(npm audit --json 2>/dev/null) || true
if [ -n "$AUDIT_OUT" ]; then
  node --input-type=commonjs <<'NODEEOF'
const chunks=[];process.stdin.on('data',c=>chunks.push(c)).on('end',()=>{
  try{
    const d=JSON.parse(chunks.join(''));
    const v=d.metadata?.vulnerabilities||{};
    const t=(v.critical||0)+(v.high||0)+(v.moderate||0)+(v.low||0);
    if(t>0){
      const sev=v.critical>0?'critical':v.high>0?'high':'medium';
      process.stdout.write(JSON.stringify({domain:'DEP',severity:sev,
        title:`npm audit: ${t} vulnerabilities (${v.critical||0} critical, ${v.high||0} high)`,
        description:`npm audit found vulnerabilities. Critical:${v.critical||0} High:${v.high||0} Moderate:${v.moderate||0} Low:${v.low||0}`,
        fix:'npm audit fix --force'})+'\n');
    }
  }catch(e){}
});
NODEEOF
  echo "$AUDIT_OUT" | node --input-type=commonjs <<'NODEEOF' >> "$OUT_FILE" || true
const chunks=[];process.stdin.on('data',c=>chunks.push(c)).on('end',()=>{
  try{
    const d=JSON.parse(chunks.join(''));
    const v=d.metadata?.vulnerabilities||{};
    const t=(v.critical||0)+(v.high||0)+(v.moderate||0)+(v.low||0);
    if(t>0){
      const sev=v.critical>0?'critical':v.high>0?'high':'medium';
      process.stdout.write(JSON.stringify({domain:'DEP',severity:sev,
        title:`npm audit: ${t} vulnerabilities (${v.critical||0} critical, ${v.high||0} high)`,
        description:`npm audit found vulnerabilities. Critical:${v.critical||0} High:${v.high||0} Moderate:${v.moderate||0} Low:${v.low||0}`,
        fix:'npm audit fix --force'})+'\n');
      FINDING_COUNT=$((FINDING_COUNT+1))
    }
  }catch(e){}
});
NODEEOF
fi

# ── DEP: outdated packages ──────────────────────────────────────────────────────
echo "[DEP] Checking outdated packages..." >&2

OUTDATED_OUT=$(npm outdated --json 2>/dev/null) || true
if [ -n "$OUTDATED_OUT" ] && [ "$OUTDATED_OUT" != "{}" ]; then
  echo "$OUTDATED_OUT" | node --input-type=commonjs <<'NODEEOF' >> "$OUT_FILE" || true
const chunks=[];process.stdin.on('data',c=>chunks.push(c)).on('end',()=>{
  try{
    const o=JSON.parse(chunks.join(''))||{};
    const pkgs=Object.keys(o);
    if(pkgs.length>0){
      const summary=pkgs.slice(0,8).map(k=>k+'@'+o[k].current+'->'+o[k].latest).join(', ');
      process.stdout.write(JSON.stringify({domain:'DEP',severity:'low',
        title:`Outdated packages: ${pkgs.length} behind`,
        description:`Packages: ${summary}`,
        fix:'npm update'})+'\n');
    }
  }catch(e){}
});
NODEEOF
fi

# ── SEC: .env backup files ──────────────────────────────────────────────────────
echo "[SEC] Checking for .env backup files..." >&2

for envfile in .env.bak .env.local .env.backup .env.old .env.copy; do
  if [ -f "$envfile" ]; then
    echo "{\"domain\":\"SEC\",\"severity\":\"high\",\"title\":\".env backup file exists: $envfile\",\"description\":\"Backup env file may expose credentials: $envfile\",\"fix\":\"rm $envfile\"}" >> "$OUT_FILE"
    FINDING_COUNT=$((FINDING_COUNT + 1))
  fi
done

# ── SEC: Hardcoded secret patterns in src/ ──────────────────────────────────────
echo "[SEC] Scanning source for secret patterns..." >&2

declare -A PATTERNS=(
  ["sk-ant-api"]="Anthropic API key"
  ["gsk_"]="Groq API key"
  ["AIzaSy"]="Google API key"
)

for pat in "${!PATTERNS[@]}"; do
  label="${PATTERNS[$pat]}"
  # Exclude test files, node_modules, dist, store
  HITS=$(grep -rl "$pat" src/ scripts/ agents/ skills/ 2>/dev/null \
    | grep -v "node_modules" \
    | grep -v "\.test\." \
    | grep -v "safety\." \
    | grep -v "notify\.sh" \
    | grep -v "security-scan\.sh" \
    | head -3 || true)
  if [ -n "$HITS" ]; then
    FILES=$(echo "$HITS" | tr '\n' ' ')
    echo "{\"domain\":\"SEC\",\"severity\":\"high\",\"title\":\"$label pattern in source: $FILES\",\"description\":\"Pattern '$pat' ($label) found hardcoded in source files\",\"fix\":\"Remove from source, rotate key, store in .env only\"}" >> "$OUT_FILE"
    FINDING_COUNT=$((FINDING_COUNT + 1))
  fi
done

# ── FS: broad ACL checks (Windows) ────────────────────────────────────────────
echo "[FS] Checking file ACLs..." >&2

if command -v icacls.exe &>/dev/null; then
  for target in ".env" "store" "store/claudeclaw.db"; do
    if [ -e "$target" ]; then
      BROAD=$(icacls.exe "$target" 2>/dev/null | grep -iE "(Everyone|BUILTIN\\\\Users)" | grep -v "NT AUTHORITY" || true)
      if [ -n "$BROAD" ]; then
        echo "{\"domain\":\"FS\",\"severity\":\"medium\",\"title\":\"Broad ACL on $target\",\"description\":\"$target grants access to broad groups: $BROAD\",\"fix\":\"icacls \\\"$target\\\" /inheritance:r /grant:r \\\"%USERNAME%:F\\\"\"}" >> "$OUT_FILE"
        FINDING_COUNT=$((FINDING_COUNT + 1))
      fi
    fi
  done
fi

# ── NET: open ports check ───────────────────────────────────────────────────────
echo "[NET] Checking for Intel AMT port 16992..." >&2

AMT=$(netstat -ano 2>/dev/null | grep ":16992" | grep LISTENING || true)
if [ -n "$AMT" ]; then
  echo "{\"domain\":\"NET\",\"severity\":\"medium\",\"title\":\"Intel AMT port 16992 still listening\",\"description\":\"Intel AMT (port 16992) is active. Disable in BIOS if not needed.\",\"fix\":\"Disable Intel AMT in BIOS/UEFI settings\"}" >> "$OUT_FILE"
  FINDING_COUNT=$((FINDING_COUNT + 1))
fi

# ── Output ──────────────────────────────────────────────────────────────────────

FINDINGS_ARRAY=$(cat "$OUT_FILE" | tr '\n' ',' | sed 's/,$//')
rm -f "$OUT_FILE"

echo "{\"timestamp\":\"$TIMESTAMP\",\"project_root\":\"$PROJECT_ROOT\",\"finding_count\":$FINDING_COUNT,\"findings\":[$FINDINGS_ARRAY]}"
echo "[SCAN] Done. $FINDING_COUNT finding(s)." >&2
