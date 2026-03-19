"""
US-310: Multi-Objective Reward Surface — Pareto Front Tracker

Tracks configs across quality, cost, and latency objectives. Maintains a
Pareto front of non-dominated configurations. Integrates with the Bayesian
optimizer (US-109) to record each evaluated config and recompute the front.

Config format:
    {
        "config_id": "uuid",
        "timestamp": "ISO",
        "weights": {"param_id": value, ...},
        "objectives": {
            "quality": 0.85,    # DQ score (higher = better)
            "cost": 0.03,       # actual cost in $ (lower = better)
            "latency": 0.6      # from model-latency-tiers (higher = faster)
        },
        "model_used": "claude-sonnet-4-6",
        "on_front": true
    }
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.parent
DEFAULT_FRONT_PATH = BASE_DIR / "data" / "pareto-front.json"
DEFAULT_LATENCY_CONFIG_PATH = BASE_DIR / "config" / "model-latency-tiers.json"

DEFAULT_OBJECTIVES = [
    {"name": "quality", "direction": "maximize"},
    {"name": "cost", "direction": "minimize"},
    {"name": "latency", "direction": "maximize"},
]


class ParetoTracker:
    """
    N-objective Pareto front tracker.

    Maintains a set of evaluated configs and computes the non-dominated
    (Pareto-optimal) subset. Persists to data/pareto-front.json.
    """

    def __init__(
        self,
        objectives: list[dict[str, str]] | None = None,
        front_path: str | Path | None = None,
        latency_config_path: str | Path | None = None,
    ):
        self.objectives = objectives or list(DEFAULT_OBJECTIVES)
        self.front_path = Path(front_path or DEFAULT_FRONT_PATH)
        self.latency_config_path = Path(
            latency_config_path or DEFAULT_LATENCY_CONFIG_PATH
        )

        self._front: list[dict[str, Any]] = []
        self._all_evaluated: list[dict[str, Any]] = []
        self._latency_tiers: dict[str, float] = {}
        self._latency_default: float = 0.5

        self._load_latency_tiers()
        self.load()

    # ------------------------------------------------------------------
    # Latency config
    # ------------------------------------------------------------------

    def _load_latency_tiers(self) -> None:
        """Load model-latency-tiers.json."""
        if not self.latency_config_path.exists():
            return
        try:
            data = json.loads(self.latency_config_path.read_text())
            self._latency_tiers = data.get("tiers", {})
            self._latency_default = data.get("default", 0.5)
        except (json.JSONDecodeError, OSError):
            pass

    def get_latency_score(self, model_id: str) -> float:
        """Return latency proxy score for a model ID. Higher = faster."""
        return self._latency_tiers.get(model_id, self._latency_default)

    # ------------------------------------------------------------------
    # Dominance & front computation
    # ------------------------------------------------------------------

    def dominates(self, a: dict, b: dict) -> bool:
        """
        Config a dominates b if a is >= b on ALL objectives and strictly
        better on at least one. Respects direction (maximize vs minimize).
        """
        a_obj = a.get("objectives", {})
        b_obj = b.get("objectives", {})

        at_least_one_better = False

        for obj in self.objectives:
            name = obj["name"]
            direction = obj["direction"]
            a_val = a_obj.get(name, 0.0)
            b_val = b_obj.get(name, 0.0)

            if direction == "maximize":
                if a_val < b_val:
                    return False
                if a_val > b_val:
                    at_least_one_better = True
            else:  # minimize
                if a_val > b_val:
                    return False
                if a_val < b_val:
                    at_least_one_better = True

        return at_least_one_better

    def compute_front(self, configs: list[dict]) -> list[dict]:
        """
        Extract non-dominated configs from a list. O(N^2) pairwise comparison.
        Returns a new list of configs that are on the Pareto front.
        """
        if not configs:
            return []

        front = []
        for i, ci in enumerate(configs):
            dominated = False
            for j, cj in enumerate(configs):
                if i == j:
                    continue
                if self.dominates(cj, ci):
                    dominated = True
                    break
            if not dominated:
                front.append(ci)

        return front

    # ------------------------------------------------------------------
    # Tracking API
    # ------------------------------------------------------------------

    def add_config(self, config: dict) -> bool:
        """
        Add a config to the tracked set. Recomputes the front.
        Returns True if the new config is on the updated front.
        """
        # Ensure on_front is initially unset — will be set by recompute
        config = dict(config)  # shallow copy
        config.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")

        self._all_evaluated.append(config)

        # Recompute front
        self._front = self.compute_front(self._all_evaluated)

        # Mark on_front flags
        front_ids = {c.get("config_id") for c in self._front}
        for c in self._all_evaluated:
            c["on_front"] = c.get("config_id") in front_ids

        on_front = config.get("config_id") in front_ids
        self.save()
        return on_front

    def get_front(self) -> list[dict]:
        """Return current Pareto-optimal configs."""
        return list(self._front)

    def get_all_evaluated(self) -> list[dict]:
        """Return all configs ever evaluated."""
        return list(self._all_evaluated)

    # ------------------------------------------------------------------
    # Dashboard API
    # ------------------------------------------------------------------

    def get_front_for_api(self) -> dict[str, Any]:
        """
        Return JSON-serializable data for dashboard consumption.

        Returns:
            {
                "objectives": [...],
                "front": [...],
                "all_evaluated_count": int,
                "front_size": int,
                "last_updated": "ISO"
            }
        """
        return {
            "objectives": self.objectives,
            "front": self._front,
            "all_evaluated_count": len(self._all_evaluated),
            "front_size": len(self._front),
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist to data/pareto-front.json."""
        self.front_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "objectives": self.objectives,
            "front": self._front,
            "all_evaluated": self._all_evaluated,
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
        self.front_path.write_text(json.dumps(data, indent=2) + "\n")

    def load(self) -> None:
        """Load from data/pareto-front.json."""
        if not self.front_path.exists():
            return
        try:
            data = json.loads(self.front_path.read_text())
            self._front = data.get("front", [])
            self._all_evaluated = data.get("all_evaluated", [])
            # Restore objectives from file if present
            if "objectives" in data and data["objectives"]:
                self.objectives = data["objectives"]
        except (json.JSONDecodeError, OSError):
            pass
