#!/usr/bin/env python3
"""
Activity Sync - Real-time session transcript watcher
Feeds activity-events.jsonl from Claude session transcripts
"""

import json
import os
import glob
import time
from datetime import datetime
from pathlib import Path
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

DATA_DIR = Path.home() / ".claude" / "data"
PROJECTS_DIR = Path.home() / ".claude" / "projects"
ACTIVITY_FILE = DATA_DIR / "activity-events.jsonl"
PROCESSED_FILE = DATA_DIR / ".activity-sync-processed"

# Track what we've already processed
def load_processed():
    if PROCESSED_FILE.exists():
        return set(PROCESSED_FILE.read_text().strip().split('\n'))
    return set()

def save_processed(processed):
    PROCESSED_FILE.write_text('\n'.join(processed))

def extract_queries_from_transcript(transcript_path):
    """Extract user queries from a Claude session transcript."""
    queries = []
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    # User messages have type: "user"
                    if entry.get('type') == 'user':
                        msg = entry.get('message', {})
                        content = msg.get('content', '')
                        if isinstance(content, str) and len(content) > 5:
                            # Extract timestamp (use seconds, not milliseconds)
                            ts = entry.get('timestamp', '')
                            if isinstance(ts, str):
                                try:
                                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                                    ts_sec = int(dt.timestamp())
                                except:
                                    ts_sec = int(time.time())
                            else:
                                ts_sec = int(time.time())

                            queries.append({
                                'timestamp': ts_sec,
                                'datetime': datetime.fromtimestamp(ts_sec).isoformat() + 'Z',
                                'type': 'query',
                                'query': content[:500],  # Truncate long queries
                                'source': 'transcript'
                            })
                except:
                    continue
    except:
        pass
    return queries

def sync_all_transcripts():
    """Sync all transcripts to activity events."""
    processed = load_processed()
    transcripts = list(PROJECTS_DIR.glob('**/*.jsonl'))

    new_events = []
    for transcript in transcripts:
        transcript_key = f"{transcript.name}:{transcript.stat().st_mtime}"
        if transcript_key in processed:
            continue

        queries = extract_queries_from_transcript(transcript)
        new_events.extend(queries)
        processed.add(transcript_key)

    if new_events:
        # Sort by timestamp
        new_events.sort(key=lambda x: x['timestamp'])

        # Append to activity file
        with open(ACTIVITY_FILE, 'a') as f:
            for event in new_events:
                f.write(json.dumps(event) + '\n')

        print(f"Synced {len(new_events)} new activity events")

    save_processed(processed)
    return len(new_events)

if WATCHDOG_AVAILABLE:
    class TranscriptHandler(FileSystemEventHandler):
        """Watch for transcript changes and sync."""
        def on_modified(self, event):
            if event.src_path.endswith('.jsonl'):
                # Debounce with simple delay
                time.sleep(0.5)
                sync_all_transcripts()

def run_watcher():
    """Run continuous file watcher."""
    if not WATCHDOG_AVAILABLE:
        print("watchdog not installed. Install with: pip install watchdog")
        print("Running one-shot sync instead...")
        sync_all_transcripts()
        return

    print("Starting activity sync watcher...")
    sync_all_transcripts()  # Initial sync

    observer = Observer()
    observer.schedule(TranscriptHandler(), str(PROJECTS_DIR), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'watch':
        run_watcher()
    else:
        # One-shot sync
        count = sync_all_transcripts()
        print(f"Activity sync complete. {count} new events.")
