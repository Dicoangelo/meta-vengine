#!/usr/bin/env python3
"""
Command Center 2.0 - Real-Time Claude Dashboard
FastAPI server that serves the same data as ccc-generator.sh but with live SSE updates.

Run: python3 ~/.claude/scripts/command-center-2.py
Open: http://localhost:8765
"""

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional, List
from collections import Counter
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

# Watchdog imports (optional - falls back to polling)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

PORT = 8765
HOST = "127.0.0.1"
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / "data"
KERNEL_DIR = CLAUDE_DIR / "kernel"
MEMORY_DIR = CLAUDE_DIR / "memory"
CONFIG_DIR = CLAUDE_DIR / "config"

WATCH_PATHS = [DATA_DIR, KERNEL_DIR]

# Pricing (matches pricing.json)
PRICING = {
    "opus": {"input": 15.0, "output": 75.0, "cache_read": 1.5},
    "sonnet": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "haiku": {"input": 0.25, "output": 1.25, "cache_read": 0.025},
}

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════════════

event_queue: asyncio.Queue = asyncio.Queue()
observer = None
polling_task = None


# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOADING FUNCTIONS (matching ccc-generator.sh logic)
# ═══════════════════════════════════════════════════════════════════════════════

def load_json_file(path: Path, default: Any = None) -> Any:
    """Safely load a JSON file."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception as e:
        print(f"Error loading {path}: {e}")
    return default if default is not None else {}


def load_jsonl_file(path: Path, limit: int = None) -> List[Dict]:
    """Load a JSONL file."""
    results = []
    try:
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        try:
                            results.append(json.loads(line))
                        except:
                            pass
            if limit:
                results = results[-limit:]
    except Exception as e:
        print(f"Error loading {path}: {e}")
    return results


def get_stats_data() -> Dict:
    """Load stats-cache.json data."""
    stats_file = CLAUDE_DIR / "stats-cache.json"
    default = {
        "totalSessions": 0,
        "totalMessages": 0,
        "totalTools": 0,
        "dailyActivity": [],
        "dailyModelTokens": [],
        "modelUsage": {},
        "hourCounts": {}
    }
    return load_json_file(stats_file, default)


def get_memory_data() -> Dict:
    """Load memory/knowledge.json data."""
    memory_file = MEMORY_DIR / "knowledge.json"
    default = {"facts": [], "decisions": [], "patterns": [], "context": {}, "projects": {}}
    return load_json_file(memory_file, default)


def get_activity_data() -> List[str]:
    """Load recent activity log entries."""
    activity_log = CLAUDE_DIR / "activity.log"
    try:
        if activity_log.exists():
            lines = activity_log.read_text().strip().split('\n')
            return lines[-200:]  # Last 200 lines
    except:
        pass
    return []


def get_project_stats(dir_path: Path, name: str, stack: str, css_class: str) -> Dict:
    """Get git stats for a project."""
    result = {
        "name": name,
        "stack": stack,
        "status": "active",
        "class": css_class,
        "files": "—",
        "commits": "—",
        "lines": "—"
    }

    git_dir = dir_path / ".git"
    if not git_dir.exists():
        return result

    try:
        # Count files
        files = 0
        for ext in ['*.ts', '*.tsx', '*.js', '*.jsx', '*.py']:
            files += len(list(dir_path.rglob(ext)))
        result["files"] = str(files)

        # Count commits
        commits = subprocess.run(
            ['git', 'rev-list', '--count', 'HEAD'],
            cwd=dir_path, capture_output=True, text=True, timeout=5
        )
        if commits.returncode == 0:
            result["commits"] = commits.stdout.strip()

        # Count lines (simplified)
        lines = 0
        for ext in ['*.ts', '*.tsx', '*.js', '*.jsx', '*.py']:
            for f in dir_path.rglob(ext):
                try:
                    lines += len(f.read_text().split('\n'))
                except:
                    pass
        if lines > 1000:
            result["lines"] = f"{lines/1000:.1f}K"
        else:
            result["lines"] = str(lines)
    except:
        pass

    return result


def get_projects_data() -> List[Dict]:
    """Get stats for all projects."""
    projects = [
        (HOME / "OS-App", "OS-App", "Vite + React 19 + Zustand + Supabase", "os-app"),
        (HOME / "CareerCoachAntigravity", "CareerCoach", "Next.js 14 + React 18 + Zustand", "career"),
        (HOME / "researchgravity", "ResearchGravity", "Python 3.8+ Research Framework", "research"),
        (HOME / "agent-core", "Agent Core", "Unified Agent Data Store", "agent"),
        (HOME / "Metaventions-AI-Landing", "Metaventions Landing", "AI Landing Page", "landing"),
        (HOME / "The-Decosystem", "The Decosystem", "Ecosystem Framework", "ecosystem"),
    ]
    return [get_project_stats(p[0], p[1], p[2], p[3]) for p in projects if p[0].exists()]


def get_routing_data() -> Dict:
    """Calculate routing metrics from dq-scores.jsonl."""
    dq_file = KERNEL_DIR / "dq-scores.jsonl"
    scores = []
    models = Counter()

    entries = load_jsonl_file(dq_file)
    for d in entries:
        if 'dqScore' in d:
            scores.append(d['dqScore'])
        elif 'dq' in d:
            dq = d['dq']
            if isinstance(dq, dict):
                dq = dq.get('score', 0)
            if dq > 0:
                scores.append(dq)
        if 'model' in d:
            models[d['model']] += 1

    total = len(scores)
    avg_dq = sum(scores) / total if scores else 0
    model_total = sum(models.values()) or 1

    model_dist = {
        'haiku': round(models.get('haiku', 0) / model_total, 3),
        'sonnet': round(models.get('sonnet', 0) / model_total, 3),
        'opus': round(models.get('opus', 0) / model_total, 3)
    }

    # Cost savings estimate
    haiku_pct = model_dist['haiku']
    sonnet_pct = model_dist['sonnet']
    opus_pct = model_dist['opus']
    actual_cost_pct = (haiku_pct * 0.017) + (sonnet_pct * 0.2) + (opus_pct * 1.0)
    cost_savings = round((1 - actual_cost_pct) * 100, 1) if opus_pct < 1 else 0

    return {
        'totalQueries': total,
        'avgDqScore': round(avg_dq, 3),
        'dataQuality': round(avg_dq, 2),
        'feedbackCount': total,
        'costReduction': cost_savings,
        'routingLatency': 42,
        'modelDistribution': model_dist,
        'modelCounts': dict(models),
        'accuracy': round(avg_dq * 100, 1),
        'targetQueries': 100,
        'targetDataQuality': 0.60,
        'targetFeedback': 100,
        'targetAccuracy': 60,
        'productionReady': total >= 100 and avg_dq >= 0.60,
        'recentScores': scores[-20:]  # For sparkline
    }


def get_coevo_data() -> Dict:
    """Get co-evolution data."""
    config_file = KERNEL_DIR / "coevo-config.json"
    patterns_file = KERNEL_DIR / "detected-patterns.json"
    mods_file = KERNEL_DIR / "modifications.jsonl"

    config = load_json_file(config_file, {"enabled": True, "autoApply": False, "minConfidence": 0.7})
    patterns = load_json_file(patterns_file, {"patterns": []})
    mods_count = len(load_jsonl_file(mods_file))

    # Get DQ score
    routing = get_routing_data()

    # Get cache efficiency from stats
    stats = get_stats_data()
    model_usage = stats.get('modelUsage', {})
    cache_efficiency = 95.0  # Default

    if model_usage and isinstance(list(model_usage.values())[0] if model_usage else {}, dict):
        model_data = list(model_usage.values())[0]
        cache_read = model_data.get('cacheReadInputTokens', 0)
        cache_create = model_data.get('cacheCreationInputTokens', 0)
        input_tokens = model_data.get('inputTokens', 0)
        total_input = cache_read + cache_create + input_tokens
        if total_input > 0:
            cache_efficiency = cache_read / total_input * 100

    return {
        "cacheEfficiency": round(cache_efficiency, 2),
        "dqScore": routing['avgDqScore'],
        "dominantPattern": patterns.get('patterns', [{}])[0].get('id', 'none') if patterns.get('patterns') else 'none',
        "modsApplied": mods_count,
        "autoApply": config.get('autoApply', False),
        "minConfidence": config.get('minConfidence', 0.7),
        "patterns": patterns.get('patterns', []),
        "lastAnalysis": config.get('lastAnalysis', 'Never')
    }


def get_subscription_data() -> Dict:
    """Get subscription value data."""
    sub_file = KERNEL_DIR / "subscription-data.json"
    data = load_json_file(sub_file, {})

    return {
        "rate": data.get('monthlySubscription', 200),
        "currency": "USD",
        "totalValue": data.get('totalValue', 0),
        "multiplier": data.get('roiMultiplier', 0),
        "savings": data.get('savingsVsApi', 0),
        "utilization": "unknown",
        "costPerMsg": 0
    }


def get_session_window_data() -> Dict:
    """Get session window/optimizer data."""
    state_file = KERNEL_DIR / "session-state.json"
    queue_file = KERNEL_DIR / "task-queue.json"

    result = {
        "window": {},
        "budget": {},
        "capacity": {},
        "queue": {"pending": 0},
        "recommendations": []
    }

    state = load_json_file(state_file, {})
    if state:
        result['window'] = state.get('window', {})
        result['budget'] = state.get('budget', {})
        result['capacity'] = state.get('capacity', {})

    queue = load_json_file(queue_file, {})
    if queue:
        pending = [t for t in queue.get('tasks', []) if t.get('status') == 'pending']
        result['queue'] = {'pending': len(pending)}

    # Generate recommendations
    tier = result['capacity'].get('tier', 'UNKNOWN')
    position = result['window'].get('positionPercent', 0)
    budget_used = result['budget'].get('utilizationPercent', 0)

    recs = []
    if tier == 'CRITICAL':
        recs.append('Switch to Haiku for remaining tasks')
    elif tier == 'LOW':
        recs.append('Avoid Opus unless critical')
    if position > 80:
        recs.append('Late in window - prioritize completion')
    if budget_used > 85:
        recs.append('Budget pressure - consider model downgrade')
    if result['queue']['pending'] > 5:
        recs.append('Batch similar tasks for efficiency')

    result['recommendations'] = recs if recs else ['Session healthy - proceed normally']
    return result


def get_session_outcomes_data() -> List[Dict]:
    """Get session outcomes."""
    outcomes_file = DATA_DIR / "session-outcomes.jsonl"
    sessions = load_jsonl_file(outcomes_file, limit=500)

    for s in sessions:
        s['quality'] = min(5, max(1, s.get('messages', 50) / 50))
        s['complexity'] = min(1.0, s.get('tools', 10) / 100)
        s['model_efficiency'] = 0.8

    return sessions


def get_pack_data() -> Dict:
    """Get context pack metrics."""
    pack_file = DATA_DIR / "pack-metrics.json"
    return load_json_file(pack_file, {
        "status": "not_configured",
        "global": {"total_sessions": 0},
        "top_packs": [],
        "daily_trend": [],
        "pack_inventory": []
    })


def get_observatory_data() -> Dict:
    """Get observatory analytics data."""
    try:
        result = subprocess.run(
            ['python3', str(CLAUDE_DIR / 'scripts/observatory/analytics-engine.py'), 'export', '9999'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {}


def get_proactive_data() -> Dict:
    """Get proactive suggestions."""
    try:
        result = subprocess.run(
            ['node', str(KERNEL_DIR / 'pattern-detector.js'), 'suggest'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return {"hasContext": False, "suggestions": []}


def get_file_activity_data() -> List[Dict]:
    """Get recent file changes from git."""
    projects = [
        ('OS-App', HOME / 'OS-App'),
        ('CareerCoach', HOME / 'CareerCoachAntigravity'),
        ('ResearchGravity', HOME / 'researchgravity'),
    ]

    file_counts = Counter()
    for name, path in projects:
        if path.exists() and (path / '.git').exists():
            try:
                result = subprocess.run(
                    ['git', 'log', '--oneline', '--name-only', '-50'],
                    cwd=path, capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split('\n'):
                    if '.' in line and '/' in line:
                        ext = line.rsplit('.', 1)[-1] if '.' in line else ''
                        if ext in ['ts', 'tsx', 'js', 'jsx', 'py', 'sh', 'json', 'md']:
                            file_counts[f"{name}:{line}"] += 1
            except:
                pass

    return [
        {'file': f.split(':', 1)[1], 'project': f.split(':')[0], 'count': c}
        for f, c in file_counts.most_common(15)
    ]


def get_pricing_data() -> Dict:
    """Get pricing configuration."""
    pricing_file = CONFIG_DIR / "pricing.json"
    return load_json_file(pricing_file, {
        "models": {
            "opus": {"input": 15, "output": 75, "cache_read": 1.5},
            "sonnet": {"input": 3, "output": 15},
            "haiku": {"input": 0.25, "output": 1.25}
        }
    })


def get_cognitive_data() -> Dict:
    """Get Cognitive OS data for dashboard."""
    cos_dir = KERNEL_DIR / "cognitive-os"
    flow_state_file = cos_dir / "flow-state.json"
    fate_file = cos_dir / "fate-predictions.jsonl"
    routing_file = cos_dir / "routing-decisions.jsonl"
    energy_file = cos_dir / "weekly-energy.json"

    result = {
        "status": "not_configured",
        "state": {
            "mode": "unknown",
            "focus_quality": 0,
            "best_for": [],
            "cognitive_load": "unknown"
        },
        "flow": {
            "state": "unknown",
            "score": 0,
            "in_flow": False,
            "protections": []
        },
        "weekly": {
            "Monday": 0.8, "Tuesday": 0.6, "Wednesday": 0.6,
            "Thursday": 0.4, "Friday": 0.6, "Saturday": 0.6, "Sunday": 0.6
        },
        "flowHistory": [],
        "routingHistory": [],
        "fate": {
            "predictions": [],
            "accuracy": 0
        },
        "commands": [
            {"cmd": "cos status", "desc": "Full system status"},
            {"cmd": "cos state", "desc": "Current cognitive mode"},
            {"cmd": "cos flow", "desc": "Flow state check"},
            {"cmd": "cos fate", "desc": "Session prediction"},
            {"cmd": "cos route", "desc": "Model recommendation"},
            {"cmd": "cos weekly", "desc": "Weekly energy map"},
            {"cmd": "cos schedule", "desc": "Task scheduling"}
        ]
    }

    # Check if cognitive-os.py exists
    cos_script = KERNEL_DIR / "cognitive-os.py"
    if not cos_script.exists():
        return result

    result["status"] = "active"

    # Try to get current state from cognitive-os.py
    try:
        state_result = subprocess.run(
            ['python3', str(cos_script), 'state', '--json'],
            capture_output=True, text=True, timeout=5
        )
        if state_result.returncode == 0:
            state_data = json.loads(state_result.stdout)
            result["state"] = {
                "mode": state_data.get("mode", "unknown"),
                "focus_quality": state_data.get("focus_quality", 0),
                "best_for": state_data.get("best_for", []),
                "cognitive_load": state_data.get("cognitive_load", "unknown")
            }
    except:
        # Fallback: determine mode from current hour
        hour = datetime.now().hour
        if 5 <= hour < 9:
            mode = "morning"
        elif 9 <= hour < 12 or 14 <= hour < 18:
            mode = "peak"
        elif 12 <= hour < 14:
            mode = "dip"
        elif 18 <= hour < 22:
            mode = "evening"
        else:
            mode = "deep_night"
        result["state"]["mode"] = mode

    # Load flow state from file (fast path)
    if flow_state_file.exists():
        flow_data = load_json_file(flow_state_file, {})
        result["flow"] = {
            "state": flow_data.get("state", "unknown"),
            "score": flow_data.get("score", 0),
            "in_flow": flow_data.get("in_flow", False),
            "protections": flow_data.get("protections", [])
        }

    # Load weekly energy map
    if energy_file.exists():
        result["weekly"] = load_json_file(energy_file, result["weekly"])

    # Load flow history (last 20 entries)
    flow_history_file = cos_dir / "flow-history.jsonl"
    if flow_history_file.exists():
        history = load_jsonl_file(flow_history_file, limit=20)
        result["flowHistory"] = [
            {"ts": h.get("timestamp", ""), "score": h.get("score", 0), "state": h.get("state", "")}
            for h in history
        ]

    # Load routing decisions (last 20)
    if routing_file.exists():
        routing = load_jsonl_file(routing_file, limit=20)
        result["routingHistory"] = [
            {"ts": r.get("timestamp", ""), "model": r.get("model", ""),
             "cognitive": r.get("cognitive_state", ""), "dq": r.get("dq_score", 0)}
            for r in routing
        ]

    # Load fate predictions and calculate accuracy
    if fate_file.exists():
        predictions = load_jsonl_file(fate_file, limit=100)
        result["fate"]["predictions"] = predictions[-10:]  # Last 10

        # Calculate accuracy
        correct = sum(1 for p in predictions if p.get("actual") == p.get("predicted"))
        total = len([p for p in predictions if p.get("actual")])
        result["fate"]["accuracy"] = round(correct / total * 100, 1) if total > 0 else 0

    return result


def get_supermemory_data() -> Dict:
    """Get supermemory statistics and status from SQLite database."""
    import sqlite3

    db_path = MEMORY_DIR / "supermemory.db"
    hooks_dir = CLAUDE_DIR / "hooks"
    cron_script = CLAUDE_DIR / "scripts" / "supermemory-cron.sh"

    result = {
        "status": "not_configured",
        "totals": {
            "memory_items": 0,
            "learnings": 0,
            "error_patterns": 0,
            "review_items": 0
        },
        "review": {
            "due_count": 0,
            "items": []
        },
        "recent_learnings": [],
        "error_patterns": [],
        "projects": {},
        "last_sync": None,
        "automations": {
            "session_sync": False,
            "error_lookup": False,
            "daily_cron": False,
            "weekly_rollup": False
        }
    }

    if not db_path.exists():
        return result

    result["status"] = "active"

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Get totals
        result["totals"]["memory_items"] = conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0]
        result["totals"]["learnings"] = conn.execute("SELECT COUNT(*) FROM learnings").fetchone()[0]
        result["totals"]["error_patterns"] = conn.execute("SELECT COUNT(*) FROM error_patterns").fetchone()[0]
        result["totals"]["review_items"] = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]

        # Get project breakdown
        rows = conn.execute("SELECT project, COUNT(*) as cnt FROM memory_items WHERE project IS NOT NULL GROUP BY project").fetchall()
        result["projects"] = {row["project"]: row["cnt"] for row in rows}

        # Get recent learnings (last 10)
        rows = conn.execute("SELECT content, category, project, date FROM learnings ORDER BY date DESC LIMIT 10").fetchall()
        result["recent_learnings"] = [{"content": r["content"], "category": r["category"], "project": r["project"], "date": r["date"]} for r in rows]

        # Get top error patterns
        rows = conn.execute("SELECT category, pattern, count, solution FROM error_patterns ORDER BY count DESC LIMIT 5").fetchall()
        result["error_patterns"] = [{"category": r["category"], "pattern": r["pattern"], "count": r["count"], "solution": r["solution"]} for r in rows]

        # Get due reviews
        today = datetime.now().strftime("%Y-%m-%d")
        result["review"]["due_count"] = conn.execute("SELECT COUNT(*) FROM reviews WHERE next_review <= ?", (today,)).fetchone()[0]
        rows = conn.execute("SELECT id, content, category, next_review FROM reviews WHERE next_review <= ? ORDER BY next_review LIMIT 5", (today,)).fetchall()
        result["review"]["items"] = [{"id": r["id"], "content": r["content"], "category": r["category"], "next_review": r["next_review"]} for r in rows]

        conn.close()
    except Exception as e:
        result["error"] = str(e)

    # Check automation status
    stop_hook = hooks_dir / "session-optimizer-stop.sh"
    if stop_hook.exists():
        content = stop_hook.read_text()
        result["automations"]["session_sync"] = "supermemory" in content.lower()

    error_hook = hooks_dir / "error-capture.sh"
    if error_hook.exists():
        content = error_hook.read_text()
        result["automations"]["error_lookup"] = "supermemory" in content.lower()

    # Check cron jobs
    result["automations"]["daily_cron"] = cron_script.exists()

    try:
        cron_result = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=5)
        if cron_result.returncode == 0:
            result["automations"]["weekly_rollup"] = "supermemory-cron.sh weekly" in cron_result.stdout
    except:
        pass

    return result


def is_session_active() -> bool:
    """Check if there's an active Claude session."""
    activity_log = CLAUDE_DIR / "activity.log"
    if activity_log.exists():
        mtime = datetime.fromtimestamp(activity_log.stat().st_mtime)
        if datetime.now() - mtime < timedelta(minutes=5):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# FILE WATCHER
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardEventHandler(FileSystemEventHandler):
    """Watch for file changes and push to SSE queue."""

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop
        self._last_event = {}

    def _debounce(self, path: str, event_type: str) -> bool:
        key = f"{path}:{event_type}"
        now = datetime.now().timestamp()
        if key in self._last_event and now - self._last_event[key] < 0.5:
            return False
        self._last_event[key] = now
        return True

    def on_modified(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not self._debounce(path, "modified"):
            return

        # Determine update type
        category = "data"
        if "session" in path.lower():
            category = "session"
        elif "activity" in path.lower() or "tool" in path.lower():
            category = "activity"
        elif "dq-scores" in path or "routing" in path:
            category = "routing"

        event_data = {"type": "update", "category": category, "ts": datetime.now().isoformat()}
        asyncio.run_coroutine_threadsafe(self.queue.put(event_data), self.loop)


def start_file_watcher(loop: asyncio.AbstractEventLoop):
    global observer, polling_task

    if WATCHDOG_AVAILABLE:
        observer = Observer()
        handler = DashboardEventHandler(event_queue, loop)
        for path in WATCH_PATHS:
            if path.exists():
                observer.schedule(handler, str(path), recursive=True)
        observer.start()
        print("  Mode: File watching (watchdog)")
    else:
        print("  Mode: Polling (watchdog not installed)")
        polling_task = asyncio.run_coroutine_threadsafe(poll_for_changes(), loop)


async def poll_for_changes():
    """Poll for file changes when watchdog isn't available."""
    last_mtimes = {}
    while True:
        await asyncio.sleep(5)
        try:
            for watch_path in WATCH_PATHS:
                if not watch_path.exists():
                    continue
                for path in watch_path.rglob("*"):
                    if path.is_file():
                        try:
                            mtime = path.stat().st_mtime
                            path_str = str(path)
                            if path_str in last_mtimes and last_mtimes[path_str] != mtime:
                                await event_queue.put({
                                    "type": "update",
                                    "category": "data",
                                    "ts": datetime.now().isoformat()
                                })
                            last_mtimes[path_str] = mtime
                        except:
                            pass
        except:
            pass


def stop_file_watcher():
    global observer, polling_task
    if observer:
        observer.stop()
        observer.join()
    if polling_task:
        polling_task.cancel()


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 60)
    print("  Command Center 2.0 - Starting...")
    print("=" * 60)

    loop = asyncio.get_event_loop()
    start_file_watcher(loop)

    print(f"\n  Dashboard: http://{HOST}:{PORT}")
    print("  Press Ctrl+C to stop\n")
    print("=" * 60 + "\n")

    yield

    stop_file_watcher()
    print("\n  Command Center 2.0 - Stopped")


app = FastAPI(title="Command Center 2.0", lifespan=lifespan)


# ═══════════════════════════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/stats")
async def api_stats():
    return get_stats_data()

@app.get("/api/memory")
async def api_memory():
    return get_memory_data()

@app.get("/api/activity")
async def api_activity():
    return get_activity_data()

@app.get("/api/projects")
async def api_projects():
    return get_projects_data()

@app.get("/api/routing")
async def api_routing():
    return get_routing_data()

@app.get("/api/coevo")
async def api_coevo():
    return get_coevo_data()

@app.get("/api/subscription")
async def api_subscription():
    return get_subscription_data()

@app.get("/api/session-window")
async def api_session_window():
    return get_session_window_data()

@app.get("/api/session-outcomes")
async def api_session_outcomes():
    return get_session_outcomes_data()

@app.get("/api/packs")
async def api_packs():
    return get_pack_data()

@app.get("/api/observatory")
async def api_observatory():
    return get_observatory_data()

@app.get("/api/proactive")
async def api_proactive():
    return get_proactive_data()

@app.get("/api/file-activity")
async def api_file_activity():
    return get_file_activity_data()

@app.get("/api/pricing")
async def api_pricing():
    return get_pricing_data()

@app.get("/api/supermemory")
async def api_supermemory():
    return get_supermemory_data()

@app.get("/api/cognitive")
async def api_cognitive():
    return get_cognitive_data()

@app.get("/api/status")
async def api_status():
    """Get current session status."""
    return {"active": is_session_active(), "ts": datetime.now().isoformat()}

@app.get("/api/all")
async def api_all():
    """Get all data in one call (for initial load)."""
    return {
        "stats": get_stats_data(),
        "memory": get_memory_data(),
        "activity": get_activity_data(),
        "projects": get_projects_data(),
        "routing": get_routing_data(),
        "coevo": get_coevo_data(),
        "subscription": get_subscription_data(),
        "sessionWindow": get_session_window_data(),
        "sessionOutcomes": get_session_outcomes_data(),
        "packs": get_pack_data(),
        "proactive": get_proactive_data(),
        "fileActivity": get_file_activity_data(),
        "pricing": get_pricing_data(),
        "supermemory": get_supermemory_data(),
        "cognitive": get_cognitive_data(),
        "status": {"active": is_session_active()}
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SSE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

async def event_generator() -> AsyncGenerator[str, None]:
    yield f"data: {json.dumps({'type': 'connected', 'ts': datetime.now().isoformat()})}\n\n"

    while True:
        try:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'ping', 'ts': datetime.now().isoformat()})}\n\n"
        except asyncio.CancelledError:
            break
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/api/live")
async def live_stream(request: Request):
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SERVE ORIGINAL DASHBOARD WITH LIVE UPDATES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard - generates fresh data each time."""
    # Read the original generated dashboard
    dashboard_file = CLAUDE_DIR / "dashboard" / "claude-command-center.html"

    if dashboard_file.exists():
        html = dashboard_file.read_text()

        # Inject SSE script for live updates
        sse_script = '''
<script>
// Command Center 2.0 - Live Updates
(function() {
  const es = new EventSource('/api/live');
  let reconnectAttempts = 0;

  es.onmessage = function(e) {
    const data = JSON.parse(e.data);
    reconnectAttempts = 0;

    if (data.type === 'update') {
      // Show update notification
      const indicator = document.querySelector('.live-indicator .live-dot');
      if (indicator) {
        indicator.style.background = '#00ff88';
        indicator.style.boxShadow = '0 0 20px #00ff88';
        setTimeout(() => {
          indicator.style.background = '';
          indicator.style.boxShadow = '';
        }, 1000);
      }

      // Auto-refresh after short delay to batch updates
      clearTimeout(window._refreshTimeout);
      window._refreshTimeout = setTimeout(() => {
        location.reload();
      }, 2000);
    }
  };

  es.onerror = function() {
    reconnectAttempts++;
    if (reconnectAttempts > 5) {
      es.close();
      console.log('SSE: Max reconnect attempts reached');
    }
  };

  // Update live indicator
  const liveText = document.querySelector('.live-indicator span:last-child');
  if (liveText) liveText.textContent = 'Live 2.0';
})();
</script>
'''
        # Inject before </body>
        html = html.replace('</body>', sse_script + '</body>')
        return HTMLResponse(html)

    # Fallback - regenerate dashboard
    return HTMLResponse("""
    <html>
    <head><title>Command Center 2.0</title></head>
    <body style="background:#050508;color:#f0f0f5;font-family:sans-serif;padding:2rem;">
        <h1>Dashboard Not Generated</h1>
        <p>Run <code>ccc</code> first to generate the dashboard, then refresh this page.</p>
        <p>Or open <a href="/api/all" style="color:#00d9ff;">/api/all</a> to see raw data.</p>
    </body>
    </html>
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
