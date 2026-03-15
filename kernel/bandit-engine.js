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
const EXPLORATION_RATE = 0.15;

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
   * Sample perturbed weights for a single routing decision.
   * Returns { sampleId, weights: { paramId: perturbedValue, ... }, exploring }
   */
  sample() {
    const exploring = Math.random() < this.explorationRate;
    const params = this.registry.getAllParams();
    const weights = {};

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
      weights[p.id] = value;
    }

    // Enforce group constraints on the perturbed weights
    this._enforceConstraints(weights);

    this.sampleCounter++;
    const sampleId = `sample-${this.sampleCounter}-${Date.now()}`;

    return { sampleId, weights, exploring };
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
   */
  update(sampleId, perturbedWeights, reward) {
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

    // Append to history
    this._logHistory(sampleId, perturbedWeights, reward);
  }

  _logHistory(sampleId, perturbedWeights, reward) {
    const entry = {
      sampleId,
      reward,
      perturbedWeights,
      timestamp: new Date().toISOString()
    };
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
 * US-103: Compute reward from routing decision + behavioral outcome.
 *
 * Reward = DQ score accuracy (0.40) + cost efficiency (0.30) + behavioral outcome (0.30)
 *
 * @param {object} routingDecision - { dqScore: number, modelUsed: string, queryTier: string }
 * @param {object} behavioralOutcome - { compositeScore: number, actualCost?: number }
 * @param {object} [pricing] - Pricing data from config/pricing.json (auto-loaded if omitted)
 * @returns {number} Reward in [0, 1]
 */
function computeReward(routingDecision, behavioralOutcome, pricing) {
  const DQ_WEIGHT = 0.40;
  const COST_WEIGHT = 0.30;
  const BEHAVIORAL_WEIGHT = 0.30;

  // Component 1: DQ score accuracy (already in [0, 1])
  const dqComponent = Math.max(0, Math.min(1, routingDecision.dqScore || 0));

  // Component 2: Cost efficiency = 1 - (actual / max_possible)
  let costComponent = 0.5; // Default if no cost data
  if (behavioralOutcome.actualCost != null) {
    const maxCost = _getMaxCostForTier(routingDecision.queryTier, pricing);
    if (maxCost > 0) {
      costComponent = Math.max(0, Math.min(1, 1.0 - (behavioralOutcome.actualCost / maxCost)));
    }
  }

  // Component 3: Behavioral outcome (already in [0, 1])
  const behavioralComponent = Math.max(0, Math.min(1, behavioralOutcome.compositeScore || 0));

  const reward = (DQ_WEIGHT * dqComponent) +
                 (COST_WEIGHT * costComponent) +
                 (BEHAVIORAL_WEIGHT * behavioralComponent);

  return Math.max(0, Math.min(1, reward));
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

module.exports = { ThompsonBandit, sampleBeta, sampleGamma, computeReward };
