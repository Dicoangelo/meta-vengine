#!/usr/bin/env python3
"""
BULK BACKFILL - Comprehensive data extraction from all historical sources
Populates all kernel systems, data pipelines, and analytics in one pass.
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
import subprocess

# Paths
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"
PROJECTS_DIR = CLAUDE_DIR / "projects"
AGENT_CORE = HOME / ".agent-core"

# Ensure directories exist
KERNEL_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("BULK BACKFILL - Comprehensive Historical Data Extraction")
print("=" * 70)
print()

# ═══════════════════════════════════════════════════════════════════════════
# 1. EXTRACT ALL DATA FROM TRANSCRIPTS
# ═══════════════════════════════════════════════════════════════════════════

print("1. EXTRACTING FROM TRANSCRIPTS...")

transcripts = list(PROJECTS_DIR.glob("**/*.jsonl"))
print(f"   Found {len(transcripts)} transcript files")

# Data collectors
tool_usage = []
session_events = []
user_queries = []
urls_found = []
model_usage = Counter()
daily_activity = defaultdict(lambda: {"messages": 0, "sessions": 0, "tools": 0})
topics = Counter()
errors_found = []

processed = 0
for transcript in transcripts:
    try:
        session_id = transcript.stem[:8]
        session_start = None
        session_end = None
        session_tools = []
        session_messages = 0
        session_model = "unknown"

        with open(transcript, 'r', errors='ignore') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    ts = entry.get('timestamp')

                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            day = dt.strftime('%Y-%m-%d')
                            if session_start is None:
                                session_start = ts
                            session_end = ts
                        except:
                            dt = None
                            day = None
                    else:
                        dt = None
                        day = None

                    # User messages - extract queries and URLs
                    if entry.get('type') == 'user':
                        session_messages += 1
                        if day:
                            daily_activity[day]["messages"] += 1

                        msg = entry.get('message', {})
                        content = msg.get('content', '')
                        if isinstance(content, str):
                            # Extract URLs
                            found = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', content)
                            urls_found.extend(found)

                            # Extract topics (words 4+ chars)
                            words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
                            topics.update(words)

                            # Store query
                            if len(content) > 10:
                                user_queries.append({
                                    "ts": int(dt.timestamp()) if dt else 0,
                                    "query": content[:200],
                                    "session": session_id
                                })

                    # Assistant messages - extract tools
                    if entry.get('type') == 'assistant':
                        session_messages += 1
                        if day:
                            daily_activity[day]["messages"] += 1

                        msg = entry.get('message', {})
                        model = msg.get('model', '')
                        if model:
                            model_name = 'opus' if 'opus' in model else 'sonnet' if 'sonnet' in model else 'haiku' if 'haiku' in model else 'unknown'
                            model_usage[model_name] += 1
                            session_model = model_name

                        content = msg.get('content', [])
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'tool_use':
                                    tool_name = item.get('name', 'unknown')
                                    session_tools.append(tool_name)
                                    if dt:
                                        tool_usage.append({
                                            "ts": int(dt.timestamp()),
                                            "tool": tool_name,
                                            "session": session_id,
                                            "model": session_model,
                                            "source": "backfill"
                                        })
                                        daily_activity[day]["tools"] += 1

                    # Tool results - check for errors
                    if entry.get('type') == 'tool_result':
                        content = entry.get('content', '')
                        if isinstance(content, str) and 'error' in content.lower():
                            errors_found.append({
                                "session": session_id,
                                "error": content[:200]
                            })

                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

        # Create session event
        if session_start:
            day = datetime.fromisoformat(session_start.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            daily_activity[day]["sessions"] += 1

            session_events.append({
                "session_id": session_id,
                "start": session_start,
                "end": session_end,
                "messages": session_messages,
                "tools": len(session_tools),
                "model": session_model,
                "top_tools": list(set(session_tools))[:5],
                "source": "backfill"
            })

        processed += 1

    except Exception as e:
        continue

print(f"   Processed {processed} transcripts")
print(f"   Tool events: {len(tool_usage)}")
print(f"   Session events: {len(session_events)}")
print(f"   User queries: {len(user_queries)}")
print(f"   URLs found: {len(urls_found)}")
print(f"   Model usage: {dict(model_usage)}")
print()

# ═══════════════════════════════════════════════════════════════════════════
# 2. WRITE TOOL USAGE DATA
# ═══════════════════════════════════════════════════════════════════════════

print("2. WRITING TOOL USAGE DATA...")

tool_file = DATA_DIR / "tool-usage.jsonl"
existing_tools = set()
if tool_file.exists():
    with open(tool_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                existing_tools.add((entry.get('ts'), entry.get('tool'), entry.get('session')))
            except:
                pass

new_tools = 0
with open(tool_file, 'a') as f:
    for entry in tool_usage:
        key = (entry['ts'], entry['tool'], entry['session'])
        if key not in existing_tools:
            f.write(json.dumps(entry) + '\n')
            new_tools += 1

print(f"   Added {new_tools} new tool events (skipped {len(tool_usage) - new_tools} duplicates)")

# ═══════════════════════════════════════════════════════════════════════════
# 3. WRITE SESSION EVENTS
# ═══════════════════════════════════════════════════════════════════════════

print("3. WRITING SESSION EVENTS...")

session_file = DATA_DIR / "session-events.jsonl"
existing_sessions = set()
if session_file.exists():
    with open(session_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                existing_sessions.add(entry.get('session_id'))
            except:
                pass

new_sessions = 0
with open(session_file, 'a') as f:
    for entry in session_events:
        if entry['session_id'] not in existing_sessions:
            f.write(json.dumps(entry) + '\n')
            new_sessions += 1

print(f"   Added {new_sessions} new session events")

# ═══════════════════════════════════════════════════════════════════════════
# 4. WRITE DQ SCORES
# ═══════════════════════════════════════════════════════════════════════════

print("4. WRITING DQ SCORES...")

dq_file = KERNEL_DIR / "dq-scores.jsonl"
dq_estimates = {'haiku': 0.3, 'sonnet': 0.6, 'opus': 0.85}

existing_dq = set()
if dq_file.exists():
    with open(dq_file) as f:
        for line in f:
            try:
                entry = json.loads(line)
                existing_dq.add((entry.get('ts'), entry.get('query', '')[:50]))
            except:
                pass

new_dq = 0
with open(dq_file, 'a') as f:
    for query in user_queries[:500]:  # Limit to 500 entries
        key = (query['ts'], query['query'][:50])
        if key not in existing_dq:
            # Estimate model from query complexity
            query_len = len(query['query'])
            if query_len < 50:
                model = 'haiku'
            elif query_len < 150:
                model = 'sonnet'
            else:
                model = 'opus'

            entry = {
                "ts": query['ts'],
                "query": query['query'][:100],
                "model": model,
                "dqScore": dq_estimates[model],
                "complexity": dq_estimates[model] * 0.9,
                "source": "backfill"
            }
            f.write(json.dumps(entry) + '\n')
            new_dq += 1

print(f"   Added {new_dq} DQ score entries")

# ═══════════════════════════════════════════════════════════════════════════
# 5. UPDATE IDENTITY EXPERTISE
# ═══════════════════════════════════════════════════════════════════════════

print("5. UPDATING IDENTITY EXPERTISE...")

identity_file = KERNEL_DIR / "identity.json"
domain_keywords = {
    'react': ['react', 'component', 'hooks', 'usestate', 'useeffect', 'jsx'],
    'typescript': ['typescript', 'types', 'interface', 'generic', 'type'],
    'python': ['python', 'pytest', 'django', 'flask', 'numpy', 'pandas'],
    'testing': ['test', 'testing', 'jest', 'vitest', 'pytest', 'mock'],
    'git': ['git', 'commit', 'branch', 'merge', 'rebase', 'push'],
    'debugging': ['debug', 'error', 'fix', 'issue', 'problem', 'stack'],
    'architecture': ['architecture', 'design', 'pattern', 'system', 'structure'],
    'api': ['api', 'endpoint', 'request', 'response', 'fetch', 'http'],
    'database': ['database', 'query', 'sql', 'schema', 'table', 'index'],
    'routing': ['routing', 'route', 'model', 'haiku', 'sonnet', 'opus'],
    'research': ['research', 'paper', 'arxiv', 'study', 'analysis'],
    'agent': ['agent', 'kernel', 'memory', 'context', 'autonomous']
}

topic_dict = dict(topics)
domain_confidence = {}
for domain, keywords in domain_keywords.items():
    score = sum(topic_dict.get(kw, 0) for kw in keywords)
    if score > 0:
        domain_confidence[domain] = min(score / 100, 1.0)

if identity_file.exists():
    identity = json.loads(identity_file.read_text())
    for domain, confidence in domain_confidence.items():
        if domain not in identity['expertise']['domains']:
            identity['expertise']['domains'].append(domain)
        identity['expertise']['confidence'][domain] = round(confidence, 3)
    identity['statistics']['totalQueries'] = max(
        identity['statistics'].get('totalQueries', 0),
        len(user_queries)
    )
    identity_file.write_text(json.dumps(identity, indent=2))
    print(f"   Updated {len(domain_confidence)} expertise domains")

# ═══════════════════════════════════════════════════════════════════════════
# 6. UPDATE STATS CACHE
# ═══════════════════════════════════════════════════════════════════════════

print("6. UPDATING STATS CACHE...")

stats_file = CLAUDE_DIR / "stats-cache.json"
stats = {
    "version": 1,
    "lastComputedDate": datetime.now().strftime('%Y-%m-%d'),
    "dailyActivity": [
        {
            "date": d,
            "messageCount": v["messages"],
            "sessionCount": v["sessions"],
            "toolCallCount": v["tools"]
        }
        for d, v in sorted(daily_activity.items(), reverse=True)[:30]
    ]
}
stats_file.write_text(json.dumps(stats, indent=2))
print(f"   Stats cache updated with {len(stats['dailyActivity'])} days")

# ═══════════════════════════════════════════════════════════════════════════
# 7. UPDATE ACTIVITY TIMELINE
# ═══════════════════════════════════════════════════════════════════════════

print("7. UPDATING ACTIVITY TIMELINE...")

timeline = {
    "generated": datetime.now().isoformat(),
    "days": list(sorted(daily_activity.items(), reverse=True))[:30],
    "totals": {
        "tools": sum(d["tools"] for d in daily_activity.values()),
        "sessions": sum(d["sessions"] for d in daily_activity.values()),
        "messages": sum(d["messages"] for d in daily_activity.values())
    }
}
(KERNEL_DIR / "activity-timeline.json").write_text(json.dumps(timeline, indent=2))
print(f"   Timeline: {timeline['totals']['tools']} tools, {timeline['totals']['sessions']} sessions, {timeline['totals']['messages']} messages")

# ═══════════════════════════════════════════════════════════════════════════
# 8. UPDATE SUBSCRIPTION DATA
# ═══════════════════════════════════════════════════════════════════════════

print("8. UPDATING SUBSCRIPTION DATA...")

# Estimate value: each tool call ~$0.50, each query ~$2
total_tools = len(tool_usage) + new_tools
total_queries = len(user_queries)
estimated_value = (total_tools * 0.5) + (total_queries * 2)

sub_data = {
    "totalValue": round(estimated_value, 2),
    "toolCalls": total_tools,
    "queries": total_queries,
    "monthlySubscription": 200,
    "roiMultiplier": round(estimated_value / 200, 1),
    "lastUpdated": datetime.now().isoformat()
}
(KERNEL_DIR / "subscription-data.json").write_text(json.dumps(sub_data, indent=2))
print(f"   Estimated value: ${estimated_value:,.0f} ({sub_data['roiMultiplier']}x ROI)")

# ═══════════════════════════════════════════════════════════════════════════
# 9. UPDATE TOOL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print("9. UPDATING TOOL SUMMARY...")

tool_counts = Counter(t['tool'] for t in tool_usage)
tool_summary = {
    "totalCalls": sum(tool_counts.values()),
    "uniqueTools": len(tool_counts),
    "topTools": tool_counts.most_common(20),
    "updated": datetime.now().isoformat()
}
(KERNEL_DIR / "tool-summary.json").write_text(json.dumps(tool_summary, indent=2))
print(f"   {tool_summary['totalCalls']} total calls, {tool_summary['uniqueTools']} unique tools")

# ═══════════════════════════════════════════════════════════════════════════
# 10. STORE LEARNINGS IN MEMORY
# ═══════════════════════════════════════════════════════════════════════════

print("10. STORING LEARNINGS IN MEMORY...")

learnings_file = AGENT_CORE / "memory" / "learnings.md"
learnings_file.parent.mkdir(parents=True, exist_ok=True)

# Generate insights from data
insights = [
    f"Primary development focus: {', '.join([t[0] for t in topics.most_common(5)])}",
    f"Most used tools: {', '.join([t[0] for t in tool_counts.most_common(5)])}",
    f"Model distribution: Haiku {model_usage.get('haiku', 0)}, Sonnet {model_usage.get('sonnet', 0)}, Opus {model_usage.get('opus', 0)}",
    f"Total sessions analyzed: {processed}",
    f"URLs referenced: {len(set(urls_found))}"
]

with open(learnings_file, 'a') as f:
    f.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} - Bulk Backfill Summary\n")
    for insight in insights:
        f.write(f"- {insight}\n")
    f.write("\n")

print(f"   Added {len(insights)} insights to learnings")

# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

print()
print("=" * 70)
print("BULK BACKFILL COMPLETE")
print("=" * 70)
print(f"""
Summary:
  • Transcripts processed: {processed}
  • Tool events added: {new_tools}
  • Session events added: {new_sessions}
  • DQ scores added: {new_dq}
  • Expertise domains: {len(domain_confidence)}
  • Estimated value: ${estimated_value:,.0f} ({sub_data['roiMultiplier']}x ROI)
  • Days with activity: {len(daily_activity)}
""")
