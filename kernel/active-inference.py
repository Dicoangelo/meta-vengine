#!/usr/bin/env python3
"""
Active Inference Router for Model Selection (US-309, Sprint 4)

Replaces HSRGS pressure-field with active inference:
- Generative model: Dirichlet beliefs over outcome quality per model x query-type
- Selection: minimize expected free energy G = -epistemic - pragmatic
- Learning: conjugate Dirichlet update from observed outcomes

Based on:
- Active Inference (Friston et al.) — free energy minimization
- Dirichlet-Categorical conjugacy for tractable belief updates
- IRT difficulty mapping for query-type classification

Author: D-Ecosystem / Metaventions AI
"""

import json
import math
import time
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================
# CONSTANTS
# ============================================================

QUERY_TYPES = ["easy", "moderate", "hard", "expert"]
OBSERVATION_CATEGORIES = ["poor", "adequate", "good", "excellent"]

# Default prior preferences (log scale)
DEFAULT_PRIOR_PREFERENCES = {
    "poor": -2.0,
    "adequate": -0.5,
    "good": 1.0,
    "excellent": 2.0
}

# IRT difficulty to query-type mapping thresholds
DIFFICULTY_THRESHOLDS = {
    "easy": (0.0, 0.3),
    "moderate": (0.3, 0.6),
    "hard": (0.6, 0.85),
    "expert": (0.85, 1.0)
}

# DQ score to observation category thresholds
OUTCOME_THRESHOLDS = [0.4, 0.6, 0.8]  # boundaries: poor|adequate|good|excellent


# ============================================================
# HELPERS
# ============================================================

def digamma_approx(x):
    """
    Stirling's approximation for the digamma function.
    digamma(x) ~ ln(x) - 1/(2x)  for x > 0.5
    For small x, use recurrence: digamma(x) = digamma(x+1) - 1/x
    """
    if x <= 0:
        return -1e10  # Guard against non-positive
    if x < 0.5:
        return digamma_approx(x + 1) - 1.0 / x
    return math.log(x) - 1.0 / (2.0 * x)


def difficulty_to_query_type(difficulty):
    """Map IRT difficulty (0-1) to query type string."""
    for qtype, (lo, hi) in DIFFICULTY_THRESHOLDS.items():
        if lo <= difficulty < hi:
            return qtype
    return "expert"  # difficulty >= 1.0


def outcome_to_category(quality_score):
    """Map outcome quality (0-1) to observation category index."""
    if quality_score < OUTCOME_THRESHOLDS[0]:
        return 0  # poor
    elif quality_score < OUTCOME_THRESHOLDS[1]:
        return 1  # adequate
    elif quality_score < OUTCOME_THRESHOLDS[2]:
        return 2  # good
    else:
        return 3  # excellent


def _load_pricing(pricing_path):
    """Load active models from pricing.json."""
    path = Path(pricing_path)
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)

    models = {}
    # Read from providers section for full model info
    for provider, pdata in data.get("providers", {}).items():
        for alias, mdata in pdata.get("models", {}).items():
            model_id = mdata.get("id", alias)
            models[model_id] = {
                "alias": alias,
                "provider": provider,
                "input_cost": mdata.get("input", 0),
                "output_cost": mdata.get("output", 0),
                "context_window": mdata.get("context_window", 128000),
                "display": mdata.get("display", model_id)
            }
    return models


def _classify_model_tier(model_id, model_info):
    """
    Classify a model into cost tier for Dirichlet initialization.
    Returns: 'cheap', 'mid', 'expensive'
    """
    cost = model_info.get("input_cost", 0)
    if cost >= 5.0:
        return "expensive"
    elif cost >= 1.0:
        return "mid"
    else:
        return "cheap"


def _init_dirichlet_for_model(tier):
    """
    Initialize Dirichlet alpha vectors per query type based on model tier.
    Returns dict: {query_type: [alpha_poor, alpha_adequate, alpha_good, alpha_excellent]}

    Expensive models: higher alphas for 'excellent' on hard/expert
    Cheap models: higher alphas for 'good' on easy/moderate
    All alphas >= 1.0
    """
    beliefs = {}
    for qtype in QUERY_TYPES:
        if tier == "expensive":
            if qtype in ("hard", "expert"):
                beliefs[qtype] = [1.0, 1.5, 3.0, 5.0]
            elif qtype == "moderate":
                beliefs[qtype] = [1.0, 2.0, 3.5, 3.0]
            else:  # easy
                beliefs[qtype] = [1.0, 1.5, 4.0, 3.5]
        elif tier == "mid":
            if qtype in ("hard", "expert"):
                beliefs[qtype] = [1.5, 2.5, 3.0, 2.0]
            elif qtype == "moderate":
                beliefs[qtype] = [1.0, 2.0, 4.0, 2.5]
            else:
                beliefs[qtype] = [1.0, 1.5, 4.5, 2.0]
        else:  # cheap
            if qtype in ("hard", "expert"):
                beliefs[qtype] = [2.5, 3.0, 2.0, 1.0]
            elif qtype == "moderate":
                beliefs[qtype] = [1.5, 3.0, 3.5, 1.5]
            else:
                beliefs[qtype] = [1.0, 2.0, 5.0, 2.0]
    return beliefs


# ============================================================
# ACTIVE INFERENCE ROUTER
# ============================================================

class ActiveInferenceRouter:
    """
    Active Inference model selector.

    Maintains Dirichlet beliefs over outcome quality per (model, query_type).
    Selects models by minimizing expected free energy:
      G(m, q) = -epistemic_value(m, q) - pragmatic_value(m, q)
    """

    def __init__(self, beliefs_path, pricing_path):
        self.beliefs_path = Path(beliefs_path)
        self.pricing_path = Path(pricing_path)
        self.log_path = Path(pricing_path).parent.parent / "data" / "active-inference-log.jsonl"

        # Load model registry
        self.model_registry = _load_pricing(pricing_path)

        # State
        self.state = {
            "beliefs": {},
            "prior_preferences": dict(DEFAULT_PRIOR_PREFERENCES),
            "total_decisions": 0,
            "last_updated": None
        }

        # Try loading persisted state; otherwise initialize from pricing
        if not self._load():
            self._initialize_beliefs()
            self.save()

    # --------------------------------------------------------
    # Persistence
    # --------------------------------------------------------

    def _load(self):
        """Load beliefs from disk. Returns True if loaded successfully."""
        if not self.beliefs_path.exists():
            return False
        try:
            with open(self.beliefs_path) as f:
                data = json.load(f)
            # Validate structure
            if "beliefs" not in data or not isinstance(data["beliefs"], dict):
                return False
            self.state = data
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def load(self):
        """Public reload."""
        self._load()

    def save(self):
        """Persist beliefs to disk."""
        self.beliefs_path.parent.mkdir(parents=True, exist_ok=True)
        self.state["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(self.beliefs_path, "w") as f:
            json.dump(self.state, f, indent=2)

    # --------------------------------------------------------
    # Initialization
    # --------------------------------------------------------

    def _initialize_beliefs(self):
        """Initialize Dirichlet beliefs from pricing.json model profiles."""
        for model_id, info in self.model_registry.items():
            tier = _classify_model_tier(model_id, info)
            self.state["beliefs"][model_id] = _init_dirichlet_for_model(tier)

    # --------------------------------------------------------
    # Expected Free Energy computation
    # --------------------------------------------------------

    def _expected_outcome(self, alphas):
        """
        Compute expected outcome distribution E[o] from Dirichlet alphas.
        E[o_i] = alpha_i / sum(alphas)  (mean of Dirichlet)
        """
        total = sum(alphas)
        if total == 0:
            n = len(alphas)
            return [1.0 / n] * n
        return [a / total for a in alphas]

    def _epistemic_value(self, alphas):
        """
        Information gain — how uncertain we are about this model's outcomes.
        Higher uncertainty = higher epistemic value = more to learn.

        epistemic = -sum( (digamma(alpha_i) - digamma(sum)) * E[o_i] )
        """
        alpha_sum = sum(alphas)
        if alpha_sum <= 0:
            return 0.0
        e_o = self._expected_outcome(alphas)
        psi_sum = digamma_approx(alpha_sum)

        value = 0.0
        for i, alpha_i in enumerate(alphas):
            psi_i = digamma_approx(alpha_i)
            value += (psi_i - psi_sum) * e_o[i]

        # Negate: we defined epistemic = -sum(...)
        # The negative of this is positive when uncertainty is high
        return -value

    def _pragmatic_value(self, alphas):
        """
        Expected utility under prior preferences.
        pragmatic = sum(E[o_i] * preference[o_i])
        """
        e_o = self._expected_outcome(alphas)
        prefs = self.state["prior_preferences"]
        value = 0.0
        for i, cat in enumerate(OBSERVATION_CATEGORIES):
            value += e_o[i] * prefs.get(cat, 0.0)
        return value

    def _free_energy(self, alphas):
        """
        Expected free energy G for a (model, query_type) pair.
        G = -epistemic - pragmatic
        Lower G = better (more informative AND/OR more preferred outcomes)
        """
        ep = self._epistemic_value(alphas)
        pr = self._pragmatic_value(alphas)
        return -ep - pr, ep, pr

    # --------------------------------------------------------
    # Model selection
    # --------------------------------------------------------

    def select_model(self, query_type, available_models=None):
        """
        Select optimal model by minimizing expected free energy.

        Args:
            query_type: one of ["easy", "moderate", "hard", "expert"]
                        or a float (IRT difficulty) which will be mapped
            available_models: optional list of model IDs to consider

        Returns:
            dict with keys: model, free_energy, epistemic, pragmatic
        """
        # Allow passing numeric difficulty
        if isinstance(query_type, (int, float)):
            query_type = difficulty_to_query_type(query_type)

        if query_type not in QUERY_TYPES:
            query_type = "moderate"  # fallback

        candidates = available_models or list(self.state["beliefs"].keys())
        if not candidates:
            # No beliefs yet — return first model from registry
            fallback = next(iter(self.model_registry), "claude-sonnet-4-6")
            return {
                "model": fallback,
                "free_energy": 0.0,
                "epistemic": 0.0,
                "pragmatic": 0.0
            }

        best = None
        best_g = float("inf")
        best_ep = 0.0
        best_pr = 0.0
        evaluated = 0

        for model_id in candidates:
            beliefs_for_model = self.state["beliefs"].get(model_id)
            if beliefs_for_model is None:
                continue
            alphas = beliefs_for_model.get(query_type)
            if alphas is None:
                continue

            g, ep, pr = self._free_energy(alphas)
            evaluated += 1

            if g < best_g:
                best_g = g
                best_ep = ep
                best_pr = pr
                best = model_id

        if best is None:
            fallback = candidates[0] if candidates else "claude-sonnet-4-6"
            return {
                "model": fallback,
                "free_energy": 0.0,
                "epistemic": 0.0,
                "pragmatic": 0.0
            }

        result = {
            "model": best,
            "free_energy": round(best_g, 4),
            "epistemic": round(best_ep, 4),
            "pragmatic": round(best_pr, 4)
        }

        # Log decision
        self._log_decision(query_type, result, evaluated)

        # Increment counter
        self.state["total_decisions"] += 1

        return result

    # --------------------------------------------------------
    # Belief updating
    # --------------------------------------------------------

    def update_beliefs(self, model, query_type, outcome_quality):
        """
        Update Dirichlet beliefs after observing an outcome.

        Args:
            model: model ID string
            query_type: "easy"/"moderate"/"hard"/"expert" or float difficulty
            outcome_quality: float 0-1 (DQ score + cost composite)
        """
        if isinstance(query_type, (int, float)):
            query_type = difficulty_to_query_type(query_type)

        if model not in self.state["beliefs"]:
            return  # Unknown model, skip

        if query_type not in self.state["beliefs"][model]:
            return

        # Map outcome to category index
        obs_idx = outcome_to_category(outcome_quality)

        # Conjugate Dirichlet update: increment the observed category's alpha
        self.state["beliefs"][model][query_type][obs_idx] += 1.0

        self.save()

    # --------------------------------------------------------
    # Accessors
    # --------------------------------------------------------

    def get_beliefs(self):
        """Return current belief state."""
        return dict(self.state)

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def _log_decision(self, query_type, result, candidates_evaluated):
        """Append decision to JSONL log."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "query_type": query_type,
                "model_selected": result["model"],
                "free_energy": result["free_energy"],
                "epistemic_value": result["epistemic"],
                "pragmatic_value": result["pragmatic"],
                "candidates_evaluated": candidates_evaluated,
                "beliefs_snapshot": self.state["beliefs"].get(result["model"], {}).get(query_type, [])
            }
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass  # Silent fail — don't break routing


# ============================================================
# CLI
# ============================================================

def main():
    """Quick CLI test."""
    import sys

    base = Path(__file__).resolve().parent.parent
    beliefs_path = base / "data" / "active-inference-beliefs.json"
    pricing_path = base / "config" / "pricing.json"

    router = ActiveInferenceRouter(str(beliefs_path), str(pricing_path))

    if len(sys.argv) > 1:
        qtype = sys.argv[1]
        result = router.select_model(qtype)
        print(f"\nActive Inference Selection (query_type={qtype})")
        print(f"  Model:       {result['model']}")
        print(f"  Free Energy: {result['free_energy']:.4f}")
        print(f"  Epistemic:   {result['epistemic']:.4f}")
        print(f"  Pragmatic:   {result['pragmatic']:.4f}")
    else:
        print("Active Inference Router — Belief Summary")
        beliefs = router.get_beliefs()
        print(f"  Total decisions: {beliefs['total_decisions']}")
        print(f"  Models tracked:  {len(beliefs['beliefs'])}")
        print(f"  Last updated:    {beliefs['last_updated']}")
        for model_id in sorted(beliefs["beliefs"].keys()):
            print(f"\n  {model_id}:")
            for qt in QUERY_TYPES:
                alphas = beliefs["beliefs"][model_id].get(qt, [])
                print(f"    {qt:10s}: {alphas}")


if __name__ == "__main__":
    main()
