#!/usr/bin/env python3
"""
Populate Error Solutions - Mines past data and adds solutions to error patterns

Sources:
1. Known solutions for common error categories
2. Context from errors.jsonl
3. Session outcomes with fixes
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict

DB_PATH = Path.home() / ".claude" / "memory" / "supermemory.db"
ERRORS_FILE = Path.home() / ".claude" / "data" / "errors.jsonl"

# Solutions from your ERRORS.md - YOUR actual documented fixes
KNOWN_SOLUTIONS = {
    # Git errors - YOUR #1 ISSUE (112 occurrences)
    ("git", "fatal:"): """YOUR DOCUMENTED GIT FIXES:

Repository Not Found:
- Case sensitivity issue: Always use `Dicoangelo` (not `dicoangelo`)
- Verify repo exists: `gh repo view owner/repo` before cloning
- Update old references in scripts

Tag/Branch Conflicts:
- Check before creating: `git tag -l | grep <tag>`
- Check before cloning: `[ -d <dir> ] || git clone ...`

Wrong Directory:
- Verify first: `git rev-parse --git-dir` before operations
- Use absolute paths when possible""",

    # Concurrency errors - Parallel Claude Sessions
    ("concurrency", "race condition"): """YOUR DOCUMENTED CONCURRENCY FIXES:

Parallel Claude Sessions Issue:
- 5+ sessions running = race conditions corrupting shared files
- Sessions overwriting each other's data

Prevention:
- Check for other sessions: `pgrep -f "claude"` at start
- Use file locks for critical writes
- Close other Claude instances before heavy work
- ONE SESSION AT A TIME rule""",

    # Permission errors
    ("permissions", "permission denied"): """YOUR DOCUMENTED PERMISSION FIXES:

Causes:
- Running commands without proper permissions
- Accessing protected files/directories

Prevention:
- Check permissions first: `ls -la <file>`
- Use `sudo` when appropriate
- Ensure scripts are executable: `chmod +x`""",

    # Quota/Rate limit errors - Already handled
    ("quota", "quota exceeded"): """YOUR DOCUMENTED QUOTA FIXES:

Status: Managed by DQ routing system

Prevention:
- DQ routing handles this (Haiku/Sonnet for simple tasks)
- Exponential backoff implemented in code
- Model downgrades automatic when hitting limits""",

    # Crash/SIGKILL errors - Resolved
    ("crash", "SIGKILL"): """YOUR DOCUMENTED CRASH FIXES:

Status: Resolved

Prevention:
- Monitor memory usage
- Implement streaming/chunking for large data
- Resource limits configured""",

    # Recursion errors - Prevented
    ("recursion", "infinite loop"): """YOUR DOCUMENTED RECURSION FIXES:

Status: Prevented

Prevention:
- Add explicit base cases
- Add iteration limits
- Use visited sets to detect cycles""",

    # Syntax errors - One-off
    ("syntax", "SyntaxError"): """YOUR DOCUMENTED SYNTAX FIXES:

Status: One-off occurrence

Prevention:
- Run linters before execution
- Use IDE with syntax highlighting
- Use formatters: `black`, `prettier`""",
}

def load_error_context():
    """Load additional context from errors.jsonl."""
    context = defaultdict(list)

    if not ERRORS_FILE.exists():
        return context

    with open(ERRORS_FILE) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                err = json.loads(line)
                category = err.get('category', 'unknown')
                error_line = err.get('line', '')[:200]
                if error_line:
                    context[category].append(error_line)
            except:
                continue

    return context

def generate_contextual_solution(category, pattern, examples):
    """Generate solution with specific examples from history."""
    base_solution = KNOWN_SOLUTIONS.get((category, pattern), "")

    if not examples:
        return base_solution

    # Add specific examples seen
    unique_examples = list(set(examples[:5]))
    if unique_examples:
        example_text = "\n\nExamples from your history:\n" + "\n".join(f"- {ex[:100]}" for ex in unique_examples)
        return base_solution + example_text if base_solution else f"Common occurrences:\n{example_text}"

    return base_solution

def populate_solutions():
    """Populate solutions in the database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Load error context
    context = load_error_context()

    # Get all patterns
    patterns = conn.execute("SELECT id, category, pattern, count FROM error_patterns").fetchall()

    updated = 0
    for p in patterns:
        category = p['category']
        pattern = p['pattern']

        # Get examples for this category
        examples = context.get(category, [])

        # Generate solution
        solution = generate_contextual_solution(category, pattern, examples)

        if solution:
            conn.execute(
                "UPDATE error_patterns SET solution = ? WHERE id = ?",
                (solution.strip(), p['id'])
            )
            updated += 1
            print(f"✓ {category}/{pattern}: Added solution ({p['count']} occurrences)")

    conn.commit()
    conn.close()

    return updated

def add_custom_solutions():
    """Add solutions for patterns without known solutions."""
    conn = sqlite3.connect(str(DB_PATH))

    # Patterns without solutions yet
    custom_solutions = {
        # Add any custom solutions here based on your specific errors
    }

    for (category, pattern), solution in custom_solutions.items():
        conn.execute(
            "UPDATE error_patterns SET solution = ? WHERE category = ? AND pattern = ?",
            (solution, category, pattern)
        )

    conn.commit()
    conn.close()

def show_stats():
    """Show solution coverage stats."""
    conn = sqlite3.connect(str(DB_PATH))

    total = conn.execute("SELECT COUNT(*) FROM error_patterns").fetchone()[0]
    with_solution = conn.execute("SELECT COUNT(*) FROM error_patterns WHERE solution IS NOT NULL").fetchone()[0]

    print(f"\n📊 Solution Coverage: {with_solution}/{total} patterns ({with_solution/total*100:.0f}%)")

    # Show top patterns with solutions
    print("\n🔧 Top Patterns with Solutions:")
    rows = conn.execute("""
        SELECT category, pattern, count,
               CASE WHEN solution IS NOT NULL THEN '✓' ELSE '✗' END as has_solution
        FROM error_patterns
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()

    for r in rows:
        print(f"  {r[3]} [{r[0]}] {r[1]} ({r[2]} occurrences)")

    conn.close()

if __name__ == "__main__":
    print("🔧 Populating Error Solutions\n")

    updated = populate_solutions()
    add_custom_solutions()

    print(f"\n✅ Updated {updated} patterns with solutions")
    show_stats()
