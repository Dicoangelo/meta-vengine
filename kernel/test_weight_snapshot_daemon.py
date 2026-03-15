"""
Tests for US-106: Weight Snapshot Daemon

Covers:
- Snapshot creation with correct structure
- Promotion logic at 3% threshold
- Prune keeps promoted snapshots
- Epoch metrics computation
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Ensure kernel is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import importlib
wsd = importlib.import_module("weight-snapshot-daemon")


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal repo structure for testing."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    kernel_dir = tmp_path / "kernel"
    kernel_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    snapshot_dir = data_dir / "weight-snapshots"
    snapshot_dir.mkdir()

    # Minimal learnable-params.json with 3 params (instead of 19) for fast tests
    params = {
        "version": "1.0.0",
        "description": "Test params",
        "banditEnabled": False,
        "parameters": [
            {
                "id": "test_weight_a",
                "configFile": "config/test.json",
                "jsonPath": "weights.a",
                "value": 0.50,
                "min": 0.0,
                "max": 1.0,
                "learnRate": 0.02,
                "group": "test_group",
            },
            {
                "id": "test_weight_b",
                "configFile": "config/test.json",
                "jsonPath": "weights.b",
                "value": 0.30,
                "min": 0.0,
                "max": 1.0,
                "learnRate": 0.02,
                "group": "test_group",
            },
            {
                "id": "test_weight_c",
                "configFile": "config/test.json",
                "jsonPath": "weights.c",
                "value": 0.20,
                "min": 0.0,
                "max": 1.0,
                "learnRate": 0.02,
                "group": "test_group",
            },
        ],
        "groups": {
            "test_group": {
                "constraint": "sumMustEqual",
                "target": 1.0,
                "description": "Test weights",
            }
        },
        "updated": "2026-03-14",
        "updatedBy": "test",
    }
    (config_dir / "learnable-params.json").write_text(json.dumps(params, indent=2))

    return tmp_path


@pytest.fixture
def registry(tmp_repo):
    """Load a ParamRegistry from the test repo."""
    from param_registry import ParamRegistry
    return ParamRegistry(tmp_repo / "config" / "learnable-params.json")


@pytest.fixture
def patch_dirs(tmp_repo, monkeypatch):
    """Patch daemon module paths to use tmp_repo."""
    monkeypatch.setattr(wsd, "REPO_ROOT", tmp_repo)
    monkeypatch.setattr(wsd, "DATA_DIR", tmp_repo / "data")
    monkeypatch.setattr(wsd, "SNAPSHOT_DIR", tmp_repo / "data" / "weight-snapshots")
    monkeypatch.setattr(wsd, "BANDIT_STATE_PATH", tmp_repo / "data" / "bandit-state.json")
    monkeypatch.setattr(wsd, "BANDIT_HISTORY_PATH", tmp_repo / "data" / "bandit-history.jsonl")
    return tmp_repo


class TestSnapshotCreation:
    """Test snapshot creation with correct structure."""

    def test_creates_snapshot_with_all_fields(self, registry, patch_dirs):
        snapshot = wsd.create_snapshot(registry, None, [], today="2026-03-14")

        assert snapshot["date"] == "2026-03-14"
        assert snapshot["version"] == "1.0.0"
        assert snapshot["param_count"] == 3
        assert "params" in snapshot
        assert "bandit_beliefs" in snapshot
        assert "epoch_metrics" in snapshot
        assert "promoted" in snapshot
        assert "created_at" in snapshot

    def test_params_contain_correct_values(self, registry, patch_dirs):
        snapshot = wsd.create_snapshot(registry, None, [], today="2026-03-14")
        params = snapshot["params"]

        assert "test_weight_a" in params
        assert params["test_weight_a"]["value"] == 0.50
        assert params["test_weight_a"]["min"] == 0.0
        assert params["test_weight_a"]["max"] == 1.0
        assert params["test_weight_a"]["group"] == "test_group"

    def test_bandit_beliefs_included_when_present(self, registry, patch_dirs):
        bandit_state = {
            "arms": {
                "test_weight_a": {"alpha": 5.0, "beta": 2.0},
                "test_weight_b": {"alpha": 3.0, "beta": 4.0},
            }
        }
        snapshot = wsd.create_snapshot(registry, bandit_state, [], today="2026-03-14")

        assert snapshot["bandit_beliefs"]["test_weight_a"]["alpha"] == 5.0
        assert snapshot["bandit_beliefs"]["test_weight_a"]["beta"] == 2.0

    def test_empty_bandit_state_gives_empty_beliefs(self, registry, patch_dirs):
        snapshot = wsd.create_snapshot(registry, None, [], today="2026-03-14")
        assert snapshot["bandit_beliefs"] == {}

    def test_save_and_load_snapshot(self, registry, patch_dirs):
        snapshot = wsd.create_snapshot(registry, None, [], today="2026-03-14")
        path = wsd.save_snapshot(snapshot)

        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["date"] == "2026-03-14"
        assert loaded["param_count"] == 3


class TestPromotionLogic:
    """Test promotion at 3% improvement threshold."""

    def test_no_promotion_without_previous(self, registry, patch_dirs):
        snapshot = wsd.create_snapshot(registry, None, [], today="2026-03-14")
        assert snapshot["promoted"] is False

    def test_promotion_at_exactly_3_percent(self, registry, patch_dirs):
        # Save a "previous" snapshot with avg_reward = 1.0
        prev = {
            "date": "2026-03-13",
            "epoch_metrics": {"avg_reward": 1.0},
            "promoted": False,
        }
        prev_path = wsd.SNAPSHOT_DIR / "2026-03-13.json"
        prev_path.write_text(json.dumps(prev))

        # History that gives avg_reward = 1.03 (exactly 3% improvement)
        history = [{"reward": 1.03, "explored": False}]
        snapshot = wsd.create_snapshot(registry, None, history, today="2026-03-14")
        assert snapshot["promoted"] is True

    def test_no_promotion_below_3_percent(self, registry, patch_dirs):
        prev = {
            "date": "2026-03-13",
            "epoch_metrics": {"avg_reward": 1.0},
            "promoted": False,
        }
        prev_path = wsd.SNAPSHOT_DIR / "2026-03-13.json"
        prev_path.write_text(json.dumps(prev))

        # 2% improvement -- not enough
        history = [{"reward": 1.02, "explored": False}]
        snapshot = wsd.create_snapshot(registry, None, history, today="2026-03-14")
        assert snapshot["promoted"] is False

    def test_promotion_above_3_percent(self, registry, patch_dirs):
        prev = {
            "date": "2026-03-13",
            "epoch_metrics": {"avg_reward": 0.80},
            "promoted": False,
        }
        prev_path = wsd.SNAPSHOT_DIR / "2026-03-13.json"
        prev_path.write_text(json.dumps(prev))

        # 10% improvement
        history = [{"reward": 0.88, "explored": False}]
        snapshot = wsd.create_snapshot(registry, None, history, today="2026-03-14")
        assert snapshot["promoted"] is True


class TestPruneLogic:
    """Test pruning keeps promoted snapshots."""

    def test_prune_old_unpromoted(self, patch_dirs):
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        snap = {"date": old_date, "promoted": False, "epoch_metrics": {}}
        (wsd.SNAPSHOT_DIR / f"{old_date}.json").write_text(json.dumps(snap))

        pruned = wsd.prune_snapshots()
        assert old_date in pruned
        assert not (wsd.SNAPSHOT_DIR / f"{old_date}.json").exists()

    def test_keep_old_promoted(self, patch_dirs):
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        snap = {"date": old_date, "promoted": True, "epoch_metrics": {}}
        (wsd.SNAPSHOT_DIR / f"{old_date}.json").write_text(json.dumps(snap))

        pruned = wsd.prune_snapshots()
        assert old_date not in pruned
        assert (wsd.SNAPSHOT_DIR / f"{old_date}.json").exists()

    def test_keep_recent_unpromoted(self, patch_dirs):
        recent_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        snap = {"date": recent_date, "promoted": False, "epoch_metrics": {}}
        (wsd.SNAPSHOT_DIR / f"{recent_date}.json").write_text(json.dumps(snap))

        pruned = wsd.prune_snapshots()
        assert recent_date not in pruned
        assert (wsd.SNAPSHOT_DIR / f"{recent_date}.json").exists()

    def test_dry_run_does_not_delete(self, patch_dirs):
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        snap = {"date": old_date, "promoted": False, "epoch_metrics": {}}
        (wsd.SNAPSHOT_DIR / f"{old_date}.json").write_text(json.dumps(snap))

        pruned = wsd.prune_snapshots(dry_run=True)
        assert old_date in pruned
        assert (wsd.SNAPSHOT_DIR / f"{old_date}.json").exists()  # still there


class TestEpochMetrics:
    """Test epoch metrics computation."""

    def test_empty_history(self):
        from param_registry import ParamRegistry
        metrics = wsd.compute_epoch_metrics([], [])
        assert metrics["avg_reward"] == 0.0
        assert metrics["reward_variance"] == 0.0
        assert metrics["exploration_rate"] == 0.0
        assert metrics["history_entries"] == 0

    def test_avg_reward_computation(self):
        history = [
            {"reward": 0.8, "explored": False},
            {"reward": 0.9, "explored": False},
            {"reward": 1.0, "explored": False},
        ]
        metrics = wsd.compute_epoch_metrics(history, [])
        assert abs(metrics["avg_reward"] - 0.9) < 0.001

    def test_exploration_rate(self):
        history = [
            {"reward": 0.8, "explored": True},
            {"reward": 0.9, "explored": False},
            {"reward": 1.0, "explored": True},
            {"reward": 0.7, "explored": False},
        ]
        metrics = wsd.compute_epoch_metrics(history, [])
        assert abs(metrics["exploration_rate"] - 0.5) < 0.001

    def test_reward_variance(self):
        history = [
            {"reward": 1.0, "explored": False},
            {"reward": 1.0, "explored": False},
        ]
        metrics = wsd.compute_epoch_metrics(history, [])
        assert metrics["reward_variance"] == 0.0

    def test_drift_from_baseline(self):
        params = [
            {"id": "a", "value": 0.5, "min": 0.0, "max": 1.0},
        ]
        metrics = wsd.compute_epoch_metrics([], params)
        # Current == baseline so drift should be 0
        assert metrics["drift_from_baseline"] == 0.0
