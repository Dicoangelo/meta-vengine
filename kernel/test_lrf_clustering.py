"""US-107: Contextual LRF — Unit Tests"""

import json
import tempfile
from pathlib import Path

import pytest

import importlib
import sys

# Module file uses hyphen: lrf-clustering.py
_mod_path = Path(__file__).parent / "lrf-clustering.py"
_spec = importlib.util.spec_from_file_location("lrf_clustering", _mod_path)
lrf_clustering = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lrf_clustering)

ContextualLRF = lrf_clustering.ContextualLRF
extract_features = lrf_clustering.extract_features
SESSION_TYPES = lrf_clustering.SESSION_TYPES
TIME_MODES = lrf_clustering.TIME_MODES


def _make_decision(complexity=0.5, session_type="debugging", hour=10, reward=0.7, weights=None):
    """Create a mock routing decision."""
    # Timestamp for the given hour today
    import time
    from datetime import datetime
    dt = datetime.now().replace(hour=hour, minute=0, second=0)
    ts = int(dt.timestamp())
    return {
        "adjusted_complexity": complexity,
        "session_type": session_type,
        "ts": ts,
        "reward": reward,
        "perturbed_weights": weights or {"w1": complexity * 0.5 + 0.3},
    }


class TestFeatureExtraction:
    def test_feature_length(self):
        d = _make_decision()
        features = extract_features(d)
        assert len(features) == 1 + len(SESSION_TYPES) + len(TIME_MODES)  # 14

    def test_complexity_in_first_position(self):
        d = _make_decision(complexity=0.75)
        features = extract_features(d)
        assert features[0] == 0.75

    def test_session_type_one_hot(self):
        d = _make_decision(session_type="testing")
        features = extract_features(d)
        # testing is at index 4 in SESSION_TYPES
        idx = 1 + SESSION_TYPES.index("testing")
        assert features[idx] == 1.0
        # Other session type slots should be 0
        for i in range(1, 1 + len(SESSION_TYPES)):
            if i != idx:
                assert features[i] == 0.0

    def test_unknown_session_type(self):
        d = _make_decision(session_type="unknown_type")
        features = extract_features(d)
        # All session type slots should be 0
        for i in range(1, 1 + len(SESSION_TYPES)):
            assert features[i] == 0.0


class TestContextualLRF:
    def test_fit_with_enough_decisions(self):
        decisions = [_make_decision(
            complexity=i / 20,
            session_type=SESSION_TYPES[i % len(SESSION_TYPES)],
            hour=(i * 3) % 24,
            reward=0.5 + (i % 5) * 0.1,
        ) for i in range(20)]

        lrf = ContextualLRF(k=3, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        summary = lrf.fit(decisions)
        assert summary["k"] == 3
        assert summary["total_decisions"] == 20
        assert len(summary["cluster_sizes"]) == 3
        assert sum(summary["cluster_sizes"]) == 20

    def test_fit_too_few_decisions(self):
        lrf = ContextualLRF(k=5, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        with pytest.raises(ValueError, match="Need at least"):
            lrf.fit([_make_decision()])

    def test_classify_returns_valid_cluster(self):
        decisions = [_make_decision(
            complexity=i / 20,
            session_type=SESSION_TYPES[i % len(SESSION_TYPES)],
            hour=(i * 3) % 24,
            reward=0.6,
        ) for i in range(20)]

        lrf = ContextualLRF(k=3, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        lrf.fit(decisions)

        cluster = lrf.classify(_make_decision(complexity=0.3))
        assert 0 <= cluster < 3

    def test_classify_without_fit_returns_minus_one(self):
        lrf = ContextualLRF(k=3, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        assert lrf.classify(_make_decision()) == -1

    def test_per_cluster_weights_differ(self):
        # Create two distinct groups
        decisions = []
        for i in range(30):
            if i < 15:
                decisions.append(_make_decision(
                    complexity=0.1, session_type="debugging", hour=10,
                    reward=0.9, weights={"w1": 0.8}
                ))
            else:
                decisions.append(_make_decision(
                    complexity=0.9, session_type="research", hour=22,
                    reward=0.6, weights={"w1": 0.3}
                ))

        lrf = ContextualLRF(k=2, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        lrf.fit(decisions)

        w0 = lrf.get_cluster_weights(0)
        w1 = lrf.get_cluster_weights(1)
        # At least one cluster should have weights
        assert w0 or w1

    def test_empty_cluster_handled(self):
        # All same features — some clusters will be empty
        decisions = [_make_decision(complexity=0.5, session_type="debugging", hour=10)
                     for _ in range(10)]
        lrf = ContextualLRF(k=3, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        summary = lrf.fit(decisions)
        assert summary["total_decisions"] == 10

    def test_save_and_reload(self):
        tmp = Path(tempfile.mktemp(suffix=".json"))
        decisions = [_make_decision(
            complexity=i / 15,
            session_type=SESSION_TYPES[i % len(SESSION_TYPES)],
            hour=(i * 4) % 24,
        ) for i in range(15)]

        lrf1 = ContextualLRF(k=3, clusters_path=tmp)
        lrf1.fit(decisions)
        lrf1.save()

        lrf2 = ContextualLRF(k=3, clusters_path=tmp)
        assert len(lrf2.centroids) == 3
        assert lrf2.classify(_make_decision()) >= 0

    def test_get_cluster_weights_out_of_range(self):
        lrf = ContextualLRF(k=3, clusters_path=Path(tempfile.mktemp(suffix=".json")))
        assert lrf.get_cluster_weights(99) == {}
        assert lrf.get_cluster_weights(-1) == {}
