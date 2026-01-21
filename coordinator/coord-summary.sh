#!/bin/bash
# Coordinator Summary Dashboard
# Shows formatted status of the multi-agent coordination system
#
# Fixed: Quoted variables, consolidated Python calls, proper exception handling

set -e

# Single Python call that outputs all values as shell variables
eval "$(python3 << 'PYEOF'
import json
import sys
from pathlib import Path

home = Path.home()
agents_file = home / ".claude/coordinator/data/active-agents.json"
locks_file = home / ".claude/coordinator/data/file-locks.json"
log_file = home / ".claude/coordinator/data/coordination-log.jsonl"

# Load agents with proper exception handling
agents = {}
if agents_file.exists():
    try:
        with open(agents_file) as f:
            content = f.read().strip()
            if content:
                agents = json.loads(content)
                if not isinstance(agents, dict):
                    agents = {}
    except json.JSONDecodeError as e:
        print(f"# Warning: Invalid JSON in agents file: {e}", file=sys.stderr)
    except IOError as e:
        print(f"# Warning: Could not read agents file: {e}", file=sys.stderr)

# Load locks with proper exception handling
locks = {}
if locks_file.exists():
    try:
        with open(locks_file) as f:
            content = f.read().strip()
            if content:
                locks = json.loads(content)
                if not isinstance(locks, dict):
                    locks = {}
    except json.JSONDecodeError as e:
        print(f"# Warning: Invalid JSON in locks file: {e}", file=sys.stderr)
    except IOError as e:
        print(f"# Warning: Could not read locks file: {e}", file=sys.stderr)

# Load recent coordinations with bounds checking
recent = []
if log_file.exists():
    try:
        # Use tail-like approach for large files
        with open(log_file, 'rb') as f:
            # Seek to end, read last 10KB max
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 10240))
            content = f.read().decode('utf-8', errors='ignore')

        lines = content.strip().split('\n')
        for line in lines[-5:]:
            if line.strip():
                try:
                    entry = json.loads(line)
                    if isinstance(entry, dict):
                        recent.append(entry)
                except json.JSONDecodeError:
                    pass
    except IOError as e:
        print(f"# Warning: Could not read log file: {e}", file=sys.stderr)

# Calculate stats
total_agents = len(agents)
by_state = {}
by_model = {}
total_cost = 0.0
active_count = 0

for a in agents.values():
    if not isinstance(a, dict):
        continue
    state = str(a.get("state", "unknown"))
    model = str(a.get("model", "unknown"))
    cost = float(a.get("cost_estimate", 0) or 0)

    by_state[state] = by_state.get(state, 0) + 1
    by_model[model] = by_model.get(model, 0) + 1
    total_cost += cost

    if state in ["pending", "running"]:
        active_count += 1

# Lock stats with type validation
total_locks = len(locks)
read_locks = 0
write_locks = 0
for l in locks.values():
    if isinstance(l, dict):
        lock_type = l.get("lock_type", "")
        if lock_type == "read":
            read_locks += 1
        elif lock_type == "write":
            write_locks += 1

# Output shell variables (no quotes needed for integers)
print(f'TOTAL_AGENTS={total_agents}')
print(f'ACTIVE_AGENTS={active_count}')
print(f'COST_EST={round(total_cost, 4)}')
print(f'TOTAL_LOCKS={total_locks}')
print(f'READ_LOCKS={read_locks}')
print(f'WRITE_LOCKS={write_locks}')
print(f'HAIKU={by_model.get("haiku", 0)}')
print(f'SONNET={by_model.get("sonnet", 0)}')
print(f'OPUS={by_model.get("opus", 0)}')
print(f'RUNNING={by_state.get("running", 0)}')
print(f'COMPLETED={by_state.get("completed", 0)}')
print(f'FAILED={by_state.get("failed", 0)}')
print(f'RECENT_COUNT={len(recent)}')

# Output recent as JSON for later parsing
import base64
recent_json = json.dumps(recent)
recent_b64 = base64.b64encode(recent_json.encode()).decode()
print(f'RECENT_B64={recent_b64}')
PYEOF
)"

# Display with properly quoted variables
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           🤖 MULTI-AGENT COORDINATOR STATUS                  ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  AGENTS                          LOCKS                       ║"
echo "║  ├─ Total:     $(printf '%-4s' "$TOTAL_AGENTS")                   ├─ Total:    $(printf '%-4s' "$TOTAL_LOCKS")           ║"
echo "║  ├─ Active:    $(printf '%-4s' "$ACTIVE_AGENTS")                   ├─ Read:     $(printf '%-4s' "$READ_LOCKS")           ║"
echo "║  └─ Cost:      \$$(printf '%-7s' "$COST_EST")              └─ Write:    $(printf '%-4s' "$WRITE_LOCKS")           ║"
echo "║                                                              ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  BY MODEL                        BY STATE                    ║"
echo "║  ├─ Haiku:     $(printf '%-4s' "$HAIKU")                   ├─ Running:  $(printf '%-4s' "$RUNNING")           ║"
echo "║  ├─ Sonnet:    $(printf '%-4s' "$SONNET")                   ├─ Complete: $(printf '%-4s' "$COMPLETED")           ║"
echo "║  └─ Opus:      $(printf '%-4s' "$OPUS")                   └─ Failed:   $(printf '%-4s' "$FAILED")           ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Recent coordinations (decode from base64)
if [ "$RECENT_COUNT" -gt 0 ]; then
    echo "  ─── Recent Coordinations ───"
    echo "$RECENT_B64" | base64 -d | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data[-3:]:
    if not isinstance(r, dict):
        continue
    task = str(r.get('task', 'Unknown'))[:40]
    status = str(r.get('status', '?'))
    strategy = str(r.get('strategy', '?'))
    icon = '✓' if status == 'success' else '✗' if status == 'failed' else '○'
    print(f'  {icon} [{strategy}] {task}...')
"
    echo ""
fi

echo "  Commands: coord research|implement|review|full \"task\""
echo ""
