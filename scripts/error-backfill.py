#!/usr/bin/env python3
"""
Error Backfill Script
Scans all session data to extract historical errors and populate ERRORS.md
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

HOME = Path.home()
CLAUDE_DIR = HOME / '.claude'
AGENT_CORE = HOME / '.agent-core'
ERRORS_MD = CLAUDE_DIR / 'ERRORS.md'
ERRORS_JSONL = CLAUDE_DIR / 'data' / 'errors.jsonl'

# Error patterns with categories
ERROR_PATTERNS = [
    (r'error[:\s]', 'general', 'medium'),
    (r'Error[:\s]', 'general', 'medium'),
    (r'ERROR', 'general', 'medium'),
    (r'failed', 'failure', 'medium'),
    (r'Failed', 'failure', 'medium'),
    (r'FAILED', 'failure', 'high'),
    (r'permission denied', 'permissions', 'high'),
    (r'Permission denied', 'permissions', 'high'),
    (r'ENOENT', 'file_not_found', 'medium'),
    (r'EACCES', 'permissions', 'high'),
    (r'No such file', 'file_not_found', 'medium'),
    (r'not found', 'missing', 'low'),
    (r'command not found', 'missing_command', 'medium'),
    (r'npm ERR!', 'npm', 'medium'),
    (r'fatal:', 'git', 'high'),
    (r'SyntaxError', 'syntax', 'high'),
    (r'TypeError', 'type', 'high'),
    (r'ReferenceError', 'reference', 'high'),
    (r'ModuleNotFoundError', 'import', 'medium'),
    (r'ImportError', 'import', 'medium'),
    (r'Cannot find module', 'import', 'medium'),
    (r'timeout', 'timeout', 'medium'),
    (r'Timeout', 'timeout', 'medium'),
    (r'ETIMEDOUT', 'timeout', 'medium'),
    (r'connection refused', 'network', 'medium'),
    (r'ECONNREFUSED', 'network', 'medium'),
    (r'401|403 Forbidden|404 Not Found|500|502|503', 'http', 'medium'),
    (r'rate limit', 'rate_limit', 'medium'),
    (r'quota exceeded', 'quota', 'high'),
    (r'out of memory', 'memory', 'critical'),
    (r'OOM', 'memory', 'critical'),
    (r'segmentation fault', 'crash', 'critical'),
    (r'SIGKILL', 'crash', 'critical'),
    (r'Maximum call stack', 'recursion', 'high'),
    (r'infinite loop', 'recursion', 'high'),
    (r'deadlock', 'concurrency', 'critical'),
    (r'race condition', 'concurrency', 'high'),
]

# Exclusions - common false positives
EXCLUSIONS = [
    r'error-tracker',
    r'error-capture',
    r'error-summary',
    r'ERRORS\.md',
    r'no error',
    r'without error',
    r'error handling',
    r'error message',
    r'if error',
    r'catch error',
    r'ErrorBoundary',
]

def should_exclude(line):
    """Check if line should be excluded (false positive)"""
    for pattern in EXCLUSIONS:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    return False

def detect_error(line):
    """Detect error category and severity from line"""
    if should_exclude(line):
        return None

    for pattern, category, severity in ERROR_PATTERNS:
        if re.search(pattern, line, re.IGNORECASE):
            return {
                'category': category,
                'severity': severity,
                'pattern': pattern
            }
    return None

def extract_date_from_path(path):
    """Extract date from file path"""
    # Try to find date patterns like 2026-01-19 or 20260119
    match = re.search(r'(\d{4})-?(\d{2})-?(\d{2})', str(path))
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return datetime.now().strftime('%Y-%m-%d')

def scan_activity_log():
    """Scan activity.log for errors"""
    errors = []
    activity_log = CLAUDE_DIR / 'activity.log'

    if not activity_log.exists():
        return errors

    print(f"Scanning activity.log ({activity_log.stat().st_size / 1024:.1f} KB)...")

    current_session = None
    with open(activity_log, 'r', errors='ignore') as f:
        for line in f:
            # Track session boundaries
            if 'SESSION' in line and 'PWD:' in line:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', line)
                current_session = date_match.group(1) if date_match else None
                continue

            error = detect_error(line)
            if error and error['severity'] in ('high', 'critical', 'medium'):
                errors.append({
                    'date': current_session or datetime.now().strftime('%Y-%m-%d'),
                    'source': 'activity_log',
                    'line': line.strip()[:200],
                    **error
                })

    return errors

def scan_session_summaries():
    """Scan session summaries for error mentions"""
    errors = []
    summaries_dir = CLAUDE_DIR / 'session-summaries'

    if not summaries_dir.exists():
        return errors

    print(f"Scanning {len(list(summaries_dir.glob('*.md')))} session summaries...")

    for summary_file in summaries_dir.glob('*.md'):
        date = extract_date_from_path(summary_file)
        content = summary_file.read_text(errors='ignore')

        for line in content.split('\n'):
            error = detect_error(line)
            if error and error['severity'] in ('high', 'critical'):
                errors.append({
                    'date': date,
                    'source': f'session:{summary_file.name}',
                    'line': line.strip()[:200],
                    **error
                })

    return errors

def scan_agent_core_sessions():
    """Scan agent-core sessions for errors"""
    errors = []
    sessions_dir = AGENT_CORE / 'sessions'

    if not sessions_dir.exists():
        return errors

    session_dirs = list(sessions_dir.iterdir())
    print(f"Scanning {len(session_dirs)} agent-core sessions...")

    for session_dir in session_dirs:
        if not session_dir.is_dir():
            continue

        date = extract_date_from_path(session_dir)

        # Check session files
        for file in session_dir.glob('*'):
            if file.suffix in ('.md', '.txt', '.json', '.log'):
                try:
                    content = file.read_text(errors='ignore')
                    for line in content.split('\n'):
                        error = detect_error(line)
                        if error and error['severity'] in ('high', 'critical'):
                            errors.append({
                                'date': date,
                                'source': f'agent-core:{session_dir.name}',
                                'line': line.strip()[:200],
                                **error
                            })
                except Exception:
                    pass

    return errors

def scan_debug_logs():
    """Scan debug directory for errors"""
    errors = []
    debug_dir = CLAUDE_DIR / 'debug'

    if not debug_dir.exists():
        return errors

    debug_files = list(debug_dir.glob('*'))
    print(f"Scanning {len(debug_files)} debug files...")

    for debug_file in debug_files[-50:]:  # Only recent 50
        if not debug_file.is_file():
            continue

        date = extract_date_from_path(debug_file)

        try:
            content = debug_file.read_text(errors='ignore')
            for line in content.split('\n'):
                error = detect_error(line)
                if error and error['severity'] in ('high', 'critical'):
                    errors.append({
                        'date': date,
                        'source': f'debug:{debug_file.name[:30]}',
                        'line': line.strip()[:200],
                        **error
                    })
        except Exception:
            pass

    return errors

def deduplicate_errors(errors):
    """Deduplicate errors by content similarity"""
    seen = set()
    unique = []

    for error in errors:
        # Create a fingerprint
        fingerprint = f"{error['category']}:{error['line'][:50]}"
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique.append(error)

    return unique

def aggregate_by_category(errors):
    """Group errors by category for summary"""
    by_category = defaultdict(list)
    for error in errors:
        by_category[error['category']].append(error)
    return dict(by_category)

def write_backfill_results(errors):
    """Write backfilled errors to ERRORS.md and errors.jsonl"""

    # Write to jsonl
    ERRORS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(ERRORS_JSONL, 'a') as f:
        for error in errors:
            entry = {
                'ts': int(datetime.now().timestamp()),
                'timestamp': datetime.now().isoformat(),
                'backfilled': True,
                **error
            }
            f.write(json.dumps(entry) + '\n')

    # Group by date and category for ERRORS.md
    by_date = defaultdict(lambda: defaultdict(list))
    for error in errors:
        by_date[error['date']][error['category']].append(error)

    # Read current ERRORS.md
    content = ERRORS_MD.read_text()

    # Find insertion point
    insert_point = content.find('## Patterns to Watch')
    if insert_point == -1:
        insert_point = len(content)

    # Build new entries
    new_entries = "\n## Backfilled Errors (Historical)\n\n"

    for date in sorted(by_date.keys(), reverse=True):
        categories = by_date[date]
        for category, cat_errors in categories.items():
            severity = max(e['severity'] for e in cat_errors)
            count = len(cat_errors)
            sample = cat_errors[0]['line'][:100]

            new_entries += f"""### {date} - {category} ({count} occurrences)
**Category:** {category} | **Severity:** {severity}
**Sample:** `{sample}...`
**Source:** {cat_errors[0]['source']}

"""

    new_entries += "---\n\n"

    # Insert into content
    content = content[:insert_point] + new_entries + content[insert_point:]
    ERRORS_MD.write_text(content)

def main():
    print("=" * 50)
    print("Error Backfill - Scanning all session data")
    print("=" * 50)
    print()

    all_errors = []

    # Scan all sources
    all_errors.extend(scan_activity_log())
    all_errors.extend(scan_session_summaries())
    all_errors.extend(scan_agent_core_sessions())
    all_errors.extend(scan_debug_logs())

    print()
    print(f"Total errors found: {len(all_errors)}")

    # Deduplicate
    unique_errors = deduplicate_errors(all_errors)
    print(f"After deduplication: {len(unique_errors)}")

    if not unique_errors:
        print("\nNo errors found to backfill.")
        return

    # Show summary
    by_category = aggregate_by_category(unique_errors)
    print("\nBy category:")
    for cat, errs in sorted(by_category.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(errs)}")

    by_severity = defaultdict(int)
    for e in unique_errors:
        by_severity[e['severity']] += 1

    print("\nBy severity:")
    for sev in ['critical', 'high', 'medium', 'low']:
        if by_severity[sev]:
            print(f"  {sev}: {by_severity[sev]}")

    # Write results
    print("\nWriting to ERRORS.md and errors.jsonl...")
    write_backfill_results(unique_errors)

    print("\nBackfill complete!")
    print(f"  - {len(unique_errors)} errors logged to ~/.claude/data/errors.jsonl")
    print(f"  - Summary added to ~/.claude/ERRORS.md")

if __name__ == '__main__':
    main()
