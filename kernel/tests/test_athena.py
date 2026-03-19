#!/usr/bin/env python3
"""
US-312: Sprint 4 Integration Test Suite — Athena

End-to-end tests covering all 12 Sprint 4 components:
  dashboard health API, weight history API, PCA projection, timeline API,
  48-param multiplier registry, multiplier bandit registry, volume gate,
  convergence detection, active inference routing, Pareto front,
  preference-aware BO, and preference scheduling.

Uses pytest + tmp_path. No real HTTP server. Target: < 30s total.
"""

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import serve.py helpers directly (no HTTP server needed)
_serve_spec = importlib.util.spec_from_file_location(
    "serve", PROJECT_ROOT / "kernel" / "dashboard" / "serve.py"
)
serve_mod = importlib.util.module_from_spec(_serve_spec)
_serve_spec.loader.exec_module(serve_mod)

# Import pca.py
_pca_spec = importlib.util.spec_from_file_location(
    "pca", PROJECT_ROOT / "kernel" / "dashboard" / "pca.py"
)
pca_mod = importlib.util.module_from_spec(_pca_spec)
_pca_spec.loader.exec_module(pca_mod)

# Import stability-monitor.py
_sm_spec = importlib.util.spec_from_file_location(
    "stability_monitor", PROJECT_ROOT / "kernel" / "stability-monitor.py"
)
stability_monitor = importlib.util.module_from_spec(_sm_spec)
_sm_spec.loader.exec_module(stability_monitor)
StabilityMonitor = stability_monitor.StabilityMonitor

# Import session-volume-gate.py
_svg_spec = importlib.util.spec_from_file_location(
    "session_volume_gate", PROJECT_ROOT / "kernel" / "session-volume-gate.py"
)
volume_gate = importlib.util.module_from_spec(_svg_spec)
_svg_spec.loader.exec_module(volume_gate)

# Import active-inference.py
_ai_spec = importlib.util.spec_from_file_location(
    "active_inference", PROJECT_ROOT / "kernel" / "active-inference.py"
)
active_inference = importlib.util.module_from_spec(_ai_spec)
_ai_spec.loader.exec_module(active_inference)
ActiveInferenceRouter = active_inference.ActiveInferenceRouter

# Import pareto.py
from kernel.pareto import ParetoTracker

# Import bayesian_optimizer.py
from kernel.bayesian_optimizer import BayesianWeightOptimizer

# Import param registry
from kernel.param_registry import ParamRegistry


# ---------------------------------------------------------------------------
# 1. Dashboard Health API
# ---------------------------------------------------------------------------

class TestDashboardHealthAPI:
    def test_dashboard_health_api(self, tmp_path):
        """Import serve.py health-building logic. Create mock data files.
        Verify response has banditEnabled, paramCount, totalDecisions."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Create mock learnable-params.json
        params = {
            "banditEnabled": True,
            "parameters": [{"id": f"p{i}", "value": 0.5} for i in range(48)],
            "groups": {},
        }
        (config_dir / "learnable-params.json").write_text(json.dumps(params))

        # Create mock bandit-state.json
        bandit = {"sampleCounter": 42}
        (data_dir / "bandit-state.json").write_text(json.dumps(bandit))

        # Monkey-patch serve module paths
        orig_lp = serve_mod.LEARNABLE_PARAMS
        orig_bs = serve_mod.BANDIT_STATE
        orig_bh = serve_mod.BANDIT_HISTORY
        orig_dh = serve_mod.DAEMON_HEALTH
        try:
            serve_mod.LEARNABLE_PARAMS = config_dir / "learnable-params.json"
            serve_mod.BANDIT_STATE = data_dir / "bandit-state.json"
            serve_mod.BANDIT_HISTORY = data_dir / "bandit-history.jsonl"
            serve_mod.DAEMON_HEALTH = tmp_path / "nonexistent-daemon.py"

            resp = serve_mod.build_health_response()
            assert resp["banditEnabled"] is True
            assert isinstance(resp["banditEnabled"], bool)
            assert resp["paramCount"] == 48
            assert isinstance(resp["paramCount"], int)
            assert resp["totalDecisions"] == 42
            assert isinstance(resp["totalDecisions"], int)
        finally:
            serve_mod.LEARNABLE_PARAMS = orig_lp
            serve_mod.BANDIT_STATE = orig_bs
            serve_mod.BANDIT_HISTORY = orig_bh
            serve_mod.DAEMON_HEALTH = orig_dh


# ---------------------------------------------------------------------------
# 2. Weight History API
# ---------------------------------------------------------------------------

class TestWeightHistoryAPI:
    def test_weight_history_api(self, tmp_path):
        """Create 3 mock weight snapshot JSON files. Verify returns sorted
        array by date with correct weight values."""
        snap_dir = tmp_path / "data" / "weight-snapshots"
        snap_dir.mkdir(parents=True)

        snapshots = [
            {"date": "2026-03-15", "weights": {"dq": 0.40, "cost": 0.30}},
            {"date": "2026-03-13", "weights": {"dq": 0.38, "cost": 0.32}},
            {"date": "2026-03-17", "weights": {"dq": 0.42, "cost": 0.28}},
        ]
        for i, snap in enumerate(snapshots):
            (snap_dir / f"snap-{i}.json").write_text(json.dumps(snap))

        orig = serve_mod.WEIGHT_SNAPSHOTS
        try:
            serve_mod.WEIGHT_SNAPSHOTS = snap_dir
            result = serve_mod.build_weight_history()

            assert len(result) == 3
            # Verify sorted by date ascending
            dates = [e["date"] for e in result]
            assert dates == sorted(dates), f"Not sorted: {dates}"
            assert dates == ["2026-03-13", "2026-03-15", "2026-03-17"]

            # Verify weight values are preserved
            assert result[0]["weights"]["dq"] == 0.38
            assert result[2]["weights"]["cost"] == 0.28
        finally:
            serve_mod.WEIGHT_SNAPSHOTS = orig


# ---------------------------------------------------------------------------
# 3. PCA Projection
# ---------------------------------------------------------------------------

class TestPCAProjection:
    def test_pca_projection(self):
        """Pass 5 synthetic 14-dim vectors. Verify output has 5 points,
        each with 2 coordinates. Different inputs produce different projections."""
        vectors = []
        for i in range(5):
            v = [0.0] * 14
            v[0] = i * 0.2
            v[1 + i] = 1.0
            v[10] = 0.5 + i * 0.1
            vectors.append(v)

        points = pca_mod.project_to_2d(vectors)

        assert len(points) == 5
        for pt in points:
            assert len(pt) == 2
            assert isinstance(pt[0], float)
            assert isinstance(pt[1], float)

        # Different input vectors should produce different projections
        unique_points = set(points)
        assert len(unique_points) == 5, (
            f"Expected 5 unique projections, got {len(unique_points)}"
        )


# ---------------------------------------------------------------------------
# 4. Timeline API
# ---------------------------------------------------------------------------

class TestTimelineAPI:
    def test_timeline_api(self, tmp_path):
        """Create mock rollback and A/B report JSON files. Verify events merged
        and sorted by timestamp descending with correct types."""
        rollback_dir = tmp_path / "data" / "rollback-reports"
        rollback_dir.mkdir(parents=True)
        ab_dir = tmp_path / "data" / "ab-reports"
        ab_dir.mkdir(parents=True)

        (rollback_dir / "rb-001.json").write_text(json.dumps({
            "timestamp": "2026-03-15T10:00:00Z",
            "trigger": "drift_exceeded",
            "severity": "warning",
        }))
        (rollback_dir / "rb-002.json").write_text(json.dumps({
            "timestamp": "2026-03-17T14:00:00Z",
            "trigger": "reward_drop",
            "severity": "critical",
        }))
        (ab_dir / "ab-001.json").write_text(json.dumps({
            "timestamp": "2026-03-16T12:00:00Z",
            "verdict": "candidate_wins",
        }))

        orig_rb = serve_mod.ROLLBACK_REPORTS_DIR
        orig_ab = serve_mod.AB_REPORTS_DIR
        try:
            serve_mod.ROLLBACK_REPORTS_DIR = rollback_dir
            serve_mod.AB_REPORTS_DIR = ab_dir

            events = serve_mod.build_timeline_response()

            assert len(events) == 3

            # Sorted descending by timestamp
            timestamps = [e["timestamp"] for e in events]
            assert timestamps == sorted(timestamps, reverse=True)

            # Verify types
            types = {e["timestamp"]: e["type"] for e in events}
            assert types["2026-03-15T10:00:00Z"] == "rollback"
            assert types["2026-03-17T14:00:00Z"] == "rollback"
            assert types["2026-03-16T12:00:00Z"] == "ab_test"
        finally:
            serve_mod.ROLLBACK_REPORTS_DIR = orig_rb
            serve_mod.AB_REPORTS_DIR = orig_ab


# ---------------------------------------------------------------------------
# 5. Multiplier Registry — 48 Params
# ---------------------------------------------------------------------------

class TestMultiplierRegistry48Params:
    def test_multiplier_registry_48_params(self):
        """Load real param registry. Verify 48 params total, session_multipliers
        group has 24 params, specific params exist with correct defaults."""
        registry = ParamRegistry()
        all_params = registry.get_all_params()

        assert len(all_params) == 48, f"Expected 48 params, got {len(all_params)}"

        # Verify session_multipliers group has 24 params
        session_mults = [p for p in all_params if p["group"] == "session_multipliers"]
        assert len(session_mults) == 24, (
            f"Expected 24 session_multipliers, got {len(session_mults)}"
        )

        # Verify specific params exist with correct defaults
        p_dq = registry.get_param("session_debugging_dq")
        assert p_dq is not None
        assert p_dq["value"] == 0.8

        p_cost = registry.get_param("session_research_cost")
        assert p_cost is not None
        assert p_cost["value"] == 0.8


# ---------------------------------------------------------------------------
# 6. Multiplier Bandit Uses Registry
# ---------------------------------------------------------------------------

class TestMultiplierBanditUsesRegistry:
    def test_multiplier_bandit_uses_registry(self):
        """Verify debugging multiplier params have expected values and differ
        from other session types."""
        registry = ParamRegistry()

        # Debugging multipliers
        debug_dq = registry.get_param("session_debugging_dq")
        debug_cost = registry.get_param("session_debugging_cost")
        debug_beh = registry.get_param("session_debugging_behavioral")

        assert debug_dq["value"] == 0.8
        assert debug_cost["value"] == 1.0
        assert debug_beh["value"] == 1.2

        # Research multipliers should be different
        research_dq = registry.get_param("session_research_dq")
        research_cost = registry.get_param("session_research_cost")
        research_beh = registry.get_param("session_research_behavioral")

        assert research_dq["value"] == 1.2
        assert research_cost["value"] == 0.8
        assert research_beh["value"] == 1.0

        # They should differ
        assert debug_dq["value"] != research_dq["value"]
        assert debug_cost["value"] != research_cost["value"]
        assert debug_beh["value"] != research_beh["value"]


# ---------------------------------------------------------------------------
# 7. Volume Gate
# ---------------------------------------------------------------------------

class TestVolumeGate:
    def test_volume_gate(self, tmp_path):
        """Create tmpdir session-type-stats.jsonl with debugging=150, creative=30.
        Verify debugging NOT gated, creative IS gated."""
        stats_path = tmp_path / "session-type-stats.jsonl"
        entries = [
            {"session_type": "debugging", "cumulative_count": 150},
            {"session_type": "creative", "cumulative_count": 30},
        ]
        with open(stats_path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        # Monkey-patch the module's STATS_PATH
        orig = volume_gate.STATS_PATH
        try:
            volume_gate.STATS_PATH = str(stats_path)

            # debugging: 150 >= 100 -> NOT gated
            assert volume_gate.is_gated("debugging") is False

            # creative: 30 < 100 -> IS gated
            assert volume_gate.is_gated("creative") is True

            # unknown type: 0 < 100 -> IS gated
            assert volume_gate.is_gated("unknown_type") is True
        finally:
            volume_gate.STATS_PATH = orig


# ---------------------------------------------------------------------------
# 8. Convergence Detection
# ---------------------------------------------------------------------------

class TestConvergenceDetection:
    def test_convergence_detection(self, tmp_path):
        """Create synthetic bandit history with 200 entries for debugging
        (barely changing <1%) -> converged. And 200 for research (>5% drift)
        -> converging."""
        history_path = tmp_path / "bandit-history.jsonl"
        stats_path = tmp_path / "session-type-stats.jsonl"
        convergence_path = tmp_path / "convergence-events.jsonl"

        # Write stats: both session types above volume gate
        with open(stats_path, "w") as f:
            f.write(json.dumps({"session_type": "debugging", "cumulative_count": 200}) + "\n")
            f.write(json.dumps({"session_type": "research", "cumulative_count": 200}) + "\n")

        # Write bandit history
        with open(history_path, "w") as f:
            # Debugging: 200 entries, multipliers barely change (<1%)
            for i in range(200):
                entry = {
                    "session_type": "debugging",
                    "multipliers": {
                        "dq": 0.80 + 0.001 * (i / 200),      # drifts 0.1%
                        "cost": 1.00 + 0.001 * (i / 200),
                        "behavioral": 1.20 + 0.001 * (i / 200),
                    },
                    "timestamp": f"2026-03-15T{10 + (i // 60):02d}:{i % 60:02d}:00Z",
                }
                f.write(json.dumps(entry) + "\n")

            # Research: 200 entries with >5% drift
            for i in range(200):
                entry = {
                    "session_type": "research",
                    "multipliers": {
                        "dq": 1.20 + 0.20 * (i / 200),       # drifts ~16.7%
                        "cost": 0.80 - 0.10 * (i / 200),
                        "behavioral": 1.00 + 0.15 * (i / 200),
                    },
                    "timestamp": f"2026-03-15T{10 + (i // 60):02d}:{i % 60:02d}:00Z",
                }
                f.write(json.dumps(entry) + "\n")

        monitor = StabilityMonitor(
            history_path=str(history_path),
            stats_path=str(stats_path),
            convergence_path=str(convergence_path),
            threshold_pct=1.0,
            window=200,
        )

        debug_result = monitor.check_convergence("debugging")
        assert debug_result["status"] == "converged", (
            f"Expected converged for debugging, got {debug_result}"
        )

        research_result = monitor.check_convergence("research")
        assert research_result["status"] == "converging", (
            f"Expected converging for research, got {research_result}"
        )


# ---------------------------------------------------------------------------
# 9. Active Inference Routing
# ---------------------------------------------------------------------------

class TestActiveInferenceRouting:
    def test_active_inference_routing(self, tmp_path):
        """Initialize ActiveInferenceRouter. Call select_model. Verify result
        has required keys. Call update_beliefs and verify alpha increased."""
        beliefs_path = tmp_path / "beliefs.json"
        pricing_path = PROJECT_ROOT / "config" / "pricing.json"

        router = ActiveInferenceRouter(str(beliefs_path), str(pricing_path))

        result = router.select_model("moderate")
        assert "model" in result
        assert "free_energy" in result
        assert "epistemic" in result
        assert "pragmatic" in result
        assert isinstance(result["model"], str)
        assert isinstance(result["free_energy"], (int, float))

        # Get the selected model and its current beliefs
        model = result["model"]
        beliefs_before = [
            a for a in router.state["beliefs"][model]["moderate"]
        ]

        # Update beliefs with a good outcome (quality=0.9 -> excellent -> index 3)
        router.update_beliefs(model, "moderate", 0.9)
        beliefs_after = router.state["beliefs"][model]["moderate"]

        # Alpha for "excellent" (index 3) should have increased by 1
        assert beliefs_after[3] == beliefs_before[3] + 1.0, (
            f"Expected alpha[3] to increase: before={beliefs_before[3]}, "
            f"after={beliefs_after[3]}"
        )


# ---------------------------------------------------------------------------
# 10. Pareto Front
# ---------------------------------------------------------------------------

class TestParetoFront:
    def test_pareto_front(self, tmp_path):
        """Create ParetoTracker with 3 objectives. Add 5 configs where 2 are
        clearly dominated. Verify front has exactly 3 non-dominated configs."""
        front_path = tmp_path / "pareto-front.json"
        tracker = ParetoTracker(
            objectives=[
                {"name": "quality", "direction": "maximize"},
                {"name": "cost", "direction": "minimize"},
                {"name": "latency", "direction": "maximize"},
            ],
            front_path=front_path,
            latency_config_path=tmp_path / "nonexistent-latency.json",
        )

        configs = [
            # Non-dominated configs (on the front)
            {"config_id": "A", "objectives": {"quality": 0.9, "cost": 0.10, "latency": 0.5}},
            {"config_id": "B", "objectives": {"quality": 0.7, "cost": 0.03, "latency": 0.8}},
            {"config_id": "C", "objectives": {"quality": 0.8, "cost": 0.05, "latency": 0.9}},
            # Dominated configs
            # D is dominated by A: lower quality, higher cost, same latency
            {"config_id": "D", "objectives": {"quality": 0.6, "cost": 0.15, "latency": 0.4}},
            # E is dominated by C: lower quality, higher cost, lower latency
            {"config_id": "E", "objectives": {"quality": 0.5, "cost": 0.08, "latency": 0.3}},
        ]

        for c in configs:
            tracker.add_config(c)

        front = tracker.get_front()
        front_ids = {c["config_id"] for c in front}

        assert len(front) == 3, f"Expected 3 on front, got {len(front)}: {front_ids}"
        assert "A" in front_ids
        assert "B" in front_ids
        assert "C" in front_ids
        assert "D" not in front_ids
        assert "E" not in front_ids


# ---------------------------------------------------------------------------
# 11. Preference-Aware BO
# ---------------------------------------------------------------------------

class TestPreferenceAwareBO:
    def test_preference_aware_bo(self, tmp_path):
        """Mock get_active_preferences to return different quality weights.
        Verify preference vectors differ between peak and off-peak."""
        prefs_path = tmp_path / "operator-preferences.json"
        prefs_data = {
            "default": {"quality": 0.5, "cost": 0.3, "latency": 0.2},
            "schedules": {
                "peak": {
                    "hours": [9, 10, 11, 12, 14, 15, 16, 17],
                    "preferences": {"quality": 0.7, "cost": 0.15, "latency": 0.15},
                },
                "off_peak": {
                    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 18, 19, 20, 21, 22, 23],
                    "preferences": {"quality": 0.3, "cost": 0.5, "latency": 0.2},
                },
            },
        }
        prefs_path.write_text(json.dumps(prefs_data))

        bo = BayesianWeightOptimizer(
            registry_path=PROJECT_ROOT / "config" / "learnable-params.json",
            history_path=tmp_path / "empty-history.jsonl",
            bo_state_path=tmp_path / "bo-state.json",
            preferences_path=prefs_path,
        )

        # Test peak hour (10)
        with patch("kernel.bayesian_optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = type("FakeDT", (), {"hour": 10})()
            mock_dt.utcnow = datetime.utcnow
            mock_dt.fromisoformat = datetime.fromisoformat
            peak_prefs = bo.get_active_preferences()

        # Test off-peak hour (22)
        with patch("kernel.bayesian_optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = type("FakeDT", (), {"hour": 22})()
            mock_dt.utcnow = datetime.utcnow
            mock_dt.fromisoformat = datetime.fromisoformat
            offpeak_prefs = bo.get_active_preferences()

        assert peak_prefs["preferences"]["quality"] == 0.7
        assert offpeak_prefs["preferences"]["quality"] == 0.3
        assert peak_prefs["preferences"] != offpeak_prefs["preferences"]


# ---------------------------------------------------------------------------
# 12. Preference Scheduling
# ---------------------------------------------------------------------------

class TestPreferenceScheduling:
    def test_preference_scheduling(self, tmp_path):
        """Mock datetime to hour=10 (peak) -> quality=0.7.
        Mock to hour=22 (off-peak) -> quality=0.3."""
        prefs_path = tmp_path / "operator-preferences.json"
        prefs_data = {
            "default": {"quality": 0.5, "cost": 0.3, "latency": 0.2},
            "schedules": {
                "peak": {
                    "hours": [9, 10, 11, 12, 14, 15, 16, 17],
                    "preferences": {"quality": 0.7, "cost": 0.15, "latency": 0.15},
                },
                "off_peak": {
                    "hours": [0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 18, 19, 20, 21, 22, 23],
                    "preferences": {"quality": 0.3, "cost": 0.5, "latency": 0.2},
                },
            },
        }
        prefs_path.write_text(json.dumps(prefs_data))

        bo = BayesianWeightOptimizer(
            registry_path=PROJECT_ROOT / "config" / "learnable-params.json",
            history_path=tmp_path / "empty-history.jsonl",
            bo_state_path=tmp_path / "bo-state.json",
            preferences_path=prefs_path,
        )

        # Peak: hour=10
        with patch("kernel.bayesian_optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = type("FakeDT", (), {"hour": 10})()
            mock_dt.utcnow = datetime.utcnow
            mock_dt.fromisoformat = datetime.fromisoformat
            result = bo.get_active_preferences()
            assert result["schedule"] == "peak"
            assert result["preferences"]["quality"] == 0.7

        # Off-peak: hour=22
        with patch("kernel.bayesian_optimizer.datetime") as mock_dt:
            mock_dt.now.return_value = type("FakeDT", (), {"hour": 22})()
            mock_dt.utcnow = datetime.utcnow
            mock_dt.fromisoformat = datetime.fromisoformat
            result = bo.get_active_preferences()
            assert result["schedule"] == "off_peak"
            assert result["preferences"]["quality"] == 0.3
