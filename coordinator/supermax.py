#!/usr/bin/env python3
"""
SUPERMAX v2 — Adaptive Agent Count with Difficulty-Aware Spawning + Free-MAD Trajectory Scoring.

US-007: Dynamically selects agent count (1-5) based on graphComplexity
from the multi-feature graph signal (US-004). Simple queries use 1 agent,
complex queries get full council evaluation.

US-008: Free-MAD trajectory scoring replaces weighted averaging. Agent
stability (not agreement speed) determines consensus quality. Sycophancy
detection via unanimous convergence flagging.

Agent priority order:
  1. Principal Engineer (technical correctness, waste penalties)
  2. Security Architect (risk, safety margins, compliance)
  3. Product Strategist (user value, speed, cost)
  4. Contrarian (adversarial challenge, from ACE)
  5. Arbiter (final adjudication, cross-perspective synthesis)

All thresholds stored in config/supermax-v2.json (learnable, not hardcoded).
"""

import json
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# Resolve paths relative to the meta-vengine root
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "supermax-v2.json"
_COSTS_DIR = _ROOT / "data"


@dataclass
class AgentSpec:
    """Specification for a SUPERMAX agent to spawn."""
    name: str
    perspective: str
    model: str
    index: int  # priority order (0-based)


@dataclass
class SpawnPlan:
    """Result of PredictiveSpawner.plan() — describes which agents to spawn."""
    graph_complexity: float
    difficulty_tier: str
    agent_count: int
    agents: List[AgentSpec]
    thresholds_used: Dict[str, Any]


def load_config(config_path: Path = None) -> dict:
    """Load SUPERMAX v2 config from JSON. Falls back to defaults if missing."""
    path = config_path or _CONFIG_PATH
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    # Emergency fallback — should never be used in production
    return {
        "agentCountThresholds": {
            "trivial": {"max": 0.25, "agentCount": 1},
            "simple": {"max": 0.45, "agentCount": 2},
            "moderate": {"max": 0.65, "agentCount": 3},
            "complex": {"max": 0.85, "agentCount": 4},
            "expert": {"max": 1.00, "agentCount": 5},
        },
        "agentPriority": [
            {"name": "PrincipalEngineer", "perspective": "Technical correctness, waste penalties", "model": "sonnet"},
            {"name": "SecurityArchitect", "perspective": "Risk, safety margins, compliance", "model": "sonnet"},
            {"name": "ProductStrategist", "perspective": "User value, speed, cost", "model": "sonnet"},
            {"name": "Contrarian", "perspective": "Adversarial challenge, assumption stress-testing", "model": "sonnet"},
            {"name": "Arbiter", "perspective": "Final adjudication, cross-perspective synthesis", "model": "opus"},
        ],
        "constraints": {"minAgents": 1, "maxAgents": 5, "defaultAgentCount": 3},
    }


class PredictiveSpawner:
    """
    Difficulty-aware agent spawner for SUPERMAX v2.

    Consumes graphComplexity (0.0-1.0) from the multi-feature graph signal
    (US-004) and selects the appropriate number of council agents.

    Thresholds and agent definitions are loaded from config/supermax-v2.json
    (learnable — future Optimas LRF).
    """

    def __init__(self, config_path: Path = None):
        self.config = load_config(config_path)
        self._thresholds = self._parse_thresholds()
        self._agents = self._parse_agents()
        self._constraints = self.config.get("constraints", {})

    def _parse_thresholds(self) -> List[dict]:
        """Parse and sort thresholds by max value ascending."""
        raw = self.config.get("agentCountThresholds", {})
        tiers = []
        for tier_name, tier_data in raw.items():
            tiers.append({
                "tier": tier_name,
                "max": tier_data["max"],
                "agentCount": tier_data["agentCount"],
            })
        tiers.sort(key=lambda t: t["max"])
        return tiers

    def _parse_agents(self) -> List[AgentSpec]:
        """Parse agent priority list from config."""
        raw = self.config.get("agentPriority", [])
        agents = []
        for i, entry in enumerate(raw):
            agents.append(AgentSpec(
                name=entry["name"],
                perspective=entry.get("perspective", ""),
                model=entry.get("model", "sonnet"),
                index=i,
            ))
        return agents

    def classify_difficulty(self, graph_complexity: float) -> tuple:
        """
        Classify a graphComplexity score into a difficulty tier and agent count.

        Args:
            graph_complexity: 0.0-1.0 composite score from computeGraphSignal()

        Returns:
            (tier_name, agent_count) tuple
        """
        clamped = max(0.0, min(1.0, graph_complexity))

        for tier in self._thresholds:
            if clamped < tier["max"] or (clamped == tier["max"] and tier["tier"] == "expert"):
                return tier["tier"], tier["agentCount"]

        # Fallback: if complexity exactly equals 1.0 and no tier matched
        if self._thresholds:
            last = self._thresholds[-1]
            return last["tier"], last["agentCount"]

        # Ultimate fallback
        default_count = self._constraints.get("defaultAgentCount", 3)
        return "unknown", default_count

    def select_agents(self, count: int) -> List[AgentSpec]:
        """
        Select agents in priority order up to the given count.

        Priority: PrincipalEngineer > SecurityArchitect > ProductStrategist > Contrarian > Arbiter

        Args:
            count: Number of agents to select (1-5)

        Returns:
            List of AgentSpec in priority order
        """
        min_agents = self._constraints.get("minAgents", 1)
        max_agents = self._constraints.get("maxAgents", 5)
        clamped_count = max(min_agents, min(max_agents, count))

        return self._agents[:clamped_count]

    def plan(self, graph_complexity: float) -> SpawnPlan:
        """
        Create a spawn plan based on graphComplexity.

        This is the main entry point — takes a difficulty score and returns
        a complete plan for which agents to spawn.

        Args:
            graph_complexity: 0.0-1.0 from computeGraphSignal() (US-004)

        Returns:
            SpawnPlan with tier, count, and agent list
        """
        tier, count = self.classify_difficulty(graph_complexity)
        agents = self.select_agents(count)

        return SpawnPlan(
            graph_complexity=graph_complexity,
            difficulty_tier=tier,
            agent_count=len(agents),
            agents=agents,
            thresholds_used={t["tier"]: t for t in self._thresholds},
        )

    def plan_with_default(self, graph_complexity: Optional[float] = None) -> SpawnPlan:
        """
        Plan with graceful degradation when graphComplexity is unavailable.

        Falls back to the default agent count from config when no
        graph signal is available.

        Args:
            graph_complexity: 0.0-1.0 or None if unavailable

        Returns:
            SpawnPlan
        """
        if graph_complexity is not None:
            return self.plan(graph_complexity)

        # Fallback: use default agent count
        default_count = self._constraints.get("defaultAgentCount", 3)
        agents = self.select_agents(default_count)

        return SpawnPlan(
            graph_complexity=-1.0,  # sentinel: unavailable
            difficulty_tier="default",
            agent_count=len(agents),
            agents=agents,
            thresholds_used={t["tier"]: t for t in self._thresholds},
        )


class SupermaxV2:
    """
    Full SUPERMAX v2 orchestrator combining adaptive spawning (US-007)
    with Free-MAD trajectory scoring (US-008).

    Usage:
        v2 = SupermaxV2()
        plan = v2.plan_agents(graph_complexity=0.7)
        # ... agents evaluate Round 1 ...
        peer_context = v2.prepare_peer_context(round1_evals)
        # ... agents evaluate Round 2 with peer context ...
        result = v2.synthesize(round1_evals, round2_evals)
        v2.log(query_hash, plan, result)
    """

    def __init__(self, config_path: Path = None):
        from coordinator.synthesizer import FreeMadSynthesizer
        self.spawner = PredictiveSpawner(config_path)
        self.synthesizer = FreeMadSynthesizer(config_path)

    def plan_agents(self, graph_complexity: float = None) -> SpawnPlan:
        """Plan agent spawning based on graph complexity."""
        return self.spawner.plan_with_default(graph_complexity)

    def prepare_peer_context(self, round1_evals):
        """Anonymize Round 1 evaluations for peer sharing."""
        return self.synthesizer.prepare_peer_context(round1_evals)

    def synthesize(self, round1_evals, round2_evals):
        """Run Free-MAD trajectory synthesis."""
        return self.synthesizer.synthesize(round1_evals, round2_evals)

    def log(self, query_hash: str, plan: SpawnPlan, result=None, cost_estimate: float = 0.0):
        """Log both cost and trajectory data."""
        from coordinator.synthesizer import log_trajectory
        log_supermax_cost(
            query_hash=query_hash,
            agent_count=plan.agent_count,
            difficulty_tier=plan.difficulty_tier,
            graph_complexity=plan.graph_complexity,
            agents_used=[a.name for a in plan.agents],
            cost_estimate=cost_estimate,
        )
        if result is not None:
            log_trajectory(query_hash, result)


def log_supermax_cost(
    query_hash: str,
    agent_count: int,
    difficulty_tier: str,
    graph_complexity: float,
    agents_used: List[str],
    cost_estimate: float = 0.0,
    log_dir: Path = None,
):
    """
    Append cost tracking entry to data/supermax-costs.jsonl.

    Args:
        query_hash: MD5 hash of the query
        agent_count: Number of agents spawned
        difficulty_tier: Classified difficulty tier
        graph_complexity: The graphComplexity score used
        agents_used: List of agent names
        cost_estimate: Estimated USD cost
        log_dir: Override for the data directory
    """
    out_dir = log_dir or _COSTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "supermax-costs.jsonl"

    entry = {
        "ts": datetime.now(tz=__import__('datetime').timezone.utc).isoformat(),
        "query_hash": query_hash,
        "agent_count": agent_count,
        "difficulty_tier": difficulty_tier,
        "graph_complexity": graph_complexity,
        "agents_used": agents_used,
        "cost_estimate": cost_estimate,
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI interface
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for SUPERMAX v2."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SUPERMAX v2 — Adaptive Agent Count",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 coordinator/supermax.py plan 0.15    # trivial → 1 agent
  python3 coordinator/supermax.py plan 0.50    # moderate → 3 agents
  python3 coordinator/supermax.py plan 0.90    # expert → 5 agents
  python3 coordinator/supermax.py classify 0.30  # → simple, 2 agents
        """,
    )

    parser.add_argument("command", choices=["plan", "classify", "config"])
    parser.add_argument("complexity", nargs="?", type=float, help="graphComplexity (0.0-1.0)")

    args = parser.parse_args()

    spawner = PredictiveSpawner()

    if args.command == "config":
        print(json.dumps(spawner.config, indent=2))

    elif args.command == "classify":
        if args.complexity is None:
            parser.error("classify requires a complexity value")
        tier, count = spawner.classify_difficulty(args.complexity)
        print(f"Complexity: {args.complexity}")
        print(f"Tier: {tier}")
        print(f"Agent count: {count}")

    elif args.command == "plan":
        if args.complexity is None:
            parser.error("plan requires a complexity value")
        plan = spawner.plan(args.complexity)
        print(f"Complexity: {plan.graph_complexity}")
        print(f"Tier: {plan.difficulty_tier}")
        print(f"Agent count: {plan.agent_count}")
        print(f"Agents:")
        for a in plan.agents:
            print(f"  {a.index + 1}. {a.name} ({a.model}) — {a.perspective}")


if __name__ == "__main__":
    main()
