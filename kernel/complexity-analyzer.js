#!/usr/bin/env node
/**
 * Complexity Analyzer - Astraea-inspired query complexity estimation
 *
 * Based on: "Astraea: A State-Aware Scheduling Engine for LLM-Powered Agents"
 * arXiv: https://arxiv.org/abs/2512.14142
 *
 * Estimates query complexity to inform model routing decisions.
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// COMPLEXITY SIGNALS
// ═══════════════════════════════════════════════════════════════════════════

const SIGNALS = {
  // Semantic keywords that indicate complexity
  code: ['function', 'class', 'async', 'import', 'export', 'const', 'let', 'var',
         'interface', 'type', 'enum', 'module', 'require', 'def ', 'return'],

  architecture: ['design', 'architecture', 'system', 'refactor', 'restructure',
                 'pattern', 'microservice', 'distributed', 'scalable', 'optimize'],

  debug: ['error', 'fix', 'bug', 'debug', 'why', 'not working', 'broken',
          'crash', 'exception', 'failed', 'issue', 'problem'],

  multiFile: ['across', 'all files', 'every', 'multiple', 'entire codebase',
              'project-wide', 'refactor all', 'update all'],

  analysis: ['analyze', 'review', 'audit', 'compare', 'evaluate', 'assess',
             'investigate', 'research', 'study', 'understand'],

  creation: ['create', 'build', 'implement', 'develop', 'write', 'generate',
             'make', 'add', 'new feature', 'from scratch'],

  simple: ['what is', 'how to', 'explain', 'show me', 'list', 'print',
           'hello', 'thanks', 'yes', 'no', 'ok']
};

// Complexity weights for each signal category
const WEIGHTS = {
  code: 0.15,
  architecture: 0.25,
  debug: 0.10,
  multiFile: 0.20,
  analysis: 0.15,
  creation: 0.10,
  simple: -0.15  // Negative weight reduces complexity
};

// Token-based complexity thresholds (from Astraea paper)
const TOKEN_THRESHOLDS = {
  simple: { max: 20, score: 0.10 },
  moderate: { max: 100, score: 0.30 },
  complex: { max: 500, score: 0.60 },
  expert: { max: Infinity, score: 0.90 }
};

// ═══════════════════════════════════════════════════════════════════════════
// ANALYSIS FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Simple tokenizer - splits on whitespace and punctuation
 */
function tokenize(text) {
  return text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length > 0);
}

/**
 * Estimate tokens (rough approximation: ~4 chars per token)
 */
function estimateTokens(text) {
  return Math.ceil(text.length / 4);
}

/**
 * Check if query contains keywords from a signal category
 */
function hasSignals(query, category) {
  const lowerQuery = query.toLowerCase();
  return SIGNALS[category].some(keyword => lowerQuery.includes(keyword));
}

/**
 * Count matching signals for a category
 */
function countSignals(query, category) {
  const lowerQuery = query.toLowerCase();
  return SIGNALS[category].filter(keyword => lowerQuery.includes(keyword)).length;
}

/**
 * Detect if query requires project context
 */
function requiresProjectContext(query) {
  const patterns = [
    /\b(this|our|my|the)\s+\w+\s+(file|code|project|app|component)/i,
    /\bin\s+(this|the)\s+(codebase|repo|project)/i,
    /\bcurrent\s+(file|directory|project)/i
  ];
  return patterns.some(p => p.test(query));
}

/**
 * Detect if query is conversational/simple
 */
function isConversational(query) {
  const patterns = [
    /^(hi|hello|hey|thanks|thank you|ok|okay|yes|no|sure)/i,
    /^what (is|are) \w+\??$/i,
    /^(how|can|could) (do|can) (i|you)/i
  ];
  return patterns.some(p => p.test(query)) && query.length < 50;
}

/**
 * Load historical complexity data for similar queries
 */
function loadHistory() {
  const historyPath = path.join(process.env.HOME, '.claude/kernel/dq-scores.jsonl');
  if (!fs.existsSync(historyPath)) return [];

  try {
    const lines = fs.readFileSync(historyPath, 'utf8').split('\n').filter(l => l.trim());
    return lines.slice(-100).map(l => JSON.parse(l)); // Last 100 entries
  } catch (e) {
    return [];
  }
}

/**
 * Find similar historical queries and their complexity
 */
function getHistoricalComplexity(query, history) {
  if (history.length === 0) return null;

  const tokens = new Set(tokenize(query));
  let bestMatch = null;
  let bestScore = 0;

  for (const entry of history) {
    if (!entry.query) continue;
    const historyTokens = new Set(tokenize(entry.query));

    // Jaccard similarity
    const intersection = [...tokens].filter(t => historyTokens.has(t)).length;
    const union = new Set([...tokens, ...historyTokens]).size;
    const similarity = intersection / union;

    if (similarity > bestScore && similarity > 0.3) {
      bestScore = similarity;
      bestMatch = entry;
    }
  }

  return bestMatch ? { complexity: bestMatch.complexity, confidence: bestScore } : null;
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN COMPLEXITY ESTIMATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Estimate complexity of a query
 * Returns: { score: 0-1, signals: object, model: string, reasoning: string }
 */
function estimateComplexity(query) {
  const tokens = estimateTokens(query);
  const history = loadHistory();

  // Start with token-based score
  let score = 0;
  const reasoning = [];

  // Token length scoring
  if (tokens <= TOKEN_THRESHOLDS.simple.max) {
    score += TOKEN_THRESHOLDS.simple.score;
    reasoning.push(`Short query (${tokens} tokens)`);
  } else if (tokens <= TOKEN_THRESHOLDS.moderate.max) {
    score += TOKEN_THRESHOLDS.moderate.score;
    reasoning.push(`Medium query (${tokens} tokens)`);
  } else if (tokens <= TOKEN_THRESHOLDS.complex.max) {
    score += TOKEN_THRESHOLDS.complex.score;
    reasoning.push(`Long query (${tokens} tokens)`);
  } else {
    score += TOKEN_THRESHOLDS.expert.score;
    reasoning.push(`Very long query (${tokens} tokens)`);
  }

  // Signal-based scoring
  const signalScores = {};
  for (const [category, weight] of Object.entries(WEIGHTS)) {
    if (hasSignals(query, category)) {
      const count = countSignals(query, category);
      const categoryScore = weight * Math.min(count, 3); // Cap at 3 matches
      signalScores[category] = { count, score: categoryScore };
      score += categoryScore;

      if (weight > 0) {
        reasoning.push(`${category}: ${count} signal(s)`);
      }
    }
  }

  // Context requirements
  if (requiresProjectContext(query)) {
    score += 0.15;
    reasoning.push('Requires project context');
  }

  // Conversational reduction
  if (isConversational(query)) {
    score -= 0.20;
    reasoning.push('Conversational/simple');
  }

  // Historical adjustment
  const historical = getHistoricalComplexity(query, history);
  if (historical && historical.confidence > 0.5) {
    const adjustment = (historical.complexity - score) * 0.3;
    score += adjustment;
    reasoning.push(`Historical: ${historical.complexity.toFixed(2)} (conf: ${historical.confidence.toFixed(2)})`);
  }

  // Clamp to 0-1
  score = Math.max(0, Math.min(1, score));

  // Determine recommended model
  let model;
  if (score < 0.25) model = 'haiku';
  else if (score < 0.60) model = 'sonnet';
  else model = 'opus';

  return {
    score: parseFloat(score.toFixed(3)),
    tokens,
    signals: signalScores,
    model,
    reasoning: reasoning.join('; ')
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    // Read from stdin
    let input = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => input += chunk);
    process.stdin.on('end', () => {
      const result = estimateComplexity(input.trim());
      console.log(JSON.stringify(result, null, 2));
    });
  } else if (args[0] === '--score-only') {
    // Just output the score
    const query = args.slice(1).join(' ');
    const result = estimateComplexity(query);
    console.log(result.score);
  } else if (args[0] === '--model-only') {
    // Just output the model
    const query = args.slice(1).join(' ');
    const result = estimateComplexity(query);
    console.log(result.model);
  } else {
    // Query as arguments
    const query = args.join(' ');
    const result = estimateComplexity(query);
    console.log(JSON.stringify(result, null, 2));
  }
}

module.exports = { estimateComplexity, tokenize, estimateTokens };
