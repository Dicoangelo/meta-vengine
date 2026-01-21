#!/usr/bin/env node
/**
 * Decision Quality (DQ) Scorer - ACE Framework Implementation
 *
 * Based on: OS-App Adaptive Convergence Engine (ACE) DQ Framework
 * Measures: validity (0.4) + specificity (0.3) + correctness (0.3)
 *
 * Scores routing decisions and learns from history.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { estimateComplexity } = require('./complexity-analyzer');

// ═══════════════════════════════════════════════════════════════════════════
// BASELINES LOADING
// ═══════════════════════════════════════════════════════════════════════════

const BASELINES_PATH = path.join(process.env.HOME, '.claude/kernel/baselines.json');

function loadBaselines() {
  if (!fs.existsSync(BASELINES_PATH)) {
    return null;  // Use hardcoded defaults
  }

  try {
    const data = fs.readFileSync(BASELINES_PATH, 'utf8');
    return JSON.parse(data);
  } catch (e) {
    console.error('Error loading baselines:', e.message);
    return null;
  }
}

const BASELINES = loadBaselines();

// ═══════════════════════════════════════════════════════════════════════════
// DQ WEIGHTS (from ACE Framework)
// ═══════════════════════════════════════════════════════════════════════════

const DQ_WEIGHTS = BASELINES?.dq_weights || {
  validity: 0.4,      // Does the routing make logical sense?
  specificity: 0.3,   // How precise is the model selection?
  correctness: 0.3    // Historical accuracy of similar queries
};

// Actionable threshold
const DQ_THRESHOLD = BASELINES?.dq_thresholds?.actionable || 0.5;

// Model capabilities (for validity assessment)
// Load from baselines if available, otherwise use hardcoded
const MODEL_CAPABILITIES = BASELINES?.complexity_thresholds ? {
  haiku: {
    strengths: ['quick answers', 'simple tasks', 'formatting', 'short responses'],
    weaknesses: ['complex reasoning', 'long context', 'code generation', 'architecture'],
    maxComplexity: BASELINES.complexity_thresholds.haiku.range[1],
    costPerMToken: BASELINES.cost_per_mtok?.haiku || { input: 0.25, output: 1.25 }
  },
  sonnet: {
    strengths: ['code generation', 'analysis', 'moderate reasoning', 'balanced tasks'],
    weaknesses: ['expert-level problems', 'novel architecture', 'research synthesis'],
    maxComplexity: BASELINES.complexity_thresholds.sonnet.range[1],
    costPerMToken: BASELINES.cost_per_mtok?.sonnet || { input: 3, output: 15 }
  },
  opus: {
    strengths: ['complex reasoning', 'novel problems', 'architecture', 'research', 'expert tasks'],
    weaknesses: ['cost', 'latency for simple tasks'],
    maxComplexity: BASELINES.complexity_thresholds.opus.range[1],
    costPerMToken: BASELINES.cost_per_mtok?.opus || { input: 5, output: 25 }
  }
} : {
  // Fallback values - Updated Jan 2026 for Opus 4.5
  haiku: {
    strengths: ['quick answers', 'simple tasks', 'formatting', 'short responses'],
    weaknesses: ['complex reasoning', 'long context', 'code generation', 'architecture'],
    maxComplexity: 0.30,
    costPerMToken: { input: 0.80, output: 4 }
  },
  sonnet: {
    strengths: ['code generation', 'analysis', 'moderate reasoning', 'balanced tasks'],
    weaknesses: ['expert-level problems', 'novel architecture', 'research synthesis'],
    maxComplexity: 0.70,
    costPerMToken: { input: 3, output: 15 }
  },
  opus: {
    strengths: ['complex reasoning', 'novel problems', 'architecture', 'research', 'expert tasks'],
    weaknesses: ['cost', 'latency for simple tasks'],
    maxComplexity: 1.0,
    costPerMToken: { input: 5, output: 25 }
  }
};

// Adaptive thresholds (from ACE)
const ADAPTIVE_THRESHOLDS = {
  simple:   { complexity: [0, 0.25],   model: 'haiku',  rounds: 3,  gap: 2 },
  moderate: { complexity: [0.25, 0.50], model: 'sonnet', rounds: 7,  gap: 3 },
  complex:  { complexity: [0.50, 0.75], model: 'sonnet', rounds: 12, gap: 4 },
  expert:   { complexity: [0.75, 1.0],  model: 'opus',   rounds: 15, gap: 5 }
};

// ═══════════════════════════════════════════════════════════════════════════
// HISTORY MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

const HISTORY_PATH = path.join(process.env.HOME, '.claude/kernel/dq-scores.jsonl');

function loadHistory() {
  if (!fs.existsSync(HISTORY_PATH)) return [];

  try {
    const lines = fs.readFileSync(HISTORY_PATH, 'utf8').split('\n').filter(l => l.trim());
    return lines.map(l => JSON.parse(l));
  } catch (e) {
    return [];
  }
}

function saveDecision(decision) {
  const line = JSON.stringify(decision) + '\n';
  fs.appendFileSync(HISTORY_PATH, line);
}

// ═══════════════════════════════════════════════════════════════════════════
// DQ SCORING FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Assess validity: Does the model selection make logical sense?
 */
function assessValidity(complexity, model) {
  const modelCaps = MODEL_CAPABILITIES[model];
  if (!modelCaps) return 0;

  // Perfect validity: complexity within model's range
  if (complexity <= modelCaps.maxComplexity) {
    // Penalize over-provisioning (using opus for simple tasks)
    const overProvision = modelCaps.maxComplexity - complexity;
    if (model === 'opus' && complexity < 0.5) {
      return 0.6; // Wasteful but valid
    }
    if (model === 'sonnet' && complexity < 0.2) {
      return 0.7; // Slightly wasteful
    }
    return 1.0 - (overProvision * 0.2); // Small penalty for over-provisioning
  }

  // Under-provisioning is worse
  const underProvision = complexity - modelCaps.maxComplexity;
  return Math.max(0, 1.0 - (underProvision * 2)); // Heavy penalty
}

/**
 * Assess specificity: How precise is the model selection?
 */
function assessSpecificity(query, complexity, model) {
  // Check if model matches the ideal for this complexity
  let idealModel;
  for (const [level, config] of Object.entries(ADAPTIVE_THRESHOLDS)) {
    if (complexity >= config.complexity[0] && complexity < config.complexity[1]) {
      idealModel = config.model;
      break;
    }
  }
  if (!idealModel) idealModel = 'opus';

  if (model === idealModel) return 1.0;

  // Adjacent model is acceptable
  const models = ['haiku', 'sonnet', 'opus'];
  const idealIdx = models.indexOf(idealModel);
  const actualIdx = models.indexOf(model);
  const distance = Math.abs(idealIdx - actualIdx);

  return Math.max(0, 1.0 - (distance * 0.4));
}

/**
 * Assess correctness: Historical accuracy for similar queries
 */
function assessCorrectness(query, model, history) {
  if (history.length === 0) return 0.5; // No history, neutral

  // Find similar queries
  const queryTokens = new Set(query.toLowerCase().split(/\s+/));
  const similar = history.filter(h => {
    if (!h.query) return false;
    const histTokens = new Set(h.query.toLowerCase().split(/\s+/));
    const intersection = [...queryTokens].filter(t => histTokens.has(t)).length;
    return intersection / Math.max(queryTokens.size, histTokens.size) > 0.3;
  });

  if (similar.length === 0) return 0.5;

  // Check success rate for this model on similar queries
  const modelMatches = similar.filter(s => s.model === model);
  if (modelMatches.length === 0) return 0.5;

  // If we have feedback, use it
  const withFeedback = modelMatches.filter(m => m.success !== undefined);
  if (withFeedback.length > 0) {
    const successRate = withFeedback.filter(m => m.success).length / withFeedback.length;
    return successRate;
  }

  // Otherwise, assume DQ score is a proxy for success
  const avgDQ = modelMatches.reduce((sum, m) => sum + (m.dqScore || 0.5), 0) / modelMatches.length;
  return avgDQ;
}

/**
 * Calculate composite DQ score
 */
function calculateDQ(query, complexity, model, history = []) {
  const validity = assessValidity(complexity, model);
  const specificity = assessSpecificity(query, complexity, model);
  const correctness = assessCorrectness(query, model, history);

  const score = (validity * DQ_WEIGHTS.validity) +
                (specificity * DQ_WEIGHTS.specificity) +
                (correctness * DQ_WEIGHTS.correctness);

  return {
    score: parseFloat(score.toFixed(3)),
    components: {
      validity: parseFloat(validity.toFixed(3)),
      specificity: parseFloat(specificity.toFixed(3)),
      correctness: parseFloat(correctness.toFixed(3))
    },
    actionable: score >= DQ_THRESHOLD
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// ROUTING DECISION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Make a routing decision with DQ scoring
 */
function route(query) {
  const history = loadHistory();
  const complexity = estimateComplexity(query);

  // Try each model and pick best DQ
  const candidates = ['haiku', 'sonnet', 'opus'].map(model => {
    const dq = calculateDQ(query, complexity.score, model, history);
    return { model, dq, complexity: complexity.score };
  });

  // Sort by DQ score (highest first), then by cost (lowest first for ties)
  candidates.sort((a, b) => {
    if (Math.abs(a.dq.score - b.dq.score) > 0.05) {
      return b.dq.score - a.dq.score;
    }
    // If DQ scores are similar, prefer cheaper model
    const costOrder = { haiku: 0, sonnet: 1, opus: 2 };
    return costOrder[a.model] - costOrder[b.model];
  });

  const best = candidates[0];

  // Estimate cost for this routing decision
  function estimateCost(model, queryText) {
    const modelCaps = MODEL_CAPABILITIES[model];
    if (!modelCaps) return 0;

    // Rough estimate: query ~100 tokens, response ~500 tokens
    const estInputTokens = Math.max(100, queryText.length / 4);
    const estOutputTokens = 500;

    const cost = (estInputTokens * modelCaps.costPerMToken.input / 1_000_000 +
                  estOutputTokens * modelCaps.costPerMToken.output / 1_000_000);

    return cost;
  }

  // Log the decision with enhanced metadata
  const decision = {
    ts: Date.now(),
    query_hash: crypto.createHash('md5').update(query).digest('hex'),
    query: query.slice(0, 200), // Truncate for storage
    query_preview: query.slice(0, 50),
    complexity: complexity.score,
    complexity_reasoning: complexity.reasoning,
    model: best.model,
    dqScore: best.dq.score,
    dqComponents: best.dq.components,
    reasoning: complexity.reasoning,
    alternatives: candidates.slice(1).map(c => ({ model: c.model, dq: c.dq.score })),
    cost_estimate: estimateCost(best.model, query),
    baseline_version: BASELINES ? BASELINES.version : 'hardcoded'
  };

  saveDecision(decision);

  return {
    model: best.model,
    complexity: complexity.score,
    dq: best.dq,
    reasoning: complexity.reasoning,
    cost_estimate: decision.cost_estimate,
    baseline_version: decision.baseline_version
  };
}

/**
 * Record feedback on a routing decision
 */
function recordFeedback(queryPrefix, success) {
  const history = loadHistory();

  // Find most recent matching query
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].query && history[i].query.startsWith(queryPrefix)) {
      history[i].success = success;
      history[i].feedbackTs = Date.now();

      // Rewrite history file
      const content = history.map(h => JSON.stringify(h)).join('\n') + '\n';
      fs.writeFileSync(HISTORY_PATH, content);
      return true;
    }
  }
  return false;
}

/**
 * Get statistics on routing decisions
 */
function getStats() {
  const history = loadHistory();
  const last24h = history.filter(h => h.ts > Date.now() - 86400000);
  const last7d = history.filter(h => h.ts > Date.now() - 604800000);

  const modelCounts = { haiku: 0, sonnet: 0, opus: 0 };
  const modelDQ = { haiku: [], sonnet: [], opus: [] };

  for (const h of last7d) {
    if (h.model) modelCounts[h.model]++;
    if (h.model && h.dqScore) modelDQ[h.model].push(h.dqScore);
  }

  const avgDQ = {};
  for (const [model, scores] of Object.entries(modelDQ)) {
    avgDQ[model] = scores.length > 0
      ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(3)
      : 'N/A';
  }

  return {
    total: history.length,
    last24h: last24h.length,
    last7d: last7d.length,
    modelDistribution: modelCounts,
    averageDQ: avgDQ,
    overallAvgDQ: last7d.length > 0
      ? (last7d.reduce((sum, h) => sum + (h.dqScore || 0), 0) / last7d.length).toFixed(3)
      : 'N/A'
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'route':
      // Route a query: node dq-scorer.js route "query here"
      const query = args.slice(1).join(' ');
      if (!query) {
        console.error('Usage: dq-scorer.js route "query"');
        process.exit(1);
      }
      const result = route(query);
      console.log(JSON.stringify(result, null, 2));
      break;

    case 'model':
      // Just get the model: node dq-scorer.js model "query"
      const q = args.slice(1).join(' ');
      const r = route(q);
      console.log(r.model);
      break;

    case 'feedback':
      // Record feedback: node dq-scorer.js feedback "query prefix" success|failure
      const prefix = args[1];
      const success = args[2] === 'success';
      const recorded = recordFeedback(prefix, success);
      console.log(recorded ? 'Feedback recorded' : 'Query not found');
      break;

    case 'stats':
      // Get statistics: node dq-scorer.js stats
      console.log(JSON.stringify(getStats(), null, 2));
      break;

    case 'score':
      // Score a specific model choice: node dq-scorer.js score "query" model
      const scoreQuery = args[1];
      const model = args[2] || 'sonnet';
      const complexity = estimateComplexity(scoreQuery);
      const dq = calculateDQ(scoreQuery, complexity.score, model, loadHistory());
      console.log(JSON.stringify({ complexity: complexity.score, model, dq }, null, 2));
      break;

    default:
      console.log('DQ Scorer - Decision Quality Framework for Model Routing');
      console.log('');
      console.log('Commands:');
      console.log('  route "query"              - Route query to optimal model');
      console.log('  model "query"              - Get just the model name');
      console.log('  score "query" [model]      - Score a specific model choice');
      console.log('  feedback "prefix" success  - Record feedback on a decision');
      console.log('  stats                      - Get routing statistics');
  }
}

module.exports = { route, calculateDQ, recordFeedback, getStats };
