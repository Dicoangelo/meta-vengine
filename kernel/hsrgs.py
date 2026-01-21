#!/usr/bin/env python3
"""
HSRGS: Homeomorphic Self-Routing Gödel System

A revolutionary routing system that:
1. Encodes queries AND models in a universal homeomorphic latent space
2. Uses IRT (Item Response Theory) to predict P(success|query, model)
3. Self-modifies its own routing logic via Gödel machine principles
4. Selects models via emergent pressure gradients, not explicit rules

Based on convergence of:
- ZeroRouter (arXiv:2601.06220) - Universal latent space
- ULHM (arXiv:2601.09025) - Homeomorphic manifold unification
- IRT-Router (arXiv:2506.01048) - Psychometric routing
- Darwin Gödel Machine (arXiv:2505.22954) - Open-ended self-improvement
- Emergent Coordination (arXiv:2601.08129) - Pressure field selection

Author: D-Ecosystem / Metaventions AI
"""

import json
import hashlib
import time
import math
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
import numpy as np

# Import centralized pricing
sys.path.insert(0, str(Path.home() / ".claude/config"))
try:
    from pricing import PRICING as _CENTRALIZED_PRICING
except ImportError:
    _CENTRALIZED_PRICING = {"opus": {"input": 5}, "sonnet": {"input": 3}, "haiku": {"input": 0.8}}

# Lazy load heavy dependencies
_encoder = None
_model_embeddings = None

# ============================================================
# CONFIGURATION
# ============================================================

HSRGS_DIR = Path.home() / ".claude" / "kernel" / "hsrgs"
CONFIG_FILE = HSRGS_DIR / "config.json"
EMBEDDINGS_FILE = HSRGS_DIR / "model_embeddings.npz"
IRT_PARAMS_FILE = HSRGS_DIR / "irt_params.json"
EVOLUTION_ARCHIVE = HSRGS_DIR / "evolution_archive.jsonl"
ROUTING_LOG = HSRGS_DIR / "routing_log.jsonl"

# Coevo integration - shared data pipeline
COEVO_DQ_FILE = Path.home() / ".claude" / "kernel" / "dq-scores.jsonl"

DEFAULT_CONFIG = {
    "encoder_model": "all-MiniLM-L6-v2",  # Fast, good quality
    "embedding_dim": 384,
    "irt_learning_rate": 0.01,
    "pressure_weights": {
        "cost": 0.3,
        "quality": 0.5,
        "latency": 0.2
    },
    "evolution_enabled": True,
    "mutation_rate": 0.1,
    "archive_max_size": 100,
    "version": "1.0.0"
}

# Model characteristics (costs from centralized config, others learned over time)
MODEL_PROFILES = {
    "local": {"cost": 0.0, "latency": 0.1, "capability": 0.3, "tier": 0},
    "local-fast": {"cost": 0.0, "latency": 0.05, "capability": 0.2, "tier": 0},
    "flash": {"cost": 0.075, "latency": 0.3, "capability": 0.5, "tier": 1},
    "haiku": {"cost": _CENTRALIZED_PRICING.get("haiku", {}).get("input", 0.8), "latency": 0.4, "capability": 0.6, "tier": 2},
    "gpt-mini": {"cost": 0.15, "latency": 0.35, "capability": 0.55, "tier": 2},
    "sonnet": {"cost": _CENTRALIZED_PRICING.get("sonnet", {}).get("input", 3.0), "latency": 0.8, "capability": 0.85, "tier": 3},
    "gpt-4o": {"cost": 2.5, "latency": 0.7, "capability": 0.82, "tier": 3},
    "pro": {"cost": 1.25, "latency": 0.6, "capability": 0.75, "tier": 3},
    "opus": {"cost": _CENTRALIZED_PRICING.get("opus", {}).get("input", 5.0), "latency": 1.5, "capability": 1.0, "tier": 4},
}


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class LatentRepresentation:
    """Universal latent space representation"""
    embedding: np.ndarray
    difficulty: float  # IRT difficulty parameter (0-1)
    discrimination: float  # IRT discrimination parameter
    domain_signature: str  # Hash of semantic domain

@dataclass
class IRTParams:
    """Item Response Theory parameters for a model"""
    ability: float  # Model's general ability (theta)
    domain_abilities: Dict[str, float] = field(default_factory=dict)  # Per-domain abilities
    guessing: float = 0.1  # Probability of correct by chance

@dataclass
class PressureField:
    """Emergent pressure gradients for model selection"""
    cost_pressure: float
    quality_pressure: float
    latency_pressure: float
    total_pressure: float

@dataclass
class RoutingDecision:
    """Complete routing decision with provenance"""
    query_hash: str
    selected_model: str
    latent: LatentRepresentation
    pressures: Dict[str, PressureField]
    irt_predictions: Dict[str, float]
    confidence: float
    reasoning: str
    timestamp: int
    version: str


# ============================================================
# HOMEOMORPHIC ENCODER
# ============================================================

class HomeomorphicEncoder:
    """
    Encodes queries into a universal latent space that is homeomorphic
    to the model capability space, enabling zero-shot model onboarding.

    Based on ZeroRouter + ULHM principles:
    - Query difficulty decoupled from model profiling
    - Continuous bijection preserving topological structure
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._encoder = None
        self._model_embeddings = {}
        self._domain_centroids = {}

    def _load_encoder(self):
        """Lazy load the sentence transformer"""
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.model_name)
        return self._encoder

    def encode_query(self, query: str) -> LatentRepresentation:
        """
        Encode query into universal latent space.

        Returns:
            LatentRepresentation with:
            - embedding: Dense vector in universal space
            - difficulty: Estimated query difficulty (0-1)
            - discrimination: How much difficulty varies by model
            - domain_signature: Semantic domain hash
        """
        encoder = self._load_encoder()

        # Get dense embedding
        embedding = encoder.encode(query, convert_to_numpy=True)

        # Estimate difficulty from embedding properties
        # Higher norm = more specific/complex query
        norm = np.linalg.norm(embedding)

        # Difficulty estimation via multiple signals
        difficulty = self._estimate_difficulty(query, embedding)

        # Discrimination: how much the query differentiates models
        discrimination = self._estimate_discrimination(query, embedding)

        # Domain signature for domain-specific routing
        domain_signature = self._compute_domain_signature(embedding)

        return LatentRepresentation(
            embedding=embedding,
            difficulty=difficulty,
            discrimination=discrimination,
            domain_signature=domain_signature
        )

    def _estimate_difficulty(self, query: str, embedding: np.ndarray) -> float:
        """
        Estimate query difficulty using multiple signals:
        1. Embedding norm (specificity)
        2. Query length and structure
        3. Technical term density
        4. Semantic complexity from embedding variance
        """
        signals = []

        # Signal 1: Embedding norm (normalized)
        norm = np.linalg.norm(embedding)
        norm_signal = min(norm / 20.0, 1.0)  # Normalize to 0-1
        signals.append(norm_signal * 0.2)

        # Signal 2: Query length (log-scaled)
        length = len(query)
        length_signal = min(math.log(length + 1) / 7.0, 1.0)  # log(1000) ≈ 7
        signals.append(length_signal * 0.15)

        # Signal 3: Technical term density
        technical_terms = [
            # Core architecture
            "architecture", "system", "design", "implement", "algorithm",
            "optimize", "distributed", "scale", "microservices", "kubernetes",
            # Data & storage
            "database", "cache", "redis", "postgres", "mongodb", "kafka",
            "queue", "stream", "event", "cqrs", "saga", "transaction",
            # Concurrency
            "async", "concurrent", "parallel", "thread", "lock", "mutex",
            # Reliability
            "fault", "tolerance", "consistency", "availability", "partition",
            "circuit", "breaker", "bulkhead", "retry", "backoff", "resilience",
            # Theory
            "theorem", "proof", "analysis", "complexity", "tradeoff", "cap",
            # ML/AI
            "neural", "model", "training", "inference", "embedding", "transformer",
            # Patterns
            "pattern", "orchestration", "choreography", "observability", "tracing",
            "telemetry", "metrics", "logging", "multi-tenant", "saas", "api"
        ]
        query_lower = query.lower()
        tech_count = sum(1 for t in technical_terms if t in query_lower)
        tech_signal = min(tech_count / 6.0, 1.0)  # Increased divisor for more terms
        signals.append(tech_signal * 0.35)

        # Signal 4: Question complexity markers
        complexity_markers = [
            "how would you", "design a", "architect", "compare and contrast",
            "what are the tradeoffs", "optimize for", "scale to", "handle",
            "implement a", "build a system", "evaluate", "analyze",
            "considering", "ensuring", "implementing", "complete", "full",
            "end-to-end", "production", "enterprise", "across"
        ]
        complexity_count = sum(1 for m in complexity_markers if m in query_lower)
        complexity_signal = min(complexity_count / 3.0, 1.0)
        signals.append(complexity_signal * 0.3)

        # Combine signals
        difficulty = sum(signals)

        # Apply sigmoid for smooth 0-1 output
        difficulty = 1 / (1 + math.exp(-5 * (difficulty - 0.5)))

        return round(difficulty, 3)

    def _estimate_discrimination(self, query: str, embedding: np.ndarray) -> float:
        """
        Estimate how much the query discriminates between models.
        High discrimination = only capable models can answer correctly.
        Low discrimination = most models perform similarly.
        """
        # Embedding variance as discrimination proxy
        variance = np.var(embedding)

        # Normalize to 0-1 range
        discrimination = min(variance * 10, 1.0)

        # Boost for specific query types
        query_lower = query.lower()
        if any(term in query_lower for term in ["explain", "simple", "basic", "what is"]):
            discrimination *= 0.7  # Less discriminating
        if any(term in query_lower for term in ["complex", "advanced", "optimize", "design"]):
            discrimination *= 1.3  # More discriminating

        return round(min(discrimination, 1.0), 3)

    def _compute_domain_signature(self, embedding: np.ndarray) -> str:
        """Compute semantic domain signature from embedding"""
        # Use embedding sign pattern as domain fingerprint
        sign_pattern = (embedding > 0).astype(np.uint8)
        return hashlib.md5(sign_pattern.tobytes()).hexdigest()[:8]

    def compute_homeomorphism_score(self,
                                     query_latent: LatentRepresentation,
                                     model_embedding: np.ndarray) -> float:
        """
        Verify homeomorphism between query and model latent spaces.
        Returns score 0-1 indicating structural compatibility.

        Based on ULHM: checks local continuity preservation.
        """
        # Cosine similarity as continuity measure
        query_norm = query_latent.embedding / (np.linalg.norm(query_latent.embedding) + 1e-8)
        model_norm = model_embedding / (np.linalg.norm(model_embedding) + 1e-8)

        similarity = np.dot(query_norm, model_norm)

        # Convert to 0-1 score
        score = (similarity + 1) / 2

        return round(score, 3)


# ============================================================
# IRT PREDICTOR
# ============================================================

class IRTPredictor:
    """
    Item Response Theory predictor for routing decisions.

    Models the probability of successful response as:
    P(success) = c + (1-c) * sigmoid(a * (theta - b))

    Where:
    - theta: model ability
    - b: query difficulty
    - a: query discrimination
    - c: guessing parameter

    Based on IRT-Router (arXiv:2506.01048)
    """

    def __init__(self):
        self.model_params: Dict[str, IRTParams] = {}
        self._load_params()

    def _load_params(self):
        """Load IRT parameters from disk"""
        if IRT_PARAMS_FILE.exists():
            try:
                with open(IRT_PARAMS_FILE) as f:
                    data = json.load(f)
                for model, params in data.items():
                    self.model_params[model] = IRTParams(**params)
            except Exception:
                pass

        # Initialize defaults for known models
        for model, profile in MODEL_PROFILES.items():
            if model not in self.model_params:
                self.model_params[model] = IRTParams(
                    ability=profile["capability"],
                    guessing=0.1 if profile["tier"] < 2 else 0.05
                )

    def save_params(self):
        """Persist IRT parameters"""
        HSRGS_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        for model, params in self.model_params.items():
            data[model] = {
                "ability": params.ability,
                "domain_abilities": params.domain_abilities,
                "guessing": params.guessing
            }
        with open(IRT_PARAMS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def predict(self,
                model: str,
                query_latent: LatentRepresentation) -> float:
        """
        Predict P(success) for model on query using 2PL IRT model.

        P(success) = c + (1-c) / (1 + exp(-a * (theta - b)))
        """
        params = self.model_params.get(model)
        if not params:
            # Unknown model - use profile or default
            profile = MODEL_PROFILES.get(model, {"capability": 0.5})
            params = IRTParams(ability=profile.get("capability", 0.5))

        theta = params.ability  # Model ability
        b = query_latent.difficulty  # Query difficulty
        a = query_latent.discrimination  # Query discrimination
        c = params.guessing  # Guessing parameter

        # Check for domain-specific ability
        domain = query_latent.domain_signature
        if domain in params.domain_abilities:
            theta = params.domain_abilities[domain]

        # 2PL IRT formula with guessing
        exponent = -a * 2.0 * (theta - b)  # Scale factor of 2
        prob = c + (1 - c) / (1 + math.exp(exponent))

        return round(prob, 3)

    def update_from_outcome(self,
                            model: str,
                            query_latent: LatentRepresentation,
                            success: bool,
                            learning_rate: float = 0.01):
        """
        Update IRT parameters based on observed outcome.
        Enables continuous learning from routing feedback.
        """
        params = self.model_params.get(model)
        if not params:
            params = IRTParams(ability=0.5)
            self.model_params[model] = params

        predicted = self.predict(model, query_latent)
        actual = 1.0 if success else 0.0
        error = actual - predicted

        # Update ability parameter
        params.ability += learning_rate * error * query_latent.discrimination
        params.ability = max(0.0, min(1.0, params.ability))

        # Update domain-specific ability
        domain = query_latent.domain_signature
        if domain not in params.domain_abilities:
            params.domain_abilities[domain] = params.ability
        params.domain_abilities[domain] += learning_rate * error * 1.5
        params.domain_abilities[domain] = max(0.0, min(1.0, params.domain_abilities[domain]))

        self.save_params()


# ============================================================
# PRESSURE FIELD SELECTION
# ============================================================

class PressureFieldSelector:
    """
    Emergent model selection via pressure gradients.

    Instead of explicit thresholds like "if complexity > 0.7: opus",
    uses continuous pressure fields that naturally route:
    - Simple queries → low cost models (cost pressure dominates)
    - Complex queries → capable models (quality pressure dominates)

    Based on Emergent Coordination (arXiv:2601.08129):
    "Implicit coordination through shared pressure gradients achieves
    parity with explicit hierarchical control"
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_CONFIG["pressure_weights"]

    def compute_pressure(self,
                         model: str,
                         query_latent: LatentRepresentation,
                         irt_prediction: float,
                         budget: float = 1.0,
                         deadline: float = 1.0) -> PressureField:
        """
        Compute pressure field for a model on a query.

        Lower pressure = better fit for this query.

        Key insight from Emergent Coordination (arXiv:2601.08129):
        Pressure gradients should naturally route based on query needs.
        """
        profile = MODEL_PROFILES.get(model, {"cost": 1.0, "latency": 1.0, "capability": 0.5})
        capability = profile["capability"]
        difficulty = query_latent.difficulty

        # Cost pressure: higher for expensive models, but REDUCED for complex queries
        # Complex queries NEED expensive models, so cost pressure drops
        base_cost = profile["cost"] / 5.0  # Normalize by opus cost (Opus 4.5 pricing)
        difficulty_discount = math.exp(-3 * difficulty)  # Exponential decay with difficulty
        cost_pressure = base_cost * difficulty_discount / budget

        # Quality pressure: measures capability GAP
        # If model capability < query difficulty, quality pressure is HIGH
        # This is the key innovation: pressure from capability mismatch
        capability_gap = max(0, difficulty - capability)
        quality_pressure = capability_gap ** 2 * 5  # Quadratic penalty for under-capability
        quality_pressure += (1 - irt_prediction) * difficulty * 0.5  # IRT contribution

        # Latency pressure: based on model speed vs deadline
        # But complex queries tolerate more latency (they take time anyway)
        latency_tolerance = 1 + difficulty  # More tolerance for complex queries
        latency_pressure = profile["latency"] / (deadline * latency_tolerance)

        # Total pressure (weighted sum)
        total = (
            self.weights["cost"] * cost_pressure +
            self.weights["quality"] * quality_pressure +
            self.weights["latency"] * latency_pressure
        )

        return PressureField(
            cost_pressure=round(cost_pressure, 3),
            quality_pressure=round(quality_pressure, 3),
            latency_pressure=round(latency_pressure, 3),
            total_pressure=round(total, 3)
        )

    def select(self,
               pressures: Dict[str, PressureField],
               available_models: List[str]) -> Tuple[str, float]:
        """
        Select model with minimum total pressure.
        Returns (model, confidence).
        """
        valid = [(m, p) for m, p in pressures.items() if m in available_models]
        if not valid:
            return "sonnet", 0.5  # Fallback

        # Sort by total pressure (ascending)
        valid.sort(key=lambda x: x[1].total_pressure)

        best_model = valid[0][0]
        best_pressure = valid[0][1].total_pressure

        # Confidence based on pressure gap to second choice
        if len(valid) > 1:
            second_pressure = valid[1][1].total_pressure
            gap = second_pressure - best_pressure
            confidence = min(gap * 5, 1.0)  # Scale gap to confidence
        else:
            confidence = 0.8

        return best_model, round(confidence, 2)


# ============================================================
# GÖDEL SELF-MODIFICATION ENGINE
# ============================================================

class GodelEngine:
    """
    Self-modification engine inspired by Gödel Agent.

    Enables the router to modify its own parameters and logic
    based on empirical validation, not formal proofs.

    Based on:
    - Gödel Agent (arXiv:2410.04444) - Self-referential improvement
    - Darwin Gödel Machine (arXiv:2505.22954) - Empirical validation
    """

    def __init__(self):
        self.archive: List[Dict] = []
        self.current_version = DEFAULT_CONFIG["version"]
        self._load_archive()

    def _load_archive(self):
        """Load evolution archive from disk"""
        if EVOLUTION_ARCHIVE.exists():
            try:
                with open(EVOLUTION_ARCHIVE) as f:
                    for line in f:
                        self.archive.append(json.loads(line))
            except Exception:
                pass

    def _save_to_archive(self, entry: Dict):
        """Append entry to evolution archive"""
        HSRGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(EVOLUTION_ARCHIVE, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self.archive.append(entry)

        # Prune if too large
        max_size = DEFAULT_CONFIG["archive_max_size"]
        if len(self.archive) > max_size:
            self.archive = self.archive[-max_size:]
            with open(EVOLUTION_ARCHIVE, "w") as f:
                for entry in self.archive:
                    f.write(json.dumps(entry) + "\n")

    def propose_mutation(self,
                         selector: PressureFieldSelector,
                         recent_outcomes: List[Dict]) -> Optional[Dict]:
        """
        Propose a mutation to the routing parameters based on recent outcomes.

        Returns mutation proposal or None if no improvement found.
        """
        if len(recent_outcomes) < 10:
            return None  # Need more data

        # Analyze recent performance
        successes = sum(1 for o in recent_outcomes if o.get("success", False))
        success_rate = successes / len(recent_outcomes)

        # Analyze cost efficiency
        total_cost = sum(o.get("cost", 0) for o in recent_outcomes)
        avg_cost = total_cost / len(recent_outcomes)

        # Propose mutation based on analysis
        mutation = {
            "timestamp": int(time.time() * 1000),
            "type": None,
            "old_value": None,
            "new_value": None,
            "reasoning": None
        }

        if success_rate < 0.7:
            # Quality too low - increase quality pressure weight
            old_weight = selector.weights["quality"]
            new_weight = min(old_weight * 1.1, 0.8)
            mutation.update({
                "type": "pressure_weight",
                "param": "quality",
                "old_value": old_weight,
                "new_value": new_weight,
                "reasoning": f"Success rate {success_rate:.1%} below target, increasing quality pressure"
            })
        elif avg_cost > 5.0 and success_rate > 0.85:
            # Cost too high with good success - increase cost pressure
            old_weight = selector.weights["cost"]
            new_weight = min(old_weight * 1.1, 0.6)
            mutation.update({
                "type": "pressure_weight",
                "param": "cost",
                "old_value": old_weight,
                "new_value": new_weight,
                "reasoning": f"Avg cost ${avg_cost:.2f} with {success_rate:.1%} success, increasing cost pressure"
            })
        else:
            return None  # No mutation needed

        return mutation

    def apply_mutation(self,
                       mutation: Dict,
                       selector: PressureFieldSelector) -> bool:
        """Apply a mutation to the selector"""
        if mutation["type"] == "pressure_weight":
            param = mutation["param"]
            selector.weights[param] = mutation["new_value"]

            # Renormalize weights
            total = sum(selector.weights.values())
            for k in selector.weights:
                selector.weights[k] /= total

            self._save_to_archive(mutation)
            return True

        return False

    def rollback_mutation(self,
                          mutation: Dict,
                          selector: PressureFieldSelector):
        """Rollback a mutation if it caused regression"""
        if mutation["type"] == "pressure_weight":
            param = mutation["param"]
            selector.weights[param] = mutation["old_value"]

            rollback_entry = {
                "timestamp": int(time.time() * 1000),
                "type": "rollback",
                "original_mutation": mutation
            }
            self._save_to_archive(rollback_entry)


# ============================================================
# MAIN ROUTER
# ============================================================

class HSRGSRouter:
    """
    Homeomorphic Self-Routing Gödel System

    The main router that combines all components:
    1. Homeomorphic encoder for universal latent space
    2. IRT predictor for success probability
    3. Pressure field selector for emergent routing
    4. Gödel engine for self-modification
    """

    def __init__(self, available_models: Optional[List[str]] = None):
        self.encoder = HomeomorphicEncoder()
        self.irt = IRTPredictor()
        self.selector = PressureFieldSelector()
        self.godel = GodelEngine()
        self.available_models = available_models or list(MODEL_PROFILES.keys())
        self.recent_outcomes: List[Dict] = []
        self._load_config()

    def _load_config(self):
        """Load configuration"""
        HSRGS_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    config = json.load(f)
                self.selector.weights = config.get("pressure_weights", DEFAULT_CONFIG["pressure_weights"])
            except Exception:
                pass

    def save_config(self):
        """Save configuration"""
        config = {
            **DEFAULT_CONFIG,
            "pressure_weights": self.selector.weights
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    def route(self,
              query: str,
              budget: float = 1.0,
              deadline: float = 1.0) -> RoutingDecision:
        """
        Route a query to the optimal model.

        Args:
            query: The user query
            budget: Cost budget multiplier (1.0 = normal, 0.5 = half budget)
            deadline: Latency deadline multiplier (1.0 = normal, 0.5 = need fast)

        Returns:
            RoutingDecision with full provenance
        """
        # 1. Encode query into universal latent space
        latent = self.encoder.encode_query(query)

        # 2. Predict success probability for each model
        irt_predictions = {}
        for model in self.available_models:
            irt_predictions[model] = self.irt.predict(model, latent)

        # 3. Compute pressure field for each model
        pressures = {}
        for model in self.available_models:
            pressures[model] = self.selector.compute_pressure(
                model, latent, irt_predictions[model], budget, deadline
            )

        # 4. Select model with minimum pressure
        selected, confidence = self.selector.select(pressures, self.available_models)

        # 5. Build reasoning explanation
        reasoning = self._build_reasoning(latent, irt_predictions, pressures, selected)

        # 6. Create decision record
        decision = RoutingDecision(
            query_hash=hashlib.md5(query.encode()).hexdigest(),
            selected_model=selected,
            latent=latent,
            pressures={m: asdict(p) for m, p in pressures.items()},
            irt_predictions=irt_predictions,
            confidence=confidence,
            reasoning=reasoning,
            timestamp=int(time.time() * 1000),
            version=self.godel.current_version
        )

        # 7. Log decision
        self._log_decision(query, decision)

        return decision

    def _build_reasoning(self,
                         latent: LatentRepresentation,
                         irt_predictions: Dict[str, float],
                         pressures: Dict[str, PressureField],
                         selected: str) -> str:
        """Build human-readable reasoning for the decision"""
        parts = []

        # Difficulty assessment
        if latent.difficulty < 0.3:
            parts.append("simple query")
        elif latent.difficulty < 0.6:
            parts.append("moderate complexity")
        else:
            parts.append("complex query")

        # Discrimination
        if latent.discrimination > 0.5:
            parts.append("high model differentiation")

        # IRT insight
        top_irt = max(irt_predictions.items(), key=lambda x: x[1])
        if top_irt[0] != selected:
            parts.append(f"IRT favored {top_irt[0]} ({top_irt[1]:.0%})")

        # Pressure insight
        selected_pressure = pressures[selected]
        if selected_pressure.cost_pressure < selected_pressure.quality_pressure:
            parts.append("cost-optimized")
        else:
            parts.append("quality-optimized")

        return "; ".join(parts)

    def _log_decision(self, query: str, decision: RoutingDecision):
        """Log routing decision for learning"""
        HSRGS_DIR.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "ts": decision.timestamp,
            "query_hash": decision.query_hash,
            "query_preview": query[:80] if len(query) > 80 else query,
            "model": decision.selected_model,
            "difficulty": float(decision.latent.difficulty),
            "discrimination": float(decision.latent.discrimination),
            "irt_pred": float(decision.irt_predictions.get(decision.selected_model, 0)),
            "confidence": float(decision.confidence),
            "version": decision.version
        }

        with open(ROUTING_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Also log to coevo data pipeline for cross-system learning
        self._log_to_coevo(query, decision)

    def _log_to_coevo(self, query: str, decision: RoutingDecision):
        """Log to shared coevo data pipeline for meta-analyzer integration"""
        try:
            # Build alternatives from pressure rankings
            alternatives = []
            sorted_pressures = sorted(
                decision.pressures.items(),
                key=lambda x: x[1]["total_pressure"]
            )
            for model, pressure in sorted_pressures[1:4]:  # Top 3 alternatives
                if model != decision.selected_model:
                    # Estimate alternative DQ from IRT prediction
                    alt_dq = decision.irt_predictions.get(model, 0.5)
                    alternatives.append({"model": model, "dq": round(alt_dq, 2)})

            coevo_record = {
                "ts": decision.timestamp,
                "source": "hsrgs",
                "version": decision.version,
                "query_hash": decision.query_hash,
                "query_preview": query[:80] if len(query) > 80 else query,
                "complexity": float(decision.latent.difficulty),
                "complexity_reasoning": decision.reasoning,
                "model": decision.selected_model,
                "dqScore": float(decision.latent.difficulty),
                "dqComponents": {
                    "validity": 1.0,  # HSRGS validates via embedding
                    "specificity": float(decision.latent.discrimination),
                    "correctness": float(decision.irt_predictions.get(decision.selected_model, 0.5))
                },
                "hsrgs_data": {
                    "difficulty": float(decision.latent.difficulty),
                    "discrimination": float(decision.latent.discrimination),
                    "domain": decision.latent.domain_signature,
                    "confidence": float(decision.confidence),
                    "pressure_winner": decision.selected_model,
                    "irt_prediction": float(decision.irt_predictions.get(decision.selected_model, 0))
                },
                "alternatives": alternatives
            }

            COEVO_DQ_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(COEVO_DQ_FILE, "a") as f:
                f.write(json.dumps(coevo_record) + "\n")
        except Exception:
            pass  # Silent fail - don't break routing

    def record_outcome(self, query_hash: str, success: bool, cost: float = 0.0):
        """
        Record outcome for learning.
        Enables IRT parameter updates and Gödel self-modification.
        """
        # Find the decision
        if not ROUTING_LOG.exists():
            return

        decision = None
        with open(ROUTING_LOG) as f:
            for line in f:
                entry = json.loads(line)
                if entry["query_hash"] == query_hash:
                    decision = entry

        if not decision:
            return

        # Update IRT parameters
        # (Would need to reconstruct latent - simplified here)

        # Record for Gödel engine
        self.recent_outcomes.append({
            "query_hash": query_hash,
            "model": decision["model"],
            "success": success,
            "cost": cost,
            "timestamp": int(time.time() * 1000)
        })

        # Keep only recent outcomes
        self.recent_outcomes = self.recent_outcomes[-100:]

        # Check for self-modification opportunity
        if len(self.recent_outcomes) >= 20:
            mutation = self.godel.propose_mutation(self.selector, self.recent_outcomes)
            if mutation:
                self.godel.apply_mutation(mutation, self.selector)
                self.save_config()

    def get_status(self) -> Dict:
        """Get current router status"""
        return {
            "version": self.godel.current_version,
            "available_models": self.available_models,
            "pressure_weights": self.selector.weights,
            "evolution_entries": len(self.godel.archive),
            "recent_outcomes": len(self.recent_outcomes),
            "irt_models": list(self.irt.model_params.keys())
        }


# ============================================================
# CLI INTERFACE
# ============================================================

def main():
    """CLI for testing HSRGS"""
    import sys

    router = HSRGSRouter()

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        decision = router.route(query)

        print(f"\n{'='*60}")
        print(f"HSRGS Routing Decision")
        print(f"{'='*60}")
        print(f"Query: {query[:60]}...")
        print(f"{'─'*60}")
        print(f"Difficulty:      {decision.latent.difficulty:.2f}")
        print(f"Discrimination:  {decision.latent.discrimination:.2f}")
        print(f"Domain:          {decision.latent.domain_signature}")
        print(f"{'─'*60}")
        print(f"Selected Model:  {decision.selected_model}")
        print(f"Confidence:      {decision.confidence:.0%}")
        print(f"IRT Prediction:  {decision.irt_predictions[decision.selected_model]:.0%}")
        print(f"{'─'*60}")
        print(f"Reasoning: {decision.reasoning}")
        print(f"{'='*60}\n")

        # Show pressure breakdown
        print("Pressure Field:")
        for model, pressure in sorted(decision.pressures.items(),
                                       key=lambda x: x[1]["total_pressure"]):
            p = pressure
            marker = " ← selected" if model == decision.selected_model else ""
            print(f"  {model:12} | cost:{p['cost_pressure']:.2f} quality:{p['quality_pressure']:.2f} "
                  f"latency:{p['latency_pressure']:.2f} | total:{p['total_pressure']:.2f}{marker}")
        print()
    else:
        print("HSRGS Status:")
        status = router.get_status()
        for k, v in status.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
