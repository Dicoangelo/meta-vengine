#!/usr/bin/env python3
"""
US-006: DQ Calibration — ECE Computation and Weight Adjustment

Computes Expected Calibration Error (ECE) between DQ predictions and behavioral
outcomes to adjust DQ dimension weights (validity, specificity, correctness).

Key design decisions:
  - ECE binned into 10 deciles per DQ dimension
  - Weight adjustments bounded: min 0.1, max 0.6 (Security Architect requirement)
  - Minimum n >= 50 per dimension before adjustment
  - First cycle: proposal requiring human coevo-apply approval
  - Subsequent bounded cycles (delta < 0.05): can auto-apply
  - Output is a PROPOSAL to the Godel engine mutation pipeline (single weight authority)

Reads: dq-scores.jsonl, behavioral-outcomes.jsonl
Writes: proposals/calibration-NNN.json
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Paths
KERNEL_DIR = Path(__file__).parent
PROJECT_DIR = KERNEL_DIR.parent
DQ_SCORES_PATH = Path.home() / ".claude" / "kernel" / "dq-scores.jsonl"
BEHAVIORAL_OUTCOMES_PATH = PROJECT_DIR / "data" / "behavioral-outcomes.jsonl"
PROPOSALS_DIR = PROJECT_DIR / "proposals"
COGNITIVE_DQ_WEIGHTS_PATH = Path.home() / ".claude" / "kernel" / "cognitive-os" / "cognitive-dq-weights.json"

# Calibration constants
NUM_BINS = 10
MIN_SAMPLES_PER_DIMENSION = 50
WEIGHT_MIN = 0.1
WEIGHT_MAX = 0.6
AUTO_APPLY_DELTA_THRESHOLD = 0.05

# Default DQ weights (fallback)
DEFAULT_DQ_WEIGHTS = {
    "validity": 0.4,
    "specificity": 0.3,
    "correctness": 0.3,
}


def load_dq_scores(path=None):
    """Load DQ scores from JSONL. Returns list of records with dqComponents."""
    fpath = path or DQ_SCORES_PATH
    if not Path(fpath).exists():
        return []
    records = []
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "dqComponents" in rec and "dqScore" in rec:
                    records.append(rec)
            except json.JSONDecodeError:
                continue
    return records


def load_behavioral_outcomes(path=None):
    """Load behavioral outcomes from JSONL. Returns dict keyed by session_id."""
    fpath = path or BEHAVIORAL_OUTCOMES_PATH
    if not Path(fpath).exists():
        return {}
    outcomes = {}
    with open(fpath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                sid = rec.get("session_id")
                if sid:
                    outcomes[sid] = rec
            except json.JSONDecodeError:
                continue
    return outcomes


def load_current_weights():
    """Load current DQ weights from cognitive-dq-weights or defaults."""
    if COGNITIVE_DQ_WEIGHTS_PATH.exists():
        try:
            with open(COGNITIVE_DQ_WEIGHTS_PATH) as f:
                data = json.load(f)
            w = data.get("dq_weights", DEFAULT_DQ_WEIGHTS)
            return {
                "validity": w.get("validity", 0.4),
                "specificity": w.get("specificity", 0.3),
                "correctness": w.get("correctness", 0.3),
            }
        except (json.JSONDecodeError, KeyError):
            pass
    return dict(DEFAULT_DQ_WEIGHTS)


def match_dq_to_outcomes(dq_records, outcomes):
    """Match DQ score records to behavioral outcome records.

    DQ records have a timestamp (`ts`) and behavioral outcomes have a `session_id`.
    We match by finding the DQ record whose timestamp falls within the session window.

    For simplicity (and since DQ records don't carry session_id), we match by
    closest timestamp to session start. Returns list of (dq_record, outcome) pairs.
    """
    if not dq_records or not outcomes:
        return []

    # Build list of outcomes with parsed timestamps
    outcome_list = []
    for sid, outcome in outcomes.items():
        started = outcome.get("started_at")
        if not started:
            continue
        try:
            ts = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
        except (ValueError, AttributeError):
            continue
        outcome_list.append((ts, outcome))

    outcome_list.sort(key=lambda x: x[0])
    if not outcome_list:
        return []

    pairs = []
    used_outcomes = set()

    for dq in dq_records:
        dq_ts = dq.get("ts", 0)
        if dq_ts <= 0:
            continue

        # Find closest outcome by timestamp (within 1 hour window)
        best_match = None
        best_delta = float("inf")
        for ots, outcome in outcome_list:
            delta = abs(dq_ts - ots)
            if delta < best_delta and delta < 3600:  # 1 hour max
                oid = outcome.get("session_id")
                if oid not in used_outcomes:
                    best_delta = delta
                    best_match = outcome

        if best_match:
            oid = best_match.get("session_id")
            used_outcomes.add(oid)
            pairs.append((dq, best_match))

    return pairs


def compute_ece(predicted_scores, actual_scores, num_bins=NUM_BINS):
    """Compute Expected Calibration Error.

    Bins predicted scores into `num_bins` deciles, then for each bin computes
    |avg_predicted - avg_actual|, weighted by bin size.

    Args:
        predicted_scores: list of predicted values (0-1)
        actual_scores: list of actual outcome values (0-1)
        num_bins: number of bins (default 10)

    Returns:
        (ece, bin_details) where bin_details is a list of dicts per bin
    """
    if len(predicted_scores) != len(actual_scores) or len(predicted_scores) == 0:
        return None, []

    n = len(predicted_scores)
    bin_details = []
    ece = 0.0

    for b in range(num_bins):
        lower = b / num_bins
        upper = (b + 1) / num_bins

        # Collect samples in this bin
        bin_pred = []
        bin_actual = []
        for pred, actual in zip(predicted_scores, actual_scores):
            if lower <= pred < upper or (b == num_bins - 1 and pred == upper):
                bin_pred.append(pred)
                bin_actual.append(actual)

        bin_size = len(bin_pred)
        if bin_size == 0:
            bin_details.append({
                "bin": b,
                "range": [round(lower, 2), round(upper, 2)],
                "count": 0,
                "avg_predicted": None,
                "avg_actual": None,
                "gap": None,
            })
            continue

        avg_pred = sum(bin_pred) / bin_size
        avg_actual = sum(bin_actual) / bin_size
        gap = abs(avg_pred - avg_actual)

        ece += (bin_size / n) * gap

        bin_details.append({
            "bin": b,
            "range": [round(lower, 2), round(upper, 2)],
            "count": bin_size,
            "avg_predicted": round(avg_pred, 4),
            "avg_actual": round(avg_actual, 4),
            "gap": round(gap, 4),
        })

    return round(ece, 6), bin_details


def compute_dimension_ece(pairs):
    """Compute ECE per DQ dimension (validity, specificity, correctness) and overall.

    Args:
        pairs: list of (dq_record, behavioral_outcome) tuples

    Returns:
        dict with per-dimension and overall ECE, plus sample counts
    """
    dimensions = ["validity", "specificity", "correctness"]
    results = {}

    for dim in dimensions:
        predicted = []
        actual = []
        for dq, outcome in pairs:
            comp = dq.get("dqComponents", {})
            pred_val = comp.get(dim)
            actual_val = outcome.get("behavioral_score")
            if pred_val is not None and actual_val is not None:
                predicted.append(pred_val)
                actual.append(actual_val)

        ece, bins = compute_ece(predicted, actual)
        results[dim] = {
            "ece": ece,
            "sample_count": len(predicted),
            "bins": bins,
            "sufficient": len(predicted) >= MIN_SAMPLES_PER_DIMENSION,
        }

    # Overall ECE using composite DQ score
    overall_pred = []
    overall_actual = []
    for dq, outcome in pairs:
        dq_score = dq.get("dqScore")
        actual_val = outcome.get("behavioral_score")
        if dq_score is not None and actual_val is not None:
            overall_pred.append(dq_score)
            overall_actual.append(actual_val)

    overall_ece, overall_bins = compute_ece(overall_pred, overall_actual)
    results["overall"] = {
        "ece": overall_ece,
        "sample_count": len(overall_pred),
        "bins": overall_bins,
        "sufficient": len(overall_pred) >= MIN_SAMPLES_PER_DIMENSION,
    }

    return results


def recommend_weight_adjustments(ece_results, current_weights):
    """Recommend weight adjustments based on ECE per dimension.

    Strategy: dimensions with LOWER ECE (better calibrated) get higher weight.
    Adjustments are bounded by WEIGHT_MIN/WEIGHT_MAX and the sum normalizes to 1.0.

    Args:
        ece_results: output of compute_dimension_ece
        current_weights: current DQ dimension weights

    Returns:
        dict with recommended weights, deltas, and whether auto-apply is safe
    """
    dimensions = ["validity", "specificity", "correctness"]

    # Check if all dimensions have sufficient data
    all_sufficient = all(
        ece_results.get(dim, {}).get("sufficient", False) for dim in dimensions
    )
    if not all_sufficient:
        return {
            "recommended_weights": current_weights,
            "deltas": {d: 0.0 for d in dimensions},
            "auto_apply_safe": False,
            "reason": "insufficient_data",
            "details": {
                d: ece_results.get(d, {}).get("sample_count", 0)
                for d in dimensions
            },
        }

    # Inverse ECE weighting: lower ECE → higher weight
    eces = {}
    for dim in dimensions:
        ece_val = ece_results[dim]["ece"]
        if ece_val is None:
            ece_val = 0.5  # Conservative default
        eces[dim] = ece_val

    # Inverse: use (1 - ece) as raw weight signal
    raw_signals = {d: max(0.01, 1.0 - eces[d]) for d in dimensions}
    signal_sum = sum(raw_signals.values())

    # Normalize to sum=1 and blend with current weights (50/50 for stability)
    recommended = {}
    for dim in dimensions:
        target = raw_signals[dim] / signal_sum
        blended = 0.5 * current_weights.get(dim, 1 / 3) + 0.5 * target
        # Apply bounds
        blended = max(WEIGHT_MIN, min(WEIGHT_MAX, blended))
        recommended[dim] = blended

    # Iteratively normalize-then-bound until stable (preserves bounds)
    for _ in range(20):
        total = sum(recommended.values())
        if abs(total - 1.0) < 1e-9:
            # Already normalized — check bounds
            all_ok = all(WEIGHT_MIN <= recommended[d] <= WEIGHT_MAX for d in recommended)
            if all_ok:
                break
        # Normalize
        recommended = {d: v / total for d, v in recommended.items()}
        # Clamp
        clamped = False
        for d in recommended:
            if recommended[d] < WEIGHT_MIN:
                recommended[d] = WEIGHT_MIN
                clamped = True
            elif recommended[d] > WEIGHT_MAX:
                recommended[d] = WEIGHT_MAX
                clamped = True
        if not clamped:
            break
    # Final round
    recommended = {d: round(v, 4) for d, v in recommended.items()}

    # Compute deltas
    deltas = {
        d: round(recommended[d] - current_weights.get(d, 1 / 3), 4)
        for d in dimensions
    }

    # Auto-apply safe if all deltas < threshold
    max_delta = max(abs(v) for v in deltas.values())
    auto_apply_safe = max_delta < AUTO_APPLY_DELTA_THRESHOLD

    return {
        "recommended_weights": recommended,
        "deltas": deltas,
        "auto_apply_safe": auto_apply_safe,
        "max_delta": round(max_delta, 4),
        "reason": "computed",
    }


def get_next_proposal_id():
    """Get the next proposal file number."""
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    existing = list(PROPOSALS_DIR.glob("calibration-*.json"))
    if not existing:
        return 1
    nums = []
    for p in existing:
        try:
            num = int(p.stem.split("-")[1])
            nums.append(num)
        except (IndexError, ValueError):
            continue
    return max(nums, default=0) + 1


def write_proposal(ece_results, adjustment, current_weights, proposal_id=None):
    """Write calibration proposal to proposals/ directory.

    This is a PROPOSAL to the Godel engine mutation pipeline.
    Single weight authority — no parallel write path.

    Returns:
        Path to the written proposal file
    """
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    pid = proposal_id or get_next_proposal_id()
    filename = f"calibration-{pid:03d}.json"
    filepath = PROPOSALS_DIR / filename

    proposal = {
        "id": f"calibration-{pid:03d}",
        "type": "dq_weight_calibration",
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "dq-calibrator",
        "mutation_target": "dq_weights",
        "mutation_pipeline": "godel_engine",
        "current_weights": current_weights,
        "recommended_weights": adjustment["recommended_weights"],
        "deltas": adjustment["deltas"],
        "max_delta": adjustment.get("max_delta", 0),
        "auto_apply_safe": adjustment["auto_apply_safe"],
        "ece_report": {
            dim: {
                "ece": ece_results[dim]["ece"],
                "sample_count": ece_results[dim]["sample_count"],
                "sufficient": ece_results[dim]["sufficient"],
            }
            for dim in ["validity", "specificity", "correctness", "overall"]
        },
        "approval_required": not adjustment["auto_apply_safe"],
        "apply_command": f"coevo-apply calibration-{pid:03d}",
    }

    with open(filepath, "w") as f:
        json.dump(proposal, f, indent=2)

    return filepath


def run_calibration(dq_path=None, outcomes_path=None):
    """Run a full calibration cycle.

    Returns:
        dict with calibration report
    """
    # Load data
    dq_records = load_dq_scores(dq_path)
    outcomes = load_behavioral_outcomes(outcomes_path)
    current_weights = load_current_weights()

    if not dq_records:
        return {"status": "error", "reason": "no_dq_scores"}
    if not outcomes:
        return {"status": "error", "reason": "no_behavioral_outcomes"}

    # Match DQ scores to behavioral outcomes
    pairs = match_dq_to_outcomes(dq_records, outcomes)
    if not pairs:
        return {"status": "error", "reason": "no_matched_pairs", "dq_count": len(dq_records), "outcome_count": len(outcomes)}

    # Compute ECE per dimension
    ece_results = compute_dimension_ece(pairs)

    # Recommend weight adjustments
    adjustment = recommend_weight_adjustments(ece_results, current_weights)

    # Write proposal
    proposal_path = write_proposal(ece_results, adjustment, current_weights)

    return {
        "status": "success",
        "matched_pairs": len(pairs),
        "current_weights": current_weights,
        "ece": {
            dim: {
                "ece": ece_results[dim]["ece"],
                "sample_count": ece_results[dim]["sample_count"],
                "sufficient": ece_results[dim]["sufficient"],
            }
            for dim in ["validity", "specificity", "correctness", "overall"]
        },
        "recommended_weights": adjustment["recommended_weights"],
        "deltas": adjustment["deltas"],
        "auto_apply_safe": adjustment["auto_apply_safe"],
        "proposal_path": str(proposal_path),
    }


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="DQ Calibration — ECE Computation and Weight Adjustment"
    )
    parser.add_argument(
        "--dq-scores",
        default=None,
        help=f"Path to dq-scores.jsonl (default: {DQ_SCORES_PATH})",
    )
    parser.add_argument(
        "--outcomes",
        default=None,
        help=f"Path to behavioral-outcomes.jsonl (default: {BEHAVIORAL_OUTCOMES_PATH})",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed calibration report",
    )

    args = parser.parse_args()

    result = run_calibration(
        dq_path=args.dq_scores,
        outcomes_path=args.outcomes,
    )

    if result["status"] == "error":
        print(f"Calibration failed: {result['reason']}")
        sys.exit(1)

    print("DQ Calibration Report")
    print("=" * 60)
    print(f"Matched pairs: {result['matched_pairs']}")
    print()

    print("Current weights:")
    for dim, w in result["current_weights"].items():
        print(f"  {dim}: {w:.3f}")
    print()

    print("ECE per dimension:")
    for dim in ["validity", "specificity", "correctness", "overall"]:
        info = result["ece"][dim]
        status = "OK" if info["sufficient"] else f"INSUFFICIENT (n={info['sample_count']}, need {MIN_SAMPLES_PER_DIMENSION})"
        ece_str = f"{info['ece']:.4f}" if info["ece"] is not None else "N/A"
        print(f"  {dim:14s}: ECE={ece_str}  n={info['sample_count']:4d}  {status}")
    print()

    print("Recommended weights:")
    for dim, w in result["recommended_weights"].items():
        delta = result["deltas"][dim]
        sign = "+" if delta >= 0 else ""
        print(f"  {dim}: {w:.4f} ({sign}{delta:.4f})")
    print()

    if result["auto_apply_safe"]:
        print("Auto-apply: SAFE (all deltas < 0.05)")
    else:
        print("Auto-apply: BLOCKED (requires human approval)")
    print(f"Proposal: {result['proposal_path']}")


if __name__ == "__main__":
    main()
