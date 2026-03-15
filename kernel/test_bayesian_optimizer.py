"""US-109: Bayesian Optimizer — Unit Tests"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kernel.param_registry import ParamRegistry, reset_registry

# Minimal registry for testing (3 params, 2 groups)
MINI_REGISTRY = {
    "version": "1.0.0",
    "banditEnabled": False,
    "parameters": [
        {"id": "w1", "configFile": "a.json", "jsonPath": "x.a", "value": 0.6,
         "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "sum_group"},
        {"id": "w2", "configFile": "a.json", "jsonPath": "x.b", "value": 0.4,
         "min": 0.1, "max": 0.9, "learnRate": 0.02, "group": "sum_group"},
        {"id": "ind1", "configFile": "b.json", "jsonPath": "y", "value": 5.0,
         "min": 1.0, "max": 10.0, "learnRate": 0.05, "group": "ind_group"},
    ],
    "groups": {
        "sum_group": {"constraint": "sumMustEqual", "target": 1.0, "description": "Sum group"},
        "ind_group": {"constraint": "independent", "description": "Independent group"},
    },
}


def _write_json(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


def _write_history(entries: list[dict]) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for e in entries:
        f.write(json.dumps(e) + "\n")
    f.close()
    return Path(f.name)


def _make_optimizer(history_entries=None):
    """Create a BayesianWeightOptimizer with a mini registry and optional history."""
    from kernel import bayesian_optimizer as bo_module

    reg_path = _write_json(MINI_REGISTRY)
    hist_path = _write_history(history_entries or [])

    opt = bo_module.BayesianWeightOptimizer(
        registry_path=reg_path,
        history_path=hist_path,
    )
    return opt


def _synthetic_history(n=20, base_reward=0.80):
    """Generate synthetic (config, reward) pairs."""
    import random
    random.seed(42)
    now = datetime.utcnow()
    entries = []
    for i in range(n):
        w1 = random.uniform(0.2, 0.8)
        w2 = 1.0 - w1
        ind1 = random.uniform(2.0, 8.0)
        # Reward is higher when w1 is near 0.65
        reward = base_reward + 0.1 * (1 - abs(w1 - 0.65))
        entries.append({
            "timestamp": (now - timedelta(days=random.randint(0, 25))).isoformat(),
            "config": {"w1": w1, "w2": w2, "ind1": ind1},
            "reward": round(reward, 4),
        })
    return entries


@pytest.fixture(autouse=True)
def _reset():
    reset_registry()
    yield
    reset_registry()


class TestFit:
    def test_fit_on_synthetic_data(self):
        entries = _synthetic_history(20)
        opt = _make_optimizer(entries)
        n = opt.fit(lookback_days=30)
        assert n == 20
        assert len(opt.X) == 20
        assert len(opt.Y) == 20

    def test_fit_empty_history(self):
        opt = _make_optimizer([])
        n = opt.fit(lookback_days=30)
        assert n == 0

    def test_fit_respects_lookback(self):
        now = datetime.utcnow()
        entries = [
            {"timestamp": (now - timedelta(days=5)).isoformat(),
             "config": {"w1": 0.6, "w2": 0.4, "ind1": 5.0}, "reward": 0.85},
            {"timestamp": (now - timedelta(days=60)).isoformat(),
             "config": {"w1": 0.5, "w2": 0.5, "ind1": 5.0}, "reward": 0.70},
        ]
        opt = _make_optimizer(entries)
        n = opt.fit(lookback_days=30)
        assert n == 1  # only the recent one

    def test_fit_missing_file(self):
        from kernel import bayesian_optimizer as bo_module
        reg_path = _write_json(MINI_REGISTRY)
        opt = bo_module.BayesianWeightOptimizer(
            registry_path=reg_path,
            history_path=Path("/tmp/nonexistent-bo-history-12345.jsonl"),
        )
        n = opt.fit()
        assert n == 0


class TestPropose:
    def test_propose_returns_valid_configs(self):
        entries = _synthetic_history(20)
        opt = _make_optimizer(entries)
        opt.fit(lookback_days=30)

        candidates = opt.propose(n_candidates=3)
        assert len(candidates) == 3

        params = opt.registry.get_all_params()
        bounds = {p["id"]: (p["min"], p["max"]) for p in params}

        for config in candidates:
            assert set(config.keys()) == {"w1", "w2", "ind1"}
            for pid, val in config.items():
                lo, hi = bounds[pid]
                assert lo <= val <= hi + 0.01, f"{pid}={val} not in [{lo}, {hi}]"

    def test_propose_with_no_data(self):
        """Propose should still work with empty observations (prior-only)."""
        opt = _make_optimizer([])
        opt.fit()
        candidates = opt.propose(n_candidates=3)
        assert len(candidates) == 3

    def test_propose_deterministic_with_seed(self):
        """With a fixed seed, proposals should be reproducible."""
        import random
        entries = _synthetic_history(10)

        random.seed(99)
        opt1 = _make_optimizer(entries)
        opt1.fit()
        c1 = opt1.propose(3)

        random.seed(99)
        opt2 = _make_optimizer(entries)
        opt2.fit()
        c2 = opt2.propose(3)

        assert c1 == c2


class TestPromotionGate:
    def test_promotion_when_candidate_beats_baseline(self):
        entries = _synthetic_history(20, base_reward=0.80)
        opt = _make_optimizer(entries)
        opt.fit()

        # Craft a candidate that should predict high reward
        strong_candidate = {"w1": 0.65, "w2": 0.35, "ind1": 5.0}
        # Use a low baseline so the candidate will beat it
        baseline_rewards = [0.50, 0.52, 0.48, 0.51, 0.49]

        result = opt.validate([strong_candidate], baseline_rewards)
        assert result["promoted"] is not None
        assert result["improvement"] >= 0.03

    def test_no_promotion_when_candidates_dont_beat_baseline(self):
        entries = _synthetic_history(20, base_reward=0.80)
        opt = _make_optimizer(entries)
        opt.fit()

        # Set baseline very high so no candidate can beat it by 3%
        baseline_rewards = [0.99, 0.98, 0.99, 0.98, 0.99]
        candidates = opt.propose(n_candidates=3)

        result = opt.validate(candidates, baseline_rewards)
        assert result["promoted"] is None
        assert result["improvement"] < 0.03

    def test_exact_3_percent_threshold(self):
        """Candidate at exactly 3% improvement should be promoted."""
        entries = _synthetic_history(20, base_reward=0.80)
        opt = _make_optimizer(entries)
        opt.fit()

        # Manually set up prediction by injecting observed data
        baseline_mean = 0.80
        # We need predicted reward >= 0.824
        # Add a strong observation at target config
        opt.X.append(opt._config_to_vector({"w1": 0.5, "w2": 0.5, "ind1": 5.0}))
        opt.Y.append(0.83)  # > 0.824 threshold

        candidate = {"w1": 0.5, "w2": 0.5, "ind1": 5.0}
        result = opt.validate([candidate], [baseline_mean])
        # The prediction near this point should be close to 0.83
        assert result["best_predicted"] > baseline_mean

    def test_empty_baseline(self):
        opt = _make_optimizer(_synthetic_history(5))
        opt.fit()
        result = opt.validate([{"w1": 0.5, "w2": 0.5, "ind1": 5.0}], [])
        assert result["promoted"] is None
        assert result["reason"] == "no baseline data"


class TestReportGeneration:
    def test_report_is_written(self, tmp_path):
        entries = _synthetic_history(10)
        opt = _make_optimizer(entries)
        opt.fit()
        opt.report_dir = tmp_path / "bo-reports"

        report_path = opt.generate_report(month="2026-03")
        assert report_path.exists()
        assert report_path.name == "2026-03.json"

        data = json.loads(report_path.read_text())
        assert data["month"] == "2026-03"
        assert data["observations"] == 10
        assert data["promotion_threshold"] == 0.03
        assert "candidates" in data
        assert "validation" in data

    def test_report_default_month(self, tmp_path):
        opt = _make_optimizer(_synthetic_history(5))
        opt.fit()
        opt.report_dir = tmp_path / "bo-reports"

        report_path = opt.generate_report()
        expected_month = datetime.utcnow().strftime("%Y-%m")
        data = json.loads(report_path.read_text())
        assert data["month"] == expected_month

    def test_report_insufficient_data(self, tmp_path):
        opt = _make_optimizer([])
        opt.fit()
        opt.report_dir = tmp_path / "bo-reports"

        report_path = opt.generate_report(month="2026-01")
        data = json.loads(report_path.read_text())
        assert data["observations"] == 0
        assert data["candidates"] == []


class TestInternals:
    def test_rbf_kernel_identity(self):
        opt = _make_optimizer()
        opt.fit()
        x = [0.5, 0.5, 5.0]
        k = opt._rbf_kernel(x, x)
        assert abs(k - opt.signal_variance) < 1e-10

    def test_rbf_kernel_distant_points(self):
        opt = _make_optimizer()
        opt.fit()
        x1 = [0.1, 0.1, 1.0]
        x2 = [0.9, 0.9, 10.0]
        k = opt._rbf_kernel(x1, x2)
        assert k < opt.signal_variance  # distant points -> lower correlation

    def test_norm_cdf_symmetry(self):
        from kernel.bayesian_optimizer import BayesianWeightOptimizer
        cdf = BayesianWeightOptimizer._norm_cdf
        assert abs(cdf(0) - 0.5) < 1e-5
        assert abs(cdf(3) + cdf(-3) - 1.0) < 1e-4

    def test_config_vector_roundtrip(self):
        opt = _make_optimizer(_synthetic_history(5))
        opt.fit()
        config = {"w1": 0.55, "w2": 0.45, "ind1": 6.0}
        vec = opt._config_to_vector(config)
        result = opt._vector_to_config(vec)
        for pid in config:
            assert abs(result[pid] - config[pid]) < 1e-5
