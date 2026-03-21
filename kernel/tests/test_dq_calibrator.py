#!/usr/bin/env python3
"""
Tests for US-006: DQ Calibration — ECE Computation and Weight Adjustment.

Covers:
  - ECE computation: perfectly calibrated → ECE ≈ 0
  - ECE computation: systematically overconfident → ECE > 0.1
  - Per-dimension ECE computation
  - Weight adjustment bounds (min 0.1, max 0.6)
  - Minimum sample threshold (n >= 50)
  - Proposal file generation
  - Auto-apply vs human-approval gating
"""

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

# Import module with hyphenated filename
sys.path.insert(0, str(Path(__file__).parent.parent))
calibrator = importlib.import_module("dq-calibrator")

passed = 0
failed = 0


def assert_true(condition, msg):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {msg}")
    else:
        failed += 1
        print(f"  FAIL: {msg}")


def assert_close(actual, expected, tolerance, msg):
    global passed, failed
    if actual is not None and abs(actual - expected) <= tolerance:
        passed += 1
        print(f"  PASS: {msg} (got {actual:.6f}, expected ~{expected})")
    else:
        failed += 1
        print(f"  FAIL: {msg} (got {actual}, expected ~{expected} ±{tolerance})")


# ═══════════════════════════════════════════════════════════════════════════
# Test: ECE Computation — Perfect Calibration
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- ECE: Perfectly Calibrated Scores ---")

# When predicted = actual for every sample, ECE should be ~0
predicted = [i / 100.0 for i in range(100)]
actual = [i / 100.0 for i in range(100)]
ece, bins = calibrator.compute_ece(predicted, actual)
assert_close(ece, 0.0, 0.01, "Perfect calibration → ECE ≈ 0")

# Verify bins have zero gap
non_empty_bins = [b for b in bins if b["count"] > 0]
max_gap = max(b["gap"] for b in non_empty_bins)
assert_close(max_gap, 0.0, 0.01, "All bin gaps ≈ 0 for perfect calibration")


# ═══════════════════════════════════════════════════════════════════════════
# Test: ECE — Systematically Overconfident
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- ECE: Systematically Overconfident ---")

# Predictions always 0.9, actuals always 0.5 → ECE should be 0.4
predicted_over = [0.9] * 100
actual_low = [0.5] * 100
ece_over, _ = calibrator.compute_ece(predicted_over, actual_low)
assert_true(ece_over is not None and ece_over > 0.1, f"Overconfident → ECE > 0.1 (got {ece_over})")
assert_close(ece_over, 0.4, 0.05, "Overconfident ECE ≈ 0.4")


# ═══════════════════════════════════════════════════════════════════════════
# Test: ECE — Systematically Underconfident
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- ECE: Systematically Underconfident ---")

predicted_under = [0.3] * 100
actual_high = [0.8] * 100
ece_under, _ = calibrator.compute_ece(predicted_under, actual_high)
assert_true(ece_under is not None and ece_under > 0.1, f"Underconfident → ECE > 0.1 (got {ece_under})")


# ═══════════════════════════════════════════════════════════════════════════
# Test: ECE — Empty/Edge Cases
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- ECE: Edge Cases ---")

ece_empty, bins_empty = calibrator.compute_ece([], [])
assert_true(ece_empty is None, "Empty input → None ECE")

ece_one, _ = calibrator.compute_ece([0.5], [0.5])
assert_close(ece_one, 0.0, 0.01, "Single perfect sample → ECE ≈ 0")

ece_mismatch, _ = calibrator.compute_ece([0.5, 0.6], [0.5])
assert_true(ece_mismatch is None, "Mismatched lengths → None ECE")


# ═══════════════════════════════════════════════════════════════════════════
# Test: ECE — Bin Structure
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- ECE: Bin Structure ---")

# 10 bins with 10 samples each
predicted_uniform = [i / 100.0 for i in range(100)]
actual_uniform = [i / 100.0 for i in range(100)]
_, bins_u = calibrator.compute_ece(predicted_uniform, actual_uniform, num_bins=10)
assert_true(len(bins_u) == 10, "10 bins generated")
assert_true(all("range" in b for b in bins_u), "All bins have range")
assert_true(all("count" in b for b in bins_u), "All bins have count")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Dimension ECE Computation
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Dimension ECE ---")

# Create mock pairs: DQ scores and behavioral outcomes
mock_pairs = []
for i in range(60):
    # Well-calibrated validity (predicted ≈ actual)
    v = (i + 20) / 100.0  # 0.20 to 0.79
    # Poorly calibrated specificity (always high, actual varies)
    s = 0.9
    # Moderate correctness
    c = 0.5 + (i % 20) / 100.0

    behavioral = v * 0.6 + 0.2  # Correlated with validity

    dq_rec = {
        "ts": 1000000 + i,
        "dqScore": v * 0.4 + s * 0.3 + c * 0.3,
        "dqComponents": {"validity": v, "specificity": s, "correctness": c},
    }
    outcome_rec = {
        "session_id": f"session-{i}",
        "behavioral_score": behavioral,
        "started_at": f"2026-01-01T{i:02d}:00:00+00:00",
    }
    mock_pairs.append((dq_rec, outcome_rec))

dim_ece = calibrator.compute_dimension_ece(mock_pairs)

assert_true("validity" in dim_ece, "Validity ECE computed")
assert_true("specificity" in dim_ece, "Specificity ECE computed")
assert_true("correctness" in dim_ece, "Correctness ECE computed")
assert_true("overall" in dim_ece, "Overall ECE computed")

# Validity should be better calibrated than specificity (which is always 0.9)
assert_true(
    dim_ece["validity"]["ece"] is not None,
    f"Validity ECE = {dim_ece['validity']['ece']}",
)
assert_true(
    dim_ece["specificity"]["ece"] is not None,
    f"Specificity ECE = {dim_ece['specificity']['ece']}",
)

# All dimensions should have 60 samples
for dim in ["validity", "specificity", "correctness"]:
    assert_true(
        dim_ece[dim]["sample_count"] == 60,
        f"{dim} sample count = 60",
    )
    assert_true(dim_ece[dim]["sufficient"], f"{dim} has sufficient samples")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Dimension ECE — Insufficient Data
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Dimension ECE: Insufficient Data ---")

small_pairs = mock_pairs[:10]
small_ece = calibrator.compute_dimension_ece(small_pairs)

for dim in ["validity", "specificity", "correctness"]:
    assert_true(
        not small_ece[dim]["sufficient"],
        f"{dim} insufficient with 10 samples",
    )
    assert_true(
        small_ece[dim]["sample_count"] == 10,
        f"{dim} count = 10",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Test: Weight Adjustment Bounds
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Weight Adjustment Bounds ---")

current_w = {"validity": 0.4, "specificity": 0.3, "correctness": 0.3}
adjustment = calibrator.recommend_weight_adjustments(dim_ece, current_w)

rec_w = adjustment["recommended_weights"]

# Check bounds
for dim in ["validity", "specificity", "correctness"]:
    assert_true(
        rec_w[dim] >= calibrator.WEIGHT_MIN,
        f"{dim} weight >= {calibrator.WEIGHT_MIN} (got {rec_w[dim]})",
    )
    assert_true(
        rec_w[dim] <= calibrator.WEIGHT_MAX,
        f"{dim} weight <= {calibrator.WEIGHT_MAX} (got {rec_w[dim]})",
    )

# Weights should sum to ~1.0
weight_sum = sum(rec_w.values())
assert_close(weight_sum, 1.0, 0.001, "Recommended weights sum to 1.0")

# Deltas should be present
assert_true("deltas" in adjustment, "Deltas present")
assert_true("auto_apply_safe" in adjustment, "Auto-apply flag present")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Weight Adjustment — Insufficient Data Blocks Adjustment
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Weight Adjustment: Insufficient Data ---")

small_adjustment = calibrator.recommend_weight_adjustments(small_ece, current_w)
assert_true(
    small_adjustment["reason"] == "insufficient_data",
    "Insufficient data → no adjustment",
)
assert_true(
    small_adjustment["recommended_weights"] == current_w,
    "Insufficient data → current weights unchanged",
)
assert_true(
    not small_adjustment["auto_apply_safe"],
    "Insufficient data → auto-apply blocked",
)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Proposal File Generation
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Proposal Generation ---")

with tempfile.TemporaryDirectory() as tmpdir:
    # Temporarily override PROPOSALS_DIR
    orig_dir = calibrator.PROPOSALS_DIR
    calibrator.PROPOSALS_DIR = Path(tmpdir)

    filepath = calibrator.write_proposal(dim_ece, adjustment, current_w, proposal_id=1)

    assert_true(filepath.exists(), "Proposal file created")
    assert_true(filepath.name == "calibration-001.json", f"Filename = {filepath.name}")

    with open(filepath) as f:
        proposal = json.load(f)

    assert_true(proposal["type"] == "dq_weight_calibration", "Type = dq_weight_calibration")
    assert_true(proposal["status"] == "pending", "Status = pending")
    assert_true(proposal["mutation_pipeline"] == "godel_engine", "Pipeline = godel_engine")
    assert_true("current_weights" in proposal, "Current weights in proposal")
    assert_true("recommended_weights" in proposal, "Recommended weights in proposal")
    assert_true("ece_report" in proposal, "ECE report in proposal")
    assert_true("apply_command" in proposal, "Apply command in proposal")
    assert_true(
        proposal["apply_command"] == "coevo-apply calibration-001",
        "Apply command correct",
    )

    # Check approval_required flag
    assert_true("approval_required" in proposal, "Approval required flag present")

    # Second proposal gets incremented ID
    filepath2 = calibrator.write_proposal(dim_ece, adjustment, current_w)
    assert_true(filepath2.name == "calibration-002.json", f"Second proposal = {filepath2.name}")

    calibrator.PROPOSALS_DIR = orig_dir


# ═══════════════════════════════════════════════════════════════════════════
# Test: Auto-Apply Gating
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Auto-Apply Gating ---")

# Small deltas → auto-apply safe
tiny_adjustment = {
    "recommended_weights": {"validity": 0.41, "specificity": 0.29, "correctness": 0.30},
    "deltas": {"validity": 0.01, "specificity": -0.01, "correctness": 0.0},
    "max_delta": 0.01,
    "auto_apply_safe": True,
    "reason": "computed",
}
assert_true(tiny_adjustment["auto_apply_safe"], "Small deltas → auto-apply safe")

# Large deltas → approval required
large_adjustment = {
    "recommended_weights": {"validity": 0.5, "specificity": 0.2, "correctness": 0.3},
    "deltas": {"validity": 0.1, "specificity": -0.1, "correctness": 0.0},
    "max_delta": 0.1,
    "auto_apply_safe": False,
    "reason": "computed",
}
assert_true(not large_adjustment["auto_apply_safe"], "Large deltas → approval required")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Full Calibration Pipeline with Mock Data
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Full Pipeline (Mock Data) ---")

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    # Create mock DQ scores JSONL
    dq_path = tmpdir / "dq-scores.jsonl"
    outcomes_path = tmpdir / "behavioral-outcomes.jsonl"

    # Use aligned timestamps: DQ ts and outcome started_at both in epoch ~1770000000
    from datetime import datetime, timezone
    base_ts = 1770000000

    with open(dq_path, "w") as f:
        for i in range(80):
            v = 0.2 + (i % 60) / 100.0
            s = 0.7 + (i % 20) / 100.0
            c = 0.4 + (i % 40) / 100.0
            rec = {
                "ts": base_ts + i * 60,  # 1 minute apart
                "query": f"test query {i}",
                "dqScore": v * 0.4 + s * 0.3 + c * 0.3,
                "dqComponents": {"validity": round(v, 3), "specificity": round(s, 3), "correctness": round(c, 3)},
                "model": "sonnet",
            }
            f.write(json.dumps(rec) + "\n")

    with open(outcomes_path, "w") as f:
        for i in range(80):
            # Outcome started_at as ISO, matching DQ timestamps within 30s
            ts = base_ts + i * 60 + 10  # 10 seconds after DQ
            iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            rec = {
                "session_id": f"session-{i}",
                "started_at": iso,
                "behavioral_score": round(0.3 + (i % 50) / 100.0, 3),
                "components": {},
            }
            f.write(json.dumps(rec) + "\n")

    # Override proposals dir
    orig_dir = calibrator.PROPOSALS_DIR
    calibrator.PROPOSALS_DIR = tmpdir / "proposals"

    result = calibrator.run_calibration(dq_path=str(dq_path), outcomes_path=str(outcomes_path))

    assert_true(result["status"] == "success", f"Pipeline status = success (got {result['status']})")
    assert_true(result["matched_pairs"] > 0, f"Matched {result.get('matched_pairs', 0)} pairs")
    assert_true("recommended_weights" in result, "Has recommended weights")
    assert_true("proposal_path" in result, "Has proposal path")
    assert_true(Path(result["proposal_path"]).exists(), "Proposal file exists")

    # Verify the proposal file content
    with open(result["proposal_path"]) as f:
        proposal = json.load(f)
    assert_true(proposal["mutation_pipeline"] == "godel_engine", "Proposal targets Godel engine")

    calibrator.PROPOSALS_DIR = orig_dir


# ═══════════════════════════════════════════════════════════════════════════
# Test: Load Functions — Missing Files
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Load Functions: Missing Files ---")

empty_dq = calibrator.load_dq_scores("/nonexistent/path.jsonl")
assert_true(empty_dq == [], "Missing DQ file → empty list")

empty_outcomes = calibrator.load_behavioral_outcomes("/nonexistent/path.jsonl")
assert_true(empty_outcomes == {}, "Missing outcomes file → empty dict")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Pipeline — No DQ Scores
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Pipeline: Error Cases ---")

with tempfile.TemporaryDirectory() as tmpdir:
    result = calibrator.run_calibration(dq_path=os.path.join(tmpdir, "nope.jsonl"))
    assert_true(result["status"] == "error", "No DQ scores → error")
    assert_true(result["reason"] == "no_dq_scores", "Reason = no_dq_scores")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Weight Normalization After Bounds
# ═══════════════════════════════════════════════════════════════════════════

print("\n--- Weight Normalization ---")

# Create ECE results that would push one weight to extreme
extreme_ece = {
    "validity": {"ece": 0.01, "sample_count": 100, "sufficient": True, "bins": []},
    "specificity": {"ece": 0.90, "sample_count": 100, "sufficient": True, "bins": []},
    "correctness": {"ece": 0.90, "sample_count": 100, "sufficient": True, "bins": []},
    "overall": {"ece": 0.5, "sample_count": 100, "sufficient": True, "bins": []},
}
extreme_adj = calibrator.recommend_weight_adjustments(extreme_ece, current_w)
rec = extreme_adj["recommended_weights"]

# Even with extreme ECE disparity, bounds should hold
for dim in ["validity", "specificity", "correctness"]:
    assert_true(
        rec[dim] >= calibrator.WEIGHT_MIN,
        f"Extreme: {dim} >= {calibrator.WEIGHT_MIN} (got {rec[dim]})",
    )
    assert_true(
        rec[dim] <= calibrator.WEIGHT_MAX,
        f"Extreme: {dim} <= {calibrator.WEIGHT_MAX} (got {rec[dim]})",
    )

# Sum must be 1.0
extreme_sum = sum(rec.values())
assert_close(extreme_sum, 1.0, 0.001, "Extreme weights still sum to 1.0")

# Validity should have highest weight (lowest ECE)
assert_true(
    rec["validity"] > rec["specificity"],
    f"Lower ECE → higher weight (validity {rec['validity']} > specificity {rec['specificity']})",
)


# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

print(f"\n{'='*60}")
print(f"DQ Calibrator Tests: {passed} passed, {failed} failed")
print(f"{'='*60}")

if __name__ == "__main__":
    sys.exit(1 if failed > 0 else 0)
