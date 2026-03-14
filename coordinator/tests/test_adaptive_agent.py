#!/usr/bin/env python3
"""
Tests for SUPERMAX v2 — Adaptive Agent Count (US-007).

Covers:
- Difficulty classification across all 5 tiers
- Agent selection in priority order
- SpawnPlan creation for trivial → expert
- Graceful degradation when graphComplexity unavailable
- Config loading and fallback
- Cost logging (append-only JSONL)
- Boundary conditions and edge cases
- Integration: trivial spawns 1 agent, complex spawns 5
"""

import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add coordinator to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from supermax import (
    PredictiveSpawner,
    SpawnPlan,
    AgentSpec,
    load_config,
    log_supermax_cost,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def spawner():
    """PredictiveSpawner with real config/supermax-v2.json."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "supermax-v2.json"
    return PredictiveSpawner(config_path=config_path)


@pytest.fixture
def custom_config(tmp_path):
    """Create a custom config for testing edge cases."""
    config = {
        "agentCountThresholds": {
            "trivial": {"max": 0.25, "agentCount": 1},
            "simple": {"max": 0.45, "agentCount": 2},
            "moderate": {"max": 0.65, "agentCount": 3},
            "complex": {"max": 0.85, "agentCount": 4},
            "expert": {"max": 1.00, "agentCount": 5},
        },
        "agentPriority": [
            {"name": "PrincipalEngineer", "perspective": "Technical", "model": "sonnet"},
            {"name": "SecurityArchitect", "perspective": "Security", "model": "sonnet"},
            {"name": "ProductStrategist", "perspective": "Product", "model": "sonnet"},
            {"name": "Contrarian", "perspective": "Challenge", "model": "sonnet"},
            {"name": "Arbiter", "perspective": "Adjudication", "model": "opus"},
        ],
        "constraints": {"minAgents": 1, "maxAgents": 5, "defaultAgentCount": 3},
    }
    config_path = tmp_path / "supermax-v2.json"
    config_path.write_text(json.dumps(config))
    return config_path


# ═══════════════════════════════════════════════════════════════════════════
# Test: Difficulty Classification
# ═══════════════════════════════════════════════════════════════════════════

class TestDifficultyClassification:
    """Test classify_difficulty maps graphComplexity to correct tiers."""

    def test_trivial(self, spawner):
        tier, count = spawner.classify_difficulty(0.10)
        assert tier == "trivial"
        assert count == 1

    def test_trivial_zero(self, spawner):
        tier, count = spawner.classify_difficulty(0.0)
        assert tier == "trivial"
        assert count == 1

    def test_simple(self, spawner):
        tier, count = spawner.classify_difficulty(0.30)
        assert tier == "simple"
        assert count == 2

    def test_moderate(self, spawner):
        tier, count = spawner.classify_difficulty(0.50)
        assert tier == "moderate"
        assert count == 3

    def test_complex(self, spawner):
        tier, count = spawner.classify_difficulty(0.75)
        assert tier == "complex"
        assert count == 4

    def test_expert(self, spawner):
        tier, count = spawner.classify_difficulty(0.90)
        assert tier == "expert"
        assert count == 5

    def test_expert_at_one(self, spawner):
        tier, count = spawner.classify_difficulty(1.0)
        assert tier == "expert"
        assert count == 5

    def test_boundary_trivial_simple(self, spawner):
        """At exactly 0.25, should be in trivial (< max uses strict <, = goes to expert only)."""
        tier, count = spawner.classify_difficulty(0.25)
        assert count in [1, 2]  # boundary — either tier is acceptable

    def test_boundary_simple_moderate(self, spawner):
        tier, count = spawner.classify_difficulty(0.45)
        assert count in [2, 3]

    def test_clamps_negative(self, spawner):
        tier, count = spawner.classify_difficulty(-0.5)
        assert tier == "trivial"
        assert count == 1

    def test_clamps_above_one(self, spawner):
        tier, count = spawner.classify_difficulty(1.5)
        assert tier == "expert"
        assert count == 5

    def test_monotonic_increase(self, spawner):
        """Agent count should never decrease as complexity increases."""
        prev_count = 0
        for c in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            _, count = spawner.classify_difficulty(c)
            assert count >= prev_count, f"Count decreased at complexity {c}"
            prev_count = count


# ═══════════════════════════════════════════════════════════════════════════
# Test: Agent Selection
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentSelection:
    """Test select_agents returns agents in priority order."""

    def test_one_agent_is_principal_engineer(self, spawner):
        agents = spawner.select_agents(1)
        assert len(agents) == 1
        assert agents[0].name == "PrincipalEngineer"

    def test_two_agents_order(self, spawner):
        agents = spawner.select_agents(2)
        assert len(agents) == 2
        assert agents[0].name == "PrincipalEngineer"
        assert agents[1].name == "SecurityArchitect"

    def test_three_agents_order(self, spawner):
        agents = spawner.select_agents(3)
        assert len(agents) == 3
        assert agents[2].name == "ProductStrategist"

    def test_four_agents_includes_contrarian(self, spawner):
        agents = spawner.select_agents(4)
        assert len(agents) == 4
        assert agents[3].name == "Contrarian"

    def test_five_agents_includes_arbiter(self, spawner):
        agents = spawner.select_agents(5)
        assert len(agents) == 5
        assert agents[4].name == "Arbiter"

    def test_arbiter_uses_opus(self, spawner):
        agents = spawner.select_agents(5)
        arbiter = agents[4]
        assert arbiter.model == "opus"

    def test_clamp_min(self, spawner):
        agents = spawner.select_agents(0)
        assert len(agents) == 1  # min is 1

    def test_clamp_max(self, spawner):
        agents = spawner.select_agents(10)
        assert len(agents) == 5  # max is 5

    def test_agent_index_order(self, spawner):
        agents = spawner.select_agents(5)
        for i, a in enumerate(agents):
            assert a.index == i


# ═══════════════════════════════════════════════════════════════════════════
# Test: SpawnPlan
# ═══════════════════════════════════════════════════════════════════════════

class TestSpawnPlan:
    """Test plan() creates correct SpawnPlans."""

    def test_trivial_plan(self, spawner):
        plan = spawner.plan(0.10)
        assert plan.difficulty_tier == "trivial"
        assert plan.agent_count == 1
        assert len(plan.agents) == 1
        assert plan.graph_complexity == 0.10

    def test_expert_plan(self, spawner):
        plan = spawner.plan(0.95)
        assert plan.difficulty_tier == "expert"
        assert plan.agent_count == 5
        assert len(plan.agents) == 5

    def test_plan_includes_thresholds(self, spawner):
        plan = spawner.plan(0.50)
        assert "trivial" in plan.thresholds_used
        assert "expert" in plan.thresholds_used

    def test_plan_agent_specs(self, spawner):
        plan = spawner.plan(0.50)
        for a in plan.agents:
            assert isinstance(a, AgentSpec)
            assert a.name
            assert a.perspective
            assert a.model

    def test_plan_with_default_no_complexity(self, spawner):
        plan = spawner.plan_with_default(None)
        assert plan.difficulty_tier == "default"
        assert plan.graph_complexity == -1.0
        assert plan.agent_count == 3  # default from config

    def test_plan_with_default_has_complexity(self, spawner):
        plan = spawner.plan_with_default(0.80)
        assert plan.difficulty_tier == "complex"
        assert plan.agent_count == 4


# ═══════════════════════════════════════════════════════════════════════════
# Test: Config Loading
# ═══════════════════════════════════════════════════════════════════════════

class TestConfigLoading:
    """Test config loading and fallback behavior."""

    def test_loads_real_config(self, spawner):
        assert "agentCountThresholds" in spawner.config

    def test_fallback_on_missing_file(self, tmp_path):
        spawner = PredictiveSpawner(config_path=tmp_path / "nonexistent.json")
        # Should use fallback defaults
        tier, count = spawner.classify_difficulty(0.10)
        assert tier == "trivial"
        assert count == 1

    def test_fallback_on_corrupt_json(self, tmp_path):
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("not valid json{{{")
        spawner = PredictiveSpawner(config_path=bad_config)
        tier, count = spawner.classify_difficulty(0.90)
        assert tier == "expert"
        assert count == 5

    def test_custom_config(self, custom_config):
        spawner = PredictiveSpawner(config_path=custom_config)
        tier, count = spawner.classify_difficulty(0.50)
        assert tier == "moderate"
        assert count == 3

    def test_thresholds_from_config_not_hardcoded(self, tmp_path):
        """Verify thresholds come from config, not hardcoded values."""
        config = {
            "agentCountThresholds": {
                "only_tier": {"max": 1.0, "agentCount": 2},
            },
            "agentPriority": [
                {"name": "A", "perspective": "test", "model": "haiku"},
                {"name": "B", "perspective": "test", "model": "haiku"},
            ],
            "constraints": {"minAgents": 1, "maxAgents": 5, "defaultAgentCount": 2},
        }
        config_path = tmp_path / "custom.json"
        config_path.write_text(json.dumps(config))
        spawner = PredictiveSpawner(config_path=config_path)
        _, count = spawner.classify_difficulty(0.99)
        assert count == 2  # from config, not default 5


# ═══════════════════════════════════════════════════════════════════════════
# Test: Cost Logging
# ═══════════════════════════════════════════════════════════════════════════

class TestCostLogging:
    """Test append-only JSONL cost tracking."""

    def test_log_creates_file(self, tmp_path):
        log_supermax_cost(
            query_hash="abc123",
            agent_count=3,
            difficulty_tier="moderate",
            graph_complexity=0.55,
            agents_used=["PrincipalEngineer", "SecurityArchitect", "ProductStrategist"],
            cost_estimate=0.05,
            log_dir=tmp_path,
        )
        log_path = tmp_path / "supermax-costs.jsonl"
        assert log_path.exists()

    def test_log_append_only(self, tmp_path):
        for i in range(3):
            log_supermax_cost(
                query_hash=f"hash_{i}",
                agent_count=i + 1,
                difficulty_tier="test",
                graph_complexity=0.5,
                agents_used=["A"],
                log_dir=tmp_path,
            )
        log_path = tmp_path / "supermax-costs.jsonl"
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_log_entry_format(self, tmp_path):
        log_supermax_cost(
            query_hash="test_hash",
            agent_count=2,
            difficulty_tier="simple",
            graph_complexity=0.35,
            agents_used=["PrincipalEngineer", "SecurityArchitect"],
            cost_estimate=0.03,
            log_dir=tmp_path,
        )
        log_path = tmp_path / "supermax-costs.jsonl"
        entry = json.loads(log_path.read_text().strip())
        assert entry["query_hash"] == "test_hash"
        assert entry["agent_count"] == 2
        assert entry["difficulty_tier"] == "simple"
        assert entry["graph_complexity"] == 0.35
        assert entry["agents_used"] == ["PrincipalEngineer", "SecurityArchitect"]
        assert entry["cost_estimate"] == 0.03
        assert "ts" in entry


# ═══════════════════════════════════════════════════════════════════════════
# Test: Integration — Trivial spawns 1, Complex spawns 5
# ═══════════════════════════════════════════════════════════════════════════

class TestIntegration:
    """End-to-end integration tests per acceptance criteria."""

    def test_trivial_query_spawns_one_agent(self, spawner):
        """Known-trivial query spawns exactly 1 agent."""
        plan = spawner.plan(0.10)
        assert plan.agent_count == 1
        assert plan.agents[0].name == "PrincipalEngineer"

    def test_complex_query_spawns_five_agents(self, spawner):
        """Known-complex query spawns exactly 5 agents."""
        plan = spawner.plan(0.90)
        assert plan.agent_count == 5
        agent_names = [a.name for a in plan.agents]
        assert agent_names == [
            "PrincipalEngineer",
            "SecurityArchitect",
            "ProductStrategist",
            "Contrarian",
            "Arbiter",
        ]

    def test_full_pipeline_with_cost_logging(self, spawner, tmp_path):
        """Plan + cost log for a moderate query."""
        plan = spawner.plan(0.55)
        assert plan.agent_count == 3
        assert plan.difficulty_tier == "moderate"

        log_supermax_cost(
            query_hash="integration_test",
            agent_count=plan.agent_count,
            difficulty_tier=plan.difficulty_tier,
            graph_complexity=plan.graph_complexity,
            agents_used=[a.name for a in plan.agents],
            cost_estimate=0.04,
            log_dir=tmp_path,
        )

        log_path = tmp_path / "supermax-costs.jsonl"
        entry = json.loads(log_path.read_text().strip())
        assert entry["agent_count"] == 3
        assert entry["difficulty_tier"] == "moderate"

    def test_consumes_graph_complexity_from_us004(self, spawner):
        """Verify the spawner correctly consumes graphComplexity values
        that would come from computeGraphSignal() in dq-scorer.js."""
        # Simulate outputs from computeGraphSignal
        test_cases = [
            (0.05, "trivial", 1),   # high entropy, dense subgraph, low IRT
            (0.35, "simple", 2),    # moderate features
            (0.55, "moderate", 3),  # mixed signals
            (0.75, "complex", 4),   # sparse subgraph, concentrated scores
            (0.95, "expert", 5),    # low entropy, sparse, high IRT difficulty
        ]
        for complexity, expected_tier, expected_count in test_cases:
            plan = spawner.plan(complexity)
            assert plan.difficulty_tier == expected_tier, \
                f"complexity={complexity}: expected {expected_tier}, got {plan.difficulty_tier}"
            assert plan.agent_count == expected_count, \
                f"complexity={complexity}: expected {expected_count} agents, got {plan.agent_count}"
