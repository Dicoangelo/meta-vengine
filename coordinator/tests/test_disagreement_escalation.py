#!/usr/bin/env python3
"""
Tests for US-009: SUPERMAX v2 — Disagreement Escalation.

Tests that high-disagreement cases are escalated to an arbiter agent,
the arbiter makes a final call with explicit reasoning, disagreement
dimensions are logged, and difficulty feedback is generated for IRT.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Allow imports from coordinator/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from coordinator.synthesizer import (
    DQEvaluation,
    AgentTrajectory,
    SynthesisResult,
    FreeMadSynthesizer,
    DisagreementEscalator,
    EscalationResult,
    find_disagreement_dimensions,
    compute_trajectory_weights,
)
from coordinator.supermax import SupermaxV2


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def escalator():
    """DisagreementEscalator with default config."""
    return DisagreementEscalator()


@pytest.fixture
def tmp_log_dir():
    """Temporary directory for log files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def make_trajectory(name, r1_scores, r2_scores, r1_reasoning="", r2_reasoning=""):
    """Helper to create an AgentTrajectory from score tuples (v, s, c)."""
    r1 = DQEvaluation(name, *r1_scores, reasoning=r1_reasoning)
    r2 = DQEvaluation(name, *r2_scores, reasoning=r2_reasoning)
    return AgentTrajectory(agent_name=name, round1=r1, round2=r2)


def make_trajectories_with_weights(trajectories):
    """Compute stability and weights for trajectories."""
    return compute_trajectory_weights(trajectories)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Escalation Trigger Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationTrigger:
    """Tests for should_escalate() — when divergence exceeds threshold."""

    def test_high_divergence_triggers_escalation(self, escalator):
        """When validity scores diverge by > 0.15, should escalate."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
            make_trajectory("PS", (0.8, 0.8, 0.7), (0.8, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is True
        assert "validity" in dims

    def test_low_divergence_no_escalation(self, escalator):
        """When all dimensions within 0.15, no escalation."""
        trajectories = [
            make_trajectory("PE", (0.8, 0.7, 0.75), (0.82, 0.72, 0.76)),
            make_trajectory("SA", (0.78, 0.68, 0.73), (0.80, 0.70, 0.74)),
            make_trajectory("PS", (0.81, 0.71, 0.74), (0.81, 0.71, 0.75)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is False
        assert dims == []

    def test_multiple_dimensions_diverge(self, escalator):
        """When multiple dimensions diverge, all are reported."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.9, 0.9), (0.9, 0.9, 0.9)),
            make_trajectory("SA", (0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is True
        assert len(dims) == 3
        assert set(dims) == {"validity", "specificity", "correctness"}

    def test_single_agent_no_escalation(self, escalator):
        """Single agent can't disagree with itself."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is False

    def test_below_threshold_no_escalation(self, escalator):
        """Divergence below 0.15 does NOT trigger."""
        trajectories = [
            make_trajectory("PE", (0.8, 0.7, 0.7), (0.84, 0.7, 0.7)),
            make_trajectory("SA", (0.8, 0.7, 0.7), (0.70, 0.7, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is False

    def test_just_above_threshold_triggers(self, escalator):
        """Divergence at 0.16 triggers escalation."""
        trajectories = [
            make_trajectory("PE", (0.8, 0.7, 0.7), (0.88, 0.7, 0.7)),
            make_trajectory("SA", (0.8, 0.7, 0.7), (0.72, 0.7, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        should, dims = escalator.should_escalate(trajectories)
        assert should is True
        assert "validity" in dims


# ─────────────────────────────────────────────────────────────────────────────
# Test: Arbiter Context Building
# ─────────────────────────────────────────────────────────────────────────────

class TestArbiterContext:
    """Tests for build_arbiter_context()."""

    def test_context_includes_all_agents(self, escalator):
        """Arbiter context includes full reasoning from all agents."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7),
                          "Tech analysis", "Held position"),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7),
                          "Risk concerns", "Maintained view"),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])

        assert len(ctx["agents"]) == 2
        assert ctx["agents"][0]["agent_name"] == "PE"
        assert ctx["agents"][0]["round1_reasoning"] == "Tech analysis"
        assert ctx["agents"][0]["round2_reasoning"] == "Held position"
        assert ctx["agents"][1]["agent_name"] == "SA"

    def test_context_includes_divergent_dimensions(self, escalator):
        """Context shows which dimensions diverged and the specific scores."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])

        assert "validity" in ctx["dimension_details"]
        detail = ctx["dimension_details"]["validity"]
        assert detail["spread"] == pytest.approx(0.3, abs=0.01)
        assert detail["highest_agent"] == "PE"
        assert detail["lowest_agent"] == "SA"

    def test_context_includes_stability_scores(self, escalator):
        """Agent stability scores are included in context."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.75, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])

        pe_ctx = next(a for a in ctx["agents"] if a["agent_name"] == "PE")
        sa_ctx = next(a for a in ctx["agents"] if a["agent_name"] == "SA")
        # PE didn't move, SA shifted — PE should be more stable
        assert pe_ctx["stability_score"] > sa_ctx["stability_score"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: Arbiter Evaluation
# ─────────────────────────────────────────────────────────────────────────────

class TestArbiterEvaluation:
    """Tests for arbiter_evaluate() — arbiter makes final call."""

    def test_arbiter_produces_verdict(self, escalator):
        """Arbiter returns verdict with all DQ dimensions."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])
        result = escalator.arbiter_evaluate(ctx)

        assert result.escalated is True
        assert "validity" in result.arbiter_verdict
        assert "specificity" in result.arbiter_verdict
        assert "correctness" in result.arbiter_verdict
        assert "composite_dq" in result.arbiter_verdict

    def test_stable_agent_prevails(self, escalator):
        """Arbiter selects the most stable agent's score on divergent dims."""
        # PE holds position (delta=0), SA shifts (delta=0.15)
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.75, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])
        result = escalator.arbiter_evaluate(ctx)

        # PE is more stable (delta=0), so arbiter uses PE's validity score
        assert result.prevailing_perspective == "PE"
        assert result.arbiter_verdict["validity"] == pytest.approx(0.9, abs=0.01)

    def test_arbiter_reasoning_references_dimensions(self, escalator):
        """Arbiter reasoning explicitly mentions divergent dimensions."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])
        result = escalator.arbiter_evaluate(ctx)

        assert "validity" in result.arbiter_reasoning
        assert "diverged" in result.arbiter_reasoning
        assert "PE" in result.arbiter_reasoning

    def test_non_divergent_dims_use_consensus(self, escalator):
        """Non-divergent dimensions use weighted consensus, not arbiter pick."""
        # Only validity diverges, specificity and correctness are same
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])
        result = escalator.arbiter_evaluate(ctx)

        # specificity and correctness should be consensus (both agents agree)
        assert result.arbiter_verdict["specificity"] == pytest.approx(0.8, abs=0.01)
        assert result.arbiter_verdict["correctness"] == pytest.approx(0.7, abs=0.01)

    def test_composite_dq_computed_correctly(self, escalator):
        """Composite DQ = validity*0.4 + specificity*0.3 + correctness*0.3."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        ctx = escalator.build_arbiter_context(trajectories, ["validity"])
        result = escalator.arbiter_evaluate(ctx)

        v = result.arbiter_verdict
        expected = v["validity"] * 0.4 + v["specificity"] * 0.3 + v["correctness"] * 0.3
        assert v["composite_dq"] == pytest.approx(expected, abs=0.001)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Difficulty Feedback for IRT
# ─────────────────────────────────────────────────────────────────────────────

class TestDifficultyFeedback:
    """Tests for IRT difficulty feedback from disagreement patterns."""

    def test_generates_feedback(self, escalator):
        """Generates difficulty boost feedback from disagreement."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        feedback = escalator.generate_difficulty_feedback(
            ["validity"], trajectories, "hash123"
        )

        assert feedback["source"] == "disagreement_escalation"
        assert feedback["query_hash"] == "hash123"
        assert feedback["difficulty_boost"] > 0
        assert "validity" in feedback["divergent_dimensions"]

    def test_more_divergence_higher_boost(self, escalator):
        """Larger disagreement spread produces larger difficulty boost."""
        small_div = [
            make_trajectory("PE", (0.8, 0.7, 0.7), (0.85, 0.7, 0.7)),
            make_trajectory("SA", (0.8, 0.7, 0.7), (0.68, 0.7, 0.7)),
        ]
        small_div = make_trajectories_with_weights(small_div)

        large_div = [
            make_trajectory("PE", (0.9, 0.7, 0.7), (0.95, 0.7, 0.7)),
            make_trajectory("SA", (0.4, 0.7, 0.7), (0.35, 0.7, 0.7)),
        ]
        large_div = make_trajectories_with_weights(large_div)

        small_fb = escalator.generate_difficulty_feedback(["validity"], small_div)
        large_fb = escalator.generate_difficulty_feedback(["validity"], large_div)

        assert large_fb["difficulty_boost"] > small_fb["difficulty_boost"]

    def test_boost_capped_at_020(self, escalator):
        """Difficulty boost never exceeds 0.20."""
        extreme_div = [
            make_trajectory("PE", (1.0, 0.7, 0.7), (1.0, 0.7, 0.7)),
            make_trajectory("SA", (0.0, 0.7, 0.7), (0.0, 0.7, 0.7)),
        ]
        extreme_div = make_trajectories_with_weights(extreme_div)
        feedback = escalator.generate_difficulty_feedback(
            ["validity"], extreme_div
        )
        assert feedback["difficulty_boost"] <= 0.20

    def test_feedback_includes_agent_count(self, escalator):
        """Feedback includes how many agents were involved."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
            make_trajectory("PS", (0.7, 0.8, 0.7), (0.7, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        feedback = escalator.generate_difficulty_feedback(
            ["validity"], trajectories
        )
        assert feedback["agent_count"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test: Logging
# ─────────────────────────────────────────────────────────────────────────────

class TestEscalationLogging:
    """Tests for escalation and difficulty feedback logging."""

    def test_escalation_logged_to_jsonl(self, escalator, tmp_log_dir):
        """Escalation events are logged to supermax-escalations.jsonl."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "hash456", log_dir=tmp_log_dir)

        log_path = tmp_log_dir / "supermax-escalations.jsonl"
        assert log_path.exists()

        with open(log_path) as f:
            entry = json.loads(f.readline())
        assert entry["query_hash"] == "hash456"
        assert entry["escalated"] is True
        assert "validity" in entry["divergent_dimensions"]
        assert "arbiter_reasoning" in entry

    def test_difficulty_feedback_logged(self, escalator, tmp_log_dir):
        """Difficulty feedback logged to disagreement-difficulty-feedback.jsonl."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        escalator.escalate(trajectories, "hash789", log_dir=tmp_log_dir)

        fb_path = tmp_log_dir / "disagreement-difficulty-feedback.jsonl"
        assert fb_path.exists()

        with open(fb_path) as f:
            entry = json.loads(f.readline())
        assert entry["source"] == "disagreement_escalation"
        assert entry["difficulty_boost"] > 0

    def test_no_log_when_no_escalation(self, escalator, tmp_log_dir):
        """No log files created when escalation is not triggered."""
        trajectories = [
            make_trajectory("PE", (0.8, 0.8, 0.7), (0.82, 0.8, 0.7)),
            make_trajectory("SA", (0.78, 0.8, 0.7), (0.80, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "hash000", log_dir=tmp_log_dir)

        assert result is None
        assert not (tmp_log_dir / "supermax-escalations.jsonl").exists()

    def test_append_only_logging(self, escalator, tmp_log_dir):
        """Multiple escalations append to same file."""
        for i in range(3):
            trajectories = [
                make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7)),
                make_trajectory("SA", (0.5, 0.8, 0.7), (0.5, 0.8, 0.7)),
            ]
            trajectories = make_trajectories_with_weights(trajectories)
            escalator.escalate(trajectories, f"hash_{i}", log_dir=tmp_log_dir)

        log_path = tmp_log_dir / "supermax-escalations.jsonl"
        with open(log_path) as f:
            lines = f.readlines()
        assert len(lines) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Test: Full Escalation Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestFullEscalationPipeline:
    """Tests for the end-to-end escalate() pipeline."""

    def test_full_pipeline_with_disagreement(self, escalator, tmp_log_dir):
        """Full pipeline: check → context → evaluate → feedback → log."""
        trajectories = [
            make_trajectory("PE", (0.9, 0.8, 0.7), (0.9, 0.8, 0.7),
                          "Tech OK", "Held firm"),
            make_trajectory("SA", (0.6, 0.8, 0.7), (0.6, 0.8, 0.7),
                          "Risk concern", "Maintained"),
            make_trajectory("PS", (0.8, 0.8, 0.7), (0.8, 0.8, 0.7),
                          "User value", "Adjusted"),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "pipeline_test", log_dir=tmp_log_dir)

        assert result is not None
        assert result.escalated is True
        assert len(result.divergent_dimensions) > 0
        assert result.arbiter_reasoning != ""
        assert result.prevailing_perspective != ""
        assert result.difficulty_feedback is not None
        assert result.difficulty_feedback["difficulty_boost"] > 0

    def test_pipeline_returns_none_no_disagreement(self, escalator, tmp_log_dir):
        """Pipeline returns None when no disagreement."""
        trajectories = [
            make_trajectory("PE", (0.8, 0.8, 0.7), (0.81, 0.8, 0.7)),
            make_trajectory("SA", (0.79, 0.8, 0.7), (0.80, 0.8, 0.7)),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "no_esc", log_dir=tmp_log_dir)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Test: SupermaxV2 Integration
# ─────────────────────────────────────────────────────────────────────────────

class TestSupermaxV2Integration:
    """Tests for disagreement escalation integrated into SupermaxV2."""

    def test_synthesize_with_escalation(self):
        """SupermaxV2.synthesize() triggers escalation on high disagreement."""
        v2 = SupermaxV2()

        # Round 1: agents disagree on validity
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.9, 0.8, 0.7, "Tech analysis"),
            DQEvaluation("SecurityArchitect", 0.5, 0.8, 0.7, "Risk concerns"),
            DQEvaluation("ProductStrategist", 0.7, 0.8, 0.7, "User value"),
        ]
        # Round 2: agents hold positions (high stability)
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.9, 0.8, 0.7, "Held position"),
            DQEvaluation("SecurityArchitect", 0.5, 0.8, 0.7, "Maintained view"),
            DQEvaluation("ProductStrategist", 0.7, 0.8, 0.7, "Stayed course"),
        ]

        result = v2.synthesize(r1, r2, query_hash="integration_test")

        # Escalation should have been triggered (validity spread = 0.4 > 0.15)
        assert result.escalation is not None
        assert result.escalation.escalated is True
        assert "validity" in result.escalation.divergent_dimensions

        # Consensus should be overridden by arbiter verdict
        # PE is most stable (delta=0), so its validity (0.9) should prevail
        assert result.consensus_validity == pytest.approx(0.9, abs=0.01)

    def test_synthesize_without_escalation(self):
        """SupermaxV2.synthesize() works normally when no disagreement."""
        v2 = SupermaxV2()

        r1 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.75, "Good"),
            DQEvaluation("SecurityArchitect", 0.78, 0.72, 0.74, "OK"),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.81, 0.71, 0.76, "Held"),
            DQEvaluation("SecurityArchitect", 0.79, 0.71, 0.75, "Held"),
        ]

        result = v2.synthesize(r1, r2, query_hash="no_esc_test")
        assert result.escalation is None

    def test_escalation_overrides_consensus(self):
        """When escalated, arbiter verdict replaces trajectory-weighted consensus."""
        v2 = SupermaxV2()

        # Large validity disagreement, SA shifts toward PE (sycophancy-ish)
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.9, 0.8, 0.7, "Strong tech"),
            DQEvaluation("SecurityArchitect", 0.5, 0.8, 0.7, "Risk flag"),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.9, 0.8, 0.7, "Unchanged"),
            DQEvaluation("SecurityArchitect", 0.65, 0.8, 0.7, "Shifted"),
        ]

        result = v2.synthesize(r1, r2, query_hash="override_test")

        if result.escalation is not None:
            # Verdict should come from arbiter, not simple averaging
            assert result.consensus_dq == pytest.approx(
                result.escalation.arbiter_verdict["composite_dq"], abs=0.001
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Manufactured Disagreement → Arbiter References Dimensions
# ─────────────────────────────────────────────────────────────────────────────

class TestManufacturedDisagreement:
    """Integration test from acceptance criteria: manufactured disagreement
    triggers arbiter; arbiter's reasoning references specific divergent dims."""

    def test_manufactured_validity_disagreement(self, escalator, tmp_log_dir):
        """PE says validity=0.95, SA says validity=0.40 → arbiter resolves."""
        trajectories = [
            make_trajectory("PrincipalEngineer",
                          (0.95, 0.8, 0.85), (0.95, 0.8, 0.85),
                          "Technically excellent", "Position held"),
            make_trajectory("SecurityArchitect",
                          (0.40, 0.8, 0.85), (0.40, 0.8, 0.85),
                          "Severe validity concern", "Concern stands"),
            make_trajectory("ProductStrategist",
                          (0.70, 0.8, 0.85), (0.70, 0.8, 0.85),
                          "Moderate validity", "View unchanged"),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "manufactured_test", log_dir=tmp_log_dir)

        # Must escalate
        assert result is not None
        assert result.escalated is True

        # Validity must be in divergent dimensions
        assert "validity" in result.divergent_dimensions

        # Arbiter reasoning must reference the divergent dimension
        assert "validity" in result.arbiter_reasoning
        assert "diverged" in result.arbiter_reasoning

        # Specificity and correctness should NOT be divergent (both 0.8 and 0.85)
        assert "specificity" not in result.divergent_dimensions
        assert "correctness" not in result.divergent_dimensions

        # Difficulty feedback must be generated
        assert result.difficulty_feedback is not None
        assert result.difficulty_feedback["difficulty_boost"] > 0

    def test_manufactured_multi_dimension_disagreement(self, escalator, tmp_log_dir):
        """Disagreement on both validity and correctness → arbiter references both."""
        trajectories = [
            make_trajectory("PrincipalEngineer",
                          (0.9, 0.8, 0.9), (0.9, 0.8, 0.9),
                          "High quality", "Held"),
            make_trajectory("SecurityArchitect",
                          (0.5, 0.8, 0.5), (0.5, 0.8, 0.5),
                          "Low quality", "Held"),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "multi_dim_test", log_dir=tmp_log_dir)

        assert result is not None
        assert "validity" in result.divergent_dimensions
        assert "correctness" in result.divergent_dimensions

        # Arbiter reasoning references both
        assert "validity" in result.arbiter_reasoning
        assert "correctness" in result.arbiter_reasoning

    def test_arbiter_reasoning_explains_prevailing(self, escalator, tmp_log_dir):
        """Arbiter reasoning explains WHY the prevailing perspective won."""
        # PE holds perfectly (delta=0), SA shifts (less stable)
        trajectories = [
            make_trajectory("PE",
                          (0.9, 0.8, 0.7), (0.9, 0.8, 0.7),
                          "Strong case", "Unchanged"),
            make_trajectory("SA",
                          (0.5, 0.8, 0.7), (0.65, 0.8, 0.7),
                          "Weak case", "Shifted toward PE"),
        ]
        trajectories = make_trajectories_with_weights(trajectories)
        result = escalator.escalate(trajectories, "prevail_test", log_dir=tmp_log_dir)

        assert result is not None
        assert result.prevailing_perspective == "PE"
        # Reasoning should mention stability as the reason
        assert "stability" in result.arbiter_reasoning.lower()
