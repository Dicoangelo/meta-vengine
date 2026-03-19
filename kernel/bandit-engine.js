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
const SESSION_TYPE_STATS_PATH = path.join(__dirname, '..', 'data', 'session-type-stats.jsonl');
const EXPLORATION_RATE = 0.15;
const VOLUME_GATE_THRESHOLD = 100;
const VOLUME_GATE_REFRESH_INTERVAL = 50;

// US-208: Cached session-type reward multipliers (loaded once, config file fallback)
let _sessionMultipliersCache = null;

// US-307: Cached session-type volume counts (refreshed every VOLUME_GATE_REFRESH_INTERVAL decisions)
let _volumeGateCache = null;
let _volumeGateDecisionCounter = 0;

/**
 * US-208: Load session-type reward multipliers from config file (fallback only).
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
 * US-307: Load session-type volume counts from data/session-type-stats.jsonl.
 * Returns { sessionType: latestCumulativeCount, ... }.
 * Uses module-level cache, refreshed every VOLUME_GATE_REFRESH_INTERVAL decisions.
 */
function _getVolumeGateCounts(forceRefresh) {
  if (_volumeGateCache && !forceRefresh && (_volumeGateDecisionCounter % VOLUME_GATE_REFRESH_INTERVAL !== 0)) {
    return _volumeGateCache;
  }
  const counts = {};
  try {
    if (fs.existsSync(SESSION_TYPE_STATS_PATH)) {
      const content = fs.readFileSync(SESSION_TYPE_STATS_PATH, 'utf8');
      const lines = content.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const entry = JSON.parse(trimmed);
          if (entry.session_type && entry.cumulative_count != null) {
            counts[entry.session_type] = entry.cumulative_count;
          }
        } catch (_) {
          // skip malformed lines
        }
      }
    }
  } catch (_) {
    // file missing or unreadable — all types gated
  }
  _volumeGateCache = counts;
  return counts;
}

/**
 * US-307: Record a routing decision for a session type (append to session-type-stats.jsonl).
 */
function _recordSessionDecision(sessionType) {
  if (!sessionType) return;
  const counts = _getVolumeGateCounts(false);
  const newCount = (counts[sessionType] || 0) + 1;
  const entry = {
    timestamp: new Date().toISOString(),
    session_type: sessionType,
    cumulative_count: newCount
  };
  try {
    const dir = path.dirname(SESSION_TYPE_STATS_PATH);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.appendFileSync(SESSION_TYPE_STATS_PATH, JSON.stringify(entry) + '\n');
    // Update cache immediately
    if (_volumeGateCache) {
      _volumeGateCache[sessionType] = newCount;
    }
  } catch (_) {
    // Non-fatal — don't break routing on stats write failure
  }
}

/**
 * US-307: Check if a session type is volume-gated (insufficient data).
 */
function _isSessionGated(sessionType) {
  if (!sessionType) return false;
  const counts = _getVolumeGateCounts(false);
  return (counts[sessionType] || 0) < VOLUME_GATE_THRESHOLD;
}

/**
 * US-306: Read session-type multipliers from param registry.
 * Constructs param IDs: session_{type}_dq, session_{type}_cost, session_{type}_behavioral
 * Falls back to {dq: 1.0, cost: 1.0, behavioral: 1.0} if params not found.
 *
 * @param {string} sessionType - e.g. "debugging", "research", "architecture"
 * @param {object} registry - ParamRegistry instance
 * @returns {{ dq: number, cost: number, behavioral: number }}
 */
function _getRegistryMultipliers(sessionType, registry) {
  const fallback = { dq: 1.0, cost: 1.0, behavioral: 1.0 };
  if (!sessionType || !registry) return fallback;

  const dqId = `session_${sessionType}_dq`;
  const costId = `session_${sessionType}_cost`;
  const behavioralId = `session_${sessionType}_behavioral`;

  try {
    const dqParam = registry.getParam(dqId);
    const costParam = registry.getParam(costId);
    const behavioralParam = registry.getParam(behavioralId);
    return { dq: dqParam.value, cost: costParam.value, behavioral: behavioralParam.value };
  } catch (_) {
    // Params not found in registry for this session type
    return fallback;
  }
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
   * Returns { sampleId, weights, exploring, boFrozen, explorationRate, clusterId, volumeGated }
   *
   * If BO evaluation is active (data/bo-state.json boEvaluationActive=true),
   * returns current registry weights without perturbation.
   *
   * US-307: Session-type params (session_{type}_dq/cost/behavioral) are only
   * perturbed when the session type has >= VOLUME_GATE_THRESHOLD decisions.
   * Gated params use registry defaults instead.
   *
   * @param {string|number|null} [clusterId] - Cluster index for per-cluster annealing
   * @param {string|null} [sessionType] - Session type for volume gate check
   */
  sample(clusterId, sessionType) {
    const boFrozen = this._isBoFrozen();
    const params = this.registry.getAllParams();
    const weights = {};

    // US-307: Refresh volume gate cache periodically and check gating
    _volumeGateDecisionCounter++;
    _getVolumeGateCounts(_volumeGateDecisionCounter % VOLUME_GATE_REFRESH_INTERVAL === 0);

    // US-307: Determine which session types are gated
    const gatedSessionTypes = new Set();
    const sessionTypes = ['debugging', 'research', 'architecture', 'refactoring', 'testing', 'docs', 'exploration', 'creative'];
    for (const st of sessionTypes) {
      if (_isSessionGated(st)) {
        gatedSessionTypes.add(st);
      }
    }
    const anyGated = gatedSessionTypes.size > 0;

    if (boFrozen) {
      // BO evaluation active — use current weights as-is, no perturbation
      for (const p of params) {
        weights[p.id] = p.value;
      }
      this.sampleCounter++;
      // US-307: Record session decision for volume tracking
      if (sessionType) _recordSessionDecision(sessionType);
      const sampleId = `sample-${this.sampleCounter}-${Date.now()}`;
      return { sampleId, weights, exploring: false, boFrozen: true, explorationRate: 0, clusterId: clusterId != null ? clusterId : null, volumeGated: anyGated };
    }

    // US-207: Per-cluster exploration annealing
    const currentExplorationRate = getExplorationRate(this.sampleCounter, clusterId != null ? clusterId : null);
    const exploring = Math.random() < currentExplorationRate;

    for (const p of params) {
      // US-307: Skip perturbation for gated session-type params
      if (p.id.startsWith('session_')) {
        // Extract session type from param id: session_{type}_{component}
        const parts = p.id.split('_');
        // parts: ['session', type, component] — type may have underscores so use all but first and last
        const paramSessionType = parts.slice(1, -1).join('_');
        if (gatedSessionTypes.has(paramSessionType)) {
          // Gated: use registry default, no perturbation
          weights[p.id] = p.value;
          continue;
        }
      }

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

    // US-307: Record session decision for volume tracking
    if (sessionType) _recordSessionDecision(sessionType);

    const sampleId = `sample-${this.sampleCounter}-${Date.now()}`;

    return { sampleId, weights, exploring, boFrozen: false, explorationRate: currentExplorationRate, clusterId: clusterId != null ? clusterId : null, volumeGated: anyGated };
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
   * @param {string} [sessionMultipliersSource] - US-306: "registry" or "config_fallback"
   * @param {boolean} [volumeGated] - US-307: Whether session multiplier learning was gated
   */
  update(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId, sessionMultipliersSource, volumeGated) {
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

    // Append to history (includes reward composition weights, exploration rate, cluster, multiplier source, volume gate)
    this._logHistory(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId, sessionMultipliersSource, volumeGated);
  }

  _logHistory(sampleId, perturbedWeights, reward, rewardWeights, explorationRate, clusterId, sessionMultipliersSource, volumeGated) {
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
    if (sessionMultipliersSource) {
      entry.sessionMultipliersSource = sessionMultipliersSource;
    }
    if (volumeGated != null) {
      entry.volumeGated = volumeGated;
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
 * @returns {{ reward: number, rewardWeights: object, sessionType?: string, sessionMultipliers?: object, sessionMultipliersSource?: string }}
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

  // US-208 / US-306: Session-type reward multipliers
  // Prefer registry (learnable via bandit), fall back to config file
  const sessionType = routingDecision.sessionType || behavioralOutcome.sessionType || null;
  let appliedMultipliers = null;
  let sessionMultipliersSource = null;

  if (sessionType) {
    const reg = registry || getRegistry();
    let multiplier;

    // US-306: Try registry first (learnable multipliers)
    const registryMults = _getRegistryMultipliers(sessionType, reg);
    const isRegistryDefault = (registryMults.dq === 1.0 && registryMults.cost === 1.0 && registryMults.behavioral === 1.0);

    // Check if registry actually has session_* params for this type
    let hasRegistryParams = false;
    try {
      reg.getParam(`session_${sessionType}_dq`);
      hasRegistryParams = true;
    } catch (_) {}

    if (hasRegistryParams) {
      multiplier = { ...registryMults };
      sessionMultipliersSource = 'registry';
    } else {
      // Fallback to config file
      const config = _getSessionMultipliers();
      const mults = config.multipliers || {};
      const defaultType = config.default || 'refactoring';
      multiplier = mults[sessionType] || mults[defaultType] || { dq: 1.0, cost: 1.0, behavioral: 1.0 };
      multiplier = { ...multiplier };
      sessionMultipliersSource = 'config_fallback';
    }

    // Apply element-wise multipliers (dq/cost/behavioral from registry or config)
    dqComponent *= (multiplier.dq || 1.0);
    costComponent *= (multiplier.cost || 1.0);
    behavioralComponent *= (multiplier.behavioral || 1.0);

    // Boosts are NOT in registry — always read from config file
    const config = _getSessionMultipliers();
    const configMults = (config.multipliers || {})[sessionType] || {};

    // Apply tool_success_boost if available in config and toolSuccessRate in outcome
    if (configMults.tool_success_boost && behavioralOutcome.toolSuccessRate != null) {
      behavioralComponent *= configMults.tool_success_boost;
      multiplier.tool_success_boost = configMults.tool_success_boost;
    }

    // Apply completion_boost if available in config and completionRate in outcome
    if (configMults.completion_boost && behavioralOutcome.completionRate != null) {
      behavioralComponent *= configMults.completion_boost;
      multiplier.completion_boost = configMults.completion_boost;
    }

    appliedMultipliers = multiplier;
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

  // US-208 / US-306: Include session type info and source in result when present
  if (sessionType) {
    result.sessionType = sessionType;
    result.sessionMultipliers = appliedMultipliers;
    result.sessionMultipliersSource = sessionMultipliersSource;
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
