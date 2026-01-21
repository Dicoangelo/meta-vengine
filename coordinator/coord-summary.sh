#!/bin/bash
# Coordinator Summary Dashboard
# Shows formatted status of the multi-agent coordination system

set -e

COORD_DIR="$HOME/.claude/coordinator"
DATA_DIR="$COORD_DIR/data"

# Get data via Python for proper JSON handling
STATUS=$(python3 << 'PYEOF'
import json
from pathlib import Path

home = Path.home()
agents_file = home / ".claude/coordinator/data/active-agents.json"
locks_file = home / ".claude/coordinator/data/file-locks.json"
log_file = home / ".claude/coordinator/data/coordination-log.jsonl"

# Load agents
agents = {}
if agents_file.exists():
    try:
        with open(agents_file) as f:
            agents = json.load(f)
    except: pass

# Load locks
locks = {}
if locks_file.exists():
    try:
        with open(locks_file) as f:
            locks = json.load(f)
    except: pass

# Load recent coordinations
recent = []
if log_file.exists():
    try:
        with open(log_file) as f:
            lines = f.readlines()[-5:]  # Last 5
            recent = [json.loads(l) for l in lines if l.strip()]
    except: pass

# Calculate stats
total_agents = len(agents)
by_state = {}
by_model = {}
total_cost = 0.0
active_count = 0

for a in agents.values():
    state = a.get("state", "unknown")
    model = a.get("model", "unknown")
    cost = a.get("cost_estimate", 0)
    
    by_state[state] = by_state.get(state, 0) + 1
    by_model[model] = by_model.get(model, 0) + 1
    total_cost += cost
    
    if state in ["pending", "running"]:
        active_count += 1

# Lock stats
total_locks = len(locks)
read_locks = sum(1 for l in locks.values() if l.get("lock_type") == "read")
write_locks = sum(1 for l in locks.values() if l.get("lock_type") == "write")

print(json.dumps({
    "agents": {
        "total": total_agents,
        "active": active_count,
        "by_state": by_state,
        "by_model": by_model,
        "cost": round(total_cost, 4)
    },
    "locks": {
        "total": total_locks,
        "read": read_locks,
        "write": write_locks
    },
    "recent": recent
}))
PYEOF
)

# Parse JSON values
TOTAL_AGENTS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['total'])")
ACTIVE_AGENTS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['active'])")
COST_EST=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['cost'])")
TOTAL_LOCKS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['locks']['total'])")
READ_LOCKS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['locks']['read'])")
WRITE_LOCKS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['locks']['write'])")

# Model counts
HAIKU=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_model'].get('haiku', 0))")
SONNET=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_model'].get('sonnet', 0))")
OPUS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_model'].get('opus', 0))")

# State counts
RUNNING=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_state'].get('running', 0))")
COMPLETED=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_state'].get('completed', 0))")
FAILED=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['agents']['by_state'].get('failed', 0))")

# Display
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           🤖 MULTI-AGENT COORDINATOR STATUS                  ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  AGENTS                          LOCKS                       ║"
echo "║  ├─ Total:     $(printf '%-4s' $TOTAL_AGENTS)                   ├─ Total:    $(printf '%-4s' $TOTAL_LOCKS)           ║"
echo "║  ├─ Active:    $(printf '%-4s' $ACTIVE_AGENTS)                   ├─ Read:     $(printf '%-4s' $READ_LOCKS)           ║"
echo "║  └─ Cost:      \$$(printf '%-7s' $COST_EST)              └─ Write:    $(printf '%-4s' $WRITE_LOCKS)           ║"
echo "║                                                              ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  BY MODEL                        BY STATE                    ║"
echo "║  ├─ Haiku:     $(printf '%-4s' $HAIKU)                   ├─ Running:  $(printf '%-4s' $RUNNING)           ║"
echo "║  ├─ Sonnet:    $(printf '%-4s' $SONNET)                   ├─ Complete: $(printf '%-4s' $COMPLETED)           ║"
echo "║  └─ Opus:      $(printf '%-4s' $OPUS)                   └─ Failed:   $(printf '%-4s' $FAILED)           ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Recent coordinations
RECENT_COUNT=$(echo "$STATUS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)['recent']))")
if [ "$RECENT_COUNT" -gt 0 ]; then
    echo "  ─── Recent Coordinations ───"
    echo "$STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data['recent'][-3:]:
    task = r.get('task', 'Unknown')[:40]
    status = r.get('status', '?')
    strategy = r.get('strategy', '?')
    icon = '✓' if status == 'success' else '✗' if status == 'failed' else '○'
    print(f'  {icon} [{strategy}] {task}...')
"
    echo ""
fi

echo "  Commands: coord research|implement|review|full \"task\""
echo ""
