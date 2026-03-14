---
name: list-cleaner
description: Contact list hygiene -- parsing, deduplication, email validation, enrichment, prospect generation, and clean export
allowed-tools: Bash(*) Read(*) Write(*) Glob(*) Grep(*) WebSearch(*) WebFetch(*)
---

# List Cleaner Skill

You handle all contact list data processing. Every operation runs as a Python script via Bash. Use `csv` (stdlib) and `openpyxl` for all file I/O.

## 1. Parsing

### CSV (auto-detect delimiter)

```python
import csv, sys, json

filepath = sys.argv[1]
with open(filepath, 'r', encoding='utf-8-sig') as f:
    sample = f.read(8192)
    f.seek(0)
    dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
    has_header = csv.Sniffer().has_header(sample)
    reader = csv.DictReader(f, dialect=dialect) if has_header else csv.reader(f, dialect=dialect)
    rows = list(reader)

if has_header:
    columns = list(rows[0].keys()) if rows else []
    print(f"Rows: {len(rows)}")
    print(f"Columns: {', '.join(columns)}")
    print(f"Delimiter: {repr(dialect.delimiter)}")
    # Show first 3 rows as sample
    for i, row in enumerate(rows[:3]):
        print(f"  Row {i+1}: {dict(row)}")
else:
    print(f"Rows: {len(rows)}")
    print(f"Columns: {len(rows[0]) if rows else 0} (no header)")
    print(f"Delimiter: {repr(dialect.delimiter)}")
```

### XLSX

```python
import sys
from openpyxl import load_workbook

filepath = sys.argv[1]
wb = load_workbook(filepath, read_only=True)
ws = wb.active

rows = list(ws.iter_rows(values_only=True))
if not rows:
    print("Empty spreadsheet")
    sys.exit(0)

headers = [str(h) if h else f"col_{i}" for i, h in enumerate(rows[0])]
data_rows = rows[1:]

print(f"Sheet: {ws.title}")
print(f"Rows: {len(data_rows)}")
print(f"Columns: {', '.join(headers)}")
for i, row in enumerate(data_rows[:3]):
    print(f"  Row {i+1}: {dict(zip(headers, row))}")

wb.close()
```

### Google Sheets

Extract the sheet ID from the URL and download as CSV:

```python
import re, sys, urllib.request, tempfile

url = sys.argv[1]
# Extract sheet ID from various Google Sheets URL formats
match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
if not match:
    print("ERROR: Could not extract sheet ID from URL")
    sys.exit(1)

sheet_id = match.group(1)
export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

try:
    req = urllib.request.Request(export_url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urllib.request.urlopen(req, timeout=30)
    content = response.read().decode('utf-8-sig')

    # Save to workspace
    outpath = f"workspace/uploads/gsheet_{sheet_id}.csv"
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Downloaded to: {outpath}")
    print(f"Size: {len(content)} bytes")
except urllib.error.HTTPError as e:
    if e.code == 403:
        print("ERROR: Sheet is private. Ask Mike to share it publicly or export and send the file directly.")
    else:
        print(f"ERROR: HTTP {e.code} -- {e.reason}")
    sys.exit(1)
```

After downloading, parse it using the CSV parser above.

## 2. Deduplication

### Strategy

1. **Normalize** all string fields: lowercase, strip whitespace, remove extra spaces
2. **Exact match** on email (primary key for dedup)
3. **Fuzzy match** on name fields when no email available (SequenceMatcher >= 0.85)
4. **Address normalization**: standardize common abbreviations (St/Street, Ave/Avenue, etc.)
5. **Email domain grouping**: flag multiple contacts at the same domain for review
6. **Always show duplicate groups** to Mike before merging -- never auto-merge

### Dedup script

```python
import csv, sys, json
from difflib import SequenceMatcher
from collections import defaultdict

filepath = sys.argv[1]
email_col = sys.argv[2] if len(sys.argv) > 2 else None  # e.g., "email"
name_cols = sys.argv[3] if len(sys.argv) > 3 else None   # e.g., "first_name,last_name"

with open(filepath, 'r', encoding='utf-8-sig') as f:
    dialect = csv.Sniffer().sniff(f.read(8192))
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    rows = list(reader)
    headers = reader.fieldnames

original_count = len(rows)

# Normalize helper
def norm(s):
    return ' '.join(str(s).lower().strip().split()) if s else ''

# --- Exact email dedup ---
dupes_by_email = defaultdict(list)
if email_col and email_col in headers:
    for i, row in enumerate(rows):
        email = norm(row.get(email_col, ''))
        if email:
            dupes_by_email[email].append(i)

email_dupe_groups = {k: v for k, v in dupes_by_email.items() if len(v) > 1}

# --- Fuzzy name dedup (for rows without email or after email dedup) ---
fuzzy_groups = []
if name_cols:
    cols = name_cols.split(',')
    seen = set()
    for i, row in enumerate(rows):
        if i in seen:
            continue
        name_i = ' '.join(norm(row.get(c, '')) for c in cols)
        if not name_i.strip():
            continue
        group = [i]
        for j, row2 in enumerate(rows[i+1:], start=i+1):
            if j in seen:
                continue
            name_j = ' '.join(norm(row2.get(c, '')) for c in cols)
            if SequenceMatcher(None, name_i, name_j).ratio() >= 0.85:
                group.append(j)
                seen.add(j)
        if len(group) > 1:
            fuzzy_groups.append(group)
            seen.update(group)

# --- Report ---
print(f"Total rows: {original_count}")
print(f"Exact email duplicates: {len(email_dupe_groups)} groups ({sum(len(v)-1 for v in email_dupe_groups.values())} extra rows)")
print(f"Fuzzy name matches: {len(fuzzy_groups)} groups")

if email_dupe_groups:
    print("\n--- Email duplicate groups ---")
    for email, indices in list(email_dupe_groups.items())[:10]:
        print(f"\n  {email}:")
        for idx in indices:
            preview = {k: rows[idx][k] for k in list(headers)[:5]}
            print(f"    Row {idx+2}: {preview}")

if fuzzy_groups:
    print("\n--- Fuzzy name match groups ---")
    for group in fuzzy_groups[:10]:
        print(f"\n  Group:")
        for idx in group:
            preview = {k: rows[idx][k] for k in list(headers)[:5]}
            print(f"    Row {idx+2}: {preview}")

print(f"\nReview the groups above. Say 'merge' to keep first of each group, or specify which to keep.")
```

### Merge script (after Mike approves)

```python
import csv, sys
from collections import defaultdict
from datetime import datetime

filepath = sys.argv[1]
email_col = sys.argv[2]
outpath = sys.argv[3] if len(sys.argv) > 3 else None

with open(filepath, 'r', encoding='utf-8-sig') as f:
    dialect = csv.Sniffer().sniff(f.read(8192))
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    rows = list(reader)
    headers = reader.fieldnames

original_count = len(rows)

def norm(s):
    return ' '.join(str(s).lower().strip().split()) if s else ''

# Keep first occurrence of each email
seen_emails = set()
deduped = []
removed = 0
for row in rows:
    email = norm(row.get(email_col, ''))
    if email and email in seen_emails:
        removed += 1
        continue
    if email:
        seen_emails.add(email)
    deduped.append(row)

if not outpath:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    outpath = f"workspace/uploads/deduped_{ts}.csv"

with open(outpath, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(deduped)

print(f"Before: {original_count} rows")
print(f"Removed: {removed} duplicates")
print(f"After: {len(deduped)} rows")
print(f"Saved to: {outpath}")
```

## 3. Email Validation

Three-tier validation:

### Tier 1: Format check (regex)

```python
import re
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def is_valid_format(email):
    return bool(EMAIL_RE.match(email.strip()))
```

### Tier 2: MX record check

```python
import subprocess

def has_mx_record(domain):
    try:
        result = subprocess.run(
            ['nslookup', '-type=mx', domain],
            capture_output=True, text=True, timeout=10
        )
        return 'mail exchanger' in result.stdout.lower() or 'mx preference' in result.stdout.lower()
    except (subprocess.TimeoutExpired, Exception):
        return None  # inconclusive
```

### Tier 3: Disposable domain detection

```python
# Common disposable email domains
DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwaway.email',
    'yopmail.com', 'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'dispostable.com', 'mailnesia.com', 'maildrop.cc', 'discard.email',
    'fakeinbox.com', 'trashmail.com', 'temp-mail.org', '10minutemail.com',
    'getnada.com', 'mohmal.com', 'emailondeck.com', 'tempail.com',
    'burnermail.io', 'guerrillamail.info', 'trash-mail.com', 'harakirimail.com',
}

def is_disposable(email):
    domain = email.strip().lower().split('@')[-1]
    return domain in DISPOSABLE_DOMAINS
```

### Full validation script

```python
import csv, sys, re, subprocess
from datetime import datetime

filepath = sys.argv[1]
email_col = sys.argv[2]

EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'tempmail.com', 'throwaway.email',
    'yopmail.com', 'sharklasers.com', 'guerrillamailblock.com', 'grr.la',
    'dispostable.com', 'mailnesia.com', 'maildrop.cc', 'discard.email',
    'fakeinbox.com', 'trashmail.com', 'temp-mail.org', '10minutemail.com',
    'getnada.com', 'mohmal.com', 'emailondeck.com', 'tempail.com',
    'burnermail.io', 'guerrillamail.info', 'trash-mail.com', 'harakirimail.com',
}

def check_mx(domain):
    try:
        result = subprocess.run(
            ['nslookup', '-type=mx', domain],
            capture_output=True, text=True, timeout=10
        )
        return 'mail exchanger' in result.stdout.lower() or 'mx preference' in result.stdout.lower()
    except Exception:
        return None

with open(filepath, 'r', encoding='utf-8-sig') as f:
    dialect = csv.Sniffer().sniff(f.read(8192))
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    rows = list(reader)
    headers = reader.fieldnames

results = {'valid': 0, 'invalid_format': 0, 'no_mx': 0, 'disposable': 0, 'empty': 0}
flagged = []
mx_cache = {}

for i, row in enumerate(rows):
    email = (row.get(email_col, '') or '').strip()
    if not email:
        results['empty'] += 1
        continue

    # Format check
    if not EMAIL_RE.match(email):
        results['invalid_format'] += 1
        flagged.append((i+2, email, 'invalid_format'))
        continue

    domain = email.lower().split('@')[-1]

    # Disposable check
    if domain in DISPOSABLE_DOMAINS:
        results['disposable'] += 1
        flagged.append((i+2, email, 'disposable'))
        continue

    # MX check (cached per domain)
    if domain not in mx_cache:
        mx_cache[domain] = check_mx(domain)

    if mx_cache[domain] is False:
        results['no_mx'] += 1
        flagged.append((i+2, email, 'no_mx'))
    else:
        results['valid'] += 1

print(f"Total rows: {len(rows)}")
print(f"Valid emails: {results['valid']}")
print(f"Invalid format: {results['invalid_format']}")
print(f"No MX record: {results['no_mx']}")
print(f"Disposable: {results['disposable']}")
print(f"Empty/missing: {results['empty']}")
print(f"Domains checked: {len(mx_cache)}")

if flagged:
    print(f"\n--- Flagged emails (first 20) ---")
    for row_num, email, reason in flagged[:20]:
        print(f"  Row {row_num}: {email} [{reason}]")

print(f"\nSay 'remove flagged' to export a clean list without flagged rows, or 'keep all' to export with a validation column added.")
```

## 4. Enrichment

Enrich contacts by looking up company info from email domains. Uses web search and scraping.

### Domain enrichment

For each unique email domain in the list:

1. Extract the domain from the email address
2. Skip common free email providers (gmail.com, yahoo.com, hotmail.com, outlook.com, aol.com, icloud.com, protonmail.com)
3. Use WebSearch or WebFetch to look up the company website
4. Extract: company name, industry, location, size estimate, LinkedIn URL
5. Add enrichment columns to the output

```python
import csv, sys, json
from collections import defaultdict

filepath = sys.argv[1]
email_col = sys.argv[2]

FREE_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'protonmail.com', 'mail.com', 'zoho.com', 'yandex.com',
    'live.com', 'msn.com', 'me.com', 'comcast.net', 'verizon.net',
    'att.net', 'cox.net', 'sbcglobal.net', 'charter.net',
}

with open(filepath, 'r', encoding='utf-8-sig') as f:
    dialect = csv.Sniffer().sniff(f.read(8192))
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    rows = list(reader)
    headers = reader.fieldnames

# Count unique business domains
domain_counts = defaultdict(int)
for row in rows:
    email = (row.get(email_col, '') or '').strip().lower()
    if '@' in email:
        domain = email.split('@')[-1]
        if domain not in FREE_PROVIDERS:
            domain_counts[domain] += 1

print(f"Total rows: {len(rows)}")
print(f"Unique business domains: {len(domain_counts)}")
print(f"Contacts with business email: {sum(domain_counts.values())}")
print(f"Contacts with free email: {len(rows) - sum(domain_counts.values())}")

if domain_counts:
    print(f"\n--- Top 20 domains ---")
    for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1])[:20]:
        print(f"  {domain}: {count} contacts")

print(f"\nSay 'enrich' to look up company info for these domains.")
```

For the actual enrichment, use WebSearch/WebFetch tool calls (not Python) to look up each domain, then write the results back into the spreadsheet using Python.

## 5. Prospect List Generation

When Mike provides targeting criteria (industry, location, company size, job titles), generate a prospect list via web search.

### Process

1. Mike provides criteria: e.g., "IT directors at defense contractors in Virginia, 50-500 employees"
2. Build search queries from the criteria
3. Use WebSearch to find relevant companies and contacts
4. Compile results into a structured CSV with columns: company_name, website, industry, location, estimated_size, contact_name, title, email (if found), linkedin (if found), source_url
5. Send the prospect list file via `[SEND_FILE:]`

### Template for prospect CSV export

```python
import csv, sys
from datetime import datetime

# prospects is a list of dicts built from web search results
prospects = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
outpath = f"workspace/uploads/prospects_{ts}.csv"

fieldnames = ['company_name', 'website', 'industry', 'location', 'estimated_size',
              'contact_name', 'title', 'email', 'linkedin', 'source_url']

with open(outpath, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(prospects)

print(f"Prospect list: {len(prospects)} entries")
print(f"Saved to: {outpath}")
```

## 6. Export

### CSV export

```python
import csv, sys
from datetime import datetime

filepath = sys.argv[1]      # input file
rows_json = sys.argv[2]     # JSON string of processed rows (or "same" to copy)
suffix = sys.argv[3] if len(sys.argv) > 3 else "cleaned"

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
outpath = f"workspace/uploads/{suffix}_{ts}.csv"

import json
rows = json.loads(rows_json) if rows_json != "same" else None

if rows is None:
    # Copy with modifications already applied in-place
    import shutil
    shutil.copy2(filepath, outpath)
else:
    headers = list(rows[0].keys()) if rows else []
    with open(outpath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

print(f"Exported to: {outpath}")
```

### XLSX export

```python
import csv, sys, json
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

filepath = sys.argv[1]
suffix = sys.argv[2] if len(sys.argv) > 2 else "cleaned"

# Read the CSV data
with open(filepath, 'r', encoding='utf-8-sig') as f:
    dialect = csv.Sniffer().sniff(f.read(8192))
    f.seek(0)
    reader = csv.DictReader(f, dialect=dialect)
    rows = list(reader)
    headers = reader.fieldnames

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
outpath = f"workspace/uploads/{suffix}_{ts}.xlsx"

wb = Workbook()
ws = wb.active
ws.title = "Cleaned Data"

# Header row with bold + light blue fill
header_font = Font(bold=True)
header_fill = PatternFill(start_color='D6EAF8', end_color='D6EAF8', fill_type='solid')

for col, header in enumerate(headers, 1):
    cell = ws.cell(row=1, column=col, value=header)
    cell.font = header_font
    cell.fill = header_fill

# Data rows
for row_idx, row in enumerate(rows, 2):
    for col_idx, header in enumerate(headers, 1):
        ws.cell(row=row_idx, column=col_idx, value=row.get(header, ''))

# Auto-width columns
for col in ws.columns:
    max_length = max(len(str(cell.value or '')) for cell in col)
    ws.column_dimensions[col[0].column_letter].width = min(max_length + 2, 50)

wb.save(outpath)
print(f"Exported to: {outpath}")
print(f"Rows: {len(rows)}, Columns: {len(headers)}")
```

## 7. Address Normalization

Used during dedup to catch duplicates with different address formatting.

```python
ABBREVIATIONS = {
    'street': 'st', 'avenue': 'ave', 'boulevard': 'blvd', 'drive': 'dr',
    'lane': 'ln', 'road': 'rd', 'court': 'ct', 'place': 'pl',
    'circle': 'cir', 'highway': 'hwy', 'parkway': 'pkwy', 'terrace': 'ter',
    'suite': 'ste', 'apartment': 'apt', 'building': 'bldg', 'floor': 'fl',
    'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
    'northeast': 'ne', 'northwest': 'nw', 'southeast': 'se', 'southwest': 'sw',
}

def normalize_address(addr):
    if not addr:
        return ''
    addr = ' '.join(addr.lower().strip().split())
    # Remove punctuation
    addr = addr.replace('.', '').replace(',', ' ').replace('#', ' ')
    addr = ' '.join(addr.split())
    # Apply abbreviations
    words = addr.split()
    normalized = []
    for w in words:
        normalized.append(ABBREVIATIONS.get(w, w))
    return ' '.join(normalized)
```

## Workflow Summary

For any list operation, follow this sequence:

1. **Parse** the file (detect format, read contents)
2. **Summarize** to Mike (row count, columns, sample, obvious issues)
3. **Wait for instructions** (what operation to run)
4. **Run analysis** (show what would change -- duplicate groups, flagged emails, etc.)
5. **Wait for approval** (Mike confirms the changes)
6. **Execute** (write the cleaned file)
7. **Report stats** (before/after numbers)
8. **Send file** via `[SEND_FILE:]`
9. **Log to hive mind**

Never skip steps 2, 4, or 5. Mike always sees the plan before execution.
