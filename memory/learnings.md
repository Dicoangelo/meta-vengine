
## 2026-01-23 - CCC Infrastructure Debugging Session

### Pattern: Datetime Naive vs Aware Comparison
**Problem:** `datetime.now()` creates naive datetimes, but APIs (arXiv, etc.) return timezone-aware. Comparison fails silently or throws error.
**Fix:** Always use `datetime.now(timezone.utc)` or `datetime.now(LOCAL_TZ)` when comparing with external timestamps.
**Files affected:** routing-research-sync.py, potentially ab-test-analyzer.py, backfill-cognitive-data.py

### Pattern: Python 3.10+ Type Hints
**Problem:** `int | float` union syntax only works in Python 3.10+. Homebrew Python 3.14 works, but some contexts use older Python.
**Fix:** Use `typing.Union[int, float]` or omit type hints for compatibility.
**Files affected:** daily-memory-log.py

### Pattern: SIGTERM Insufficient for Claude Processes
**Problem:** `kill -TERM` sends polite shutdown signal. Stuck Claude processes ignore it.
**Fix:** Escalate: SIGTERM → wait 3s → check survivors → SIGKILL (-9)
**Implementation:** ccc-self-heal.py fix_kill_stale_processes()

### Pattern: Watchdog Race Condition
**Problem:** Multiple launchctl calls in quick succession can detect same daemon as down multiple times.
**Fix:** Single `launchctl list` call, parse output, track healed daemons in set to avoid duplicates.
**Implementation:** ccc-watchdog.py check_and_heal()

### Pattern: PEP 668 Externally Managed Python
**Problem:** Homebrew Python blocks `pip install` to protect system packages.
**Fix:** Create project venv at `~/.claude/venv/` for packages like arxiv, requests.
**Usage:** `~/.claude/venv/bin/python3` in cron jobs and scripts needing external packages.

### Architecture: 5-Layer Self-Healing
1. **Watchdog** (60s) - monitors all daemons, auto-reloads
2. **KeepAlive** - launchd restarts watchdog if it dies
3. **Bootstrap** - reloads everything on login
4. **Wake Hook** - reloads after sleep
5. **Self-Heal** (6h) - deep health checks, data validation, cleanup


## 2026-01-23 - CCC Autonomous System Session

### Architecture Created
- **4-Layer Autonomous Architecture**: Reactive → Guardian → Cognitive → Experimental
- **9 Daemons**: watchdog, brain, self-heal, dashboard-refresh, supermemory, session-analysis, autonomous-maintenance, bootstrap, wake-hook
- **Intelligence Layer**: Predictive routing, cost prevention, session success, optimal timing

### Key Files
- `~/.claude/scripts/ccc-autonomous-brain.py` - Cognitive layer
- `~/.claude/scripts/ccc-intelligence-layer.py` - Predictive analytics
- `~/.claude/scripts/ccc-autopilot.py` - Full autonomy orchestration
- `~/.claude/AUTONOMOUS_CAPABILITIES.md` - Documentation

### Patterns Learned
- Tool sequences predictable (64% Bash→Bash, 48% Read→Read)
- SIGTERM insufficient for stuck processes, need SIGKILL escalation
- Single launchctl call prevents watchdog race conditions
- Venv needed for external packages (PEP 668)

