#!/usr/bin/env python3
"""
Free-MAD Trajectory Scoring Synthesizer for SUPERMAX v2.

US-008: Replaces DisagreementAwareSynthesizer weighted averaging with
trajectory stability scoring. Based on Free-MAD (arXiv:2509.11035).

Protocol:
  1. Each agent evaluates independently (Round 1)
  2. Anonymized peer reasoning shared (agent labels stripped — anti-sycophancy)
  3. Each agent re-evaluates (Round 2)
  4. Delta = trajectory. Stable agents → higher weight. Unstable → lower weight.
  5. Unanimous convergence → flag sycophancy → trigger Contrarian.
"""

import json
import math
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

# Resolve paths relative to the meta-vengine root
_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _ROOT / "config" / "supermax-v2.json"
_TRAJECTORIES_DIR = _ROOT / "data"


@dataclass
class DQEvaluation:
    """A single DQ evaluation from one agent."""
    agent_name: str
    validity: float      # 0.0-1.0
    specificity: float   # 0.0-1.0
    correctness: float   # 0.0-1.0
    reasoning: str = ""
    composite_dq: float = 0.0

    def __post_init__(self):
        self.composite_dq = (
            self.validity * 0.4 +
            self.specificity * 0.3 +
            self.correctness * 0.3
        )

    def dimensions(self) -> Dict[str, float]:
        return {
            "validity": self.validity,
            "specificity": self.specificity,
            "correctness": self.correctness,
        }


@dataclass
class AgentTrajectory:
    """Trajectory data for one agent across Round 1 and Round 2."""
    agent_name: str
    round1: DQEvaluation
    round2: DQEvaluation
    delta_validity: float = 0.0
    delta_specificity: float = 0.0
    delta_correctness: float = 0.0
    delta_composite: float = 0.0
    stability_score: float = 0.0  # 0.0 (unstable) to 1.0 (perfectly stable)
    trajectory_weight: float = 0.0  # weight in final consensus

    def __post_init__(self):
        self.delta_validity = abs(self.round2.validity - self.round1.validity)
        self.delta_specificity = abs(self.round2.specificity - self.round1.specificity)
        self.delta_correctness = abs(self.round2.correctness - self.round1.correctness)
        self.delta_composite = abs(self.round2.composite_dq - self.round1.composite_dq)

    @property
    def max_dimension_delta(self) -> float:
        return max(self.delta_validity, self.delta_specificity, self.delta_correctness)


@dataclass
class SynthesisResult:
    """Final consensus result from Free-MAD trajectory scoring."""
    consensus_dq: float
    consensus_validity: float
    consensus_specificity: float
    consensus_correctness: float
    trajectories: List[AgentTrajectory]
    sycophancy_flagged: bool
    contrarian_triggered: bool
    disagreement_dimensions: List[str]  # which dimensions diverged > threshold
    method: str = "free_mad_trajectory"


def load_free_mad_config(config_path: Path = None) -> dict:
    """Load Free-MAD specific config from supermax-v2.json."""
    path = config_path or _CONFIG_PATH
    try:
        if path.exists():
            with open(path, "r") as f:
                cfg = json.load(f)
                return cfg.get("freeMad", _default_free_mad_config())
    except (json.JSONDecodeError, OSError):
        pass
    return _default_free_mad_config()


def _default_free_mad_config() -> dict:
    """Emergency fallback config for Free-MAD."""
    return {
        "stabilityDecayRate": 5.0,
        "sycophancyConvergenceThreshold": 0.05,
        "disagreementEscalationThreshold": 0.15,
        "minStabilityWeight": 0.1,
        "maxStabilityWeight": 1.0,
    }


def anonymize_reasoning(evaluations: List[DQEvaluation]) -> List[Dict[str, Any]]:
    """
    Strip agent labels from evaluations for anti-sycophancy peer sharing.

    Returns anonymized reasoning blocks with only scores and reasoning text.
    Agent names are replaced with opaque identifiers (Evaluator A, B, C...).
    """
    anonymized = []
    for i, ev in enumerate(evaluations):
        label = chr(65 + i)  # A, B, C, ...
        anonymized.append({
            "evaluator": f"Evaluator {label}",
            "scores": {
                "validity": ev.validity,
                "specificity": ev.specificity,
                "correctness": ev.correctness,
                "composite_dq": ev.composite_dq,
            },
            "reasoning": ev.reasoning,
        })
    return anonymized


def compute_stability_score(trajectory: AgentTrajectory, decay_rate: float = 5.0) -> float:
    """
    Compute stability score from trajectory delta using exponential decay.

    stability = exp(-decay_rate * max_dimension_delta)

    Small delta → stability ≈ 1.0 (agent held position)
    Large delta → stability → 0.0 (agent capitulated)

    Args:
        trajectory: The agent's trajectory across rounds
        decay_rate: How aggressively to penalize instability (default 5.0)

    Returns:
        Stability score 0.0-1.0
    """
    return math.exp(-decay_rate * trajectory.max_dimension_delta)


def compute_trajectory_weights(
    trajectories: List[AgentTrajectory],
    config: dict = None,
) -> List[AgentTrajectory]:
    """
    Compute trajectory-based weights for all agents.

    Stable agents get higher weight. Weights are normalized to sum to 1.0.
    Minimum weight prevents any agent from being completely silenced.

    Args:
        trajectories: List of agent trajectories
        config: Free-MAD config dict

    Returns:
        Same trajectories with stability_score and trajectory_weight populated
    """
    cfg = config or _default_free_mad_config()
    decay_rate = cfg.get("stabilityDecayRate", 5.0)
    min_weight = cfg.get("minStabilityWeight", 0.1)
    max_weight = cfg.get("maxStabilityWeight", 1.0)

    # Compute raw stability scores
    for t in trajectories:
        t.stability_score = compute_stability_score(t, decay_rate)

    # Clamp and normalize
    raw_weights = [max(min_weight, min(max_weight, t.stability_score)) for t in trajectories]
    total = sum(raw_weights)

    if total > 0:
        for i, t in enumerate(trajectories):
            t.trajectory_weight = raw_weights[i] / total
    else:
        # Uniform fallback
        uniform = 1.0 / len(trajectories) if trajectories else 0.0
        for t in trajectories:
            t.trajectory_weight = uniform

    return trajectories


def detect_sycophancy(
    trajectories: List[AgentTrajectory],
    convergence_threshold: float = 0.05,
) -> bool:
    """
    Detect unanimous convergence (potential sycophancy).

    If ALL agents shifted toward each other (all deltas point toward the
    group mean and are below threshold after convergence), flag as sycophancy.

    Args:
        trajectories: List of agent trajectories after Round 2
        convergence_threshold: Max spread in Round 2 scores to flag convergence

    Returns:
        True if sycophancy pattern detected
    """
    if len(trajectories) < 2:
        return False

    # Check if all agents moved (none held position perfectly)
    all_moved = all(t.delta_composite > 0.01 for t in trajectories)
    if not all_moved:
        return False

    # Check if Round 2 scores converged to a tight cluster
    r2_composites = [t.round2.composite_dq for t in trajectories]
    r2_spread = max(r2_composites) - min(r2_composites)

    # Check Round 1 had meaningful disagreement
    r1_composites = [t.round1.composite_dq for t in trajectories]
    r1_spread = max(r1_composites) - min(r1_composites)

    # Sycophancy: started with disagreement, ended with tight convergence, all moved
    return r1_spread > convergence_threshold and r2_spread <= convergence_threshold


def find_disagreement_dimensions(
    trajectories: List[AgentTrajectory],
    threshold: float = 0.15,
) -> List[str]:
    """
    Find DQ dimensions where agent trajectories diverge beyond threshold.

    Used for disagreement escalation (US-009).

    Args:
        trajectories: List of agent trajectories
        threshold: Divergence threshold per dimension

    Returns:
        List of dimension names that diverged
    """
    if len(trajectories) < 2:
        return []

    divergent = []
    for dim in ["validity", "specificity", "correctness"]:
        # Check spread of Round 2 scores on this dimension
        r2_scores = [getattr(t.round2, dim) for t in trajectories]
        spread = max(r2_scores) - min(r2_scores)
        if spread > threshold:
            divergent.append(dim)

    return divergent


def synthesize_consensus(
    trajectories: List[AgentTrajectory],
) -> Dict[str, float]:
    """
    Compute weighted consensus from trajectory-weighted agents.

    Uses Round 2 scores weighted by trajectory stability.

    Args:
        trajectories: Trajectories with trajectory_weight populated

    Returns:
        Dict with consensus scores per dimension + composite
    """
    consensus_v = 0.0
    consensus_s = 0.0
    consensus_c = 0.0

    for t in trajectories:
        consensus_v += t.round2.validity * t.trajectory_weight
        consensus_s += t.round2.specificity * t.trajectory_weight
        consensus_c += t.round2.correctness * t.trajectory_weight

    composite = consensus_v * 0.4 + consensus_s * 0.3 + consensus_c * 0.3

    return {
        "validity": consensus_v,
        "specificity": consensus_s,
        "correctness": consensus_c,
        "composite_dq": composite,
    }


class FreeMadSynthesizer:
    """
    Free-MAD Trajectory Scoring Synthesizer.

    Replaces DisagreementAwareSynthesizer with trajectory stability scoring.
    Protocol:
      1. Receive Round 1 evaluations from agents
      2. Anonymize and share peer reasoning
      3. Receive Round 2 evaluations
      4. Compute trajectories, stability, weights
      5. Detect sycophancy / disagreement
      6. Produce weighted consensus
    """

    def __init__(self, config_path: Path = None):
        self.config = load_free_mad_config(config_path)
        self._decay_rate = self.config.get("stabilityDecayRate", 5.0)
        self._sycophancy_threshold = self.config.get("sycophancyConvergenceThreshold", 0.05)
        self._escalation_threshold = self.config.get("disagreementEscalationThreshold", 0.15)

    def prepare_peer_context(self, round1_evals: List[DQEvaluation]) -> List[Dict[str, Any]]:
        """
        Prepare anonymized peer reasoning for Round 2.

        Strips agent labels (anti-sycophancy per CONSENSAGENT ACL 2025).

        Args:
            round1_evals: Round 1 evaluations from all agents

        Returns:
            Anonymized reasoning blocks for peer exposure
        """
        return anonymize_reasoning(round1_evals)

    def score_trajectories(
        self,
        round1_evals: List[DQEvaluation],
        round2_evals: List[DQEvaluation],
    ) -> List[AgentTrajectory]:
        """
        Compute trajectories from Round 1 → Round 2 evaluations.

        Args:
            round1_evals: Initial independent evaluations
            round2_evals: Post-peer-exposure evaluations

        Returns:
            List of AgentTrajectory with stability and weights computed
        """
        if len(round1_evals) != len(round2_evals):
            raise ValueError(
                f"Round 1 ({len(round1_evals)}) and Round 2 ({len(round2_evals)}) "
                "evaluation counts must match"
            )

        trajectories = []
        for r1, r2 in zip(round1_evals, round2_evals):
            if r1.agent_name != r2.agent_name:
                raise ValueError(
                    f"Agent mismatch: Round 1 '{r1.agent_name}' vs Round 2 '{r2.agent_name}'"
                )
            trajectories.append(AgentTrajectory(
                agent_name=r1.agent_name,
                round1=r1,
                round2=r2,
            ))

        # Compute stability scores and weights
        trajectories = compute_trajectory_weights(trajectories, self.config)

        return trajectories

    def synthesize(
        self,
        round1_evals: List[DQEvaluation],
        round2_evals: List[DQEvaluation],
    ) -> SynthesisResult:
        """
        Full Free-MAD synthesis: trajectories → sycophancy check → consensus.

        This is the main entry point for SUPERMAX v2 consensus.

        Args:
            round1_evals: Independent evaluations (Round 1)
            round2_evals: Post-peer-exposure evaluations (Round 2)

        Returns:
            SynthesisResult with consensus scores, trajectories, and flags
        """
        trajectories = self.score_trajectories(round1_evals, round2_evals)

        # Detect sycophancy
        sycophancy_flagged = detect_sycophancy(
            trajectories, self._sycophancy_threshold
        )

        # Find disagreement dimensions (for US-009 escalation)
        disagreement_dims = find_disagreement_dimensions(
            trajectories, self._escalation_threshold
        )

        # Determine if Contrarian should be triggered
        contrarian_triggered = sycophancy_flagged

        # Compute weighted consensus
        consensus = synthesize_consensus(trajectories)

        return SynthesisResult(
            consensus_dq=consensus["composite_dq"],
            consensus_validity=consensus["validity"],
            consensus_specificity=consensus["specificity"],
            consensus_correctness=consensus["correctness"],
            trajectories=trajectories,
            sycophancy_flagged=sycophancy_flagged,
            contrarian_triggered=contrarian_triggered,
            disagreement_dimensions=disagreement_dims,
        )


def log_trajectory(
    query_hash: str,
    result: SynthesisResult,
    log_dir: Path = None,
):
    """
    Append trajectory data per query to data/supermax-trajectories.jsonl.

    Args:
        query_hash: MD5 hash of the query
        result: SynthesisResult from synthesize()
        log_dir: Override for the data directory
    """
    out_dir = log_dir or _TRAJECTORIES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "supermax-trajectories.jsonl"

    trajectory_data = []
    for t in result.trajectories:
        trajectory_data.append({
            "agent": t.agent_name,
            "round1_dq": t.round1.composite_dq,
            "round2_dq": t.round2.composite_dq,
            "delta_validity": round(t.delta_validity, 4),
            "delta_specificity": round(t.delta_specificity, 4),
            "delta_correctness": round(t.delta_correctness, 4),
            "delta_composite": round(t.delta_composite, 4),
            "stability_score": round(t.stability_score, 4),
            "trajectory_weight": round(t.trajectory_weight, 4),
        })

    entry = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "query_hash": query_hash,
        "consensus_dq": round(result.consensus_dq, 4),
        "sycophancy_flagged": result.sycophancy_flagged,
        "contrarian_triggered": result.contrarian_triggered,
        "disagreement_dimensions": result.disagreement_dimensions,
        "agent_count": len(result.trajectories),
        "trajectories": trajectory_data,
        "method": result.method,
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI interface
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """CLI entry point for Free-MAD Synthesizer."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Free-MAD Trajectory Scoring Synthesizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 coordinator/synthesizer.py config     # Show Free-MAD config
  python3 coordinator/synthesizer.py demo       # Run demo synthesis
        """,
    )

    parser.add_argument("command", choices=["config", "demo"])
    args = parser.parse_args()

    synth = FreeMadSynthesizer()

    if args.command == "config":
        print(json.dumps(synth.config, indent=2))

    elif args.command == "demo":
        # Demo: 3 agents, one stable, one unstable, one moderate
        r1 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.7, 0.9, "Technically sound"),
            DQEvaluation("SecurityArchitect", 0.6, 0.8, 0.7, "Some risk concerns"),
            DQEvaluation("ProductStrategist", 0.9, 0.6, 0.8, "Good user value"),
        ]
        # After peer exposure: Engineer holds, Architect shifts, Strategist moderate shift
        r2 = [
            DQEvaluation("PrincipalEngineer", 0.8, 0.72, 0.88, "Held position after review"),
            DQEvaluation("SecurityArchitect", 0.78, 0.75, 0.82, "Shifted toward peers"),
            DQEvaluation("ProductStrategist", 0.85, 0.65, 0.8, "Minor adjustment"),
        ]

        result = synth.synthesize(r1, r2)
        print(f"Consensus DQ: {result.consensus_dq:.4f}")
        print(f"Sycophancy flagged: {result.sycophancy_flagged}")
        print(f"Disagreement dims: {result.disagreement_dimensions}")
        print(f"\nTrajectories:")
        for t in result.trajectories:
            print(f"  {t.agent_name}: stability={t.stability_score:.4f} weight={t.trajectory_weight:.4f} Δ={t.delta_composite:.4f}")


if __name__ == "__main__":
    main()
