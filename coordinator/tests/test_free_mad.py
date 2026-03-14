#!/usr/bin/env python3
"""
Tests for US-008: SUPERMAX v2 — Free-MAD Trajectory Scoring.

Covers:
- DQEvaluation creation and composite scoring
- Anonymization of peer reasoning (anti-sycophancy)
- Stability score computation (exponential decay)
- Trajectory weight normalization
- Sycophancy detection (unanimous convergence)
- Disagreement dimension detection
- Weighted consensus computation
- FreeMadSynthesizer end-to-end
- Trajectory logging to JSONL
- Integration: stable agent gets higher weight than capitulating agent
- SupermaxV2 orchestrator integration
"""

import json
import math
import sys
import tempfile
import os
import pytest
from pathlib import Path

# Allow imports from coordinator/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from coordinator.synthesizer import (
    DQEvaluation,
    AgentTrajectory,
    SynthesisResult,
    FreeMadSynthesizer,
    anonymize_reasoning,
    compute_stability_score,
    compute_trajectory_weights,
    detect_sycophancy,
    find_disagreement_dimensions,
    synthesize_consensus,
    log_trajectory,
    load_free_mad_config,
)
from coordinator.supermax import PredictiveSpawner, SupermaxV2


# ─── DQEvaluation ───────────────────────────────────────────────────────────

class TestDQEvaluation:
    def test_composite_formula(self):
        ev = DQEvaluation("TestAgent", 0.8, 0.7, 0.9, "Some reasoning")
        expected = 0.8 * 0.4 + 0.7 * 0.3 + 0.9 * 0.3
        assert abs(ev.composite_dq - expected) < 0.001

    def test_agent_name_preserved(self):
        ev = DQEvaluation("TestAgent", 0.8, 0.7, 0.9, "Some reasoning")
        assert ev.agent_name == "TestAgent"

    def test_reasoning_preserved(self):
        ev = DQEvaluation("TestAgent", 0.8, 0.7, 0.9, "Some reasoning")
        assert ev.reasoning == "Some reasoning"

    def test_dimensions_dict(self):
        ev = DQEvaluation("TestAgent", 0.8, 0.7, 0.9)
        dims = ev.dimensions()
        assert abs(dims["validity"] - 0.8) < 0.001
        assert abs(dims["specificity"] - 0.7) < 0.001
        assert abs(dims["correctness"] - 0.9) < 0.001

    def test_perfect_scores(self):
        ev = DQEvaluation("Perfect", 1.0, 1.0, 1.0)
        assert abs(ev.composite_dq - 1.0) < 0.001

    def test_zero_scores(self):
        ev = DQEvaluation("Zero", 0.0, 0.0, 0.0)
        assert abs(ev.composite_dq - 0.0) < 0.001


# ─── Anonymize Reasoning ────────────────────────────────────────────────────

class TestAnonymizeReasoning:
    @pytest.fixture
    def evals(self):
        return [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.9, "Tech analysis"),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7, "Risk assessment"),
            DQEvaluation("ProductStrategist", 0.9, 0.6, 0.8, "User value check"),
        ]

    def test_correct_count(self, evals):
        anon = anonymize_reasoning(evals)
        assert len(anon) == 3

    def test_opaque_labels(self, evals):
        anon = anonymize_reasoning(evals)
        assert anon[0]["evaluator"] == "Evaluator A"
        assert anon[1]["evaluator"] == "Evaluator B"
        assert anon[2]["evaluator"] == "Evaluator C"

    def test_agent_names_stripped(self, evals):
        anon = anonymize_reasoning(evals)
        all_text = json.dumps(anon)
        assert "PrincipalEngineer" not in all_text
        assert "SecurityArchitect" not in all_text
        assert "ProductStrategist" not in all_text

    def test_scores_preserved(self, evals):
        anon = anonymize_reasoning(evals)
        assert abs(anon[0]["scores"]["validity"] - 0.8) < 0.001

    def test_reasoning_preserved(self, evals):
        anon = anonymize_reasoning(evals)
        assert anon[0]["reasoning"] == "Tech analysis"


# ─── Stability Score ────────────────────────────────────────────────────────

class TestStabilityScore:
    def test_zero_delta_perfect_stability(self):
        t = AgentTrajectory(
            "Stable",
            DQEvaluation("Stable", 0.8, 0.7, 0.9),
            DQEvaluation("Stable", 0.8, 0.7, 0.9),
        )
        assert abs(compute_stability_score(t) - 1.0) < 0.001

    def test_large_delta_low_stability(self):
        t = AgentTrajectory(
            "Unstable",
            DQEvaluation("Unstable", 0.2, 0.3, 0.1),
            DQEvaluation("Unstable", 0.9, 0.8, 0.9),
        )
        assert compute_stability_score(t) < 0.1

    def test_moderate_delta_mid_stability(self):
        t = AgentTrajectory(
            "Moderate",
            DQEvaluation("Moderate", 0.7, 0.6, 0.8),
            DQEvaluation("Moderate", 0.75, 0.65, 0.85),
        )
        s = compute_stability_score(t)
        assert 0.3 < s < 0.9

    def test_exponential_decay_formula(self):
        t = AgentTrajectory(
            "Known",
            DQEvaluation("Known", 0.5, 0.5, 0.5),
            DQEvaluation("Known", 0.6, 0.5, 0.5),
        )
        expected = math.exp(-5.0 * 0.1)
        assert abs(compute_stability_score(t) - expected) < 0.001

    def test_custom_decay_rate(self):
        t = AgentTrajectory(
            "Known",
            DQEvaluation("Known", 0.5, 0.5, 0.5),
            DQEvaluation("Known", 0.6, 0.5, 0.5),
        )
        expected = math.exp(-10.0 * 0.1)
        assert abs(compute_stability_score(t, decay_rate=10.0) - expected) < 0.001


# ─── Trajectory Weights ────────────────────────────────────────────────────

class TestTrajectoryWeights:
    @pytest.fixture
    def trajectories(self):
        t_stable = AgentTrajectory(
            "Stable",
            DQEvaluation("Stable", 0.8, 0.7, 0.9),
            DQEvaluation("Stable", 0.8, 0.7, 0.9),
        )
        t_unstable = AgentTrajectory(
            "Unstable",
            DQEvaluation("Unstable", 0.2, 0.3, 0.1),
            DQEvaluation("Unstable", 0.9, 0.8, 0.9),
        )
        t_moderate = AgentTrajectory(
            "Moderate",
            DQEvaluation("Moderate", 0.7, 0.6, 0.8),
            DQEvaluation("Moderate", 0.75, 0.65, 0.85),
        )
        return [t_stable, t_unstable, t_moderate]

    def test_stable_gets_highest_weight(self, trajectories):
        compute_trajectory_weights(trajectories)
        assert trajectories[0].trajectory_weight > trajectories[1].trajectory_weight

    def test_weights_sum_to_one(self, trajectories):
        compute_trajectory_weights(trajectories)
        total = sum(t.trajectory_weight for t in trajectories)
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self, trajectories):
        compute_trajectory_weights(trajectories)
        for t in trajectories:
            assert t.trajectory_weight > 0

    def test_equal_stability_uniform_weights(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.5, 0.5, 0.5), DQEvaluation("A", 0.5, 0.5, 0.5)),
            AgentTrajectory("B", DQEvaluation("B", 0.5, 0.5, 0.5), DQEvaluation("B", 0.5, 0.5, 0.5)),
            AgentTrajectory("C", DQEvaluation("C", 0.5, 0.5, 0.5), DQEvaluation("C", 0.5, 0.5, 0.5)),
        ]
        compute_trajectory_weights(trajs)
        for t in trajs:
            assert abs(t.trajectory_weight - 1.0 / 3) < 0.01


# ─── Sycophancy Detection ──────────────────────────────────────────────────

class TestSycophancyDetection:
    def test_unanimous_convergence_flagged(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.9, 0.9, 0.9), DQEvaluation("A", 0.7, 0.7, 0.7)),
            AgentTrajectory("B", DQEvaluation("B", 0.5, 0.5, 0.5), DQEvaluation("B", 0.7, 0.7, 0.7)),
            AgentTrajectory("C", DQEvaluation("C", 0.7, 0.7, 0.7), DQEvaluation("C", 0.71, 0.71, 0.71)),
        ]
        assert detect_sycophancy(trajs, 0.05)

    def test_one_agent_holds_no_sycophancy(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.9, 0.9, 0.9), DQEvaluation("A", 0.9, 0.9, 0.9)),
            AgentTrajectory("B", DQEvaluation("B", 0.5, 0.5, 0.5), DQEvaluation("B", 0.55, 0.55, 0.55)),
        ]
        assert not detect_sycophancy(trajs, 0.05)

    def test_single_agent_no_sycophancy(self):
        trajs = [AgentTrajectory("A", DQEvaluation("A", 0.5, 0.5, 0.5), DQEvaluation("A", 0.7, 0.7, 0.7))]
        assert not detect_sycophancy(trajs)

    def test_no_initial_disagreement_no_sycophancy(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.7, 0.7, 0.7), DQEvaluation("A", 0.71, 0.71, 0.71)),
            AgentTrajectory("B", DQEvaluation("B", 0.7, 0.7, 0.7), DQEvaluation("B", 0.72, 0.72, 0.72)),
        ]
        assert not detect_sycophancy(trajs, 0.05)


# ─── Disagreement Dimensions ───────────────────────────────────────────────

class TestDisagreementDimensions:
    def test_validity_diverges(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.9, 0.7, 0.8), DQEvaluation("A", 0.9, 0.7, 0.8)),
            AgentTrajectory("B", DQEvaluation("B", 0.5, 0.7, 0.8), DQEvaluation("B", 0.5, 0.7, 0.8)),
        ]
        dims = find_disagreement_dimensions(trajs, 0.15)
        assert "validity" in dims
        assert "specificity" not in dims
        assert "correctness" not in dims

    def test_all_agree_no_dimensions(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.7, 0.7, 0.7), DQEvaluation("A", 0.7, 0.7, 0.7)),
            AgentTrajectory("B", DQEvaluation("B", 0.75, 0.72, 0.73), DQEvaluation("B", 0.75, 0.72, 0.73)),
        ]
        assert len(find_disagreement_dimensions(trajs, 0.15)) == 0

    def test_all_dimensions_diverge(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.9, 0.9, 0.9), DQEvaluation("A", 0.9, 0.9, 0.9)),
            AgentTrajectory("B", DQEvaluation("B", 0.5, 0.5, 0.5), DQEvaluation("B", 0.5, 0.5, 0.5)),
        ]
        assert len(find_disagreement_dimensions(trajs, 0.15)) == 3


# ─── Consensus Computation ──────────────────────────────────────────────────

class TestConsensusComputation:
    def test_equal_weights_average(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 0.8, 0.6, 0.7), DQEvaluation("A", 0.8, 0.6, 0.7)),
            AgentTrajectory("B", DQEvaluation("B", 0.6, 0.8, 0.9), DQEvaluation("B", 0.6, 0.8, 0.9)),
        ]
        trajs[0].trajectory_weight = 0.5
        trajs[1].trajectory_weight = 0.5
        c = synthesize_consensus(trajs)
        assert abs(c["validity"] - 0.7) < 0.01
        assert abs(c["specificity"] - 0.7) < 0.01
        assert abs(c["correctness"] - 0.8) < 0.01

    def test_skewed_weights_toward_dominant(self):
        trajs = [
            AgentTrajectory("A", DQEvaluation("A", 1.0, 1.0, 1.0), DQEvaluation("A", 1.0, 1.0, 1.0)),
            AgentTrajectory("B", DQEvaluation("B", 0.0, 0.0, 0.0), DQEvaluation("B", 0.0, 0.0, 0.0)),
        ]
        trajs[0].trajectory_weight = 0.9
        trajs[1].trajectory_weight = 0.1
        c = synthesize_consensus(trajs)
        assert abs(c["validity"] - 0.9) < 0.01
        assert abs(c["composite_dq"] - 0.9) < 0.01


# ─── FreeMadSynthesizer E2E ────────────────────────────────────────────────

class TestFreeMadSynthesizer:
    @pytest.fixture
    def synth(self):
        return FreeMadSynthesizer()

    @pytest.fixture
    def standard_evals(self):
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.9, "Tech solid"),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7, "Risky"),
            DQEvaluation("ProductStrategist", 0.9, 0.6, 0.8, "User value"),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.72, 0.88, "Held position"),
            DQEvaluation("SecurityArchitect", 0.78, 0.75, 0.82, "Shifted a lot"),
            DQEvaluation("ProductStrategist", 0.85, 0.65, 0.8, "Minor shift"),
        ]
        return r1, r2

    def test_returns_synthesis_result(self, synth, standard_evals):
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        assert isinstance(result, SynthesisResult)

    def test_consensus_in_range(self, synth, standard_evals):
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        assert 0.0 <= result.consensus_dq <= 1.0

    def test_correct_trajectory_count(self, synth, standard_evals):
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        assert len(result.trajectories) == 3

    def test_method_label(self, synth, standard_evals):
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        assert result.method == "free_mad_trajectory"

    def test_no_sycophancy_in_standard_case(self, synth, standard_evals):
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        assert not result.sycophancy_flagged

    def test_stable_agent_higher_weight(self, synth, standard_evals):
        """Engineer (small delta) should outweigh Architect (large shift)."""
        r1, r2 = standard_evals
        result = synth.synthesize(r1, r2)
        eng = result.trajectories[0]
        arch = result.trajectories[1]
        assert eng.trajectory_weight > arch.trajectory_weight

    def test_mismatched_round_counts_error(self, synth, standard_evals):
        r1, r2 = standard_evals
        with pytest.raises(ValueError):
            synth.synthesize(r1[:2], r2)

    def test_mismatched_agent_names_error(self, synth, standard_evals):
        r1, _ = standard_evals
        r2_wrong = [
            DQEvaluation("Wrong", 0.8, 0.7, 0.9),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7),
            DQEvaluation("ProductStrategist", 0.9, 0.6, 0.8),
        ]
        with pytest.raises(ValueError):
            synth.synthesize(r1, r2_wrong)

    def test_peer_context_anonymized(self, synth, standard_evals):
        r1, _ = standard_evals
        ctx = synth.prepare_peer_context(r1)
        assert len(ctx) == 3
        all_text = json.dumps(ctx)
        assert "PrincipalEngineer" not in all_text
        assert "SecurityArchitect" not in all_text


# ─── Trajectory Logging ────────────────────────────────────────────────────

class TestTrajectoryLogging:
    @pytest.fixture
    def result(self):
        synth = FreeMadSynthesizer()
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.9),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.72, 0.88),
            DQEvaluation("SecurityArchitect", 0.78, 0.75, 0.82),
        ]
        return synth.synthesize(r1, r2)

    def test_log_file_created(self, result):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_trajectory("abc123", result, log_dir=Path(tmpdir))
            assert (Path(tmpdir) / "supermax-trajectories.jsonl").exists()

    def test_log_entry_structure(self, result):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_trajectory("abc123", result, log_dir=Path(tmpdir))
            with open(Path(tmpdir) / "supermax-trajectories.jsonl") as f:
                entry = json.loads(f.readline())
            assert entry["query_hash"] == "abc123"
            assert entry["method"] == "free_mad_trajectory"
            assert "sycophancy_flagged" in entry
            assert "disagreement_dimensions" in entry
            assert "ts" in entry

    def test_trajectory_detail_fields(self, result):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_trajectory("abc123", result, log_dir=Path(tmpdir))
            with open(Path(tmpdir) / "supermax-trajectories.jsonl") as f:
                entry = json.loads(f.readline())
            t0 = entry["trajectories"][0]
            for field in ["agent", "round1_dq", "round2_dq", "stability_score", "trajectory_weight", "delta_validity"]:
                assert field in t0

    def test_append_only(self, result):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_trajectory("abc123", result, log_dir=Path(tmpdir))
            log_trajectory("def456", result, log_dir=Path(tmpdir))
            with open(Path(tmpdir) / "supermax-trajectories.jsonl") as f:
                lines = f.readlines()
            assert len(lines) == 2


# ─── Integration: Stable Agent Beats Capitulating ───────────────────────────

class TestIntegrationStabilityWins:
    def test_stable_engineer_outweighs_capitulating_architect(self):
        """Engineer holds firm, Architect capitulates to peer pressure."""
        synth = FreeMadSynthesizer()
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.85, 0.80, 0.90, "Technically correct"),
            DQEvaluation("SecurityArchitect", 0.50, 0.60, 0.40, "Security risks"),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.84, 0.79, 0.91, "Still correct"),
            DQEvaluation("SecurityArchitect", 0.83, 0.78, 0.88, "Actually Engineer is right"),
        ]
        result = synth.synthesize(r1, r2)
        eng = result.trajectories[0]
        arch = result.trajectories[1]
        assert eng.trajectory_weight > arch.trajectory_weight
        assert eng.stability_score > 0.9
        assert arch.stability_score < 0.5

    def test_consensus_weighted_toward_stable(self):
        """Consensus should reflect stable agent's scores more."""
        synth = FreeMadSynthesizer()
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.85, 0.80, 0.90),
            DQEvaluation("SecurityArchitect", 0.50, 0.60, 0.40),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.84, 0.79, 0.91),
            DQEvaluation("SecurityArchitect", 0.83, 0.78, 0.88),
        ]
        result = synth.synthesize(r1, r2)
        assert result.consensus_validity > 0.80


# ─── Sycophancy → Contrarian Trigger ───────────────────────────────────────

class TestSycophancyContrarian:
    def test_sycophancy_triggers_contrarian(self):
        synth = FreeMadSynthesizer()
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.9, 0.9, 0.9, "High"),
            DQEvaluation("SecurityArchitect", 0.5, 0.5, 0.5, "Low"),
            DQEvaluation("ProductStrategist", 0.7, 0.7, 0.7, "Med"),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.7, 0.7, 0.7, "Down"),
            DQEvaluation("SecurityArchitect", 0.7, 0.7, 0.7, "Up"),
            DQEvaluation("ProductStrategist", 0.71, 0.71, 0.71, "Converged"),
        ]
        result = synth.synthesize(r1, r2)
        assert result.sycophancy_flagged
        assert result.contrarian_triggered


# ─── Config Loading ─────────────────────────────────────────────────────────

class TestConfigLoading:
    def test_config_has_required_keys(self):
        cfg = load_free_mad_config()
        assert "stabilityDecayRate" in cfg
        assert "sycophancyConvergenceThreshold" in cfg
        assert "disagreementEscalationThreshold" in cfg

    def test_fallback_on_missing_file(self):
        cfg = load_free_mad_config(Path("/nonexistent/path.json"))
        assert "stabilityDecayRate" in cfg


# ─── SupermaxV2 Orchestrator ───────────────────────────────────────────────

class TestSupermaxV2Orchestrator:
    @pytest.fixture
    def v2(self):
        return SupermaxV2()

    def test_plan_agents_complex(self, v2):
        plan = v2.plan_agents(0.7)
        assert plan.difficulty_tier == "complex"
        assert plan.agent_count == 4

    def test_synthesize_returns_result(self, v2):
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.9),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7),
        ]
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.72, 0.88),
            DQEvaluation("SecurityArchitect", 0.78, 0.75, 0.82),
        ]
        result = v2.synthesize(r1, r2)
        assert isinstance(result, SynthesisResult)
        assert result.consensus_dq > 0

    def test_peer_context(self, v2):
        r1 = [DQEvaluation("A", 0.8, 0.7, 0.9)]
        ctx = v2.prepare_peer_context(r1)
        assert len(ctx) == 1

    def test_log_creates_files(self, v2):
        import coordinator.synthesizer as synth_mod
        import coordinator.supermax as supermax_mod
        r1 = [DQEvaluation("A", 0.8, 0.7, 0.9)]
        r2 = [DQEvaluation("A", 0.8, 0.72, 0.88)]
        result = v2.synthesize(r1, r2)
        plan = v2.plan_agents(0.5)
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_traj = synth_mod._TRAJECTORIES_DIR
            orig_cost = supermax_mod._COSTS_DIR
            synth_mod._TRAJECTORIES_DIR = Path(tmpdir)
            supermax_mod._COSTS_DIR = Path(tmpdir)
            try:
                v2.log("test", plan, result, 0.05)
                assert (Path(tmpdir) / "supermax-trajectories.jsonl").exists()
                assert (Path(tmpdir) / "supermax-costs.jsonl").exists()
            finally:
                synth_mod._TRAJECTORIES_DIR = orig_traj
                supermax_mod._COSTS_DIR = orig_cost
