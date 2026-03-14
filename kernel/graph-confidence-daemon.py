#!/usr/bin/env python3
"""
US-010: Graph Confidence Loop — Write Direction

Background daemon that updates knowledge graph triple confidence scores
based on routing outcomes. Successful interactions boost confidence,
failures degrade it, flagging sparse subgraphs for attention.

Runs as a background daemon (NOT in hook chain — Security Architect requirement),
processing behavioral outcomes every 60 seconds.

Reads from:
  - data/behavioral-outcomes.jsonl (US-005 output)
  - ~/.claude/memory/supermemory.db (memory_links table)

Writes to:
  - supermemory.db memory_links.confidence column
  - data/graph-snapshots/YYYY-MM-DD-HHMMSS.json (pre-update snapshots)
  - data/sparse-subgraph-flags.jsonl (sparse subgraph alerts)
"""

import json
import os
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Paths
VENGINE_DIR = Path(__file__).parent.parent
DATA_DIR = VENGINE_DIR / "data"
BEHAVIORAL_OUTCOMES_FILE = DATA_DIR / "behavioral-outcomes.jsonl"
SNAPSHOTS_DIR = DATA_DIR / "graph-snapshots"
SPARSE_FLAGS_FILE = DATA_DIR / "sparse-subgraph-flags.jsonl"
SUPERMEMORY_DB = Path(os.path.expanduser("~/.claude/memory/supermemory.db"))
DAEMON_STATE_FILE = DATA_DIR / "graph-confidence-state.json"

# Confidence update rules (from PRD)
BOOST_THRESHOLD = 0.7       # DQ outcome >= 0.7 → boost
DEGRADE_THRESHOLD = 0.4     # DQ outcome < 0.4 → degrade
BOOST_DELTA = 0.05          # Confidence boost per successful outcome
DEGRADE_DELTA = -0.10       # Confidence degradation per failed outcome
CONFIDENCE_CAP = 1.0
CONFIDENCE_FLOOR = 0.0
DEFAULT_CONFIDENCE = 0.5

# Batch limits (Security Architect requirements)
MAX_LINKS_PER_CYCLE = 100
MAX_HOP_DEPTH = 2

# Sparse subgraph threshold
SPARSE_DENSITY_THRESHOLD = 0.1

# Daemon timing
POLL_INTERVAL_SECONDS = 60


def ensure_confidence_column(db_path=None):
    """Add confidence column to memory_links if not present.

    Migration: ALTER TABLE memory_links ADD COLUMN confidence REAL DEFAULT 0.5
    """
    path = db_path or SUPERMEMORY_DB
    conn = sqlite3.connect(str(path))
    cursor = conn.execute("PRAGMA table_info(memory_links)")
    columns = [row[1] for row in cursor.fetchall()]

    if "confidence" not in columns:
        conn.execute(
            "ALTER TABLE memory_links ADD COLUMN confidence REAL DEFAULT 0.5"
        )
        conn.commit()

    # Ensure from_id index exists for efficient subgraph queries
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_links_from_id "
        "ON memory_links(from_id)"
    )
    conn.commit()
    conn.close()


def load_daemon_state():
    """Load daemon state (last processed outcome line number)."""
    if DAEMON_STATE_FILE.exists():
        try:
            with open(DAEMON_STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"last_processed_line": 0, "total_boosts": 0, "total_degrades": 0}


def save_daemon_state(state):
    """Persist daemon state."""
    DAEMON_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DAEMON_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_new_outcomes(state):
    """Load behavioral outcomes not yet processed.

    Returns list of outcome dicts and updated line count.
    """
    if not BEHAVIORAL_OUTCOMES_FILE.exists():
        return [], state["last_processed_line"]

    outcomes = []
    current_line = 0
    with open(BEHAVIORAL_OUTCOMES_FILE) as f:
        for line in f:
            current_line += 1
            if current_line <= state["last_processed_line"]:
                continue
            line = line.strip()
            if not line:
                continue
            try:
                outcomes.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return outcomes, current_line


def get_retrieved_node_ids(outcome):
    """Extract retrieved node IDs from an outcome record.

    The behavioral outcome has a session_id. We look for memory items
    that were accessed around the session time. For now, use project-based
    matching as a proxy for retrieved nodes.
    """
    # Use session_id and project_path to find relevant memory items
    session_id = outcome.get("session_id", "")
    project = outcome.get("project_path", "")

    # Return identifiers that can be matched against memory_links
    # The session_id itself and project path serve as node identifiers
    node_ids = set()
    if session_id:
        node_ids.add(session_id)
    if project:
        # Use project name as a topic key
        node_ids.add(project)
    return node_ids


def find_links_for_nodes(conn, node_ids, max_depth=MAX_HOP_DEPTH, max_links=MAX_LINKS_PER_CYCLE):
    """Find memory_links connected to given node IDs, depth-limited.

    Returns list of link dicts with id, from_id, to_id, confidence.
    Depth-limited to max_depth hops from seed nodes.
    """
    if not node_ids:
        return []

    visited_links = []
    current_nodes = set(node_ids)
    seen_nodes = set(node_ids)

    for depth in range(max_depth):
        if not current_nodes or len(visited_links) >= max_links:
            break

        placeholders = ",".join("?" for _ in current_nodes)
        query = (
            f"SELECT id, from_id, to_id, strength, "
            f"COALESCE(confidence, {DEFAULT_CONFIDENCE}) as confidence "
            f"FROM memory_links "
            f"WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders}) "
            f"LIMIT ?"
        )
        params = list(current_nodes) + list(current_nodes) + [max_links - len(visited_links)]

        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # confidence column might not exist yet
            break

        next_nodes = set()
        seen_link_ids = {link["id"] for link in visited_links}

        for row in rows:
            link_id = row[0]
            if link_id in seen_link_ids:
                continue
            link = {
                "id": link_id,
                "from_id": row[1],
                "to_id": row[2],
                "strength": row[3],
                "confidence": row[4],
            }
            visited_links.append(link)
            seen_link_ids.add(link_id)

            # Expand frontier
            if row[1] not in seen_nodes:
                next_nodes.add(row[1])
            if row[2] not in seen_nodes:
                next_nodes.add(row[2])

            if len(visited_links) >= max_links:
                break

        current_nodes = next_nodes
        seen_nodes |= next_nodes

    return visited_links


def compute_subgraph_density(links):
    """Compute density of the retrieved subgraph.

    density = actual_edges / possible_edges
    For n nodes: possible_edges = n * (n - 1) / 2
    """
    if not links:
        return 0.0

    nodes = set()
    for link in links:
        nodes.add(link["from_id"])
        nodes.add(link["to_id"])

    n = len(nodes)
    if n < 2:
        return 0.0

    possible_edges = n * (n - 1) / 2
    actual_edges = len(links)
    return min(1.0, actual_edges / possible_edges)


def take_snapshot(links, outcome_session_id):
    """Save pre-update snapshot of affected links.

    Stored as data/graph-snapshots/YYYY-MM-DD-HHMMSS.json
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    filename = now.strftime("%Y-%m-%d-%H%M%S") + ".json"
    snapshot = {
        "timestamp": now.isoformat(),
        "outcome_session_id": outcome_session_id,
        "link_count": len(links),
        "links": [
            {
                "id": link["id"],
                "from_id": link["from_id"],
                "to_id": link["to_id"],
                "pre_confidence": link["confidence"],
            }
            for link in links
        ],
    }
    snapshot_path = SNAPSHOTS_DIR / filename
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    return snapshot_path


def update_confidence(conn, links, delta):
    """Update confidence for a batch of links.

    Args:
        conn: SQLite connection (read-write)
        links: list of link dicts
        delta: confidence change (+0.05 or -0.10)

    Returns:
        list of (link_id, old_confidence, new_confidence) tuples
    """
    updates = []
    for link in links:
        old_conf = link["confidence"]
        new_conf = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CAP, old_conf + delta))
        if new_conf != old_conf:
            conn.execute(
                "UPDATE memory_links SET confidence = ? WHERE id = ?",
                (round(new_conf, 4), link["id"]),
            )
            updates.append((link["id"], old_conf, new_conf))
    conn.commit()
    return updates


def flag_sparse_subgraph(outcome, density):
    """Log sparse subgraph flag when density < threshold and outcome is poor.

    Appends to data/sparse-subgraph-flags.jsonl
    """
    SPARSE_FLAGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    flag = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": outcome.get("session_id"),
        "project_path": outcome.get("project_path"),
        "behavioral_score": outcome.get("behavioral_score"),
        "subgraph_density": round(density, 4),
        "reason": "sparse_subgraph_with_poor_outcome",
    }
    with open(SPARSE_FLAGS_FILE, "a") as f:
        f.write(json.dumps(flag) + "\n")


def process_single_outcome(conn, outcome):
    """Process a single behavioral outcome and update graph confidence.

    Returns dict with processing stats.
    """
    score = outcome.get("behavioral_score", 0.5)
    session_id = outcome.get("session_id", "unknown")

    # Determine action based on score thresholds
    if score >= BOOST_THRESHOLD:
        action = "boost"
        delta = BOOST_DELTA
    elif score < DEGRADE_THRESHOLD:
        action = "degrade"
        delta = DEGRADE_DELTA
    else:
        return {"action": "no_change", "session_id": session_id, "score": score, "links_updated": 0}

    # Find retrieved nodes for this session
    node_ids = get_retrieved_node_ids(outcome)
    if not node_ids:
        return {"action": "no_nodes", "session_id": session_id, "score": score, "links_updated": 0}

    # Find connected links (depth-limited, batch-limited)
    links = find_links_for_nodes(conn, node_ids)
    if not links:
        return {"action": "no_links", "session_id": session_id, "score": score, "links_updated": 0}

    # Compute subgraph density
    density = compute_subgraph_density(links)

    # Flag sparse subgraphs with poor outcomes
    if density < SPARSE_DENSITY_THRESHOLD and score < DEGRADE_THRESHOLD:
        flag_sparse_subgraph(outcome, density)

    # Take snapshot before updates
    take_snapshot(links, session_id)

    # Apply confidence updates
    updates = update_confidence(conn, links, delta)

    return {
        "action": action,
        "session_id": session_id,
        "score": score,
        "links_found": len(links),
        "links_updated": len(updates),
        "subgraph_density": round(density, 4),
    }


def run_cycle(db_path=None):
    """Run a single processing cycle.

    Returns dict with cycle stats.
    """
    state = load_daemon_state()
    outcomes, new_line_count = load_new_outcomes(state)

    if not outcomes:
        return {"cycle": "no_new_outcomes", "checked_up_to_line": new_line_count}

    path = db_path or SUPERMEMORY_DB
    if not path.exists():
        return {"cycle": "error", "reason": f"supermemory.db not found at {path}"}

    # Open read-write connection for updates
    conn = sqlite3.connect(str(path))

    results = []
    boosts = 0
    degrades = 0

    for outcome in outcomes:
        result = process_single_outcome(conn, outcome)
        results.append(result)
        if result["action"] == "boost":
            boosts += 1
        elif result["action"] == "degrade":
            degrades += 1

    conn.close()

    # Update state
    state["last_processed_line"] = new_line_count
    state["total_boosts"] = state.get("total_boosts", 0) + boosts
    state["total_degrades"] = state.get("total_degrades", 0) + degrades
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    save_daemon_state(state)

    return {
        "cycle": "processed",
        "outcomes_processed": len(outcomes),
        "boosts": boosts,
        "degrades": degrades,
        "no_change": len(outcomes) - boosts - degrades,
        "results": results,
    }


def daemon_loop(db_path=None, interval=POLL_INTERVAL_SECONDS):
    """Main daemon loop — runs indefinitely, processing every interval seconds."""
    running = True

    def handle_signal(signum, frame):
        nonlocal running
        running = False
        print(f"[graph-confidence] Received signal {signum}, shutting down...")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    print(f"[graph-confidence] Daemon started, polling every {interval}s")

    # Ensure schema is ready
    ensure_confidence_column(db_path)

    while running:
        try:
            result = run_cycle(db_path)
            if result.get("cycle") == "processed":
                print(
                    f"[graph-confidence] Cycle: {result['outcomes_processed']} outcomes, "
                    f"{result['boosts']} boosts, {result['degrades']} degrades"
                )
        except Exception as e:
            print(f"[graph-confidence] Cycle error: {e}", file=sys.stderr)

        # Sleep in small increments for responsive shutdown
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    print("[graph-confidence] Daemon stopped")


def status():
    """Print daemon status."""
    state = load_daemon_state()
    print("Graph Confidence Daemon Status")
    print("=" * 40)
    print(f"  Last processed line: {state.get('last_processed_line', 0)}")
    print(f"  Total boosts: {state.get('total_boosts', 0)}")
    print(f"  Total degrades: {state.get('total_degrades', 0)}")
    print(f"  Last run: {state.get('last_run', 'never')}")

    # Check confidence column exists
    if SUPERMEMORY_DB.exists():
        conn = sqlite3.connect(str(SUPERMEMORY_DB))
        cursor = conn.execute("PRAGMA table_info(memory_links)")
        columns = [row[1] for row in cursor.fetchall()]
        has_confidence = "confidence" in columns
        print(f"  Confidence column: {'present' if has_confidence else 'missing'}")

        if has_confidence:
            cursor = conn.execute(
                "SELECT AVG(COALESCE(confidence, 0.5)), COUNT(*) FROM memory_links"
            )
            row = cursor.fetchone()
            print(f"  Avg confidence: {row[0]:.4f} ({row[1]} links)")
        conn.close()
    else:
        print(f"  supermemory.db: not found at {SUPERMEMORY_DB}")

    # Check snapshots
    if SNAPSHOTS_DIR.exists():
        snapshots = list(SNAPSHOTS_DIR.glob("*.json"))
        print(f"  Snapshots: {len(snapshots)}")
    else:
        print("  Snapshots: 0")

    # Check sparse flags
    if SPARSE_FLAGS_FILE.exists():
        count = sum(1 for line in open(SPARSE_FLAGS_FILE) if line.strip())
        print(f"  Sparse subgraph flags: {count}")
    else:
        print("  Sparse subgraph flags: 0")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Graph Confidence Loop — updates knowledge graph confidence from routing outcomes"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # start command
    start_parser = subparsers.add_parser("start", help="Start daemon loop")
    start_parser.add_argument("--db", default=None, help="Path to supermemory.db")
    start_parser.add_argument(
        "--interval", type=int, default=POLL_INTERVAL_SECONDS,
        help=f"Poll interval in seconds (default: {POLL_INTERVAL_SECONDS})"
    )

    # run-once command
    run_parser = subparsers.add_parser("run-once", help="Run a single cycle")
    run_parser.add_argument("--db", default=None, help="Path to supermemory.db")

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Add confidence column to supermemory.db")
    migrate_parser.add_argument("--db", default=None, help="Path to supermemory.db")

    # status command
    subparsers.add_parser("status", help="Show daemon status")

    args = parser.parse_args()

    if args.command == "start":
        db = Path(args.db) if args.db else None
        daemon_loop(db_path=db, interval=args.interval)
    elif args.command == "run-once":
        db = Path(args.db) if args.db else None
        ensure_confidence_column(db)
        result = run_cycle(db)
        print(json.dumps(result, indent=2))
    elif args.command == "migrate":
        db = Path(args.db) if args.db else None
        ensure_confidence_column(db)
        print("Migration complete — confidence column added to memory_links")
    elif args.command == "status":
        status()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
