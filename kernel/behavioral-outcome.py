#!/usr/bin/env python3
"""
US-005: Behavioral Outcome Signal — Composite Score Extractor

Computes composite behavioral outcome scores per session from non-circular
telemetry signals. Replaces unreliable ACE self-assessment with ground truth
derived from actual user behavior.

Composite score components (weights from PRD):
  - Session completion (not abandoned): 0.30
  - Tool success rate: 0.25
  - Efficiency ratio (messages / DQ complexity): 0.20
  - No model override by user: 0.15
  - No follow-up session on same topic within 24h: 0.10

Reads from: claude.db (sessions, tool_events, activity_events, command_events)
Outputs to: data/behavioral-outcomes.jsonl (append-only)
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Default paths
CLAUDE_DB_PATH = os.path.expanduser("~/.claude/data/claude.db")
OUTPUT_DIR = Path(__file__).parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "behavioral-outcomes.jsonl"

# Component weights (from PRD — designed as future Optimas LRF)
WEIGHTS = {
    "completion": 0.30,
    "tool_success": 0.25,
    "efficiency": 0.20,
    "no_override": 0.15,
    "no_followup": 0.10,
}


def get_db_connection(db_path=None):
    """Open read-only connection to claude.db."""
    path = db_path or CLAUDE_DB_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"claude.db not found at {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def compute_completion_score(session):
    """Score 1: Session completion (not abandoned). Weight: 0.30.

    Mapping:
      success/completed → 1.0
      partial/quick → 0.5
      abandoned → 0.0
    """
    outcome = (session["outcome"] or "").lower()
    if outcome in ("success", "completed"):
        return 1.0
    elif outcome in ("partial", "quick"):
        return 0.5
    else:  # abandoned or unknown
        return 0.0


def compute_tool_success_rate(conn, session):
    """Score 2: Tool success rate from tool_events. Weight: 0.25.

    Since tool_events has no session_id, we correlate by timestamp range
    matching the session's started_at/ended_at window.
    Returns success_count / total_count, or 0.5 if no tool events found.
    """
    started = session["started_at"]
    ended = session["ended_at"]
    if not started or not ended:
        return 0.5  # No time range, neutral score

    # Convert ISO timestamps to unix timestamps for tool_events comparison
    try:
        start_ts = int(datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp())
        end_ts = int(datetime.fromisoformat(ended.replace("Z", "+00:00")).timestamp())
    except (ValueError, AttributeError):
        return 0.5

    cursor = conn.execute(
        "SELECT success, COUNT(*) as cnt FROM tool_events "
        "WHERE timestamp >= ? AND timestamp <= ? "
        "GROUP BY success",
        (start_ts, end_ts),
    )
    rows = cursor.fetchall()
    if not rows:
        return 0.5  # No tool events in window, neutral

    total = sum(r["cnt"] for r in rows)
    success = sum(r["cnt"] for r in rows if r["success"] == 1)
    return success / total if total > 0 else 0.5


def compute_efficiency_ratio(session):
    """Score 3: Efficiency ratio (messages relative to complexity). Weight: 0.20.

    Lower message count per unit complexity = more efficient.
    Score = 1.0 - clamp(messages / (complexity * expected_messages), 0, 1)

    Expected messages per complexity unit (heuristic):
      complexity 0.0 → ~10 messages expected
      complexity 1.0 → ~200 messages expected
    """
    messages = session["message_count"] or 0
    complexity = session["complexity"]

    if complexity is None or complexity <= 0:
        # No complexity data — use message count heuristic
        # Under 50 messages = efficient, over 200 = inefficient
        if messages <= 0:
            return 0.5
        ratio = min(messages / 100.0, 1.0)
        return 1.0 - ratio

    # Scale expected messages by complexity
    expected = 10 + (complexity * 190)  # 10 at c=0, 200 at c=1
    ratio = messages / expected
    # ratio < 1 means more efficient than expected
    return max(0.0, min(1.0, 1.0 - (ratio - 1.0) * 0.5))


def compute_no_override_score(conn, session):
    """Score 4: No model override by user. Weight: 0.15.

    Check command_events for model switch commands during the session window.
    If user manually switched models, score = 0.0 (they weren't happy with routing).
    If no override, score = 1.0.
    """
    started = session["started_at"]
    ended = session["ended_at"]
    if not started or not ended:
        return 1.0  # Can't check, assume no override

    try:
        start_ts = int(datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp())
        end_ts = int(datetime.fromisoformat(ended.replace("Z", "+00:00")).timestamp())
    except (ValueError, AttributeError):
        return 1.0

    # Look for model-switching commands
    cursor = conn.execute(
        "SELECT COUNT(*) as cnt FROM command_events "
        "WHERE timestamp >= ? AND timestamp <= ? "
        "AND (command LIKE '%model%' OR command LIKE '%switch%' "
        "OR command LIKE '%opus%' OR command LIKE '%sonnet%' OR command LIKE '%haiku%')",
        (start_ts, end_ts),
    )
    row = cursor.fetchone()
    return 0.0 if (row and row["cnt"] > 0) else 1.0


def compute_no_followup_score(conn, session):
    """Score 5: No follow-up session on same topic within 24h. Weight: 0.10.

    If no session with the same project_path starts within 24 hours after
    this session ends, score = 1.0 (task was resolved).
    If there is a follow-up, score = 0.0 (user had to come back).
    """
    ended = session["ended_at"]
    project = session["project_path"]

    if not ended or not project:
        return 0.5  # Can't determine, neutral

    try:
        end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        window_end = end_dt + timedelta(hours=24)
    except (ValueError, AttributeError):
        return 0.5

    cursor = conn.execute(
        "SELECT COUNT(*) as cnt FROM sessions "
        "WHERE project_path = ? AND started_at > ? AND started_at < ? "
        "AND id != ?",
        (project, ended, window_end.isoformat(), session["id"]),
    )
    row = cursor.fetchone()
    return 0.0 if (row and row["cnt"] > 0) else 1.0


def compute_behavioral_score(conn, session):
    """Compute composite behavioral outcome score for a single session.

    Returns dict with component scores and weighted composite.
    """
    components = {
        "completion": compute_completion_score(session),
        "tool_success": compute_tool_success_rate(conn, session),
        "efficiency": compute_efficiency_ratio(session),
        "no_override": compute_no_override_score(conn, session),
        "no_followup": compute_no_followup_score(conn, session),
    }

    # Weighted composite
    composite = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    composite = max(0.0, min(1.0, composite))

    return {
        "session_id": session["id"],
        "started_at": session["started_at"],
        "project_path": session["project_path"],
        "model": session["model"],
        "outcome": session["outcome"],
        "message_count": session["message_count"],
        "components": components,
        "weights": WEIGHTS,
        "behavioral_score": round(composite, 4),
        "ace_quality_score": session["quality_score"],  # Preserved as weak signal
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def load_processed_ids(output_path):
    """Load set of already-processed session IDs from output JSONL."""
    processed = set()
    if not output_path.exists():
        return processed
    with open(output_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                processed.add(record.get("session_id"))
            except json.JSONDecodeError:
                continue
    return processed


def process_sessions(db_path=None, output_path=None, backfill=False, limit=None):
    """Process sessions and output behavioral scores.

    Args:
        db_path: Path to claude.db (default: ~/.claude/data/claude.db)
        output_path: Path to output JSONL (default: data/behavioral-outcomes.jsonl)
        backfill: If True, process all historical sessions
        limit: Max sessions to process (None = all)

    Returns:
        dict with processing stats
    """
    out = output_path or OUTPUT_FILE
    out.parent.mkdir(parents=True, exist_ok=True)

    conn = get_db_connection(db_path)
    processed_ids = load_processed_ids(out)

    # Query sessions
    query = "SELECT * FROM sessions ORDER BY started_at ASC"
    if limit:
        query += f" LIMIT {int(limit)}"

    cursor = conn.execute(query)
    sessions = cursor.fetchall()

    stats = {"total": len(sessions), "processed": 0, "skipped": 0, "errors": 0}

    with open(out, "a") as f:
        for session in sessions:
            sid = session["id"]
            if sid in processed_ids:
                stats["skipped"] += 1
                continue

            try:
                result = compute_behavioral_score(conn, session)
                f.write(json.dumps(result) + "\n")
                stats["processed"] += 1
            except Exception as e:
                stats["errors"] += 1
                if not backfill:  # In backfill mode, silently skip errors
                    print(f"Error processing {sid}: {e}", file=sys.stderr)

    conn.close()
    return stats


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute behavioral outcome scores from session telemetry"
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Process all historical sessions",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=f"Path to claude.db (default: {CLAUDE_DB_PATH})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=f"Output JSONL path (default: {OUTPUT_FILE})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max sessions to process",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show stats from existing output file",
    )

    args = parser.parse_args()

    if args.stats:
        out = Path(args.output) if args.output else OUTPUT_FILE
        if not out.exists():
            print("No behavioral outcomes file found.")
            return
        count = 0
        total_score = 0.0
        with open(out) as f:
            for line in f:
                if line.strip():
                    try:
                        r = json.loads(line)
                        count += 1
                        total_score += r.get("behavioral_score", 0)
                    except json.JSONDecodeError:
                        pass
        avg = total_score / count if count > 0 else 0
        print(f"Sessions scored: {count}")
        print(f"Average behavioral score: {avg:.4f}")
        return

    output_path = Path(args.output) if args.output else None
    stats = process_sessions(
        db_path=args.db,
        output_path=output_path,
        backfill=args.backfill,
        limit=args.limit,
    )

    print(f"Behavioral Outcome Scoring Complete")
    print(f"  Total sessions: {stats['total']}")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped (already done): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()
