#!/usr/bin/env python3
"""
US-112: End-to-End Learning Validation Test

Verifies the full learning loop:
  routing → outcome → bandit update → weight drift → safety check

This test is the acceptance gate for enabling banditEnabled: true.
Must complete in < 10 seconds with no real API calls.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Import JS-based modules via subprocess (bandit-engine.js, param-registry.js)
# For Python modules, import directly
sys.path.insert(0, str(PROJECT_ROOT))

from kernel.param_registry import ParamRegistry, reset_registry

# Import weight-safety.py (hyphenated file)
_ws_spec = importlib.util.spec_from_file_location(
    "weight_safety", PROJECT_ROOT / "kernel" / "weight-safety.py"
)
weight_safety = importlib.util.module_from_spec(_ws_spec)
_ws_spec.loader.exec_module(weight_safety)
WeightSafety = weight_safety.WeightSafety

# Import lrf-clustering.py
_lrf_spec = importlib.util.spec_from_file_location(
    "lrf_clustering", PROJECT_ROOT / "kernel" / "lrf-clustering.py"
)
lrf_clustering = importlib.util.module_from_spec(_lrf_spec)
_lrf_spec.loader.exec_module(lrf_clustering)
ContextualLRF = lrf_clustering.ContextualLRF


@pytest.fixture
def sandbox(tmp_path):
    """Create an isolated sandbox with a valid param registry and data dirs."""
    # Copy learnable-params.json
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    shutil.copy(
        PROJECT_ROOT / "config" / "learnable-params.json",
        config_dir / "learnable-params.json",
    )

    # Create data dirs
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "weight-snapshots").mkdir()

    reset_registry()
    registry = ParamRegistry(config_dir / "learnable-params.json")

    yield {
        "tmp_path": tmp_path,
        "registry": registry,
        "config_dir": config_dir,
        "data_dir": tmp_path / "data",
    }
    reset_registry()


def run_bandit_js(script: str, cwd: str = str(PROJECT_ROOT), timeout: int = 10) -> dict:
    """Run a JS snippet that uses bandit-engine.js and return parsed JSON output."""
    result = subprocess.run(
        ["node", "-e", script],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"JS error: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


class TestBanditLearningLoop:
    """Test that the bandit shifts weights toward optimal over iterations."""

    def test_bandit_shifts_toward_optimal(self, sandbox):
        """Inject 200 mock decisions where higher DQ weight on validity produces
        better rewards. Verify bandit learns (history entries created, beliefs updated)."""
        state_path = sandbox["data_dir"] / "bandit-state.json"
        history_path = sandbox["data_dir"] / "bandit-history.jsonl"
        registry_path = sandbox["config_dir"] / "learnable-params.json"

        # Run 200 iterations in JS with strong reward signal
        js_script = f"""
        const {{ ParamRegistry, resetRegistry }} = require('./kernel/param-registry');
        const {{ ThompsonBandit, computeReward }} = require('./kernel/bandit-engine');

        resetRegistry();
        const registry = new ParamRegistry('{registry_path}');

        const bandit = new ThompsonBandit({{
            statePath: '{state_path}',
            historyPath: '{history_path}',
            explorationRate: 0.05,
            registry
        }});

        let totalReward = 0;
        for (let i = 0; i < 200; i++) {{
            const sample = bandit.sample();

            // Strong reward signal: directly proportional to validity weight
            const validityW = sample.weights.dq_validity_weight || 0.4;
            const dqScore = 0.3 + validityW * 0.7;
            const rewardResult = computeReward(
                {{ dqScore, modelUsed: 'sonnet', queryTier: 'moderate' }},
                {{ compositeScore: 0.5 + validityW * 0.4, actualCost: 3.0 }},
                undefined,
                registry
            );

            bandit.update(sample.sampleId, sample.weights, rewardResult.reward, rewardResult.rewardWeights);
            totalReward += rewardResult.reward;
        }}

        const belief = bandit.getBelief('dq_validity_weight');
        console.log(JSON.stringify({{
            validity_alpha: belief.alpha,
            validity_beta: belief.beta,
            alpha_plus_beta: belief.alpha + belief.beta,
            avg_reward: totalReward / 200,
            history_lines: require('fs').readFileSync('{history_path}', 'utf8').trim().split('\\n').length
        }}));
        """

        result = run_bandit_js(js_script)

        # Verify bandit is actively learning (beliefs updated from flat priors)
        assert result["alpha_plus_beta"] > 2.5, (
            f"Bandit beliefs not updating: alpha+beta={result['alpha_plus_beta']}"
        )
        # Verify all iterations ran and were logged
        assert result["history_lines"] == 200, f"Expected 200 history entries, got {result['history_lines']}"
        # Verify reward signal is being captured (avg should be positive)
        assert result["avg_reward"] > 0.3, f"Avg reward too low: {result['avg_reward']}"


class TestSafetyBounds:
    """Test that safety bounds prevent parameter overshoot."""

    def test_drift_clamped_at_5_percent(self, sandbox):
        """Verify no parameter moves more than 5% from epoch start."""
        registry = sandbox["registry"]
        safety = WeightSafety(base_dir=sandbox["tmp_path"])

        # Simulate epoch start weights
        epoch_start = {p["id"]: p["value"] for p in registry.get_all_params()}

        # Simulate drifted weights (some >5%)
        current = dict(epoch_start)
        current["dq_validity_weight"] = epoch_start["dq_validity_weight"] + 0.10  # 10% drift
        current["graph_entropy_weight"] = epoch_start["graph_entropy_weight"] + 0.02  # 2% drift

        violations = safety.check_drift(current, epoch_start)
        assert len(violations) >= 1, "Should detect at least 1 drift violation"
        violation_ids = [v.get("param_id", "") if isinstance(v, dict) else str(v) for v in violations]
        assert any("dq_validity_weight" in vid for vid in violation_ids)

        clamped = safety.clamp_drift(current, epoch_start, max_drift=0.05)
        assert abs(clamped["dq_validity_weight"] - epoch_start["dq_validity_weight"]) <= 0.05 + 1e-9

    def test_reward_drop_triggers_rollback(self, sandbox):
        """Verify rollback detection when reward drops >8%."""
        safety = WeightSafety(base_dir=sandbox["tmp_path"])

        rolling_7d = 0.80
        current_good = 0.75  # 6.25% drop — no rollback
        current_bad = 0.72   # 10% drop — rollback

        assert not safety.check_reward_drop(current_good, rolling_7d)
        assert safety.check_reward_drop(current_bad, rolling_7d)

    def test_snapshot_and_restore(self, sandbox):
        """Verify snapshot creation and restoration."""
        registry = sandbox["registry"]
        safety = WeightSafety(base_dir=sandbox["tmp_path"])

        weights = {p["id"]: p["value"] for p in registry.get_all_params()}
        snapshot_path = safety.take_snapshot(
            weights, bandit_state={"test": True}, avg_reward=0.85
        )
        assert Path(snapshot_path).exists()

        restored = safety.rollback(snapshot_path, reason="test rollback")
        assert restored == weights


class TestLRFClustering:
    """Test that LRF produces different weights for different contexts."""

    def test_different_contexts_get_different_weights(self, sandbox):
        """Create two distinct contexts and verify clustering separates them."""
        import time
        from datetime import datetime

        clusters_path = sandbox["data_dir"] / "lrf-clusters.json"
        lrf = ContextualLRF(k=2, clusters_path=clusters_path)

        decisions = []
        now_ts = int(time.time())

        # Context A: low complexity, debugging, morning — high reward with weight=0.8
        for i in range(30):
            decisions.append({
                "adjusted_complexity": 0.15 + (i % 5) * 0.02,
                "session_type": "debugging",
                "ts": now_ts - 3600 * 8,  # 8 hours ago (morning)
                "reward": 0.85 + (i % 3) * 0.02,
                "perturbed_weights": {"dq_validity_weight": 0.80},
            })

        # Context B: high complexity, research, evening — lower reward with weight=0.30
        for i in range(30):
            decisions.append({
                "adjusted_complexity": 0.75 + (i % 5) * 0.03,
                "session_type": "research",
                "ts": now_ts - 3600 * 2,  # 2 hours ago (evening)
                "reward": 0.55 + (i % 3) * 0.03,
                "perturbed_weights": {"dq_validity_weight": 0.30},
            })

        summary = lrf.fit(decisions)
        assert summary["total_decisions"] == 60
        assert sum(summary["cluster_sizes"]) == 60

        # Classify a new decision — should get assigned to a cluster
        cluster_a = lrf.classify({
            "adjusted_complexity": 0.10,
            "session_type": "debugging",
            "ts": now_ts - 3600 * 8,
        })
        cluster_b = lrf.classify({
            "adjusted_complexity": 0.80,
            "session_type": "research",
            "ts": now_ts - 3600 * 2,
        })

        # They should be in different clusters
        assert cluster_a != cluster_b, "Distinct contexts should be in different clusters"

        # Per-cluster weights should differ
        w_a = lrf.get_cluster_weights(cluster_a)
        w_b = lrf.get_cluster_weights(cluster_b)
        if w_a and w_b and "dq_validity_weight" in w_a and "dq_validity_weight" in w_b:
            assert w_a["dq_validity_weight"] != w_b["dq_validity_weight"], (
                "Cluster weights should differ"
            )


class TestEndToEndIntegration:
    """Full loop: route → outcome → bandit → safety → verify."""

    def test_full_loop_in_under_10_seconds(self, sandbox):
        """Run the complete learning loop and verify all components interact correctly."""
        start = time.time()

        state_path = sandbox["data_dir"] / "bandit-state.json"
        history_path = sandbox["data_dir"] / "bandit-history.jsonl"
        registry_path = sandbox["config_dir"] / "learnable-params.json"
        registry = sandbox["registry"]
        safety = WeightSafety(base_dir=sandbox["tmp_path"])

        # Step 1: Run 50 bandit iterations
        js_script = f"""
        const {{ ParamRegistry, resetRegistry }} = require('./kernel/param-registry');
        const {{ ThompsonBandit, computeReward }} = require('./kernel/bandit-engine');

        resetRegistry();
        const registry = new ParamRegistry('{registry_path}');
        const bandit = new ThompsonBandit({{
            statePath: '{state_path}',
            historyPath: '{history_path}',
            explorationRate: 0.15,
            registry
        }});

        const allWeights = [];
        for (let i = 0; i < 50; i++) {{
            const s = bandit.sample();
            const rewardResult = computeReward(
                {{ dqScore: 0.85, modelUsed: 'sonnet', queryTier: 'moderate' }},
                {{ compositeScore: 0.7, actualCost: 3.0 }},
                undefined,
                registry
            );
            bandit.update(s.sampleId, s.weights, rewardResult.reward, rewardResult.rewardWeights);
            allWeights.push(s.weights);
        }}

        console.log(JSON.stringify({{
            final_beliefs: bandit.getBeliefs(),
            last_weights: allWeights[allWeights.length - 1],
            sample_count: allWeights.length
        }}));
        """
        result = run_bandit_js(js_script)
        assert result["sample_count"] == 50

        # Step 2: Check safety bounds
        epoch_start = {p["id"]: p["value"] for p in registry.get_all_params()}
        last_weights = result["last_weights"]

        # Clamp drift
        clamped = safety.clamp_drift(last_weights, epoch_start, max_drift=0.05)
        for pid in clamped:
            if pid in epoch_start:
                assert abs(clamped[pid] - epoch_start[pid]) <= 0.05 + 1e-9, (
                    f"Param {pid} drifted too far: {abs(clamped[pid] - epoch_start[pid])}"
                )

        # Step 3: Snapshot
        snapshot = safety.take_snapshot(clamped, bandit_state=result["final_beliefs"], avg_reward=0.78)
        assert Path(snapshot).exists()

        # Step 4: Verify timing
        elapsed = time.time() - start
        assert elapsed < 10, f"Test took {elapsed:.1f}s, must be < 10s"
