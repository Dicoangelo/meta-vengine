#!/usr/bin/env python3
"""
Agent Registry - Tracks active agents, their state, progress, and cleanup.

Part of the Multi-Agent Coordination System.
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
import fcntl


class AgentState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class AgentRecord:
    """Record of an active or completed agent."""
    agent_id: str
    task_id: str  # Parent coordination task
    subtask: str
    agent_type: str  # explore, general-purpose, Bash, Plan
    model: str  # haiku, sonnet, opus
    state: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    files_locked: List[str] = None
    progress: float = 0.0  # 0-1
    last_heartbeat: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    dq_score: float = 0.5
    cost_estimate: float = 0.0

    def __post_init__(self):
        if self.files_locked is None:
            self.files_locked = []


class AgentRegistry:
    """
    Manages active agent tracking with file-based persistence.

    Features:
    - Thread-safe file locking
    - Heartbeat monitoring for stale agent detection
    - Automatic cleanup of completed/failed agents
    """

    DATA_DIR = Path.home() / ".claude" / "coordinator" / "data"
    AGENTS_FILE = DATA_DIR / "active-agents.json"
    OUTCOMES_FILE = DATA_DIR / "agent-outcomes.jsonl"

    # Timeout thresholds
    HEARTBEAT_TIMEOUT = 60  # seconds - mark stale after this
    AGENT_TIMEOUT = 300  # seconds - default max runtime
    STALE_CLEANUP = 600  # seconds - auto-cleanup after this

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_files()

    def _ensure_files(self):
        """Ensure data files exist."""
        if not self.AGENTS_FILE.exists():
            self._write_agents({})
        if not self.OUTCOMES_FILE.exists():
            self.OUTCOMES_FILE.touch()

    def _read_agents(self) -> Dict[str, Dict]:
        """Read agents with file locking."""
        try:
            with open(self.AGENTS_FILE, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_agents(self, data: Dict):
        """Write agents with file locking."""
        with open(self.AGENTS_FILE, 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def register(self,
                 task_id: str,
                 subtask: str,
                 agent_type: str,
                 model: str = "sonnet",
                 files_to_lock: List[str] = None,
                 dq_score: float = 0.5,
                 cost_estimate: float = 0.0) -> str:
        """
        Register a new agent.

        Returns:
            agent_id: Unique identifier for the agent
        """
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"

        record = AgentRecord(
            agent_id=agent_id,
            task_id=task_id,
            subtask=subtask,
            agent_type=agent_type,
            model=model,
            state=AgentState.PENDING.value,
            created_at=datetime.now().isoformat(),
            files_locked=files_to_lock or [],
            dq_score=dq_score,
            cost_estimate=cost_estimate
        )

        agents = self._read_agents()
        agents[agent_id] = asdict(record)
        self._write_agents(agents)

        return agent_id

    def start(self, agent_id: str):
        """Mark agent as started."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["state"] = AgentState.RUNNING.value
            agents[agent_id]["started_at"] = datetime.now().isoformat()
            agents[agent_id]["last_heartbeat"] = datetime.now().isoformat()
            self._write_agents(agents)

    def heartbeat(self, agent_id: str, progress: float = None):
        """Update agent heartbeat."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["last_heartbeat"] = datetime.now().isoformat()
            if progress is not None:
                agents[agent_id]["progress"] = min(1.0, max(0.0, progress))
            self._write_agents(agents)

    def complete(self, agent_id: str, result: Dict = None):
        """Mark agent as completed."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["state"] = AgentState.COMPLETED.value
            agents[agent_id]["completed_at"] = datetime.now().isoformat()
            agents[agent_id]["progress"] = 1.0
            agents[agent_id]["result"] = result
            self._write_agents(agents)
            self._log_outcome(agents[agent_id])

    def fail(self, agent_id: str, error: str):
        """Mark agent as failed."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["state"] = AgentState.FAILED.value
            agents[agent_id]["completed_at"] = datetime.now().isoformat()
            agents[agent_id]["error"] = error
            self._write_agents(agents)
            self._log_outcome(agents[agent_id])

    def timeout(self, agent_id: str):
        """Mark agent as timed out."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["state"] = AgentState.TIMEOUT.value
            agents[agent_id]["completed_at"] = datetime.now().isoformat()
            agents[agent_id]["error"] = "Agent timed out"
            self._write_agents(agents)
            self._log_outcome(agents[agent_id])

    def cancel(self, agent_id: str):
        """Cancel an agent."""
        agents = self._read_agents()
        if agent_id in agents:
            agents[agent_id]["state"] = AgentState.CANCELLED.value
            agents[agent_id]["completed_at"] = datetime.now().isoformat()
            self._write_agents(agents)
            self._log_outcome(agents[agent_id])

    def get(self, agent_id: str) -> Optional[AgentRecord]:
        """Get agent by ID."""
        agents = self._read_agents()
        if agent_id in agents:
            return AgentRecord(**agents[agent_id])
        return None

    def get_task_agents(self, task_id: str) -> List[AgentRecord]:
        """Get all agents for a coordination task."""
        agents = self._read_agents()
        return [
            AgentRecord(**a) for a in agents.values()
            if a.get("task_id") == task_id
        ]

    def get_active(self) -> List[AgentRecord]:
        """Get all running agents."""
        agents = self._read_agents()
        return [
            AgentRecord(**a) for a in agents.values()
            if a.get("state") in [AgentState.PENDING.value, AgentState.RUNNING.value]
        ]

    def get_stale(self) -> List[AgentRecord]:
        """Get agents with stale heartbeats."""
        agents = self._read_agents()
        now = time.time()
        stale = []

        for a in agents.values():
            if a.get("state") != AgentState.RUNNING.value:
                continue

            last_hb = a.get("last_heartbeat")
            if last_hb:
                hb_time = datetime.fromisoformat(last_hb).timestamp()
                if now - hb_time > self.HEARTBEAT_TIMEOUT:
                    stale.append(AgentRecord(**a))

        return stale

    def cleanup_completed(self, older_than_seconds: int = None):
        """Remove completed/failed agents from active tracking."""
        if older_than_seconds is None:
            older_than_seconds = self.STALE_CLEANUP

        agents = self._read_agents()
        now = time.time()
        to_remove = []

        for agent_id, a in agents.items():
            if a.get("state") not in [
                AgentState.COMPLETED.value,
                AgentState.FAILED.value,
                AgentState.TIMEOUT.value,
                AgentState.CANCELLED.value
            ]:
                continue

            completed_at = a.get("completed_at")
            if completed_at:
                completed_time = datetime.fromisoformat(completed_at).timestamp()
                if now - completed_time > older_than_seconds:
                    to_remove.append(agent_id)

        for agent_id in to_remove:
            del agents[agent_id]

        self._write_agents(agents)
        return len(to_remove)

    def _log_outcome(self, agent_data: Dict):
        """Append agent outcome to JSONL log."""
        with open(self.OUTCOMES_FILE, 'a') as f:
            f.write(json.dumps({
                "timestamp": datetime.now().isoformat(),
                **agent_data
            }) + "\n")

    def get_stats(self) -> Dict:
        """Get registry statistics."""
        agents = self._read_agents()

        by_state = {}
        by_model = {}
        total_cost = 0.0

        for a in agents.values():
            state = a.get("state", "unknown")
            model = a.get("model", "unknown")
            cost = a.get("cost_estimate", 0.0)

            by_state[state] = by_state.get(state, 0) + 1
            by_model[model] = by_model.get(model, 0) + 1
            total_cost += cost

        return {
            "total_agents": len(agents),
            "by_state": by_state,
            "by_model": by_model,
            "total_cost_estimate": total_cost,
            "active_count": len(self.get_active()),
            "stale_count": len(self.get_stale())
        }


# CLI interface
if __name__ == "__main__":
    import sys

    registry = AgentRegistry()

    if len(sys.argv) < 2:
        print("Usage: registry.py <command> [args]")
        print("Commands: list, stats, cleanup, get <id>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        agents = registry.get_active()
        if not agents:
            print("No active agents")
        else:
            print(f"Active agents: {len(agents)}")
            for a in agents:
                print(f"  {a.agent_id}: {a.subtask} [{a.state}] ({a.model})")

    elif cmd == "stats":
        stats = registry.get_stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "cleanup":
        removed = registry.cleanup_completed()
        print(f"Cleaned up {removed} completed agents")

    elif cmd == "get" and len(sys.argv) > 2:
        agent = registry.get(sys.argv[2])
        if agent:
            print(json.dumps(asdict(agent), indent=2))
        else:
            print("Agent not found")

    else:
        print(f"Unknown command: {cmd}")
