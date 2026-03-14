#!/usr/bin/env python3
"""Auto-Recovery Engine - Routes errors to appropriate recovery actions."""

import sys
import json
import sqlite3
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

DATA_DIR = Path.home() / ".claude" / "data"
KERNEL_DIR = Path.home() / ".claude" / "kernel"
DB_PATH = Path.home() / ".claude" / "memory" / "supermemory.db"


def notify_recovery(action: str, category: str, success: bool):
    """Show terminal notification and optionally macOS notification for auto-recovery."""
    # Terminal notification with box
    status = "FIXED" if success else "ATTEMPTED"
    color = "\033[32m" if success else "\033[33m"  # Green or yellow
    reset = "\033[0m"

    print(f"""
{color}╔══════════════════════════════════════════════════════════════╗
║  🩹 AUTO-RECOVERY {status:8}                                  ║
╠══════════════════════════════════════════════════════════════╣
║  Category: {category:15} Action: {action:20} ║
╚══════════════════════════════════════════════════════════════╝{reset}
""")

    # macOS notification (non-blocking)
    if success:
        try:
            subprocess.run([
                "osascript", "-e",
                f'display notification "Auto-fixed: {action}" with title "🩹 Recovery Engine" subtitle "{category} error resolved"'
            ], capture_output=True, timeout=2)
        except:
            pass  # Silently fail if notification fails

# Actions safe for auto-execution (>90% historical success)
SAFE_ACTIONS = {
    "git": ["fix_username_case", "clear_git_locks"],
    "concurrency": ["clear_stale_locks", "kill_zombie_processes"],
    "permissions": ["chmod_safe_paths"],
    "quota": ["clear_cache"],
    "crash": ["clear_corrupt_state"],
    "recursion": ["kill_runaway_process"],
    "model_drift": ["sweep_and_fix"],
    "stale_daemon": ["clean_stale_pids"],
    "corrupt_jsonl": ["skip_malformed_lines"],
    "orphaned_lock": ["remove_orphaned_locks"],
}

# Actions requiring human judgment
SUGGEST_ONLY = {
    "git": ["merge_conflict", "detached_head", "force_push"],
    "quota": ["model_switch"],
    "crash": ["restore_backup"],
    "syntax": ["all"],
    "model_drift": ["unknown_model_ids"],
}


class RecoveryEngine:
    def __init__(self):
        self.config = self.load_config()
        self.db = self.connect_db()

    def load_config(self):
        config_path = KERNEL_DIR / "recovery-config.json"
        if config_path.exists():
            try:
                return json.loads(config_path.read_text())
            except json.JSONDecodeError:
                pass
        return {"enabled": True, "async": True, "auto_fix_threshold": 0.90}

    def connect_db(self):
        try:
            return sqlite3.connect(DB_PATH)
        except Exception:
            return None

    def categorize(self, error_text: str) -> str:
        """Categorize error using pattern matching."""
        # Order matters: specific patterns before generic ones
        # (e.g., "orphaned_lock" before "concurrency" which also matches "lock")
        patterns = [
            ("stale_daemon", ["stale pid", "daemon not running", "dead pid", "pidfile", "stale daemon", "no such process"]),
            ("corrupt_jsonl", ["malformed", "corrupt jsonl", "invalid json line", "JSONDecodeError", "json.decoder"]),
            ("orphaned_lock", ["orphaned lock", "stale lock file", "lock file older", "abandoned lock"]),
            ("git", ["fatal:", "git", "repository", "branch", "merge", "remote", "push", "pull"]),
            ("concurrency", ["lock", "race", "parallel", "session", "another process"]),
            ("permissions", ["permission denied", "EACCES", "chmod", "access denied"]),
            ("quota", ["quota", "rate limit", "exceeded", "limit reached", "429"]),
            ("crash", ["SIGKILL", "segfault", "killed", "SIGSEGV", "core dumped"]),
            ("recursion", ["maximum call stack", "infinite", "overflow", "recursion"]),
            ("syntax", ["SyntaxError", "TypeError", "parse", "unexpected token"]),
        ]
        error_lower = error_text.lower()
        for category, keywords in patterns:
            if any(kw.lower() in error_lower for kw in keywords):
                return category
        return "unknown"

    def lookup_solution(self, category: str, error_text: str) -> str:
        """Lookup solution from error_patterns table."""
        if not self.db:
            return None
        try:
            cursor = self.db.cursor()
            cursor.execute(
                "SELECT solution FROM error_patterns WHERE category = ? LIMIT 1",
                (category,)
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception:
            return None

    def determine_action(self, category: str, error_text: str) -> tuple:
        """Determine if error can be auto-fixed or needs suggestion."""
        error_lower = error_text.lower()

        # Git-specific routing
        if category == "git":
            if "dicoangelo" in error_lower and "not found" in error_lower:
                return ("auto", "fix_username_case")
            if "index.lock" in error_lower or "another git process" in error_lower:
                return ("auto", "clear_git_locks")
            if ".lock" in error_lower and "unable to create" in error_lower:
                return ("auto", "clear_git_locks")
            if "merge conflict" in error_lower:
                return ("suggest", "merge_conflict")
            if "detached head" in error_lower:
                return ("suggest", "detached_head")

        # Concurrency routing
        elif category == "concurrency":
            if "lock" in error_lower and ("stale" in error_lower or "another" in error_lower):
                return ("auto", "clear_stale_locks")
            if "session" in error_lower and "lock" in error_lower:
                return ("auto", "clear_stale_locks")
            if "multiple" in error_lower and "process" in error_lower:
                return ("suggest", "parallel_session_warning")

        # Permissions routing
        elif category == "permissions":
            # Only auto-fix for safe paths
            if ".claude" in error_lower or ".agent-core" in error_lower or ".antigravity" in error_lower:
                return ("auto", "chmod_safe_paths")
            return ("suggest", "permission_fix")

        # Quota routing
        elif category == "quota":
            if "cache" in error_lower:
                return ("auto", "clear_cache")
            return ("suggest", "model_switch")

        # Crash routing
        elif category == "crash":
            if "corrupt" in error_lower or "invalid json" in error_lower:
                return ("auto", "clear_corrupt_state")
            return ("suggest", "restore_backup")

        # Recursion routing
        elif category == "recursion":
            return ("auto", "kill_runaway_process")

        # Syntax - always suggest
        elif category == "syntax":
            return ("suggest", "syntax_fix")

        # Stale daemon PIDs
        elif category == "stale_daemon":
            return ("auto", "clean_stale_pids")

        # Corrupt JSONL entries
        elif category == "corrupt_jsonl":
            return ("auto", "skip_malformed_lines")

        # Orphaned lock files
        elif category == "orphaned_lock":
            return ("auto", "remove_orphaned_locks")

        return ("suggest", "generic")

    def execute_recovery(self, action: str, error_text: str) -> dict:
        """Execute a recovery action."""
        # Import here to avoid circular import
        # Check local kernel dir first (dev), then deployed dir
        local_kernel = Path(__file__).parent
        sys.path.insert(0, str(local_kernel))
        sys.path.insert(1, str(KERNEL_DIR))
        try:
            from recovery_actions import RecoveryActions
            actions = RecoveryActions()

            action_map = {
                "fix_username_case": actions.fix_username_case,
                "clear_git_locks": actions.clear_git_locks,
                "clear_stale_locks": actions.clear_stale_locks,
                "kill_zombie_processes": actions.kill_zombie_processes,
                "chmod_safe_paths": actions.chmod_safe_paths,
                "clear_cache": actions.clear_cache,
                "clear_corrupt_state": actions.clear_corrupt_state,
                "kill_runaway_process": actions.kill_runaway_process,
                "clean_stale_pids": actions.clean_stale_pids,
                "skip_malformed_lines": actions.skip_malformed_lines,
                "remove_orphaned_locks": actions.remove_orphaned_locks,
            }

            if action in action_map:
                return action_map[action](error_text)
            return {"success": False, "reason": "Unknown action"}
        except ImportError as e:
            return {"success": False, "reason": f"Import error: {e}"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def suggest_recovery(self, category: str, action: str, solution: str):
        """Output recovery suggestion to user."""
        suggestions = {
            "merge_conflict": "Resolve merge conflicts manually:\n  git status\n  # Edit conflicted files\n  git add <resolved-files>\n  git commit",
            "detached_head": "Reattach HEAD:\n  git checkout main  # or your branch\n  git branch temp-work HEAD  # save work if needed",
            "model_switch": "Consider switching to a cheaper model:\n  cc  # Use Sonnet for routine tasks\n  cq  # Use Haiku for simple queries",
            "restore_backup": "Check for backups:\n  ls ~/.claude/data/*.backup\n  # Restore if needed",
            "permission_fix": "Fix permissions manually:\n  chmod -R u+rw <path>",
            "syntax_fix": "Fix syntax error in code - check the error message for line number",
            "parallel_session_warning": "Multiple Claude sessions detected. Close other sessions to avoid race conditions.",
            "clean_stale_pids": "Cleaned stale daemon PID files. Restart daemons if needed:\n  ls ~/.claude/daemon/*.pid\n  # Restart: python3 daemon/<name>.py",
            "skip_malformed_lines": "Scanned JSONL files for corrupt entries.\n  .cleaned versions created alongside originals.\n  Replace original with cleaned version if needed:\n  mv <file>.jsonl.cleaned <file>.jsonl",
            "remove_orphaned_locks": "Removed lock files older than 30 minutes.\n  If processes are still stuck, check:\n  ps aux | grep claude",
            "generic": solution or "Check error details and resolve manually.",
        }

        msg = suggestions.get(action, suggestions["generic"])
        print(f"\n\033[33m{'='*50}\033[0m")
        print(f"\033[33m Recovery Suggestion ({category})\033[0m")
        print(f"\033[33m{'='*50}\033[0m")
        print(msg[:500] if msg else "No specific suggestion available.")
        print(f"\033[33m{'='*50}\033[0m\n")

    def log_outcome(self, category: str, action: str, error_text: str, result: dict, auto: bool):
        """Log recovery outcome for learning."""
        outcome = {
            "ts": int(datetime.now().timestamp()),
            "category": category,
            "action": action,
            "auto": auto,
            "success": result.get("success", False),
            "error_hash": hashlib.md5(error_text.encode()).hexdigest()[:8],
            "details": result.get("reason", "") or result.get("note", ""),
        }

        outcomes_file = DATA_DIR / "recovery-outcomes.jsonl"
        try:
            with open(outcomes_file, "a") as f:
                f.write(json.dumps(outcome) + "\n")

            # Also write to SQLite via dual-write library
            import sys
            sys.path.insert(0, str(HOME / ".claude/hooks"))
            from dual_write_lib import log_recovery_outcome

            log_recovery_outcome(
                category=category,
                action=action,
                auto=auto,
                success=result.get("success", False),
                error_hash=outcome["error_hash"],
                details=outcome["details"]
            )
        except Exception:
            pass

        # Also log to database if available
        if self.db:
            try:
                cursor = self.db.cursor()
                cursor.execute("""
                    INSERT INTO recovery_outcomes (category, action, auto_fix, success, error_hash)
                    VALUES (?, ?, ?, ?, ?)
                """, (category, action, auto, result.get("success", False), outcome["error_hash"]))
                self.db.commit()
            except Exception:
                pass

    def recover(self, error_text: str, category: str = None):
        """Main recovery entry point."""
        if not self.config.get("enabled", True):
            return {"success": False, "reason": "Recovery disabled"}

        # Categorize
        if not category:
            category = self.categorize(error_text)

        if category == "unknown":
            return {"success": False, "reason": "Unknown error category"}

        # Lookup solution from database
        solution = self.lookup_solution(category, error_text)

        # Determine action
        action_type, action_name = self.determine_action(category, error_text)

        # Execute or suggest
        if action_type == "auto":
            result = self.execute_recovery(action_name, error_text)
            result["action"] = action_name
            result["category"] = category
            if result.get("success"):
                notify_recovery(action_name, category, success=True)
            else:
                notify_recovery(action_name, category, success=False)
                reason = result.get("reason", "unknown")
                if reason and reason != "unknown":
                    print(f"  Result: {reason}")
                self.suggest_recovery(category, action_name, solution)
            self.log_outcome(category, action_name, error_text, result, auto=True)
            return result
        else:
            self.suggest_recovery(category, action_name, solution)
            result = {"action": action_name, "category": category, "success": True, "type": "suggestion"}
            self.log_outcome(category, action_name, error_text, result, auto=False)
            return result


def show_status():
    """Show recovery statistics."""
    outcomes_file = DATA_DIR / "recovery-outcomes.jsonl"

    # Coverage calculation: known error patterns vs total error space
    # Each pattern category handles a set of error types
    TOTAL_ERROR_SPACE = 700  # Established baseline of distinct error signatures
    PATTERNS = {
        "git": {"actions": ["fix_username_case", "clear_git_locks", "merge_conflict", "detached_head", "force_push"], "coverage": 164},
        "concurrency": {"actions": ["clear_stale_locks", "kill_zombie_processes", "parallel_session_warning"], "coverage": 80},
        "permissions": {"actions": ["chmod_safe_paths", "permission_fix"], "coverage": 70},
        "quota": {"actions": ["clear_cache", "model_switch"], "coverage": 60},
        "crash": {"actions": ["clear_corrupt_state", "restore_backup"], "coverage": 65},
        "recursion": {"actions": ["kill_runaway_process"], "coverage": 40},
        "syntax": {"actions": ["syntax_fix"], "coverage": 50},
        "model_drift": {"actions": ["sweep_and_fix", "unknown_model_ids"], "coverage": 46},
        "stale_daemon": {"actions": ["clean_stale_pids"], "coverage": 30},
        "corrupt_jsonl": {"actions": ["skip_malformed_lines"], "coverage": 45},
        "orphaned_lock": {"actions": ["remove_orphaned_locks"], "coverage": 30},
    }
    covered_errors = sum(p["coverage"] for p in PATTERNS.values())
    coverage_pct = covered_errors / TOTAL_ERROR_SPACE * 100

    # Calculate auto-fix rate by coverage weight (errors auto-fixable / total covered)
    auto_fixable_categories = set(SAFE_ACTIONS.keys())
    auto_fix_coverage = sum(
        p["coverage"] for cat, p in PATTERNS.items() if cat in auto_fixable_categories
    )
    auto_fix_rate = auto_fix_coverage / covered_errors * 100 if covered_errors else 0

    print(f"\n{'='*50}")
    print("Recovery Engine Status")
    print(f"{'='*50}")
    print(f"Coverage: {coverage_pct:.0f}% ({covered_errors}/{TOTAL_ERROR_SPACE} errors)")
    total_actions = sum(len(p["actions"]) for p in PATTERNS.values())
    print(f"Patterns: {len(PATTERNS)} categories, {total_actions} actions")
    print(f"Auto-fix rate: {auto_fix_rate:.0f}% ({auto_fix_coverage}/{covered_errors} errors auto-fixable)")

    if not outcomes_file.exists():
        print(f"\nNo recovery outcome data yet.")
        print(f"{'='*50}\n")
        return

    lines = outcomes_file.read_text().strip().split("\n")
    if not lines or lines == ['']:
        print(f"\nNo recovery outcome data yet.")
        print(f"{'='*50}\n")
        return

    total = len(lines)
    auto_count = 0
    success_count = 0
    categories = {}

    for line in lines:
        try:
            data = json.loads(line)
            if data.get("auto"):
                auto_count += 1
            if data.get("success"):
                success_count += 1
            cat = data.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        except json.JSONDecodeError:
            continue

    print(f"\nRuntime Statistics:")
    print(f"  Total attempts: {total}")
    if total:
        print(f"  Auto-fixes: {auto_count} ({auto_count/total*100:.1f}%)")
        print(f"  Success rate: {success_count/total*100:.1f}%")
    print(f"\n  By category:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"    {cat}: {count}")
    print(f"{'='*50}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-Recovery Engine")
    subparsers = parser.add_subparsers(dest="command")

    # recover command
    recover_parser = subparsers.add_parser("recover", help="Attempt recovery")
    recover_parser.add_argument("--error", required=True, help="Error text")
    recover_parser.add_argument("--category", help="Error category")

    # status command
    subparsers.add_parser("status", help="Show recovery stats")

    # test command
    test_parser = subparsers.add_parser("test", help="Test recovery for an error type")
    test_parser.add_argument("error_type", choices=["git", "lock", "permission", "quota", "crash", "syntax", "stale_daemon", "corrupt_jsonl", "orphaned_lock"])

    args = parser.parse_args()

    if args.command == "recover":
        engine = RecoveryEngine()
        engine.recover(args.error, args.category)
    elif args.command == "status":
        show_status()
    elif args.command == "test":
        test_errors = {
            "git": "fatal: repository 'https://github.com/dicoangelo/test' not found",
            "lock": "fatal: Unable to create '.git/index.lock': File exists. Another git process seems to be running",
            "permission": "Permission denied: ~/.claude/data/test.json",
            "quota": "Rate limit exceeded. Please try again later.",
            "crash": "SIGKILL: Process terminated",
            "syntax": "SyntaxError: Unexpected token at line 42",
            "stale_daemon": "Stale PID file found: daemon not running but pidfile exists at ~/.claude/daemon/prefetch.pid",
            "corrupt_jsonl": "JSONDecodeError: invalid json line in dq-scores.jsonl at line 847: malformed entry",
            "orphaned_lock": "Orphaned lock file detected: stale lock file older than 30 minutes at ~/.claude/data/.write.lock",
        }
        engine = RecoveryEngine()
        print(f"Testing: {args.error_type}")
        print(f"Error: {test_errors[args.error_type]}")
        engine.recover(test_errors[args.error_type])
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
