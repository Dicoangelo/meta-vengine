# SOP: Connecting Data Sources to Command Center Dashboard

## Purpose
Standard procedure for integrating new data sources into the Claude Command Center dashboard.

---

## Pre-Flight Checklist

Before starting, gather:

| Item | Example | Where to Find |
|------|---------|---------------|
| Source data location | `~/.agent-core/context-packs/` | User's description |
| Source file format | JSON, JSONL | `file` or `head -5` |
| Source field names | `name`, `tokens`, `type` | Read source files |
| Target tab in dashboard | CONTEXT PACKS | `command-center.html` |
| Target field names | `pack_id`, `size_tokens` | Grep template |

---

## Phase 1: Understand Source Data

### 1.1 Locate and inspect source files
```bash
# Find the data
ls -la <source_directory>/

# Inspect structure
cat <source_file>.json | python3 -m json.tool | head -50

# For JSONL files
head -3 <source_file>.jsonl | python3 -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]"
```

### 1.2 Document the schema
Create a schema map:
```
SOURCE SCHEMA:
├── registry.json
│   └── packs.<name>
│       ├── type: string
│       ├── size_tokens: number
│       └── created: timestamp
└── metrics.json
    └── pack_stats.<name>
        ├── times_selected: number
        └── avg_dq_score: number
```

---

## Phase 2: Understand Target (Dashboard)

### 2.1 Find the relevant tab rendering code
```bash
# Search for tab name
grep -n "CONTEXT PACKS\|loadPackMetrics" ~/.claude/scripts/command-center.html

# Find data placeholder
grep -n "__PACK_DATA__\|PACK_DATA" ~/.claude/scripts/command-center.html
```

### 2.2 Document expected fields
```bash
# Find what fields the template expects
grep -E "\\\${pack\." ~/.claude/scripts/command-center.html
```

Example output:
```
${pack.pack_id}
${pack.size_tokens}
${pack.keywords.slice(0,3).join(', ')}
```

### 2.3 Create field mapping table
```
| Template Expects | Source Has    | Transform Needed |
|------------------|---------------|------------------|
| pack.pack_id     | pack.name     | Rename           |
| pack.size_tokens | pack.tokens   | Rename           |
| pack.keywords    | (none)        | Remove/default   |
```

---

## Phase 3: Create Data Generator

### 3.1 Generator script template
Location: `~/.claude/scripts/generate-<source>-metrics.py`

```python
#!/usr/bin/env python3
"""
Generate <SOURCE> metrics for Command Center dashboard.
Reads from: <source_location>
Writes to: ~/.claude/data/<source>-metrics.json
"""

import json
from datetime import datetime
from pathlib import Path

# Paths
SOURCE_DIR = Path.home() / "<source_path>"
OUTPUT_FILE = Path.home() / ".claude/data/<source>-metrics.json"

def main():
    output = {
        "status": "not_configured",
        "generated": datetime.now().isoformat(),
        # Add expected structure...
    }

    # Check source exists
    if not SOURCE_DIR.exists():
        print(f"Source not found: {SOURCE_DIR}")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        return

    # Load source data
    # Transform to target schema
    # Write output

    output["status"] = "active"
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Wrote metrics to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
```

### 3.2 Make executable
```bash
chmod +x ~/.claude/scripts/generate-<source>-metrics.py
```

---

## Phase 4: Integrate with ccc-generator.sh

### 4.1 Add generator call
Find the data loading section in `ccc-generator.sh` and add:

```bash
echo "  📦 Loading <source> metrics..."
# Generate fresh metrics
python3 "$HOME/.claude/scripts/generate-<source>-metrics.py" 2>/dev/null || true

<SOURCE>_METRICS_FILE="$HOME/.claude/data/<source>-metrics.json"
if [[ -f "$<SOURCE>_METRICS_FILE" ]]; then
  <SOURCE>_DATA=$(cat "$<SOURCE>_METRICS_FILE")
else
  <SOURCE>_DATA='{"status":"not_configured"}'
fi
```

### 4.2 Inject into template
In the Python section of ccc-generator.sh:

```python
<source>_data = safe_parse('''$<SOURCE>_DATA''', {"status":"not_configured"})
output = output.replace('__<SOURCE>_DATA__', json.dumps(<source>_data))
```

---

## Phase 5: Fix Template Field Mappings

### 5.1 Update field references
In `command-center.html`, change:
```javascript
// Before
${pack.pack_id}
${pack.size_tokens}

// After (with fallbacks)
${pack.name || pack.pack_id}
${pack.tokens || pack.size_tokens || 0}
```

### 5.2 Handle missing fields
```javascript
// Remove or provide defaults
${pack.keywords?.slice(0,3).join(', ') || 'N/A'}

// Or conditionally render
${pack.times_used ? `<span>Used: ${pack.times_used}x</span>` : ''}
```

---

## Phase 6: Verification

### 6.1 Test generator standalone
```bash
python3 ~/.claude/scripts/generate-<source>-metrics.py
cat ~/.claude/data/<source>-metrics.json | python3 -m json.tool
```

### 6.2 Test full pipeline
```bash
~/.claude/scripts/ccc-generator.sh
```

### 6.3 Verify in browser
```bash
# Check injected data
grep -A3 "const <SOURCE>_DATA" /tmp/claude-command-center.html
```

### 6.4 Visual verification
- Open dashboard
- Navigate to target tab
- Confirm data displays (not "undefined" or "not configured")

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "undefined" in UI | Field name mismatch | Check template vs data field names |
| "not_configured" | Generator not running | Check python3 path, file permissions |
| Empty data | Source files missing | Verify source path exists |
| Tab not updating | Browser cache | Hard refresh (Cmd+Shift+R) |
| Data not injected | Placeholder mismatch | Check `__PLACEHOLDER__` spelling |

---

## Quick Reference Commands

```bash
# Regenerate all dashboard data
python3 ~/.claude/scripts/fix-all-dashboard-data.py

# Generate specific metrics
python3 ~/.claude/scripts/generate-pack-metrics.py

# Build and open dashboard
~/.claude/scripts/ccc-generator.sh

# Check generated dashboard data
grep "const PACK_DATA" /tmp/claude-command-center.html | head -1

# Verify field names in template
grep -E "\\\${pack\." ~/.claude/scripts/command-center.html
```

---

## Files Reference

| Purpose | Location |
|---------|----------|
| Dashboard template | `~/.claude/scripts/command-center.html` |
| Dashboard generator | `~/.claude/scripts/ccc-generator.sh` |
| Data repair script | `~/.claude/scripts/fix-all-dashboard-data.py` |
| Generated dashboard | `/tmp/claude-command-center.html` |
| Pack metrics | `~/.claude/data/pack-metrics.json` |
| Session outcomes | `~/.claude/data/session-outcomes.jsonl` |

---

## Checklist Template

```markdown
## Integration: [Data Source Name]

- [ ] Located source files at: ___
- [ ] Documented source schema
- [ ] Found target tab: ___
- [ ] Documented target field names
- [ ] Created field mapping table
- [ ] Created generator script
- [ ] Added to ccc-generator.sh
- [ ] Fixed template field references
- [ ] Tested generator standalone
- [ ] Tested full pipeline
- [ ] Verified in browser
```
