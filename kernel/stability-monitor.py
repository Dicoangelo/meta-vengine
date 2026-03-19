#!/usr/bin/env python3
"""
US-308: Multiplier Stability Monitor

Tracks multiplier convergence per session type — detects when learning
has stabilized.  For each of the 8 session types, compares the 3 reward
multipliers (dq, cost, behavioral) at the start vs end of a sliding
window from bandit-history.jsonl.

Status levels:
  learning   — below volume gate (< 100 decisions)
  converging — above gate, multipliers still drifting > threshold
  converged  — all 3 multipliers changed < threshold over the window

Standalone:  python3 kernel/stability-monitor.py
API helper:  from kernel import stability_monitor; stability_monitor.api_convergence()
"""

import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_KERNEL_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_KERNEL_DIR)
_DATA_DIR = os.path.join(_PROJECT_ROOT, 'data')

BANDIT_HISTORY_PATH = os.path.join(_DATA_DIR, 'bandit-history.jsonl')
STATS_PATH = os.path.join(_DATA_DIR, 'session-type-stats.jsonl')
CONVERGENCE_EVENTS_PATH = os.path.join(_DATA_DIR, 'convergence-events.jsonl')
LEARNABLE_PARAMS_PATH = os.path.join(_PROJECT_ROOT, 'config', 'learnable-params.json')

SESSION_TYPES = [
    "debugging", "research", "architecture", "refactoring",
    "testing", "docs", "exploration", "creative",
]

MULTIPLIER_KEYS = ["dq", "cost", "behavioral"]

VOLUME_GATE_THRESHOLD = 100


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_jsonl(path):
    """Read all entries from a JSONL file."""
    if not os.path.isfile(path):
        return []
    entries = []
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass
    return entries


def _get_volume_counts():
    """Return dict of session_type -> cumulative_count from session-type-stats."""
    counts = {}
    for entry in _read_jsonl(STATS_PATH):
        st = entry.get('session_type')
        cc = entry.get('cumulative_count')
        if st is not None and cc is not None:
            counts[st] = cc
    return counts


def _get_current_multipliers():
    """Read current session multiplier values from learnable-params.json."""
    multipliers = {}
    if not os.path.isfile(LEARNABLE_PARAMS_PATH):
        return multipliers
    try:
        with open(LEARNABLE_PARAMS_PATH, 'r') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return multipliers

    for param in data.get('parameters', []):
        if param.get('group') != 'session_multipliers':
            continue
        pid = param.get('id', '')
        # Parse: session_{type}_{component}
        parts = pid.split('_')
        if len(parts) >= 3 and parts[0] == 'session':
            session_type = '_'.join(parts[1:-1])
            component = parts[-1]  # dq, cost, or behavioral
            if session_type not in multipliers:
                multipliers[session_type] = {}
            multipliers[session_type][component] = param.get('value', 0.0)
    return multipliers


def _get_previous_convergence_statuses():
    """Read last known status per session type from convergence-events.jsonl."""
    statuses = {}
    for entry in _read_jsonl(CONVERGENCE_EVENTS_PATH):
        st = entry.get('session_type')
        status = entry.get('status')
        if st and status:
            statuses[st] = status
    return statuses


def _log_convergence_event(session_type, status, final_multipliers, drift_pct, decisions):
    """Append a convergence event to convergence-events.jsonl."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_type": session_type,
        "status": status,
        "final_multipliers": final_multipliers,
        "drift_pct": drift_pct,
        "decisions_analyzed": decisions,
    }
    with open(CONVERGENCE_EVENTS_PATH, 'a') as f:
        f.write(json.dumps(event) + '\n')


# ---------------------------------------------------------------------------
# StabilityMonitor
# ---------------------------------------------------------------------------

class StabilityMonitor:
    """Tracks multiplier convergence per session type."""

    def __init__(self, history_path=None, stats_path=None,
                 convergence_path=None, threshold_pct=1.0, window=200):
        self.history_path = history_path or BANDIT_HISTORY_PATH
        self.stats_path = stats_path or STATS_PATH
        self.convergence_path = convergence_path or CONVERGENCE_EVENTS_PATH
        self.threshold_pct = threshold_pct
        self.window = window

    def _get_counts(self):
        """Session-type decision counts from stats file."""
        counts = {}
        for entry in _read_jsonl(self.stats_path):
            st = entry.get('session_type')
            cc = entry.get('cumulative_count')
            if st is not None and cc is not None:
                counts[st] = cc
        return counts

    def _get_history_for_type(self, session_type):
        """Return last `window` bandit-history entries for a session type."""
        all_entries = _read_jsonl(self.history_path)
        # Filter to entries that contain session multiplier info for this type
        typed = []
        for e in all_entries:
            st = e.get('session_type') or e.get('sessionType')
            if st == session_type:
                typed.append(e)
        return typed[-self.window:] if len(typed) > self.window else typed

    def _extract_multipliers_from_entry(self, entry, session_type):
        """Extract {dq, cost, behavioral} multiplier values from a history entry."""
        mults = {}
        # Try nested multipliers object
        m = entry.get('multipliers') or entry.get('session_multipliers') or {}
        if m:
            for k in MULTIPLIER_KEYS:
                if k in m:
                    mults[k] = m[k]
            if len(mults) == 3:
                return mults

        # Try flat keys: session_{type}_{component}
        for k in MULTIPLIER_KEYS:
            key = f"session_{session_type}_{k}"
            if key in entry:
                mults[k] = entry[key]

        # Try params/weights sub-object
        params = entry.get('params') or entry.get('weights') or {}
        for k in MULTIPLIER_KEYS:
            key = f"session_{session_type}_{k}"
            if key in params:
                mults[k] = params[key]

        return mults if len(mults) == 3 else None

    def check_convergence(self, session_type):
        """Check single session type.

        Returns:
            dict with keys: status, multipliers, drift_pct, decisions
        """
        counts = self._get_counts()
        decision_count = counts.get(session_type, 0)

        # Get current multiplier values from config as fallback
        current_mults = _get_current_multipliers().get(session_type, {})
        for k in MULTIPLIER_KEYS:
            current_mults.setdefault(k, 1.0)

        # Below volume gate → learning
        if decision_count < VOLUME_GATE_THRESHOLD:
            return {
                "status": "learning",
                "multipliers": current_mults,
                "drift_pct": {k: 0.0 for k in MULTIPLIER_KEYS},
                "decisions": decision_count,
            }

        # Enough decisions — check bandit history for drift
        entries = self._get_history_for_type(session_type)

        if len(entries) < 2:
            # Have volume gate data but no bandit history entries
            return {
                "status": "learning",
                "multipliers": current_mults,
                "drift_pct": {k: 0.0 for k in MULTIPLIER_KEYS},
                "decisions": decision_count,
            }

        # Extract multipliers at start and end of window
        start_mults = None
        end_mults = None

        # Walk from beginning to find first valid entry
        for e in entries:
            start_mults = self._extract_multipliers_from_entry(e, session_type)
            if start_mults:
                break

        # Walk from end to find last valid entry
        for e in reversed(entries):
            end_mults = self._extract_multipliers_from_entry(e, session_type)
            if end_mults:
                break

        if not start_mults or not end_mults:
            # History exists but no multiplier data extractable
            return {
                "status": "learning",
                "multipliers": current_mults,
                "drift_pct": {k: 0.0 for k in MULTIPLIER_KEYS},
                "decisions": decision_count,
            }

        # Compute drift percentage for each component
        drift = {}
        for k in MULTIPLIER_KEYS:
            sv = start_mults[k]
            ev = end_mults[k]
            if sv == 0:
                drift[k] = 0.0 if ev == 0 else 100.0
            else:
                drift[k] = round(abs(ev - sv) / abs(sv) * 100.0, 2)

        converged = all(d < self.threshold_pct for d in drift.values())
        status = "converged" if converged else "converging"

        return {
            "status": status,
            "multipliers": end_mults,
            "drift_pct": drift,
            "decisions": len(entries),
        }

    def analyze(self):
        """Analyze all 8 session types. Returns per-type status dict.

        Also logs convergence events when a session type transitions
        to 'converged' for the first time (or re-converges).
        """
        previous = _get_previous_convergence_statuses()
        results = {}

        for st in SESSION_TYPES:
            result = self.check_convergence(st)
            results[st] = result

            # Log convergence event on transition to 'converged'
            if result['status'] == 'converged' and previous.get(st) != 'converged':
                _log_convergence_event(
                    session_type=st,
                    status='converged',
                    final_multipliers=result['multipliers'],
                    drift_pct=result['drift_pct'],
                    decisions=result['decisions'],
                )

        return results


# ---------------------------------------------------------------------------
# API helper (for serve.py import)
# ---------------------------------------------------------------------------

def api_convergence():
    """Return convergence data as a JSON-serialisable dict for /api/convergence."""
    monitor = StabilityMonitor()
    results = monitor.analyze()
    summary = {
        "converged": sum(1 for r in results.values() if r['status'] == 'converged'),
        "converging": sum(1 for r in results.values() if r['status'] == 'converging'),
        "learning": sum(1 for r in results.values() if r['status'] == 'learning'),
        "total": len(SESSION_TYPES),
    }
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "session_types": results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_table(results):
    """Pretty-print convergence table."""
    print("Multiplier Stability Monitor — Convergence Status")
    print("=" * 72)
    print(f"  {'Session Type':<16s}  {'Status':<12s}  {'DQ':>6s}  {'Cost':>6s}  {'Behav':>6s}  {'Decisions':>9s}")
    print("-" * 72)

    status_order = {"converged": 0, "converging": 1, "learning": 2}
    sorted_types = sorted(results.keys(), key=lambda t: (status_order.get(results[t]['status'], 9), t))

    for st in sorted_types:
        r = results[st]
        status = r['status']
        mults = r['multipliers']
        drift = r['drift_pct']
        decisions = r['decisions']

        if status == "learning":
            drift_str = f"{'—':>6s}  {'—':>6s}  {'—':>6s}"
        else:
            drift_str = f"{drift.get('dq', 0):>5.1f}%  {drift.get('cost', 0):>5.1f}%  {drift.get('behavioral', 0):>5.1f}%"

        # Status indicator
        indicator = {"converged": "[OK]", "converging": "[~~]", "learning": "[..]"}
        tag = indicator.get(status, "[??]")

        print(f"  {st:<16s}  {tag} {status:<7s}  {drift_str}  {decisions:>9d}")

    # Summary
    converged = sum(1 for r in results.values() if r['status'] == 'converged')
    converging = sum(1 for r in results.values() if r['status'] == 'converging')
    learning = sum(1 for r in results.values() if r['status'] == 'learning')
    print("-" * 72)
    print(f"  Converged: {converged}  |  Converging: {converging}  |  Learning: {learning}  |  Total: {len(results)}")


if __name__ == '__main__':
    monitor = StabilityMonitor()
    results = monitor.analyze()
    _print_table(results)
