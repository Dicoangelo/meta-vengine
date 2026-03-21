"""
US-109: Bayesian Optimization — Monthly Refinement

Lightweight Bayesian weight optimizer using kernel-weighted averaging
(no scipy/numpy dependency). Reads bandit-history.jsonl for (config, reward)
pairs, fits a simple GP surrogate, proposes candidates via Expected Improvement,
and enforces a 3% promotion gate before accepting new configs.
"""

import json
import math
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kernel.param_registry import ParamRegistry
from kernel.pareto import ParetoTracker

BASE_DIR = Path(__file__).parent.parent
DEFAULT_REGISTRY_PATH = BASE_DIR / "config" / "learnable-params.json"
DEFAULT_HISTORY_PATH = BASE_DIR / "data" / "bandit-history.jsonl"
DEFAULT_REPORT_DIR = BASE_DIR / "data" / "bo-reports"
DEFAULT_BO_STATE_PATH = BASE_DIR / "data" / "bo-state.json"
DEFAULT_PREFERENCES_PATH = BASE_DIR / "config" / "operator-preferences.json"


class BayesianWeightOptimizer:
    """
    Lightweight Bayesian optimizer over the learnable weight space.

    Uses kernel-weighted averaging (RBF kernel) for prediction and uncertainty
    estimation. Expected Improvement acquisition function proposes candidates.
    """

    PROMOTION_THRESHOLD = 0.03  # 3% improvement required

    def __init__(
        self,
        registry_path: str | Path | None = None,
        history_path: str | Path | None = None,
        bo_state_path: str | Path | None = None,
        preferences_path: str | Path | None = None,
    ):
        self.registry = ParamRegistry(registry_path or DEFAULT_REGISTRY_PATH)
        self.history_path = Path(history_path or DEFAULT_HISTORY_PATH)
        self.report_dir = DEFAULT_REPORT_DIR
        self.bo_state_path = Path(bo_state_path or DEFAULT_BO_STATE_PATH)
        self.preferences_path = Path(preferences_path or DEFAULT_PREFERENCES_PATH)

        # Observed data after fit()
        self.X: list[list[float]] = []  # config vectors
        self.Y: list[float] = []  # rewards
        self.param_ids: list[str] = []  # ordered param IDs for vector mapping

        # Pareto front tracker (US-310)
        self.pareto = ParetoTracker()

        # RBF kernel hyperparameters
        self.length_scale = 0.3
        self.signal_variance = 1.0
        self.noise_variance = 0.01

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, lookback_days: int = 30) -> int:
        """
        Fit the surrogate model on recent (config, reward) pairs from
        bandit-history.jsonl.

        Returns the number of observations loaded.
        """
        self.param_ids = [p["id"] for p in self.registry.get_all_params()]
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        self.X = []
        self.Y = []

        if not self.history_path.exists():
            return 0

        with open(self.history_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp", "")
                try:
                    entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
                except (ValueError, AttributeError):
                    # If timestamp is unparseable, include it anyway
                    entry_time = datetime.now(timezone.utc)

                if entry_time < cutoff:
                    continue

                config = entry.get("config", {})
                reward = entry.get("reward")
                if reward is None:
                    continue

                vec = self._config_to_vector(config)
                self.X.append(vec)
                self.Y.append(float(reward))

        return len(self.X)

    def get_active_preferences(self) -> dict[str, Any]:
        """
        Load operator preferences and resolve the active schedule based on
        current hour.

        Returns:
            {
                "preferences": {"quality": 0.7, "cost": 0.15, "latency": 0.15},
                "schedule": "peak",
                "hour": 14
            }
        """
        current_hour = datetime.now().hour

        # Load preferences config
        prefs_data: dict[str, Any] = {}
        if self.preferences_path.exists():
            try:
                prefs_data = json.loads(self.preferences_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        default_prefs = prefs_data.get("default", {"quality": 0.5, "cost": 0.3, "latency": 0.2})
        schedules = prefs_data.get("schedules", {})

        # Find matching schedule for current hour
        for schedule_name, schedule_def in schedules.items():
            hours = schedule_def.get("hours", [])
            if current_hour in hours:
                return {
                    "preferences": schedule_def.get("preferences", default_prefs),
                    "schedule": schedule_name,
                    "hour": current_hour,
                }

        # No schedule matched — use default
        return {
            "preferences": default_prefs,
            "schedule": "default",
            "hour": current_hour,
        }

    def _preference_weighted_ei(
        self,
        x: list[float],
        front: list[dict],
        preferences: dict[str, float],
    ) -> float:
        """
        Compute preference-weighted Expected Improvement across objectives.

        For each objective, computes EI relative to the best value on the
        Pareto front, then returns the weighted sum using operator preferences.
        """
        mu, sigma2 = self._predict(x)
        sigma = math.sqrt(sigma2)

        if sigma < 1e-8:
            return 0.0

        # Compute per-objective best values from the Pareto front
        obj_bests: dict[str, float] = {}
        for obj_def in self.pareto.objectives:
            name = obj_def["name"]
            direction = obj_def["direction"]
            values = [c.get("objectives", {}).get(name, 0.0) for c in front]
            if not values:
                obj_bests[name] = 0.0
            elif direction == "maximize":
                obj_bests[name] = max(values)
            else:  # minimize — flip sign so EI maximizes improvement
                obj_bests[name] = min(values)

        # The surrogate predicts a scalar reward; we decompose EI by
        # projecting the improvement onto each objective axis proportionally.
        # Per-objective EI ≈ preference_i * EI(scalar), weighted by how much
        # the objective contributes to the scalar reward.
        z = (mu - sum(obj_bests.values())) / sigma
        base_ei = (mu - sum(obj_bests.values())) * self._norm_cdf(z) + sigma * self._norm_pdf(z)
        base_ei = max(base_ei, 0.0)

        weighted_ei = 0.0
        for obj_name, pref_weight in preferences.items():
            weighted_ei += pref_weight * base_ei

        return weighted_ei

    def propose(self, n_candidates: int = 3) -> list[dict[str, float]]:
        """
        Propose n candidate weight configurations via Expected Improvement.

        Generates random candidates within parameter bounds, scores them
        with EI, and returns the top n.
        """
        params = self.registry.get_all_params()
        n_random = max(200, n_candidates * 100)

        candidates = []
        for _ in range(n_random):
            vec = []
            for p in params:
                val = random.uniform(p["min"], p["max"])
                vec.append(val)
            vec = self._enforce_constraints(vec)
            candidates.append(vec)

        # Score each candidate with EI — use preference-weighted EI when
        # a Pareto front exists (US-311), fall back to standard EI otherwise
        scored = []
        active_prefs = self.get_active_preferences()
        front = self.pareto.get_front()

        best_y = max(self.Y) if self.Y else 0.0
        for vec in candidates:
            if front:
                ei = self._preference_weighted_ei(
                    vec, front, active_prefs["preferences"]
                )
            else:
                # Cold start: no Pareto front yet, standard single-objective EI
                ei = self._expected_improvement(vec, best_y)
            scored.append((ei, vec))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:n_candidates]

        results = []
        for _, vec in top:
            config = self._vector_to_config(vec)
            results.append(config)

        return results

    def _set_bo_evaluation_active(self, active: bool) -> None:
        """
        Set the BO evaluation state in data/bo-state.json.

        When active=True, the bandit engine will skip perturbation and use
        current weights as-is, allowing clean evaluation of BO candidates.
        """
        self.bo_state_path.parent.mkdir(parents=True, exist_ok=True)
        state = {}
        if self.bo_state_path.exists():
            try:
                state = json.loads(self.bo_state_path.read_text())
            except (json.JSONDecodeError, OSError):
                state = {}
        state["boEvaluationActive"] = active
        state["lastUpdated"] = datetime.now(timezone.utc).isoformat() + "Z"
        self.bo_state_path.write_text(json.dumps(state, indent=2) + "\n")

    def validate(
        self,
        candidates: list[dict[str, float]],
        baseline_rewards: list[float],
    ) -> dict[str, Any]:
        """
        Validate candidates against baseline. A candidate is promoted only
        if its predicted reward beats the baseline mean by >= 3%.

        Sets boEvaluationActive=true before evaluation so the bandit engine
        freezes perturbation, then clears it after evaluation completes.

        Returns a dict with 'promoted' (the winning config or None),
        'baseline_mean', 'best_predicted', and 'improvement'.
        """
        if not baseline_rewards:
            return {
                "promoted": None,
                "baseline_mean": 0.0,
                "best_predicted": 0.0,
                "improvement": 0.0,
                "reason": "no baseline data",
            }

        # Freeze bandit perturbation during BO evaluation
        self._set_bo_evaluation_active(True)

        try:
            baseline_mean = sum(baseline_rewards) / len(baseline_rewards)
            threshold = baseline_mean * (1 + self.PROMOTION_THRESHOLD)

            best_candidate = None
            best_predicted = -math.inf

            for candidate in candidates:
                vec = self._config_to_vector(candidate)
                mu, _ = self._predict(vec)
                if mu > best_predicted:
                    best_predicted = mu
                    best_candidate = candidate

            improvement = (
                (best_predicted - baseline_mean) / baseline_mean
                if baseline_mean > 0
                else 0.0
            )

            if best_predicted >= threshold:
                return {
                    "promoted": best_candidate,
                    "baseline_mean": baseline_mean,
                    "best_predicted": best_predicted,
                    "improvement": improvement,
                    "reason": "candidate beats baseline by >= 3%",
                }

            return {
                "promoted": None,
                "baseline_mean": baseline_mean,
                "best_predicted": best_predicted,
                "improvement": improvement,
                "reason": f"best candidate improvement {improvement:.4f} < {self.PROMOTION_THRESHOLD}",
            }
        finally:
            # Always unfreeze bandit perturbation after evaluation
            self._set_bo_evaluation_active(False)

    def record_pareto_config(
        self,
        config: dict[str, float],
        quality: float,
        cost: float,
        model_used: str,
    ) -> bool:
        """
        Record a BO-evaluated config on the Pareto front (US-310).

        Latency is looked up from model-latency-tiers.json based on model_used.
        Returns True if the config lands on the Pareto front.
        """
        latency = self.pareto.get_latency_score(model_used)
        pareto_config = {
            "config_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "weights": config,
            "objectives": {
                "quality": quality,
                "cost": cost,
                "latency": latency,
            },
            "model_used": model_used,
        }
        return self.pareto.add_config(pareto_config)

    def generate_report(self, month: str | None = None) -> Path:
        """
        Generate a monthly BO report as data/bo-reports/YYYY-MM.json.

        Args:
            month: 'YYYY-MM' string. Defaults to current month.

        Returns the path to the written report file.
        """
        if month is None:
            month = datetime.now(timezone.utc).strftime("%Y-%m")

        self.report_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.report_dir / f"{month}.json"

        n_obs = len(self.X)
        baseline_rewards = list(self.Y) if self.Y else []

        candidates = self.propose(n_candidates=3) if n_obs >= 2 else []
        validation = (
            self.validate(candidates, baseline_rewards)
            if candidates
            else {"promoted": None, "reason": "insufficient data"}
        )

        # Include active preferences in report (US-311)
        active_prefs = self.get_active_preferences()

        report = {
            "month": month,
            "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            "observations": n_obs,
            "baseline_mean": (
                sum(self.Y) / len(self.Y) if self.Y else None
            ),
            "candidates": candidates,
            "validation": validation,
            "param_count": len(self.param_ids),
            "promotion_threshold": self.PROMOTION_THRESHOLD,
            "preferences": active_prefs,
        }

        report_path.write_text(json.dumps(report, indent=2) + "\n")
        return report_path

    # ------------------------------------------------------------------
    # Internal: GP surrogate via kernel-weighted averaging
    # ------------------------------------------------------------------

    def _rbf_kernel(self, x1: list[float], x2: list[float]) -> float:
        """Radial Basis Function kernel between two vectors."""
        sq_dist = sum((a - b) ** 2 for a, b in zip(x1, x2))
        return self.signal_variance * math.exp(
            -sq_dist / (2 * self.length_scale ** 2)
        )

    def _predict(self, x: list[float]) -> tuple[float, float]:
        """
        Predict mean and variance at point x using kernel-weighted averaging.

        With no observations, returns prior (0, signal_variance).
        """
        if not self.X:
            return 0.0, self.signal_variance

        weights = []
        for xi in self.X:
            k = self._rbf_kernel(x, xi)
            weights.append(k)

        total_weight = sum(weights) + self.noise_variance
        if total_weight < 1e-12:
            return 0.0, self.signal_variance

        # Kernel-weighted mean
        mu = sum(w * y for w, y in zip(weights, self.Y)) / total_weight

        # Uncertainty: prior variance minus explained variance
        k_self = self._rbf_kernel(x, x)
        explained = sum(w ** 2 for w in weights) / (total_weight ** 2)
        sigma2 = max(k_self * (1 - explained), 1e-8)

        return mu, sigma2

    def _expected_improvement(self, x: list[float], best_y: float) -> float:
        """
        Expected Improvement acquisition function.

        Uses the closed-form EI with a simple normal CDF/PDF approximation.
        """
        mu, sigma2 = self._predict(x)
        sigma = math.sqrt(sigma2)

        if sigma < 1e-8:
            return 0.0

        z = (mu - best_y) / sigma
        ei = (mu - best_y) * self._norm_cdf(z) + sigma * self._norm_pdf(z)
        return max(ei, 0.0)

    @staticmethod
    def _norm_pdf(x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

    @staticmethod
    def _norm_cdf(x: float) -> float:
        """
        Standard normal CDF approximation (Abramowitz & Stegun).
        Accurate to ~1e-5.
        """
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    # ------------------------------------------------------------------
    # Internal: vector <-> config conversion + constraint enforcement
    # ------------------------------------------------------------------

    def _config_to_vector(self, config: dict[str, float]) -> list[float]:
        """Convert a param_id->value dict to an ordered vector."""
        result = []
        for pid in self.param_ids:
            if pid in config:
                result.append(float(config[pid]))
            else:
                # Fall back to registry default
                p = self.registry.get_param(pid)
                result.append(p["value"])
        return result

    def _vector_to_config(self, vec: list[float]) -> dict[str, float]:
        """Convert an ordered vector back to a param_id->value dict."""
        return {pid: round(v, 6) for pid, v in zip(self.param_ids, vec)}

    def _enforce_constraints(self, vec: list[float]) -> list[float]:
        """
        Enforce group constraints (sum-to-target, monotonic, bounds)
        on a raw candidate vector.
        """
        params = self.registry.get_all_params()
        pid_to_idx = {p["id"]: i for i, p in enumerate(params)}

        # Clamp to bounds
        for i, p in enumerate(params):
            vec[i] = max(p["min"], min(p["max"], vec[i]))

        # Enforce sum constraints
        for gname in self.registry.get_group_names():
            gdef = self.registry.get_group_constraint(gname)
            if not gdef:
                continue

            members = self.registry.get_group(gname)
            indices = [pid_to_idx[m["id"]] for m in members]

            if gdef.get("constraint") == "sumMustEqual":
                target = gdef["target"]
                current_sum = sum(vec[i] for i in indices)
                if current_sum > 0:
                    scale = target / current_sum
                    for i in indices:
                        vec[i] *= scale
                        # Re-clamp after scaling
                        p = params[i]
                        vec[i] = max(p["min"], min(p["max"], vec[i]))

            elif gdef.get("constraint") == "monotonic":
                if gdef.get("direction") == "ascending":
                    vals = [(i, vec[i]) for i in indices]
                    vals.sort(key=lambda x: x[1])
                    for rank, (i, _) in enumerate(vals):
                        vec[i] = vals[rank][1]

        return vec
