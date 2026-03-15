#!/usr/bin/env python3
"""
US-107: Contextual LRF — Query Context Clustering

Clusters routing decisions by context so each cluster can have locally
optimized weights (Optimas Local Reward Function).

Context features: graphComplexity, sessionType (8 types), timeOfDay (5 modes), domain.
K-means clustering with k=5.
Per-cluster weight preferences: which configs produced highest rewards.
"""

import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
CLUSTERS_PATH = BASE_DIR / "data" / "lrf-clusters.json"
HISTORY_PATH = BASE_DIR / "data" / "bandit-history.jsonl"
DQ_SCORES_PATH = BASE_DIR / "kernel" / "dq-scores.jsonl"

# Session types from pattern-detector.js
SESSION_TYPES = [
    "debugging", "research", "architecture", "refactoring",
    "testing", "docs", "exploration", "creative"
]

# Cognitive OS time-of-day modes
TIME_MODES = ["morning", "peak", "dip", "evening", "deep_night"]


def _session_type_vector(session_type: str) -> list[float]:
    """One-hot encode session type."""
    vec = [0.0] * len(SESSION_TYPES)
    if session_type in SESSION_TYPES:
        vec[SESSION_TYPES.index(session_type)] = 1.0
    return vec


def _time_mode_vector(mode: str) -> list[float]:
    """One-hot encode time mode."""
    vec = [0.0] * len(TIME_MODES)
    if mode in TIME_MODES:
        vec[TIME_MODES.index(mode)] = 1.0
    return vec


def _hour_to_mode(hour: int) -> str:
    """Map hour to cognitive mode."""
    if 5 <= hour < 9:
        return "morning"
    elif 9 <= hour < 12 or 14 <= hour < 18:
        return "peak"
    elif 12 <= hour < 14:
        return "dip"
    elif 18 <= hour < 22:
        return "evening"
    else:
        return "deep_night"


def extract_features(decision: dict) -> list[float]:
    """Extract feature vector from a routing decision record.

    Returns a 14-dimensional vector:
      [0]     graphComplexity (float, 0-1)
      [1:9]   sessionType one-hot (8 dims)
      [9:14]  timeOfDay one-hot (5 dims)
    """
    complexity = decision.get("adjusted_complexity", decision.get("complexity", 0.5))
    session_type = decision.get("session_type", "exploration")
    ts = decision.get("ts", 0)

    if ts > 1e12:
        ts = ts / 1000  # Convert ms to seconds
    hour = datetime.fromtimestamp(ts).hour if ts > 0 else 12

    features = [float(complexity)]
    features.extend(_session_type_vector(session_type))
    features.extend(_time_mode_vector(_hour_to_mode(hour)))
    return features


def _euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


class ContextualLRF:
    """K-means clustering of routing decisions for per-context weight optimization."""

    def __init__(self, k: int = 5, clusters_path: Path | None = None):
        self.k = k
        self.clusters_path = clusters_path or CLUSTERS_PATH
        self.centroids: list[list[float]] = []
        self.cluster_weights: list[dict[str, float]] = []
        self.cluster_sizes: list[int] = []
        self.cluster_avg_rewards: list[float] = []
        self._loaded = False
        self._try_load()

    def _try_load(self) -> None:
        """Load existing clusters if available."""
        if self.clusters_path.exists():
            try:
                data = json.loads(self.clusters_path.read_text())
                self.centroids = data.get("centroids", [])
                self.cluster_weights = data.get("cluster_weights", [])
                self.cluster_sizes = data.get("cluster_sizes", [])
                self.cluster_avg_rewards = data.get("cluster_avg_rewards", [])
                self.k = len(self.centroids) if self.centroids else self.k
                self._loaded = bool(self.centroids)
            except (json.JSONDecodeError, KeyError):
                pass

    def fit(self, decisions: list[dict], max_iter: int = 50) -> dict[str, Any]:
        """Run k-means on routing decisions.

        Args:
            decisions: list of routing decision dicts with features + reward
            max_iter: maximum k-means iterations

        Returns:
            dict with cluster info
        """
        if len(decisions) < self.k:
            raise ValueError(f"Need at least {self.k} decisions, got {len(decisions)}")

        features = [extract_features(d) for d in decisions]
        rewards = [d.get("reward", 0.5) for d in decisions]
        weights_used = [d.get("perturbed_weights", {}) for d in decisions]

        # Initialize centroids via k-means++
        self.centroids = self._kmeans_pp_init(features)

        # Run k-means
        assignments = [0] * len(features)
        for _ in range(max_iter):
            # Assign
            new_assignments = [self._nearest(f) for f in features]
            if new_assignments == assignments:
                break
            assignments = new_assignments

            # Update centroids
            for c in range(self.k):
                members = [features[i] for i in range(len(features)) if assignments[i] == c]
                if members:
                    self.centroids[c] = _mean_vector(members)

        # Compute per-cluster metrics
        self.cluster_sizes = [0] * self.k
        self.cluster_avg_rewards = [0.0] * self.k
        cluster_best_weights: list[list[tuple[float, dict]]] = [[] for _ in range(self.k)]

        for i, c in enumerate(assignments):
            self.cluster_sizes[c] += 1
            cluster_best_weights[c].append((rewards[i], weights_used[i]))

        self.cluster_weights = []
        for c in range(self.k):
            entries = cluster_best_weights[c]
            if entries:
                self.cluster_avg_rewards[c] = sum(r for r, _ in entries) / len(entries)
                # Pick weights from the top 20% of rewards in this cluster
                entries.sort(key=lambda x: x[0], reverse=True)
                top_n = max(1, len(entries) // 5)
                top_weights = [w for _, w in entries[:top_n] if w]
                if top_weights:
                    avg_weights: dict[str, list[float]] = {}
                    for tw in top_weights:
                        for pid, val in tw.items():
                            avg_weights.setdefault(pid, []).append(val)
                    self.cluster_weights.append(
                        {pid: sum(vals) / len(vals) for pid, vals in avg_weights.items()}
                    )
                else:
                    self.cluster_weights.append({})
            else:
                self.cluster_avg_rewards[c] = 0.0
                self.cluster_weights.append({})

        self._loaded = True
        return self._summary()

    def _kmeans_pp_init(self, features: list[list[float]]) -> list[list[float]]:
        """K-means++ initialization."""
        centroids = [features[random.randint(0, len(features) - 1)]]
        for _ in range(1, self.k):
            dists = [min(_euclidean(f, c) for c in centroids) for f in features]
            total = sum(d * d for d in dists)
            if total == 0:
                centroids.append(features[random.randint(0, len(features) - 1)])
                continue
            r = random.random() * total
            cumulative = 0.0
            for i, d in enumerate(dists):
                cumulative += d * d
                if cumulative >= r:
                    centroids.append(features[i])
                    break
        return centroids

    def _nearest(self, feature: list[float]) -> int:
        """Find nearest centroid index."""
        return min(range(len(self.centroids)), key=lambda c: _euclidean(feature, self.centroids[c]))

    def classify(self, decision: dict) -> int:
        """Classify a single decision into a cluster.

        Returns cluster index, or -1 if no clusters loaded.
        """
        if not self._loaded or not self.centroids:
            return -1
        features = extract_features(decision)
        return self._nearest(features)

    def get_cluster_weights(self, cluster_idx: int) -> dict[str, float]:
        """Get optimal weight bias for a cluster.

        Returns empty dict if cluster not found or no weights available.
        """
        if 0 <= cluster_idx < len(self.cluster_weights):
            return dict(self.cluster_weights[cluster_idx])
        return {}

    def save(self) -> None:
        """Save clusters to disk."""
        self.clusters_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0.0",
            "k": self.k,
            "centroids": self.centroids,
            "cluster_weights": self.cluster_weights,
            "cluster_sizes": self.cluster_sizes,
            "cluster_avg_rewards": self.cluster_avg_rewards,
            "updated": datetime.now().isoformat(),
            "feature_schema": [
                "graphComplexity",
                *[f"sessionType_{t}" for t in SESSION_TYPES],
                *[f"timeMode_{m}" for m in TIME_MODES],
            ],
        }
        self.clusters_path.write_text(json.dumps(data, indent=2))

    def _summary(self) -> dict[str, Any]:
        return {
            "k": self.k,
            "cluster_sizes": self.cluster_sizes,
            "cluster_avg_rewards": self.cluster_avg_rewards,
            "total_decisions": sum(self.cluster_sizes),
        }
