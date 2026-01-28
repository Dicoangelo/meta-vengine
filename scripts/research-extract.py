#!/usr/bin/env python3
"""Extract learnings from latest Claude session."""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

def main():
    agent_core = Path.home() / ".agent-core"
    claude_projects = Path.home() / ".claude" / "projects"

    # Find the most recent transcript (modified in last 60 min)
    transcripts = sorted(
        claude_projects.glob("**/*.jsonl"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if not transcripts:
        print("No sessions found")
        return

    latest = transcripts[0]
    print(f"Processing: {latest.name[:40]}...")

    learnings_file = agent_core / "memory" / "learnings.md"
    auto_capture_log = agent_core / "auto_capture_log.json"

    # Ensure directories exist
    learnings_file.parent.mkdir(parents=True, exist_ok=True)

    # Extract URLs, findings, and key insights
    urls = set()
    findings = []
    tools_used = []

    with open(latest) as f:
        for line in f:
            try:
                entry = json.loads(line)

                # Extract URLs from messages
                if entry.get('type') in ['user', 'assistant']:
                    msg = entry.get('message', {})
                    content = msg.get('content', '')
                    if isinstance(content, str):
                        # Find URLs
                        found_urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
                        urls.update(found_urls)

                        # Find key findings (lines starting with - or *)
                        for line_text in content.split('\n'):
                            stripped = line_text.strip()
                            if stripped.startswith(('-', '*', '•')) and len(stripped) > 20:
                                findings.append(stripped[:200])

                # Track tools
                if entry.get('type') == 'assistant':
                    msg = entry.get('message', {})
                    content = msg.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'tool_use':
                                tools_used.append(item.get('name'))

            except (json.JSONDecodeError, KeyError):
                continue

    # Append to learnings if we found anything significant
    if urls or findings:
        session_id = latest.stem[:8]
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')

        with open(learnings_file, 'a') as f:
            f.write(f"\n## {timestamp} - Session {session_id}\n")
            if urls:
                f.write("### URLs Referenced\n")
                for url in list(urls)[:10]:  # Max 10 URLs
                    f.write(f"- {url}\n")
            if findings:
                f.write("### Key Findings\n")
                for finding in findings[:5]:  # Max 5 findings
                    f.write(f"{finding}\n")
            f.write("\n")

        print(f"Captured: {len(urls)} URLs, {len(findings)} findings, {len(set(tools_used))} unique tools")

        # Update auto capture log
        log_data = []
        if auto_capture_log.exists():
            try:
                loaded = json.loads(auto_capture_log.read_text())
                # Ensure it's a list, not a dict
                log_data = loaded if isinstance(loaded, list) else []
            except:
                pass

        log_data.append({
            "timestamp": datetime.now().isoformat(),
            "session": session_id,
            "urls": len(urls),
            "findings": len(findings),
            "tools": len(set(tools_used))
        })

        # Keep last 100 entries
        auto_capture_log.write_text(json.dumps(log_data[-100:], indent=2))
    else:
        print("No significant learnings to capture")

if __name__ == '__main__':
    main()
