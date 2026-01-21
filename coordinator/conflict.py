#!/usr/bin/env python3
"""
Conflict Manager - File locking to prevent write conflicts between agents.

Rules:
- Multiple readers OK (no conflict)
- Single writer exclusive
- Writer conflicts with all other locks
"""

import json
import time
import fcntl
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class LockType(str, Enum):
    READ = "read"
    WRITE = "write"


@dataclass
class FileLock:
    """A lock on a file."""
    path: str
    agent_id: str
    lock_type: str
    acquired_at: str
    expires_at: Optional[str] = None


class ConflictManager:
    """
    Manages file locks for multi-agent coordination.

    Prevents:
    - Multiple writers to same file
    - Writers when readers exist
    - Readers when writer exists
    """

    DATA_DIR = Path.home() / ".claude" / "coordinator" / "data"
    LOCKS_FILE = DATA_DIR / "file-locks.json"

    # Lock timeout (auto-release stale locks)
    LOCK_TIMEOUT = 600  # 10 minutes

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        """Ensure locks file exists."""
        if not self.LOCKS_FILE.exists():
            self._write_locks({})

    def _read_locks(self) -> Dict[str, List[Dict]]:
        """Read locks with file locking."""
        try:
            with open(self.LOCKS_FILE, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_locks(self, data: Dict):
        """Write locks with file locking."""
        with open(self.LOCKS_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _normalize_path(self, path: str) -> str:
        """Normalize path for consistent comparison."""
        return str(Path(path).resolve())

    def _cleanup_expired(self, locks: Dict) -> Dict:
        """Remove expired locks."""
        now = time.time()
        cleaned = {}

        for path, lock_list in locks.items():
            valid_locks = []
            for lock in lock_list:
                acquired = datetime.fromisoformat(lock["acquired_at"]).timestamp()
                if now - acquired < self.LOCK_TIMEOUT:
                    valid_locks.append(lock)
            if valid_locks:
                cleaned[path] = valid_locks

        return cleaned

    def check_conflicts(self, paths: List[str], lock_type: str, agent_id: str = None) -> List[Tuple[str, str, str]]:
        """
        Check if acquiring locks would conflict.

        Args:
            paths: Files to check
            lock_type: "read" or "write"
            agent_id: Agent requesting (to allow self-upgrade)

        Returns:
            List of (path, conflicting_agent_id, conflict_reason)
        """
        locks = self._read_locks()
        locks = self._cleanup_expired(locks)
        conflicts = []

        for path in paths:
            norm_path = self._normalize_path(path)
            existing = locks.get(norm_path, [])

            for lock in existing:
                # Skip own locks
                if agent_id and lock["agent_id"] == agent_id:
                    continue

                # Write conflicts with everything
                if lock_type == LockType.WRITE.value:
                    conflicts.append((
                        path,
                        lock["agent_id"],
                        f"File has existing {lock['lock_type']} lock"
                    ))
                    break

                # Read conflicts with write
                elif lock["lock_type"] == LockType.WRITE.value:
                    conflicts.append((
                        path,
                        lock["agent_id"],
                        "File has existing write lock"
                    ))
                    break

        return conflicts

    def check_all(self, subtasks: List[Dict]) -> List[Tuple[str, str, str]]:
        """
        Check all subtasks for file conflicts.

        Args:
            subtasks: List of subtask dicts with 'files' and 'lock_type' keys

        Returns:
            List of all conflicts found
        """
        all_conflicts = []

        for subtask in subtasks:
            files = subtask.get("files", [])
            lock_type = subtask.get("lock_type", LockType.READ.value)
            agent_id = subtask.get("agent_id")

            conflicts = self.check_conflicts(files, lock_type, agent_id)
            all_conflicts.extend(conflicts)

        return all_conflicts

    def acquire(self, path: str, agent_id: str, lock_type: str) -> bool:
        """
        Acquire a lock on a file.

        Args:
            path: File path
            agent_id: Agent ID
            lock_type: "read" or "write"

        Returns:
            True if acquired, False if conflict
        """
        norm_path = self._normalize_path(path)

        # Check conflicts first
        conflicts = self.check_conflicts([path], lock_type, agent_id)
        if conflicts:
            return False

        locks = self._read_locks()
        locks = self._cleanup_expired(locks)

        # Add lock
        if norm_path not in locks:
            locks[norm_path] = []

        # Remove any existing lock by this agent (upgrade/downgrade)
        locks[norm_path] = [l for l in locks[norm_path] if l["agent_id"] != agent_id]

        locks[norm_path].append({
            "path": path,
            "agent_id": agent_id,
            "lock_type": lock_type,
            "acquired_at": datetime.now().isoformat()
        })

        self._write_locks(locks)
        return True

    def acquire_batch(self, files: List[str], agent_id: str, lock_type: str) -> Tuple[bool, List[str]]:
        """
        Acquire locks on multiple files atomically.

        Returns:
            (success, list of failed files)
        """
        # Check all conflicts first
        conflicts = self.check_conflicts(files, lock_type, agent_id)
        if conflicts:
            return False, [c[0] for c in conflicts]

        # Acquire all
        for path in files:
            if not self.acquire(path, agent_id, lock_type):
                # Rollback acquired locks
                self.release_agent(agent_id)
                return False, [path]

        return True, []

    def release(self, path: str, agent_id: str):
        """Release a lock on a file."""
        norm_path = self._normalize_path(path)

        locks = self._read_locks()
        if norm_path in locks:
            locks[norm_path] = [
                l for l in locks[norm_path]
                if l["agent_id"] != agent_id
            ]
            if not locks[norm_path]:
                del locks[norm_path]

        self._write_locks(locks)

    def release_agent(self, agent_id: str):
        """Release all locks held by an agent."""
        locks = self._read_locks()
        cleaned = {}

        for path, lock_list in locks.items():
            remaining = [l for l in lock_list if l["agent_id"] != agent_id]
            if remaining:
                cleaned[path] = remaining

        self._write_locks(cleaned)

    def get_agent_locks(self, agent_id: str) -> List[FileLock]:
        """Get all locks held by an agent."""
        locks = self._read_locks()
        agent_locks = []

        for path, lock_list in locks.items():
            for lock in lock_list:
                if lock["agent_id"] == agent_id:
                    agent_locks.append(FileLock(**lock))

        return agent_locks

    def get_file_locks(self, path: str) -> List[FileLock]:
        """Get all locks on a file."""
        norm_path = self._normalize_path(path)
        locks = self._read_locks()

        if norm_path in locks:
            return [FileLock(**l) for l in locks[norm_path]]
        return []

    def cleanup_stale(self) -> int:
        """Remove all stale locks."""
        locks = self._read_locks()
        cleaned = self._cleanup_expired(locks)
        self._write_locks(cleaned)

        # Count removed
        old_count = sum(len(v) for v in locks.values())
        new_count = sum(len(v) for v in cleaned.values())
        return old_count - new_count

    def get_stats(self) -> Dict:
        """Get lock statistics."""
        locks = self._read_locks()

        total_locks = sum(len(v) for v in locks.values())
        read_locks = sum(
            1 for v in locks.values()
            for l in v if l["lock_type"] == LockType.READ.value
        )
        write_locks = total_locks - read_locks

        agents = set()
        for v in locks.values():
            for l in v:
                agents.add(l["agent_id"])

        return {
            "total_locks": total_locks,
            "read_locks": read_locks,
            "write_locks": write_locks,
            "files_locked": len(locks),
            "agents_with_locks": len(agents)
        }


def detect_potential_conflicts(subtasks: List[Dict]) -> Dict:
    """
    Pre-flight check for potential conflicts between planned subtasks.

    Args:
        subtasks: List of subtasks with 'files' (list of paths) and 'lock_type'

    Returns:
        {
            "has_conflicts": bool,
            "can_parallelize": bool,
            "conflicts": [...],
            "parallel_groups": [[subtask_indices], ...]
        }
    """
    # Track which files each subtask needs
    file_usage = {}  # path -> [(subtask_idx, lock_type)]

    for idx, subtask in enumerate(subtasks):
        files = subtask.get("files", [])
        lock_type = subtask.get("lock_type", LockType.READ.value)

        for path in files:
            norm_path = str(Path(path).resolve())
            if norm_path not in file_usage:
                file_usage[norm_path] = []
            file_usage[norm_path].append((idx, lock_type))

    # Find conflicts
    conflicts = []
    conflicting_pairs = set()

    for path, usages in file_usage.items():
        if len(usages) <= 1:
            continue

        # Check each pair
        for i, (idx1, lock1) in enumerate(usages):
            for idx2, lock2 in usages[i + 1:]:
                # Conflict if any is a writer
                if lock1 == LockType.WRITE.value or lock2 == LockType.WRITE.value:
                    conflicts.append({
                        "path": path,
                        "subtasks": [idx1, idx2],
                        "locks": [lock1, lock2]
                    })
                    conflicting_pairs.add((min(idx1, idx2), max(idx1, idx2)))

    # Build parallel groups (subtasks that don't conflict)
    n = len(subtasks)
    parallel_groups = []
    assigned = set()

    for idx in range(n):
        if idx in assigned:
            continue

        # Start new group
        group = [idx]
        assigned.add(idx)

        # Try to add others that don't conflict with group
        for other in range(idx + 1, n):
            if other in assigned:
                continue

            # Check if other conflicts with anyone in group
            can_add = True
            for member in group:
                if (min(member, other), max(member, other)) in conflicting_pairs:
                    can_add = False
                    break

            if can_add:
                group.append(other)
                assigned.add(other)

        parallel_groups.append(group)

    return {
        "has_conflicts": len(conflicts) > 0,
        "can_parallelize": len(parallel_groups) > 0 and any(len(g) > 1 for g in parallel_groups),
        "conflicts": conflicts,
        "parallel_groups": parallel_groups
    }


# CLI interface
if __name__ == "__main__":
    import sys

    mgr = ConflictManager()

    if len(sys.argv) < 2:
        print("Usage: conflict.py <command> [args]")
        print("Commands: status, check <path> <type>, cleanup, agent <id>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        stats = mgr.get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "check" and len(sys.argv) >= 4:
        path = sys.argv[2]
        lock_type = sys.argv[3]
        conflicts = mgr.check_conflicts([path], lock_type)
        if conflicts:
            print("Conflicts found:")
            for path, agent, reason in conflicts:
                print(f"  {path}: {reason} (by {agent})")
        else:
            print("No conflicts")

    elif cmd == "cleanup":
        removed = mgr.cleanup_stale()
        print(f"Cleaned up {removed} stale locks")

    elif cmd == "agent" and len(sys.argv) > 2:
        agent_id = sys.argv[2]
        locks = mgr.get_agent_locks(agent_id)
        if locks:
            print(f"Locks held by {agent_id}:")
            for lock in locks:
                print(f"  {lock.path}: {lock.lock_type}")
        else:
            print("No locks held")

    else:
        print(f"Unknown command: {cmd}")
