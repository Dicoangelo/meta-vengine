#!/usr/bin/env python3
"""Recovery action implementations - all the actual fixes."""

import os
import subprocess
import signal
import time
from pathlib import Path

SAFE_PATHS = [
    Path.home() / ".claude",
    Path.home() / ".agent-core",
    Path.home() / ".antigravity",
]


class RecoveryActions:

    # ═══════════════════════════════════════════════════════════
    # GIT RECOVERY
    # ═══════════════════════════════════════════════════════════

    def fix_username_case(self, error_text: str = None) -> dict:
        """Fix GitHub username case sensitivity (dicoangelo -> Dicoangelo)."""
        try:
            # Add URL rewrite rule for SSH (use --replace-all to handle existing configs)
            subprocess.run([
                "git", "config", "--global", "--replace-all",
                "url.git@github.com:Dicoangelo/.insteadOf",
                "git@github.com:dicoangelo/"
            ], check=True, capture_output=True)

            # Add URL rewrite rule for HTTPS
            subprocess.run([
                "git", "config", "--global", "--replace-all",
                "url.https://github.com/Dicoangelo/.insteadOf",
                "https://github.com/dicoangelo/"
            ], check=True, capture_output=True)

            return {"success": True, "action": "fix_username_case", "note": "Added git URL rewrites"}
        except subprocess.CalledProcessError as e:
            return {"success": False, "reason": f"Git config failed: {e}"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def clear_git_locks(self, error_text: str = None) -> dict:
        """Remove stale git lock files."""
        try:
            # Check if git is actually running (wait a moment for transient operations)
            result = subprocess.run(["pgrep", "-x", "git"], capture_output=True)
            if result.returncode == 0:
                # Git is running - wait briefly and recheck
                time.sleep(0.5)
                result = subprocess.run(["pgrep", "-x", "git"], capture_output=True)
                if result.returncode == 0:
                    return {"success": False, "reason": "Git process still running"}

            # Common repo paths to check
            repo_paths = [
                Path.cwd(),
                Path.home() / "OS-App",
                Path.home() / "CareerCoachAntigravity",
                Path.home() / "researchgravity",
                Path.home() / ".claude",
            ]

            locks_removed = 0
            for repo_path in repo_paths:
                git_dir = repo_path / ".git"
                if not git_dir.exists():
                    continue

                # Check for various lock files
                lock_files = [
                    git_dir / "index.lock",
                    git_dir / "HEAD.lock",
                    git_dir / "config.lock",
                ]

                for lock_file in lock_files:
                    if lock_file.exists():
                        # Check age - only remove if older than 5 seconds
                        age = time.time() - lock_file.stat().st_mtime
                        if age > 5:
                            lock_file.unlink()
                            locks_removed += 1

            if locks_removed > 0:
                return {"success": True, "action": "clear_git_locks", "removed": locks_removed}
            return {"success": True, "action": "clear_git_locks", "note": "No stale locks found"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ═══════════════════════════════════════════════════════════
    # CONCURRENCY RECOVERY
    # ═══════════════════════════════════════════════════════════

    def clear_stale_locks(self, error_text: str = None) -> dict:
        """Clear stale session locks."""
        try:
            locks_cleared = 0
            lock_files = [
                Path.home() / ".claude" / ".session.lock",
                Path.home() / ".claude" / "data" / ".lock",
                Path.home() / ".agent-core" / ".session.lock",
            ]

            for lock_file in lock_files:
                if lock_file.exists():
                    # Check age (stale if > 1 hour)
                    age = time.time() - lock_file.stat().st_mtime
                    if age > 3600:
                        lock_file.unlink()
                        locks_cleared += 1

            if locks_cleared > 0:
                return {"success": True, "action": "clear_stale_locks", "cleared": locks_cleared}
            return {"success": True, "action": "clear_stale_locks", "note": "No stale locks found"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def kill_zombie_processes(self, error_text: str = None) -> dict:
        """Kill zombie claude processes."""
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid,state,comm"],
                capture_output=True, text=True
            )
            killed = 0
            for line in result.stdout.split("\n"):
                parts = line.split()
                if len(parts) >= 3:
                    state = parts[1] if len(parts) > 1 else ""
                    comm = parts[2] if len(parts) > 2 else ""
                    if "Z" in state and "claude" in comm.lower():
                        try:
                            pid = int(parts[0])
                            os.kill(pid, signal.SIGKILL)
                            killed += 1
                        except (ValueError, ProcessLookupError):
                            pass

            return {"success": True, "action": "kill_zombie_processes", "killed": killed}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ═══════════════════════════════════════════════════════════
    # PERMISSIONS RECOVERY
    # ═══════════════════════════════════════════════════════════

    def chmod_safe_paths(self, error_text: str = None) -> dict:
        """Fix permissions on known safe paths."""
        try:
            fixed = 0
            for safe_path in SAFE_PATHS:
                if safe_path.exists():
                    # Only fix user read/write, not execute or group/other
                    subprocess.run(
                        ["chmod", "-R", "u+rw", str(safe_path)],
                        capture_output=True,
                        timeout=10
                    )
                    fixed += 1

            return {"success": True, "action": "chmod_safe_paths", "fixed": fixed}
        except subprocess.TimeoutExpired:
            return {"success": False, "reason": "chmod timed out"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ═══════════════════════════════════════════════════════════
    # QUOTA RECOVERY
    # ═══════════════════════════════════════════════════════════

    def clear_cache(self, error_text: str = None) -> dict:
        """Clear non-essential caches."""
        try:
            cache_dirs = [
                Path.home() / ".claude" / "cache",
                Path.home() / ".claude" / "kernel" / "__pycache__",
            ]

            cleared = 0
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    # Only clear files older than 1 day
                    now = time.time()
                    for f in cache_dir.iterdir():
                        if f.is_file() and (now - f.stat().st_mtime) > 86400:
                            try:
                                f.unlink()
                                cleared += 1
                            except Exception:
                                pass

            return {"success": True, "action": "clear_cache", "cleared": cleared}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ═══════════════════════════════════════════════════════════
    # CRASH RECOVERY
    # ═══════════════════════════════════════════════════════════

    def clear_corrupt_state(self, error_text: str = None) -> dict:
        """Clear corrupted state files (regeneratable only)."""
        try:
            import json as json_module

            # Only clear regeneratable files
            regeneratable = [
                "kernel/session-state.json",
                "kernel/token-cache.json",
                "data/current-session.json",
                "kernel/activity.json",
                "kernel/complexity-data.json",
            ]

            cleared = 0
            claude_dir = Path.home() / ".claude"

            for rel_path in regeneratable:
                full_path = claude_dir / rel_path
                if full_path.exists():
                    try:
                        # Test if JSON is valid
                        content = full_path.read_text()
                        if content.strip():
                            json_module.loads(content)
                    except json_module.JSONDecodeError:
                        # Corrupt JSON - remove it
                        full_path.unlink()
                        cleared += 1
                    except Exception:
                        pass

            if cleared > 0:
                return {"success": True, "action": "clear_corrupt_state", "cleared": cleared}
            return {"success": True, "action": "clear_corrupt_state", "note": "No corrupt files found"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ═══════════════════════════════════════════════════════════
    # RECURSION RECOVERY
    # ═══════════════════════════════════════════════════════════

    def kill_runaway_process(self, error_text: str = None) -> dict:
        """Kill runaway processes using excessive CPU."""
        try:
            # Find processes using >90% CPU
            result = subprocess.run(
                ["ps", "-eo", "pid,%cpu,comm", "-r"],
                capture_output=True, text=True
            )

            killed = 0
            protected = ["kernel_task", "WindowServer", "loginwindow", "launchd"]

            for line in result.stdout.split("\n")[1:5]:  # Top 5 by CPU
                parts = line.split()
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        cpu = float(parts[1])
                        comm = parts[2]

                        # Only kill if >90% CPU and not protected
                        if cpu > 90 and comm not in protected and "claude" not in comm.lower():
                            os.kill(pid, signal.SIGTERM)
                            killed += 1
                    except (ValueError, ProcessLookupError):
                        pass

            return {"success": True, "action": "kill_runaway_process", "killed": killed}
        except Exception as e:
            return {"success": False, "reason": str(e)}
