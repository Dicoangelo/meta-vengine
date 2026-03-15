"""
Tests for US-105: WeightSafety — Drift Detection and Rollback
"""

import json
import os
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from project root or kernel/
import sys
sys.path.insert(0, str(Path(__file__).parent))

from importlib import import_module
weight_safety_mod = import_module("weight-safety")
WeightSafety = weight_safety_mod.WeightSafety


@pytest.fixture
def tmp_base(tmp_path):
    """Provide a temporary base directory with data/ subdirs."""
    (tmp_path / "data" / "weight-snapshots").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def safety(tmp_base):
    return WeightSafety(base_dir=tmp_base)


# ── Drift Detection ─────────────────────────────────────────────────

class TestCheckDrift:
    def test_no_violations_within_threshold(self, safety):
        start = {"a": 1.0, "b": 0.5}
        current = {"a": 1.04, "b": 0.52}  # 4% drift each
        violations = safety.check_drift(current, start)
        assert violations == []

    def test_triggers_on_greater_than_5pct(self, safety):
        start = {"a": 1.0, "b": 0.5}
        current = {"a": 1.06, "b": 0.5}  # a drifted 6%
        violations = safety.check_drift(current, start)
        assert len(violations) == 1
        assert violations[0]["param_id"] == "a"
        assert violations[0]["drift"] > 0.05

    def test_negative_drift_detected(self, safety):
        start = {"x": 0.40}
        current = {"x": 0.37}  # 7.5% drop
        violations = safety.check_drift(current, start)
        assert len(violations) == 1
        assert violations[0]["param_id"] == "x"

    def test_custom_max_drift(self, safety):
        start = {"a": 1.0}
        current = {"a": 1.02}  # 2% drift
        # Should violate a 1% threshold
        violations = safety.check_drift(current, start, max_drift=0.01)
        assert len(violations) == 1

    def test_missing_param_in_epoch_start_ignored(self, safety):
        start = {"a": 1.0}
        current = {"a": 1.0, "new_param": 0.5}
        violations = safety.check_drift(current, start)
        assert violations == []


# ── Clamp Drift ──────────────────────────────────────────────────────

class TestClampDrift:
    def test_clamps_excessive_upward_drift(self, safety):
        start = {"a": 1.0}
        current = {"a": 1.10}  # 10% drift, should clamp to 1.05
        clamped = safety.clamp_drift(current, start, max_drift=0.05)
        assert clamped["a"] == pytest.approx(1.05, abs=1e-5)

    def test_clamps_excessive_downward_drift(self, safety):
        start = {"a": 1.0}
        current = {"a": 0.90}  # -10% drift, should clamp to 0.95
        clamped = safety.clamp_drift(current, start, max_drift=0.05)
        assert clamped["a"] == pytest.approx(0.95, abs=1e-5)

    def test_no_clamp_within_bounds(self, safety):
        start = {"a": 1.0}
        current = {"a": 1.03}
        clamped = safety.clamp_drift(current, start, max_drift=0.05)
        assert clamped["a"] == pytest.approx(1.03, abs=1e-5)

    def test_new_param_passed_through(self, safety):
        start = {"a": 1.0}
        current = {"a": 1.0, "b": 0.5}
        clamped = safety.clamp_drift(current, start)
        assert clamped["b"] == 0.5


# ── Reward Drop Detection ───────────────────────────────────────────

class TestCheckRewardDrop:
    def test_detects_8pct_drop(self, safety):
        rolling = 0.90
        current = 0.82  # 8.9% drop
        assert safety.check_reward_drop(current, rolling) is True

    def test_no_trigger_below_threshold(self, safety):
        rolling = 0.90
        current = 0.85  # 5.6% drop, below 8%
        assert safety.check_reward_drop(current, rolling) is False

    def test_exact_threshold_no_trigger(self, safety):
        rolling = 1.0
        current = 0.92  # exactly 8%, not > 8%
        assert safety.check_reward_drop(current, rolling) is False

    def test_zero_rolling_avg_no_trigger(self, safety):
        assert safety.check_reward_drop(0.5, 0.0) is False


# ── Snapshots ────────────────────────────────────────────────────────

class TestSnapshots:
    def test_take_and_get_snapshot(self, safety, tmp_base):
        weights = {"a": 0.3, "b": 0.7}
        bandit = {"trials": 50, "arm": "graph_signal"}
        path = safety.take_snapshot(weights, bandit, avg_reward=0.85)

        assert os.path.exists(path)
        data = json.loads(Path(path).read_text())
        assert data["weights"] == weights
        assert data["bandit_state"] == bandit
        assert data["avg_reward"] == 0.85
        assert data["promoted"] is False

    def test_get_latest_snapshot(self, safety, tmp_base):
        safety.take_snapshot({"a": 0.1}, avg_reward=0.7)
        latest = safety.get_latest_snapshot()
        assert latest is not None
        assert latest["weights"]["a"] == 0.1

    def test_get_latest_snapshot_empty(self, safety, tmp_base):
        # Clear snapshot dir
        for f in (tmp_base / "data" / "weight-snapshots").glob("*.json"):
            f.unlink()
        assert safety.get_latest_snapshot() is None

    def test_rollback_restores_weights(self, safety, tmp_base):
        weights = {"x": 0.4, "y": 0.6}
        path = safety.take_snapshot(weights, avg_reward=0.9)
        restored = safety.rollback(path, reason="test rollback")
        assert restored == weights

    def test_rollback_missing_file_raises(self, safety, tmp_base):
        with pytest.raises(FileNotFoundError):
            safety.rollback("/nonexistent/path.json", reason="missing")


# ── Rollback Logging ────────────────────────────────────────────────

class TestRollbackLogging:
    def test_log_rollback_appends(self, safety, tmp_base):
        safety.log_rollback("drift too high", {"a": 0.5}, {"a": 0.3})
        safety.log_rollback("reward drop", {"b": 0.8}, {"b": 0.7})

        lines = safety.rollback_log.read_text().strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["reason"] == "drift too high"
        assert first["pre_weights"] == {"a": 0.5}
        assert first["post_weights"] == {"a": 0.3}

        second = json.loads(lines[1])
        assert second["reason"] == "reward drop"

    def test_log_alert(self, safety, tmp_base):
        safety.log_alert("drift_exceeded", {"param": "a", "drift": 0.07})
        lines = safety.alert_log.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["alert_type"] == "drift_exceeded"
        assert entry["details"]["param"] == "a"


# ── Prune Snapshots ─────────────────────────────────────────────────

class TestPruneSnapshots:
    def test_prune_old_snapshots(self, safety, tmp_base):
        snap_dir = tmp_base / "data" / "weight-snapshots"
        # Create an old snapshot (100 days ago)
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        old_snap = {"date": old_date, "weights": {}, "promoted": False}
        (snap_dir / f"{old_date}.json").write_text(json.dumps(old_snap))

        # Create a recent snapshot
        recent_date = datetime.now().strftime("%Y-%m-%d")
        recent_snap = {"date": recent_date, "weights": {}, "promoted": False}
        (snap_dir / f"{recent_date}.json").write_text(json.dumps(recent_snap))

        deleted = safety.prune_snapshots(max_age_days=90)
        assert deleted == 1
        assert not (snap_dir / f"{old_date}.json").exists()
        assert (snap_dir / f"{recent_date}.json").exists()

    def test_prune_keeps_promoted(self, safety, tmp_base):
        snap_dir = tmp_base / "data" / "weight-snapshots"
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        promoted_snap = {"date": old_date, "weights": {}, "promoted": True}
        (snap_dir / f"{old_date}.json").write_text(json.dumps(promoted_snap))

        deleted = safety.prune_snapshots(max_age_days=90, keep_promoted=True)
        assert deleted == 0
        assert (snap_dir / f"{old_date}.json").exists()

    def test_prune_deletes_promoted_when_flag_false(self, safety, tmp_base):
        snap_dir = tmp_base / "data" / "weight-snapshots"
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        promoted_snap = {"date": old_date, "weights": {}, "promoted": True}
        (snap_dir / f"{old_date}.json").write_text(json.dumps(promoted_snap))

        deleted = safety.prune_snapshots(max_age_days=90, keep_promoted=False)
        assert deleted == 1
