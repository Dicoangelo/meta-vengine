/**
 * US-102: Thompson Sampling Bandit — Core Engine
 *
 * Proposes weight perturbations for each routing decision using Thompson Sampling.
 * Each learnable parameter has a Beta(alpha, beta) distribution representing belief
 * about the optimal perturbation direction.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { getRegistry } = require('./param-registry');

const STATE_PATH = path.join(__dirname, '..', 'data', 'bandit-state.json');
const HISTORY_PATH = path.join(__dirname, '..', 'data', 'bandit-history.jsonl');
const BO_STATE_PATH = path.join(__dirname, '..', 'data', 'bo-state.json');
const LRF_CLUSTERS_PATH = path.join(__dirname, '..', 'data', 'lrf-clusters.json');
const SESSION_MULTIPLIERS_PATH = path.join(__dirname, '..', 'config', 'session-reward-multipliers.json');
const EXPLORATION_RATE = 0.15;

// US-208: Cached session-type reward multipliers (loaded once)
let _sessionMultipliersCache = null;

/**
 * US-208: Load session-type reward multipliers from config.
 * Cached after first load for performance.
 * @returns {object} The parsed multipliers config
 */
function _getSessionMultipliers() {
  if (_sessionMultipliersCache) return _sessionMultipliersCache;
  try {
    _sessionMultipliersCache = JSON.parse(fs.readFileSync(SESSION_MULTIPLIERS_PATH, 'utf8'));
  } catch (_) {
    _sessionMultipliersCache = { multipliers: { refactoring: { dq: 1.0, cost: 1.0, behavioral: 1.0 } }, default: 'refactoring' };
  }
  return _sessionMultipliersCache;
}

/**
 * Sample from Beta(alpha, beta) using Joehnk's method.
 * Returns value in [0, 1].
 */
function sampleBeta(alpha, beta) {
  // For alpha, beta >= 1, use gamma-based sampling
  const gammaA = sampleGamma(alpha);
  const gammaB = sampleGamma(beta);
  return gammaA / (gammaA + gammaB);
}

/**
 * Sample from Gamma(shape, 1) using Marsaglia and Tsang's method.
 */
function sampleGamma(shape) {
  if (shape < 1) {
    return sampleGamma(shape + 1) * Math.pow(Math.random(), 1 / shape);
  }
  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);
  while (true) {
    let x, v;
    do {
      x = randn();
      v = 1 + c * x;
    } while (v <= 0);
    v = v * v * v;
    const u = Math.random();
    if (u < 1 - 0.0331 * (x * x) * (x * x)) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

/**
 * Standard normal using Box-Muller transform.
 */
function randn() {
  const u1 = Math.random();
  const u2 = Math.random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/**
 * US-207: Per-Cluster Exploration Annealing
 *
 * Replaces fixed 15% exploration with a schedule that decays by total decisions,
 * with per-cluster overrides so sparse clusters explore more.
 *
 * @param {number} sampleCounter - Total decisions made so far
 * @param {string|null} [clusterId] - Cluster index (string or number) for per-cluster override
 * @param {number} [globalFloor] - explorationFloorGlobal from param registry (default 0.05)
 * @returns {number} Exploration rate in [globalFloor, 0.50]
 */
function getExplorationRate(sampleCounter, clusterId, globalFloor) {
  if (globalFloor == null) {
    try {
      const reg = getRegistry();
      const p = reg.getParam('explorationFloorGlobal');
      globalFloor = p.value;
    } catch (_) {
      globalFloor = 0.05;
    }
  }

  // Base schedule by total sampleCounter
  let baseRate;
  if (sampleCounter <= 100) {
    baseRate = 0.50;
  } else if (sampleCounter <= 500) {
    // Linear decay from 50% → 10% over decisions 100–500
    const t = (sampleCounter - 100) / 400;
    baseRate = 0.50 - t * 0.40;
  } else if (sampleCounter <= 2000) {
    // Linear decay from 10% → globalFloor over decisions 500–2000
    const t = (sampleCounter - 500) / 1500;
    baseRate = 0.10 - t * (0.10 - globalFloor);
  } else {
    baseRate = globalFloor;
  }

  // Per-cluster override: sparse clusters get a higher floor
  if (clusterId != null) {
    let clusterDecisionCount = null;
    try {
      if (fs.existsSync(LRF_CLUSTERS_PATH)) {
        const data = JSON.parse(fs.readFileSync(LRF_CLUSTERS_PATH, 'utf8'));
        const clusters = data.clusters || [];
        const idx = typeof clusterId === 'string' ? parseInt(clusterId, 10) : clusterId;
        if (clusters[idx] && clusters[idx].decisionCount != null) {
          clusterDecisionCount = clusters[idx].decisionCount;
        } else if (data.cluster_sizes && data.cluster_sizes[idx] != null) {
          // Fallback: use cluster_sizes if decisionCount not yet populated
          clusterDecisionCount = data.cluster_sizes[idx];
        }
      }
    } catch (_) {
      // No cluster data — skip override
    }

    if (clusterDecisionCount != null) {
      let clusterFloor;
      if (clusterDecisionCount < 50) {
        clusterFloor = Math.max(0.15, globalFloor);
      } else if (clusterDecisionCount <= 200) {
        clusterFloor = Math.max(0.08, globalFloor);
      } else {
        clusterFloor = globalFloor;
      }
      // Take the max of base rate and cluster floor
      baseRate = Math.max(baseRate, clusterFloor);
    }
  }

  return baseRate;
}

class ThompsonBandit {
  /**
   * @param {object} opts
   * @param {string} [opts.statePath] - Path to persist state
   * @param {string} [opts.historyPath] - Path for append-only history
   * @param {number} [opts.explorationRate] - Fraction of decisions using uniform prior
   * @param {object} [opts.registry] - ParamRegistry instance (for testing)
   */
  constructor(opts = {}) {
    this.statePath = opts.statePath || STATE_PATH;
    this.historyPath = opts.historyPath || HISTORY_PATH;
    this.explorationRate = opts.explorationRate != null ? opts.explorationRate : EXPLORATION_RATE;
    this.registry = opts.registry || getRegistry();
    this.beliefs = {};
    this.sampleCounter = 0;

    this._loadState();
  }

  _loadState() {
    try {
      if (fs.existsSync(this.statePath)) {
        const data = JSON.parse(fs.readFileSync(this.statePath, 'utf8'));
        this.beliefs = data.beliefs || {};
        this.sampleCounter = data.sampleCounter || 0;
      }
    } catch (_) {
      // Start fresh on corrupt state
      this.beliefs = {};
      this.sampleCounter = 0;
    }

    // Initialize beliefs for any new params not yet in state
    const params = this.registry.getAllParams();
    for (const p of params) {
      if (!this.beliefs[p.id]) {
        this.beliefs[p.id] = { alpha: 1.0, beta: 1.0 };
      }
    }
  }

  _saveState() {
    const dir = path.dirname(this.statePath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(this.statePath, JSON.stringify({
      beliefs: this.beliefs,
      sampleCounter: this.sampleCounter,
      lastUpdated: new Date().toISOString()
    }, null, 2));
  }

  /**
   * Check if Bayesian Optimization evaluation is active (freeze perturbation).
   * @returns {boolean}
   */
  _isBoFrozen() {
    try {
      if (fs.existsSync(BO_STATE_PATH)) {
        const data = JSON.parse(fs.readFileSync(BO_STATE_PATH, 'utf8'));
        return data.boEvaluationActive === true;
      }
    } catch (_) {
      // Corrupt or missing — not frozen
    }
    return false;
  }

  /**
   * Sample perturbed weights for a single routing decision.
   * Returns { sampleId, weights, exploring, boFrozen, explorationRate, clusterId }
   *
   * If BO evaluation is active (data/bo-state.json boEvaluationActive=true),
   * returns current registry weights without perturbation.
   *
   * @param {string|number|null} [clusterId] - Cluster index for per-cluster annealing
   */
  sample(clusterId) {
    const boFrozen = this._isBoFrozen();
    const params = this.registry.getAllParams();
    const weights = {};

    if (boFrozen) {
      // BO evaluation active — use current weights as-is, no perturbation
      for (const p of params) {
        weights[p.id] = p.value;
      }
      this.sampleCounter++;
      const sampleId = `sample-${this.sampleCounter}-${Date.now()}`;
      return { sampleId, weights, exploring: false, boFrozen: true, explorationRate: 0, clusterId: clusterId != null ? clusterId : null };
    }

    // US-207: Per-cluster exploration annealing
    const currentExplorationRate = getExplorationRate(this.sampleCounter, clusterId != null ? clusterId : null);
    const exploring = Math.random() < currentExplorationRate;

    for (const p of params) {
      const belief = this.beliefs[p.id];
      let direction;

      if (exploring) {
        // Uniform prior: equal chance of positive or negative perturbation
        direction = sampleBeta(1.0, 1.0);
      } else {
        // Learned posterior
        direction = sampleBeta(belief.alpha, belief.beta);
      }

      // Map [0, 1] -> [-1, 1] perturbation direction
      const perturbation = (direction - 0.5) * 2 * p.learnRate;
      let value = p.value + perturbation;

      // Clamp to bounds
      value = Math.max(p.min, Math.min(p.max, value));
      // Integer constraint: round after perturbation
      if (p.integerOnly) {
        value = Math.round(value);
        value = Math.max(p.min, Math.min(p.max, value));
      }
      weights[p.id] = value;
    }

    // Enforce group constraints on the perturbed weights
    this._enforceConstraints(weights);

    this.sampleCounter++;
    const sampleId = `sample-${this.sampleCounter}-${Date.now()}`;

    return { sampleId, weights, exploring, boFrozen: false, explorationRate: currentExplorationRate, clusterId: clusterId != null ? clusterId : null };
  }

  _enforceConstraints(weights) {
    const groupNames = this.registry.getGroupNames();

    for (const groupName of groupNames) {
      const constraint = this.registry.getGroupConstraint(groupName);
      if (!constraint) continue;

      const members = this.registry.getGroup(groupName);
      const ids = members.map(m => m.id);

      if (constraint.constraint === 'sumMustEqual') {
        const target = constraint.target;
        const sum = ids.reduce((acc, id) => acc + weights[id], 0);
        if (sum > 0 && Math.abs(sum - target) > 0.0001) {
          // Normalize to target
          const ratio = target / sum;
          for (const id of ids) {
            const p = members.find(m => m.id === id);
            weights[id] = Math.max(p.min, Math.min(p.max, weights[id] * ratio));
          }
        }
      }

      if (constraint.constraint === 'monotonic' && constraint.direction === 'ascending') {
        // Sort by original value order and enforce ascending
        const sorted = ids.slice().sort((a, b) => {
          const pa = members.find(m => m.id === a);
          const pb = members.find(m => m.id === b);
          return pa.value - pb.value;
        });
        for (let i = 1; i < sorted.length; i++) {
          if (weights[sorted[i]] <= weights[sorted[i - 1]]) {
            weights[sorted[i]] = weights[sorted[i - 1]] + 0.001;
            const p = members.find(m => m.id === sorted[i]);
            weights[sorted[i]] = Math.min(p.max, weights[sorted[i]]);
          }
        }
      }
    }
  }

  /**
   * Update beliefs based on observed reward.
   * @param {string} sampleId - ID from sample() call
   * @param {object} perturbedWeights - The weights that were used
   * @param {number} reward - Reward in [0, 1]
   * @param {object} [rewardWeights] - The reward composition weights used { dq, cost, behavioral }
   * @param {number} [explorationRate] - The exploration rate used for this decision
   * @param {string|number} [clusterId] - The cluster this decision belonged to
   */
  update(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId) {
    if (typeof reward !== 'number' || reward < 0 || reward > 1) {
      throw new Error(`Bandit update: reward must be in [0, 1], got ${reward}`);
    }

    const params = this.registry.getAllParams();

    for (const p of params) {
      const perturbedValue = perturbedWeights[p.id];
      if (perturbedValue === undefined) continue;

      const belief = this.beliefs[p.id];
      const wentUp = perturbedValue > p.value;

      if (reward > 0.5) {
        // Good outcome — reinforce the direction taken
        if (wentUp) {
          belief.alpha += reward;
        } else {
          belief.beta += reward;
        }
      } else {
        // Bad outcome — penalize the direction taken
        if (wentUp) {
          belief.beta += (1 - reward);
        } else {
          belief.alpha += (1 - reward);
        }
      }
    }

    // Persist state
    this._saveState();

    // Append to history (includes reward composition weights, exploration rate, cluster when available)
    this._logHistory(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId);
  }

  _logHistory(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId) {
    const entry = {
      sampleId,
      reward,
      perturbedWeights,
      timestamp: new Date().toISOString()
    };
    if (rewardWeights) {
      entry.rewardWeights = rewardWeights;
    }
    if (explorationRate != null) {
      entry.explorationRate = explorationRate;
    }
    if (clusterId != null) {
      entry.clusterId = clusterId;
    }
    const dir = path.dirname(this.historyPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.appendFileSync(this.historyPath, JSON.stringify(entry) + '\n');
  }

  /**
   * Get current beliefs for inspection.
   */
  getBeliefs() {
    return JSON.parse(JSON.stringify(this.beliefs));
  }

  /**
   * Get belief for a specific parameter.
   */
  getBelief(paramId) {
    return this.beliefs[paramId] ? { ...this.beliefs[paramId] } : null;
  }
}

/**
 * US-103 / US-205 / US-208: Compute reward from routing decision + behavioral outcome.
 *
 * Reward weights are loaded from the param registry (reward_composition group)
 * instead of being hardcoded, enabling meta-learning of the reward function itself.
 *
 * US-208: If sessionType is provided (via routingDecision.sessionType or
 * behavioralOutcome.sessionType), session-type-specific multipliers are applied
 * element-wise to the reward components before computing the composite reward.
 * The result is normalized back to [0,1].
 *
 * @param {object} routingDecision - { dqScore, modelUsed, queryTier, sessionType? }
 * @param {object} behavioralOutcome - { compositeScore, actualCost?, toolSuccessRate?, completionRate?, sessionType? }
 * @param {object} [pricing] - Pricing data from config/pricing.json (auto-loaded if omitted)
 * @param {object} [registry] - ParamRegistry instance (auto-loaded if omitted)
 * @returns {{ reward: number, rewardWeights: object, sessionType?: string, sessionMultipliers?: object }}
 */
function computeReward(routingDecision, behavioralOutcome, pricing, registry) {
  // Load reward weights from registry (learnable) with hardcoded fallbacks
  let DQ_WEIGHT = 0.40;
  let COST_WEIGHT = 0.30;
  let BEHAVIORAL_WEIGHT = 0.30;

  try {
    const reg = registry || getRegistry();
    const rewardGroup = reg.getGroup('reward_composition');
    if (rewardGroup && rewardGroup.length === 3) {
      for (const p of rewardGroup) {
        if (p.id === 'rewardWeightDQ') DQ_WEIGHT = p.value;
        else if (p.id === 'rewardWeightCost') COST_WEIGHT = p.value;
        else if (p.id === 'rewardWeightBehavioral') BEHAVIORAL_WEIGHT = p.value;
      }
    }
  } catch (_) {
    // Fall back to defaults if registry unavailable
  }

  // Component 1: DQ score accuracy (already in [0, 1])
  let dqComponent = Math.max(0, Math.min(1, routingDecision.dqScore || 0));

  // Component 2: Cost efficiency = 1 - (actual / max_possible)
  let costComponent = 0.5; // Default if no cost data
  if (behavioralOutcome.actualCost != null) {
    const maxCost = _getMaxCostForTier(routingDecision.queryTier, pricing);
    if (maxCost > 0) {
      costComponent = Math.max(0, Math.min(1, 1.0 - (behavioralOutcome.actualCost / maxCost)));
    }
  }

  // Component 3: Behavioral outcome (already in [0, 1])
  let behavioralComponent = Math.max(0, Math.min(1, behavioralOutcome.compositeScore || 0));

  // US-208: Session-type reward multipliers
  const sessionType = routingDecision.sessionType || behavioralOutcome.sessionType || null;
  let appliedMultipliers = null;

  if (sessionType) {
    const config = _getSessionMultipliers();
    const mults = config.multipliers || {};
    const defaultType = config.default || 'refactoring';
    const multiplier = mults[sessionType] || mults[defaultType] || { dq: 1.0, cost: 1.0, behavioral: 1.0 };

    // Apply element-wise multipliers
    dqComponent *= (multiplier.dq || 1.0);
    costComponent *= (multiplier.cost || 1.0);
    behavioralComponent *= (multiplier.behavioral || 1.0);

    // Apply tool_success_boost if available in multiplier and toolSuccessRate in outcome
    if (multiplier.tool_success_boost && behavioralOutcome.toolSuccessRate != null) {
      behavioralComponent *= multiplier.tool_success_boost;
    }

    // Apply completion_boost if available in multiplier and completionRate in outcome
    if (multiplier.completion_boost && behavioralOutcome.completionRate != null) {
      behavioralComponent *= multiplier.completion_boost;
    }

    appliedMultipliers = { ...multiplier };
  }

  const rawReward = (DQ_WEIGHT * dqComponent) +
                    (COST_WEIGHT * costComponent) +
                    (BEHAVIORAL_WEIGHT * behavioralComponent);

  // Normalize back to [0, 1]
  const clampedReward = Math.max(0, Math.min(1, rawReward));

  const result = {
    reward: clampedReward,
    rewardWeights: { dq: DQ_WEIGHT, cost: COST_WEIGHT, behavioral: BEHAVIORAL_WEIGHT }
  };

  // US-208: Include session type info in result when present
  if (sessionType) {
    result.sessionType = sessionType;
    result.sessionMultipliers = appliedMultipliers;
  }

  return result;
}

/**
 * Get max possible cost for a query tier based on the most expensive model.
 */
function _getMaxCostForTier(queryTier, pricing) {
  if (!pricing) {
    try {
      const pricingPath = path.join(__dirname, '..', 'config', 'pricing.json');
      pricing = JSON.parse(fs.readFileSync(pricingPath, 'utf8'));
    } catch (_) {
      return 25.0; // Fallback to Opus output price per 1M tokens
    }
  }

  // Find the most expensive output price across all providers
  let maxOutput = 0;
  for (const provider of Object.values(pricing.providers || {})) {
    for (const model of Object.values(provider.models || {})) {
      if (model.output > maxOutput) {
        maxOutput = model.output;
      }
    }
  }
  return maxOutput || 25.0;
}

module.exports = { ThompsonBandit, sampleBeta, sampleGamma, computeReward, getExplorationRate };
