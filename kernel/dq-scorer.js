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
const { execSync } = require('child_process');
const { estimateComplexity } = require('./complexity-analyzer');
const { PRICING } = require(path.join(process.env.HOME, '.claude/config/pricing.js'));

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
// DQ WEIGHTS (from ACE Framework + Cognitive OS adjustments)
// ═══════════════════════════════════════════════════════════════════════════

const COGNITIVE_DQ_WEIGHTS_PATH = path.join(process.env.HOME, '.claude/kernel/cognitive-os/cognitive-dq-weights.json');
const EXPERTISE_ROUTING_STATE_PATH = path.join(process.env.HOME, '.claude/kernel/expertise-routing-state.json');

function loadCognitiveDQWeights() {
  // Try to load cognitive-aware weights from Cognitive OS
  if (fs.existsSync(COGNITIVE_DQ_WEIGHTS_PATH)) {
    try {
      const data = JSON.parse(fs.readFileSync(COGNITIVE_DQ_WEIGHTS_PATH, 'utf8'));
      const fileAge = Date.now() - new Date(data.timestamp).getTime();
      // Only use if less than 30 minutes old
      if (fileAge < 30 * 60 * 1000 && data.dq_weights) {
        return {
          weights: data.dq_weights,
          complexityModifier: data.complexity_threshold_modifier || 1.0,
          cognitiveMode: data.cognitive_mode,
          reasoning: data.reasoning
        };
      }
    } catch (e) {
      // Fall through to defaults
    }
  }
  return null;
}

const COGNITIVE_WEIGHTS = loadCognitiveDQWeights();

const DQ_WEIGHTS = COGNITIVE_WEIGHTS?.weights || BASELINES?.dq_weights || {
  validity: 0.4,      // Does the routing make logical sense?
  specificity: 0.3,   // How precise is the model selection?
  correctness: 0.3    // Historical accuracy of similar queries
};

// Complexity threshold modifier from Cognitive OS (affects model selection boundaries)
const COMPLEXITY_MODIFIER = COGNITIVE_WEIGHTS?.complexityModifier || 1.0;

// ═══════════════════════════════════════════════════════════════════════════
// EXPERTISE ROUTING
// ═══════════════════════════════════════════════════════════════════════════

function loadExpertiseState() {
  if (fs.existsSync(EXPERTISE_ROUTING_STATE_PATH)) {
    try {
      const data = JSON.parse(fs.readFileSync(EXPERTISE_ROUTING_STATE_PATH, 'utf8'));
      const fileAge = Date.now() - new Date(data.timestamp).getTime();
      // Use if less than 1 hour old
      if (fileAge < 60 * 60 * 1000) {
        return data;
      }
    } catch (e) {}
  }
  return null;
}

const EXPERTISE_STATE = loadExpertiseState();

/**
 * Detect domain of query and check expertise level
 */
function getExpertiseAdjustment(query) {
  if (!EXPERTISE_STATE) return null;

  const highExpertise = EXPERTISE_STATE.high_expertise_domains || [];
  const lowExpertise = EXPERTISE_STATE.low_expertise_domains || [];
  const queryLower = query.toLowerCase();

  // Check if query matches high expertise domains
  for (const domain of highExpertise) {
    if (queryLower.includes(domain) ||
        (domain === 'react' && (queryLower.includes('component') || queryLower.includes('hook'))) ||
        (domain === 'typescript' && queryLower.includes('type')) ||
        (domain === 'python' && queryLower.includes('.py'))) {
      return { domain, adjustment: 'downgrade', expertise: 'high' };
    }
  }

  // Check if query matches low expertise domains
  for (const domain of lowExpertise) {
    if (queryLower.includes(domain)) {
      return { domain, adjustment: 'upgrade', expertise: 'low' };
    }
  }

  return null;
}

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
  // Fallback values from centralized pricing config
  haiku: {
    strengths: ['quick answers', 'simple tasks', 'formatting', 'short responses'],
    weaknesses: ['complex reasoning', 'long context', 'code generation', 'architecture'],
    maxComplexity: 0.30,
    costPerMToken: { input: PRICING.haiku.input, output: PRICING.haiku.output }
  },
  sonnet: {
    strengths: ['code generation', 'analysis', 'moderate reasoning', 'balanced tasks'],
    weaknesses: ['expert-level problems', 'novel architecture', 'research synthesis'],
    maxComplexity: 0.70,
    costPerMToken: { input: PRICING.sonnet.input, output: PRICING.sonnet.output }
  },
  opus: {
    strengths: ['complex reasoning', 'novel problems', 'architecture', 'research', 'expert tasks'],
    weaknesses: ['cost', 'latency for simple tasks'],
    maxComplexity: 1.0,
    costPerMToken: { input: PRICING.opus.input, output: PRICING.opus.output }
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

/**
 * Apply cognitive complexity modifier to adjust thresholds
 */
function applyCognitiveModifier(complexity) {
  // If modifier > 1, we can handle more complexity (raise thresholds effectively)
  // If modifier < 1, we should use simpler models (lower thresholds effectively)
  return complexity / COMPLEXITY_MODIFIER;
}

// ═══════════════════════════════════════════════════════════════════════════
// DISTRIBUTIONAL FEATURES (US-001: Multi-Feature Graph Signal)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Compute distributional features from supermemory retrieval score distributions.
 * Used by the multi-feature graph signal (US-004) to replace single skewness metric.
 *
 * @param {number[]} scores - Raw retrieval scores from supermemory
 * @returns {{entropy: number, gini: number, skewness: number, sampleSize: number} | null}
 *          Returns null when scores.length < 5 (minimum sample threshold per Security Architect)
 */
function computeDistributionalFeatures(scores) {
  if (!Array.isArray(scores) || scores.length < 5) {
    return null;
  }

  const n = scores.length;

  // Normalize scores to a probability distribution (sum to 1)
  const sum = scores.reduce((a, b) => a + b, 0);
  if (sum === 0) {
    return { entropy: 0, gini: 1 / n, skewness: 0, sampleSize: n };
  }
  const probs = scores.map(s => s / sum);

  // Shannon entropy: -Σ(p * log(p)), skip p=0 terms
  const entropy = -probs.reduce((acc, p) => {
    if (p > 0) acc += p * Math.log(p);
    return acc;
  }, 0);

  // Gini impurity: 1 - Σ(p_i²)
  const gini = 1 - probs.reduce((acc, p) => acc + p * p, 0);

  // Skewness (Fisher-Pearson, sample-adjusted)
  const mean = scores.reduce((a, b) => a + b, 0) / n;
  const variance = scores.reduce((acc, s) => acc + (s - mean) ** 2, 0) / n;
  const stdDev = Math.sqrt(variance);
  let skewness = 0;
  if (stdDev > 0 && n >= 3) {
    const m3 = scores.reduce((acc, s) => acc + ((s - mean) / stdDev) ** 3, 0) / n;
    // Apply sample adjustment factor
    skewness = (Math.sqrt(n * (n - 1)) / (n - 2)) * m3;
  }

  return {
    entropy: parseFloat(entropy.toFixed(6)),
    gini: parseFloat(gini.toFixed(6)),
    skewness: parseFloat(skewness.toFixed(6)),
    sampleSize: n
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// IRT DIFFICULTY BRIDGE (US-003: Multi-Feature Graph Signal — IRT Integration)
// ═══════════════════════════════════════════════════════════════════════════

const IRT_BRIDGE_PATH = path.join(process.env.HOME, '.claude/kernel/hsrgs/irt-bridge.json');

/**
 * Load IRT difficulty data from the HSRGS bridge file (Python → Node.js).
 * Returns the bridge data if fresh (< 60 seconds old), null otherwise.
 *
 * @param {string} [queryHash] - Optional query hash to match against bridge data
 * @returns {{difficulty: number, discrimination: number, domain_signature: string,
 *            irt_predictions: Object, selected_model: string, timestamp: number} | null}
 */
function loadIRTBridge(queryHash) {
  try {
    if (!fs.existsSync(IRT_BRIDGE_PATH)) return null;

    const data = JSON.parse(fs.readFileSync(IRT_BRIDGE_PATH, 'utf8'));

    // Staleness check: bridge data must be < 60 seconds old
    const ageMs = Date.now() - data.timestamp;
    if (ageMs > 60000) return null;

    // If queryHash provided, verify it matches
    if (queryHash && data.query_hash !== queryHash) return null;

    // Validate required fields
    if (typeof data.difficulty !== 'number') return null;

    return data;
  } catch (e) {
    return null;
  }
}

/**
 * Compute IRT difficulty modifier for routing.
 * High IRT difficulty (> 0.7) biases toward Opus (positive modifier).
 * Low IRT difficulty (< 0.3) biases toward Haiku (negative modifier).
 * Mid-range: no effect.
 *
 * @param {number} irtDifficulty - IRT difficulty from HSRGS (0.0-1.0)
 * @returns {number} Modifier to apply to complexity score (-0.15 to +0.15)
 */
function computeIRTModifier(irtDifficulty) {
  if (typeof irtDifficulty !== 'number' || isNaN(irtDifficulty)) return 0.0;

  // Clamp to valid range
  const d = Math.max(0.0, Math.min(1.0, irtDifficulty));

  if (d > 0.7) {
    // High difficulty: bias toward more capable model (Opus)
    // Scale: 0.7 → 0.0, 1.0 → +0.15
    return parseFloat(((d - 0.7) / 0.3 * 0.15).toFixed(4));
  } else if (d < 0.3) {
    // Low difficulty: bias toward cheaper model (Haiku)
    // Scale: 0.3 → 0.0, 0.0 → -0.15
    return parseFloat(((d - 0.3) / 0.3 * 0.15).toFixed(4));
  }

  // Mid-range: no modification
  return 0.0;
}

// ═══════════════════════════════════════════════════════════════════════════
// SUBGRAPH DENSITY (US-002: Multi-Feature Graph Signal)
// ═══════════════════════════════════════════════════════════════════════════

const SUPERMEMORY_DB_PATH = path.join(process.env.HOME, '.claude/memory/supermemory.db');

/**
 * Query supermemory.db via sqlite3 CLI (zero-dependency, no native modules).
 * Uses UNION for indexed lookups on both from_id and to_id.
 *
 * @param {string} sql - SQL query to execute
 * @returns {string} Raw output from sqlite3
 */
function querySuperMemory(sql) {
  try {
    return execSync(
      `sqlite3 "${SUPERMEMORY_DB_PATH}" "${sql.replace(/"/g, '\\"')}"`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim();
  } catch (e) {
    return '';
  }
}

/**
 * Compute subgraph density for a set of retrieved knowledge nodes.
 * Sparse subgraphs (density < 0.1) cause ~30% of KG-RAG errors (GraphRouter ICLR 2025).
 *
 * @param {string[]} retrievedNodes - Array of node IDs from supermemory retrieval
 * @param {string} [queryTopic] - Optional topic string for coverage rate estimation via FTS
 * @returns {{density: number, nodeCount: number, edgeCount: number, coverageRate: number} | null}
 *          Returns null when retrievedNodes.length < 2 (need at least 2 nodes for density)
 */
function computeSubgraphDensity(retrievedNodes, queryTopic) {
  if (!Array.isArray(retrievedNodes) || retrievedNodes.length < 2) {
    return null;
  }

  // Deduplicate nodes
  const nodes = [...new Set(retrievedNodes)];
  const nodeCount = nodes.length;

  if (nodeCount < 2) {
    return null;
  }

  // Maximum possible edges in an undirected graph: n*(n-1)/2
  const maxEdges = (nodeCount * (nodeCount - 1)) / 2;

  // Query actual edges among retrieved nodes using indexed UNION approach
  // Build IN clause for the node set
  const inClause = nodes.map(n => `'${n.replace(/'/g, "''")}'`).join(',');

  // Count edges where BOTH endpoints are in the retrieved set
  // UNION approach uses indexes on both from_id and to_id efficiently
  const edgeSql = `SELECT COUNT(*) FROM (
    SELECT DISTINCT from_id, to_id FROM (
      SELECT from_id, to_id FROM memory_links WHERE from_id IN (${inClause}) AND to_id IN (${inClause})
      UNION
      SELECT from_id, to_id FROM memory_links WHERE to_id IN (${inClause}) AND from_id IN (${inClause})
    )
  )`;

  const edgeResult = querySuperMemory(edgeSql);
  const edgeCount = parseInt(edgeResult, 10) || 0;

  // Density = actual edges / possible edges
  const density = maxEdges > 0 ? edgeCount / maxEdges : 0;

  // Coverage rate: retrieved nodes / estimated relevant nodes
  // Use FTS match count from memory_items as the estimate of relevant nodes
  let coverageRate = 1.0; // Default: assume full coverage if no topic
  if (queryTopic && queryTopic.trim()) {
    const safeTopic = queryTopic.replace(/"/g, '').replace(/'/g, "''").replace(/[^\w\s-]/g, '');
    if (safeTopic.trim()) {
      const ftsSql = `SELECT COUNT(*) FROM memory_fts WHERE memory_fts MATCH '${safeTopic}'`;
      const ftsResult = querySuperMemory(ftsSql);
      const relevantCount = parseInt(ftsResult, 10) || 0;
      if (relevantCount > 0) {
        coverageRate = Math.min(1.0, nodeCount / relevantCount);
      }
    }
  }

  return {
    density: parseFloat(density.toFixed(6)),
    nodeCount,
    edgeCount,
    coverageRate: parseFloat(coverageRate.toFixed(6))
  };
}

/**
 * Compute subgraph density from pre-fetched graph links (no DB access needed).
 * Used for testing and when links are already loaded.
 *
 * @param {string[]} retrievedNodes - Array of node IDs
 * @param {{from_id: string, to_id: string}[]} graphLinks - Pre-fetched edge list
 * @returns {{density: number, nodeCount: number, edgeCount: number, coverageRate: number} | null}
 */
function computeSubgraphDensityFromLinks(retrievedNodes, graphLinks) {
  if (!Array.isArray(retrievedNodes) || retrievedNodes.length < 2) {
    return null;
  }
  if (!Array.isArray(graphLinks)) {
    return null;
  }

  const nodeSet = new Set(retrievedNodes);
  const nodeCount = nodeSet.size;

  if (nodeCount < 2) {
    return null;
  }

  const maxEdges = (nodeCount * (nodeCount - 1)) / 2;

  // Count unique edges where both endpoints are in the node set
  const edgeSet = new Set();
  for (const link of graphLinks) {
    if (nodeSet.has(link.from_id) && nodeSet.has(link.to_id) && link.from_id !== link.to_id) {
      // Normalize edge direction for undirected counting
      const edgeKey = [link.from_id, link.to_id].sort().join('::');
      edgeSet.add(edgeKey);
    }
  }

  const edgeCount = edgeSet.size;
  const density = maxEdges > 0 ? edgeCount / maxEdges : 0;

  return {
    density: parseFloat(density.toFixed(6)),
    nodeCount,
    edgeCount,
    coverageRate: 1.0 // No topic available for in-memory computation
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// A/B TEST FRAMEWORK (US-012: Graph Signal vs Keyword Complexity)
// ═══════════════════════════════════════════════════════════════════════════

const AB_TEST_LOG_PATH = path.join(__dirname, '..', 'data', 'ab-test-graph-signal.jsonl');
const AB_TEST_STATE_PATH = path.join(__dirname, '..', 'data', 'ab-test-state.json');

/**
 * Load A/B test state (rollback status, decision count).
 * @returns {{active: boolean, rollback: boolean, reason: string|null, decisionCount: number}}
 */
function loadABTestState() {
  try {
    if (fs.existsSync(AB_TEST_STATE_PATH)) {
      return JSON.parse(fs.readFileSync(AB_TEST_STATE_PATH, 'utf8'));
    }
  } catch (e) { /* fall through */ }
  return { active: true, rollback: false, reason: null, decisionCount: 0 };
}

/**
 * Save A/B test state.
 */
function saveABTestState(state) {
  try {
    fs.writeFileSync(AB_TEST_STATE_PATH, JSON.stringify(state, null, 2));
  } catch (e) {
    console.error('Failed to save A/B test state:', e.message);
  }
}

/**
 * Log an A/B test decision to the dedicated JSONL file.
 * Records both complexity signals, the routing decision, and which signal was used.
 *
 * @param {Object} entry - A/B test log entry
 */
function logABTestDecision(entry) {
  try {
    const dir = path.dirname(AB_TEST_LOG_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(AB_TEST_LOG_PATH, JSON.stringify(entry) + '\n');
  } catch (e) {
    // Non-fatal: don't break routing if logging fails
  }
}

/**
 * Determine A/B test group for a session.
 * Odd session IDs → graph signal, even → keyword. Deterministic and reproducible.
 *
 * @param {number} sessionId - Session identifier (unix seconds)
 * @returns {'graph'|'keyword'}
 */
function getABTestGroup(sessionId) {
  return (sessionId % 2 === 1) ? 'graph' : 'keyword';
}

// ═══════════════════════════════════════════════════════════════════════════
// MULTI-FEATURE GRAPH SIGNAL (US-004: Signal Composition)
// ═══════════════════════════════════════════════════════════════════════════

const GRAPH_SIGNAL_WEIGHTS_PATH = path.join(__dirname, '..', 'config', 'graph-signal-weights.json');

/**
 * Load graph signal weights from config file (the ONLY authority).
 * Designed as a future Optimas Local Reward Function (learnable).
 *
 * @returns {{entropy: number, gini: number, subgraphDensity: number, irtDifficulty: number}}
 */
function loadGraphSignalWeights() {
  try {
    if (fs.existsSync(GRAPH_SIGNAL_WEIGHTS_PATH)) {
      const config = JSON.parse(fs.readFileSync(GRAPH_SIGNAL_WEIGHTS_PATH, 'utf8'));
      if (config.weights) return config.weights;
    }
  } catch (e) {
    // Fall through to defaults
  }
  // Emergency fallback only — should never be used in production
  return { entropy: 0.30, gini: 0.25, subgraphDensity: 0.25, irtDifficulty: 0.20 };
}

/**
 * Compose entropy, Gini, subgraph density, and IRT difficulty into a single
 * graphComplexity score (0.0-1.0). Replaces keyword-based complexity for routing.
 *
 * Higher graphComplexity means the query is harder (sparse knowledge, concentrated
 * retrieval scores, high IRT difficulty) and should route to more capable models.
 *
 * Feature normalization:
 * - entropy: inverted (high entropy = well-distributed knowledge = EASIER)
 *   normalized to [0,1] via 1 - entropy/maxEntropy
 * - gini: inverted (high Gini = diverse distribution = EASIER)
 *   normalized to [0,1] via 1 - gini
 * - subgraphDensity: inverted (dense subgraph = well-connected knowledge = EASIER)
 *   normalized to [0,1] via 1 - density
 * - irtDifficulty: direct (high difficulty = HARDER), already [0,1]
 *
 * @param {Object} params
 * @param {Object|null} params.distributional - Output of computeDistributionalFeatures()
 * @param {Object|null} params.subgraph - Output of computeSubgraphDensity()
 * @param {number|null} params.irtDifficulty - IRT difficulty from HSRGS bridge (0.0-1.0)
 * @returns {{graphComplexity: number, features: Object, weights: Object, featureCount: number} | null}
 *          Returns null if no features are available
 */
function computeGraphSignal({ distributional, subgraph, irtDifficulty }) {
  const weights = loadGraphSignalWeights();
  const features = {};
  let totalWeight = 0;
  let weightedSum = 0;

  // Entropy: invert so high entropy (easy) → low complexity
  if (distributional && typeof distributional.entropy === 'number') {
    // Max entropy for n items = ln(n). Use sampleSize for normalization.
    const maxEntropy = Math.log(distributional.sampleSize);
    const normalizedEntropy = maxEntropy > 0 ? distributional.entropy / maxEntropy : 0;
    const complexityFromEntropy = 1 - normalizedEntropy; // invert: low entropy = high complexity
    features.entropy = parseFloat(complexityFromEntropy.toFixed(6));
    weightedSum += features.entropy * weights.entropy;
    totalWeight += weights.entropy;
  }

  // Gini: invert so high Gini (diverse) → low complexity
  if (distributional && typeof distributional.gini === 'number') {
    const complexityFromGini = 1 - distributional.gini; // invert: low diversity = high complexity
    features.gini = parseFloat(complexityFromGini.toFixed(6));
    weightedSum += features.gini * weights.gini;
    totalWeight += weights.gini;
  }

  // Subgraph density: invert so dense graph → low complexity
  if (subgraph && typeof subgraph.density === 'number') {
    const complexityFromDensity = 1 - subgraph.density; // invert: sparse = high complexity
    features.subgraphDensity = parseFloat(complexityFromDensity.toFixed(6));
    weightedSum += features.subgraphDensity * weights.subgraphDensity;
    totalWeight += weights.subgraphDensity;
  }

  // IRT difficulty: direct mapping (already 0-1, high = hard)
  if (typeof irtDifficulty === 'number' && !isNaN(irtDifficulty)) {
    const clampedIRT = Math.max(0, Math.min(1, irtDifficulty));
    features.irtDifficulty = parseFloat(clampedIRT.toFixed(6));
    weightedSum += features.irtDifficulty * weights.irtDifficulty;
    totalWeight += weights.irtDifficulty;
  }

  const featureCount = Object.keys(features).length;
  if (featureCount === 0) return null;

  // Normalize by actual weight used (handles partial feature availability)
  const graphComplexity = totalWeight > 0 ? weightedSum / totalWeight : 0;

  return {
    graphComplexity: parseFloat(Math.max(0, Math.min(1, graphComplexity)).toFixed(6)),
    features,
    weights,
    featureCount
  };
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

  // Apply cognitive modifier to complexity for threshold comparisons
  const adjustedComplexity = applyCognitiveModifier(complexity.score);

  // Apply IRT difficulty modifier (US-003: cross-runtime bridge from HSRGS)
  const queryHash = crypto.createHash('md5').update(query).digest('hex');
  const irtBridge = loadIRTBridge(queryHash);
  const irtDifficulty = irtBridge ? irtBridge.difficulty : null;
  const IRT_MOD = computeIRTModifier(irtDifficulty);
  const irtAdjustedComplexity = Math.max(0, Math.min(1, adjustedComplexity + IRT_MOD));

  // US-004: Compute multi-feature graph signal
  // Attempt to gather distributional features and subgraph density
  // These may be null if no retrieval scores / nodes are available for this query
  const graphSignal = computeGraphSignal({
    distributional: null, // Populated by caller or retrieval pipeline when available
    subgraph: null,       // Populated by caller or retrieval pipeline when available
    irtDifficulty: irtDifficulty
  });

  // US-012: A/B test — determine which complexity signal to use for routing
  // Odd session IDs use graph signal, even use keyword (deterministic, reproducible)
  const sessionId = Math.floor(Date.now() / 1000);
  const abState = loadABTestState();
  const abGroup = getABTestGroup(sessionId);
  const graphAvailable = graphSignal && graphSignal.featureCount >= 2;
  // Use graph signal only if: A/B test active, not rolled back, graph available, and in graph group
  const useGraphSignal = abState.active && !abState.rollback && graphAvailable && abGroup === 'graph';
  const routingComplexity = useGraphSignal ? graphSignal.graphComplexity : irtAdjustedComplexity;

  // Compute DQ candidates for BOTH signals (for A/B comparison logging)
  const keywordCandidates = ['haiku', 'sonnet', 'opus'].map(model => {
    const dq = calculateDQ(query, irtAdjustedComplexity, model, history);
    return { model, dq };
  });
  const graphCandidates = graphAvailable ? ['haiku', 'sonnet', 'opus'].map(model => {
    const dq = calculateDQ(query, graphSignal.graphComplexity, model, history);
    return { model, dq };
  }) : null;

  // Try each model and pick best DQ using the active signal
  const candidates = ['haiku', 'sonnet', 'opus'].map(model => {
    const dq = calculateDQ(query, routingComplexity, model, history);
    return { model, dq, complexity: complexity.score, adjustedComplexity: routingComplexity };
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

  let best = candidates[0];

  // Apply expertise-based adjustment
  const expertiseAdj = getExpertiseAdjustment(query);
  let expertiseOverride = null;

  if (expertiseAdj) {
    const models = ['haiku', 'sonnet', 'opus'];
    const currentIdx = models.indexOf(best.model);

    if (expertiseAdj.adjustment === 'downgrade' && currentIdx > 0) {
      // High expertise - can use cheaper model
      const newModel = models[currentIdx - 1];
      expertiseOverride = {
        original: best.model,
        adjusted: newModel,
        domain: expertiseAdj.domain,
        reason: `High expertise in ${expertiseAdj.domain}`
      };
      // Find the candidate for the new model
      const newCandidate = candidates.find(c => c.model === newModel);
      if (newCandidate) {
        best = newCandidate;
      }
    } else if (expertiseAdj.adjustment === 'upgrade' && currentIdx < models.length - 1) {
      // Low expertise - need more capable model
      const newModel = models[currentIdx + 1];
      expertiseOverride = {
        original: best.model,
        adjusted: newModel,
        domain: expertiseAdj.domain,
        reason: `Low expertise in ${expertiseAdj.domain}`
      };
      const newCandidate = candidates.find(c => c.model === newModel);
      if (newCandidate) {
        best = newCandidate;
      }
    }
  }

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
    ts: Math.floor(Date.now() / 1000),  // Unix seconds (not ms)
    query_hash: crypto.createHash('md5').update(query).digest('hex'),
    query: query.slice(0, 200), // Truncate for storage
    query_preview: query.slice(0, 50),
    complexity: complexity.score,
    adjusted_complexity: irtAdjustedComplexity,
    complexity_reasoning: complexity.reasoning,
    irt: irtBridge ? {
      difficulty: irtDifficulty,
      modifier: IRT_MOD,
      source: 'hsrgs-bridge'
    } : null,
    graphSignal: graphSignal || null,
    ab_test: {
      keyword_complexity: irtAdjustedComplexity,
      graph_complexity: graphSignal ? graphSignal.graphComplexity : null,
      signal_used: useGraphSignal ? 'graph' : 'keyword',
      session_id: sessionId
    },
    model: best.model,
    dqScore: best.dq.score,
    dqComponents: best.dq.components,
    reasoning: complexity.reasoning,
    alternatives: candidates.slice(1).map(c => ({ model: c.model, dq: c.dq.score })),
    cost_estimate: estimateCost(best.model, query),
    baseline_version: BASELINES ? BASELINES.version : 'hardcoded',
    cognitive: COGNITIVE_WEIGHTS ? {
      mode: COGNITIVE_WEIGHTS.cognitiveMode,
      modifier: COMPLEXITY_MODIFIER,
      weights_applied: true
    } : null,
    expertise: expertiseOverride
  };

  saveDecision(decision);

  // US-012: Log to dedicated A/B test JSONL with both signals for comparison
  const bestKeyword = [...keywordCandidates].sort((a, b) => {
    if (Math.abs(a.dq.score - b.dq.score) > 0.05) return b.dq.score - a.dq.score;
    const co = { haiku: 0, sonnet: 1, opus: 2 };
    return co[a.model] - co[b.model];
  })[0];
  const bestGraph = graphCandidates ? [...graphCandidates].sort((a, b) => {
    if (Math.abs(a.dq.score - b.dq.score) > 0.05) return b.dq.score - a.dq.score;
    const co = { haiku: 0, sonnet: 1, opus: 2 };
    return co[a.model] - co[b.model];
  })[0] : null;

  logABTestDecision({
    ts: decision.ts,
    session_id: sessionId,
    query_hash: decision.query_hash,
    ab_group: abGroup,
    signal_used: useGraphSignal ? 'graph' : 'keyword',
    keyword_complexity: irtAdjustedComplexity,
    graph_complexity: graphSignal ? graphSignal.graphComplexity : null,
    keyword_model: bestKeyword.model,
    keyword_dq: bestKeyword.dq.score,
    keyword_dq_components: bestKeyword.dq.components,
    graph_model: bestGraph ? bestGraph.model : null,
    graph_dq: bestGraph ? bestGraph.dq.score : null,
    graph_dq_components: bestGraph ? bestGraph.dq.components : null,
    actual_model: best.model,
    actual_dq: best.dq.score,
    cost_estimate: decision.cost_estimate,
    graph_feature_count: graphSignal ? graphSignal.featureCount : 0,
    rollback_active: abState.rollback
  });

  return {
    model: best.model,
    complexity: complexity.score,
    dq: best.dq,
    reasoning: complexity.reasoning,
    cost_estimate: decision.cost_estimate,
    baseline_version: decision.baseline_version,
    cognitive: decision.cognitive,
    expertise: decision.expertise
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

module.exports = { route, calculateDQ, recordFeedback, getStats, computeDistributionalFeatures, computeSubgraphDensity, computeSubgraphDensityFromLinks, loadIRTBridge, computeIRTModifier, computeGraphSignal, loadGraphSignalWeights, loadABTestState, saveABTestState, logABTestDecision, getABTestGroup };
