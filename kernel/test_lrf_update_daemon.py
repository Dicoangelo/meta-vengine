"""
Tests for US-108: Weekly LRF Update Daemon

Covers:
- Skip when < 200 decisions
- Report generation with mock decisions
- Promotion detection at 5% threshold
- Dry-run doesn't write files
"""

import json
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# Import the module under test
sys_path_entry = str(Path(__file__).resolve().parent)
import sys
if sys_path_entry not in sys.path:
    sys.path.insert(0, sys_path_entry)

from importlib import import_module

# Import using importlib because of the hyphenated filename
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "lrf_update_daemon",
    Path(__file__).resolve().parent / "lrf-update-daemon.py",
)
lrf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lrf)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_decision(
    ts: float,
    complexity: float = 0.5,
    dq_score: float = 0.8,
    session_type: str = "testing",
    cognitive_mode: str = "peak",
    graph_confidence: float = 0.7,
    sample_id: str = "",
    perturbed_weights: dict | None = None,
) -> dict:
    """Create a mock routing decision."""
    d = {
        "ts": int(ts),
        "complexity": complexity,
        "dq": {"score": dq_score},
        "session_type": session_type,
        "cognitive_mode": cognitive_mode,
        "graph_confidence": graph_confidence,
    }
    if sample_id:
        d["bandit"] = {
            "sampleId": sample_id,
            "perturbedWeights": perturbed_weights or {},
        }
    return d


def _make_bandit_entry(sample_id: str, reward: float, ts: float) -> dict:
    return {
        "sampleId": sample_id,
        "reward": reward,
        "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
    }


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TempPaths:
    """Temporary file paths for testing."""

    def __init__(self, tmpdir: Path):
        self.dq_scores = tmpdir / "dq-scores.jsonl"
        self.bandit_history = tmpdir / "bandit-history.jsonl"
        self.lrf_clusters = tmpdir / "lrf-clusters.json"
        self.lrf_reports = tmpdir / "lrf-reports"


@pytest.fixture
def tmp_paths(tmp_path):
    return TempPaths(tmp_path)


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


# ─── Tests ───────────────────────────────────────────────────────────────────


class TestSkipWhenInsufficientDecisions:
    """Test that update is skipped when < 200 decisions."""

    def test_skip_with_zero_decisions(self, tmp_paths):
        # No files exist
        report = lrf.run_update(
            dry_run=False,
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )
        assert report["status"] == "skipped"
        assert report["totalDecisions"] == 0
        assert "200" in report["reason"]

    def test_skip_with_199_decisions(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(199)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )
        assert report["status"] == "skipped"
        assert report["totalDecisions"] == 199

    def test_does_not_skip_with_200_decisions(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(200)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )
        assert report["status"] == "completed"
        assert report["totalDecisions"] == 200


class TestReportGeneration:
    """Test report generation with mock decisions."""

    def test_report_has_required_fields(self, tmp_paths):
        now = _now_ts()
        decisions = [
            _make_decision(
                now - i * 60,
                complexity=0.3 if i < 100 else 0.8,
                dq_score=0.7 + (i % 10) * 0.02,
                session_type="debugging" if i < 100 else "research",
            )
            for i in range(250)
        ]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert report["status"] == "completed"
        assert report["totalDecisions"] == 250
        assert report["clusterCount"] == 5
        assert len(report["clusters"]) == 5
        assert "weekLabel" in report
        assert "timestamp" in report
        assert "summary" in report
        assert "trustedClusters" in report["summary"]
        assert "promotionCount" in report["summary"]
        assert "avgRewardOverall" in report["summary"]

    def test_clusters_have_required_fields(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(200)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        for c in report["clusters"]:
            assert "id" in c
            assert "size" in c
            assert "centroid" in c
            assert "avgReward" in c
            assert "bestWeights" in c
            assert "trusted" in c

    def test_cluster_sizes_sum_to_total(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(300)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        total_size = sum(c["size"] for c in report["clusters"])
        assert total_size == 300

    def test_report_written_to_disk(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(200)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert tmp_paths.lrf_clusters.exists()
        cluster_data = json.loads(tmp_paths.lrf_clusters.read_text())
        assert "clusters" in cluster_data
        assert cluster_data["version"] == "1.0.0"

        reports = list(tmp_paths.lrf_reports.glob("*.json"))
        assert len(reports) == 1

    def test_bandit_rewards_used_when_available(self, tmp_paths):
        now = _now_ts()
        decisions = []
        bandit_entries = []
        for i in range(200):
            sid = f"sample-{i}"
            decisions.append(
                _make_decision(
                    now - i * 60,
                    dq_score=0.5,
                    sample_id=sid,
                    perturbed_weights={"dq_validity_weight": 0.4},
                )
            )
            bandit_entries.append(_make_bandit_entry(sid, 0.9, now - i * 60))

        _write_jsonl(tmp_paths.dq_scores, decisions)
        _write_jsonl(tmp_paths.bandit_history, bandit_entries)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        # With bandit rewards of 0.9, overall avg should be ~0.9 not ~0.5
        assert report["summary"]["avgRewardOverall"] > 0.85


class TestPromotionDetection:
    """Test promotion detection at 5% threshold."""

    def test_promotion_detected_above_5pct(self):
        old_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.70, "trusted": True, "centroid": [], "bestWeights": {}},
            {"id": 1, "size": 100, "avgReward": 0.60, "trusted": True, "centroid": [], "bestWeights": {}},
        ]
        new_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.74, "trusted": True, "centroid": [], "bestWeights": {}},  # +5.7%
            {"id": 1, "size": 100, "avgReward": 0.61, "trusted": True, "centroid": [], "bestWeights": {}},  # +1.7%
        ]

        promotions = lrf.detect_promotions(new_clusters, old_clusters)
        assert len(promotions) == 1
        assert promotions[0]["clusterId"] == 0
        assert promotions[0]["improvementPct"] > 5.0

    def test_no_promotion_at_exactly_5pct(self):
        old_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.80, "trusted": True, "centroid": [], "bestWeights": {}},
        ]
        new_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.84, "trusted": True, "centroid": [], "bestWeights": {}},  # exactly 5%
        ]

        promotions = lrf.detect_promotions(new_clusters, old_clusters)
        assert len(promotions) == 0

    def test_no_promotion_below_5pct(self):
        old_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.80, "trusted": True, "centroid": [], "bestWeights": {}},
        ]
        new_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.83, "trusted": True, "centroid": [], "bestWeights": {}},  # +3.75%
        ]

        promotions = lrf.detect_promotions(new_clusters, old_clusters)
        assert len(promotions) == 0

    def test_promotion_skipped_for_untrusted_cluster(self):
        old_clusters = [
            {"id": 0, "size": 100, "avgReward": 0.60, "trusted": True, "centroid": [], "bestWeights": {}},
        ]
        new_clusters = [
            {"id": 0, "size": 30, "avgReward": 0.80, "trusted": False, "centroid": [], "bestWeights": {}},  # +33% but untrusted
        ]

        promotions = lrf.detect_promotions(new_clusters, old_clusters)
        assert len(promotions) == 0

    def test_promotion_with_previous_clusters(self, tmp_paths):
        """Integration: full cycle with existing clusters then improvement."""
        now = _now_ts()

        # Write existing clusters with low reward
        old_cluster_data = {
            "version": "1.0.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "k": 5,
            "clusters": [
                {"id": i, "size": 60, "centroid": [0.5] * 5, "avgReward": 0.50,
                 "bestWeights": {}, "trusted": True}
                for i in range(5)
            ],
        }
        tmp_paths.lrf_clusters.parent.mkdir(parents=True, exist_ok=True)
        tmp_paths.lrf_clusters.write_text(json.dumps(old_cluster_data))

        # Write 300 new decisions with high DQ scores (reward ~0.9)
        decisions = [
            _make_decision(now - i * 60, dq_score=0.90, complexity=0.5)
            for i in range(300)
        ]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert report["status"] == "completed"
        # At least some clusters should show promotions (0.50 -> ~0.90 = +80%)
        assert report["summary"]["promotionCount"] > 0


class TestDryRun:
    """Test that dry-run computes without writing files."""

    def test_dry_run_does_not_write_clusters(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(200)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dry_run=True,
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert report["status"] == "completed"
        assert not tmp_paths.lrf_clusters.exists()

    def test_dry_run_does_not_write_report(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(200)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        lrf.run_update(
            dry_run=True,
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert not tmp_paths.lrf_reports.exists()

    def test_dry_run_returns_valid_report(self, tmp_paths):
        now = _now_ts()
        decisions = [_make_decision(now - i * 60) for i in range(250)]
        _write_jsonl(tmp_paths.dq_scores, decisions)

        report = lrf.run_update(
            dry_run=True,
            dq_scores_path=tmp_paths.dq_scores,
            bandit_history_path=tmp_paths.bandit_history,
            lrf_clusters_path=tmp_paths.lrf_clusters,
            lrf_reports_dir=tmp_paths.lrf_reports,
        )

        assert report["status"] == "completed"
        assert len(report["clusters"]) == 5
        assert report["totalDecisions"] == 250


class TestKMeans:
    """Test the inline k-means implementation."""

    def test_kmeans_basic(self):
        points = [[0, 0], [0, 1], [10, 10], [10, 11]]
        centroids, assignments = lrf.kmeans(points, k=2, seed=42)
        assert len(centroids) == 2
        assert len(assignments) == 4
        # Points 0,1 should be in same cluster, 2,3 in another
        assert assignments[0] == assignments[1]
        assert assignments[2] == assignments[3]
        assert assignments[0] != assignments[2]

    def test_kmeans_empty(self):
        centroids, assignments = lrf.kmeans([], k=3)
        assert centroids == []
        assert assignments == []

    def test_kmeans_k_larger_than_n(self):
        points = [[1, 2], [3, 4]]
        centroids, assignments = lrf.kmeans(points, k=5, seed=42)
        assert len(centroids) == 2  # k clamped to n
        assert len(assignments) == 2


class TestFeatureExtraction:
    """Test feature extraction from decisions."""

    def test_basic_extraction(self):
        d = _make_decision(time.time(), complexity=0.7, dq_score=0.85,
                           session_type="research", cognitive_mode="morning")
        features = lrf.extract_features(d)
        assert len(features) == 5
        assert features[0] == 0.7  # complexity
        assert abs(features[1] - 1 / 7) < 0.01  # research = index 1
        assert features[2] == 0.0  # morning = index 0
        assert features[4] == 0.85  # dq_score

    def test_missing_fields_use_defaults(self):
        features = lrf.extract_features({"ts": int(time.time())})
        assert len(features) == 5
        assert features[0] == 0.5  # default complexity
        assert features[3] == 0.5  # default graph_confidence
        assert features[4] == 0.5  # default dq_score
