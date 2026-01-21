#!/usr/bin/env python3
"""
Migrate existing JSON data to unified SQLite database.
Run once to import historical data, then use datastore.py going forward.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add config to path
sys.path.insert(0, str(Path.home() / ".claude/config"))
from datastore import Datastore
from pricing import ESTIMATES

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
PROJECTS_DIR = CLAUDE_DIR / "projects"

def log(msg):
    print(f"[migrate] {msg}")

def parse_timestamp(ts):
    """Parse various timestamp formats."""
    if not ts:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except:
        return None

def main():
    log("Starting migration to SQLite...")
    db = Datastore()

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: Import sessions from transcripts
    # ═══════════════════════════════════════════════════════════════════════════
    log("Step 1: Scanning transcripts for session data...")

    daily_stats = defaultdict(lambda: {
        'opus_messages': 0, 'sonnet_messages': 0, 'haiku_messages': 0,
        'opus_tokens_in': 0, 'opus_tokens_out': 0, 'opus_cache_read': 0,
        'sonnet_tokens_in': 0, 'sonnet_tokens_out': 0, 'sonnet_cache_read': 0,
        'haiku_tokens_in': 0, 'haiku_tokens_out': 0, 'haiku_cache_read': 0,
        'session_count': 0, 'tool_calls': 0
    })

    hourly_activity = defaultdict(lambda: defaultdict(int))
    tool_counts = defaultdict(int)
    session_count = 0

    for transcript in PROJECTS_DIR.glob("**/*.jsonl"):
        try:
            session_id = transcript.stem
            project_path = str(transcript.parent)

            messages = []
            tools = 0
            model = 'sonnet'  # default
            input_tokens = 0
            output_tokens = 0
            cache_read = 0
            started_at = None
            ended_at = None

            with open(transcript) as f:
                for line in f:
                    try:
                        entry = json.loads(line)

                        # Track timestamps
                        ts = parse_timestamp(entry.get('timestamp'))
                        if ts:
                            if started_at is None or ts < started_at:
                                started_at = ts
                            if ended_at is None or ts > ended_at:
                                ended_at = ts

                        # Track model
                        if 'model' in entry:
                            m = entry['model'].lower()
                            if 'opus' in m:
                                model = 'opus'
                            elif 'haiku' in m:
                                model = 'haiku'
                            else:
                                model = 'sonnet'

                        # Track messages
                        if entry.get('type') in ['user', 'assistant']:
                            messages.append(entry)

                        # Track tools
                        if entry.get('type') == 'tool_use':
                            tools += 1
                            tool_name = entry.get('name', 'unknown')
                            tool_counts[tool_name] += 1

                        # Track tokens
                        if 'usage' in entry:
                            usage = entry['usage']
                            input_tokens += usage.get('input_tokens', 0)
                            output_tokens += usage.get('output_tokens', 0)
                            cache_read += usage.get('cache_read_input_tokens', 0)

                    except json.JSONDecodeError:
                        continue

            if not started_at:
                continue

            # Determine outcome based on message count
            msg_count = len(messages)
            if msg_count < 5:
                outcome = 'abandoned'
            elif msg_count < 20:
                outcome = 'quick'
            else:
                outcome = 'completed'

            # Calculate cost estimate
            cost = msg_count * ESTIMATES.get(model, 0.017)

            # Log session
            db.log_session(
                session_id=session_id,
                project_path=project_path,
                model=model,
                started_at=started_at,
                ended_at=ended_at,
                message_count=msg_count,
                tool_count=tools,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                outcome=outcome,
                cost_estimate=cost
            )

            # Aggregate daily stats
            date_str = started_at.strftime('%Y-%m-%d')
            hour = started_at.hour

            daily_stats[date_str][f'{model}_messages'] += msg_count
            daily_stats[date_str][f'{model}_tokens_in'] += input_tokens
            daily_stats[date_str][f'{model}_tokens_out'] += output_tokens
            daily_stats[date_str][f'{model}_cache_read'] += cache_read
            daily_stats[date_str]['session_count'] += 1
            daily_stats[date_str]['tool_calls'] += tools

            hourly_activity[date_str][hour] += 1

            session_count += 1

        except Exception as e:
            continue

    log(f"  Imported {session_count} sessions")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2: Save daily stats
    # ═══════════════════════════════════════════════════════════════════════════
    log("Step 2: Saving daily statistics...")

    for date_str, stats in daily_stats.items():
        # Calculate cost estimate for the day
        cost = (
            stats['opus_messages'] * ESTIMATES.get('opus', 0.027) +
            stats['sonnet_messages'] * ESTIMATES.get('sonnet', 0.017) +
            stats['haiku_messages'] * ESTIMATES.get('haiku', 0.004)
        )

        db.update_daily_stats(
            date=date_str,
            opus_messages=stats['opus_messages'],
            sonnet_messages=stats['sonnet_messages'],
            haiku_messages=stats['haiku_messages'],
            opus_tokens_in=stats['opus_tokens_in'],
            opus_tokens_out=stats['opus_tokens_out'],
            opus_cache_read=stats['opus_cache_read'],
            sonnet_tokens_in=stats['sonnet_tokens_in'],
            sonnet_tokens_out=stats['sonnet_tokens_out'],
            sonnet_cache_read=stats['sonnet_cache_read'],
            haiku_tokens_in=stats['haiku_tokens_in'],
            haiku_tokens_out=stats['haiku_tokens_out'],
            haiku_cache_read=stats['haiku_cache_read'],
            session_count=stats['session_count'],
            tool_calls=stats['tool_calls'],
            cost_estimate=cost
        )

    log(f"  Saved {len(daily_stats)} days of statistics")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 3: Save hourly activity
    # ═══════════════════════════════════════════════════════════════════════════
    log("Step 3: Saving hourly activity...")

    hourly_count = 0
    for date_str, hours in hourly_activity.items():
        for hour, count in hours.items():
            db.update_hourly_activity(date_str, hour, sessions=count)
            hourly_count += 1

    log(f"  Saved {hourly_count} hourly records")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 4: Save tool usage
    # ═══════════════════════════════════════════════════════════════════════════
    log("Step 4: Saving tool usage...")

    for tool_name, count in tool_counts.items():
        db.update_tool_usage(tool_name, calls=count)

    log(f"  Saved {len(tool_counts)} tool statistics")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 5: Import routing decisions
    # ═══════════════════════════════════════════════════════════════════════════
    log("Step 5: Importing routing decisions...")

    dq_file = CLAUDE_DIR / "kernel" / "dq-scores.jsonl"
    routing_count = 0

    if dq_file.exists():
        with open(dq_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    db.log_routing_decision(
                        query_hash=entry.get('query_hash', ''),
                        query_preview=entry.get('query_preview', entry.get('query', '')[:50]),
                        complexity=entry.get('complexity', 0.5),
                        selected_model=entry.get('model', 'sonnet'),
                        dq_score=entry.get('dqScore', 0.5),
                        dq_validity=entry.get('dqComponents', {}).get('validity'),
                        dq_specificity=entry.get('dqComponents', {}).get('specificity'),
                        dq_correctness=entry.get('dqComponents', {}).get('correctness'),
                        cost_estimate=entry.get('cost_estimate')
                    )
                    routing_count += 1
                except:
                    continue

    log(f"  Imported {routing_count} routing decisions")

    # ═══════════════════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════════════════
    log("")
    log("=" * 60)
    log("MIGRATION COMPLETE")
    log("=" * 60)

    totals = db.get_totals()
    log(f"Sessions:     {totals.get('total_sessions', 0):,}")
    log(f"Messages:     {totals.get('total_messages', 0):,}")
    log(f"Tools:        {totals.get('total_tools', 0):,}")
    log(f"Cost (est):   ${totals.get('total_cost', 0):,.2f}")
    log("")
    log(f"Database: {db.db_path}")


if __name__ == "__main__":
    main()
