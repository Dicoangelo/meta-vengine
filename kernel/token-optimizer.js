#!/usr/bin/env node
/**
 * Token Optimizer - Mem0-inspired Memory Consolidation
 *
 * Based on: "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory"
 * arXiv: https://arxiv.org/abs/2504.19413
 *
 * Implements:
 * - 90% token savings via selective memory injection
 * - Relevance + recency + frequency scoring
 * - Budget-constrained memory selection
 * - Memory consolidation and summarization
 */

const fs = require('fs');
const path = require('path');

// Import memory linker functions
const memoryLinker = require('./memory-linker');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const KERNEL_DIR = path.join(process.env.HOME, '.claude', 'kernel');
const GRAPH_FILE = path.join(KERNEL_DIR, 'memory-graph.json');
const OPTIMIZATION_LOG = path.join(KERNEL_DIR, 'token-optimization.jsonl');

// Mem0 scoring weights
const SCORING_WEIGHTS = {
  relevance: 0.50,    // Semantic similarity to query
  recency: 0.25,      // How recently the memory was accessed/created
  frequency: 0.15,    // How often the memory has been accessed
  connectivity: 0.10  // How well-connected in the graph
};

// Default token budget (conservative estimate)
const DEFAULT_TOKEN_BUDGET = 4000;

// Approximate tokens per character (rough estimate)
const CHARS_PER_TOKEN = 4;

// ═══════════════════════════════════════════════════════════════════════════
// TOKEN ESTIMATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Estimate token count for text
 * Uses character-based approximation (more accurate than word count)
 */
function estimateTokens(text) {
  if (!text) return 0;
  // Claude tokenization: ~4 chars per token on average
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

/**
 * Estimate tokens for a memory note
 */
function estimateNoteTokens(note) {
  let tokens = 0;
  tokens += estimateTokens(note.content);
  tokens += estimateTokens(note.context);
  tokens += note.keywords.length * 2; // Keywords are short
  tokens += 20; // Metadata overhead
  return tokens;
}

// ═══════════════════════════════════════════════════════════════════════════
// SCORING FUNCTIONS (Mem0 Algorithm)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Calculate recency score based on last evolved/accessed time
 * Uses exponential decay (Mem0 pattern)
 */
function calculateRecencyScore(note) {
  const now = Date.now();
  const evolved = new Date(note.evolved || note.created).getTime();
  const ageHours = (now - evolved) / (1000 * 60 * 60);

  // Exponential decay with 24-hour half-life
  // Score 1.0 for just created, 0.5 after 24 hours, 0.25 after 48 hours, etc.
  const halfLife = 24;
  return Math.exp(-0.693 * ageHours / halfLife);
}

/**
 * Calculate frequency score based on access count
 * Uses logarithmic scaling to prevent dominance
 */
function calculateFrequencyScore(note) {
  const accessCount = note.accessCount || 0;
  // Log scale: 0 accesses = 0, 1 access = 0.3, 10 accesses = 0.7, 100 accesses = 1.0
  return Math.min(1.0, Math.log10(accessCount + 1) / 2);
}

/**
 * Calculate connectivity score based on graph links
 */
function calculateConnectivityScore(note, totalNotes) {
  const linkCount = (note.links || []).length;
  if (totalNotes <= 1) return 0;
  // Normalize by maximum possible connections
  const maxLinks = Math.min(10, totalNotes - 1);
  return Math.min(1.0, linkCount / maxLinks);
}

/**
 * Calculate composite Mem0 score for a memory
 */
function calculateMem0Score(note, relevance, totalNotes) {
  const recency = calculateRecencyScore(note);
  const frequency = calculateFrequencyScore(note);
  const connectivity = calculateConnectivityScore(note, totalNotes);

  const score = (
    (relevance * SCORING_WEIGHTS.relevance) +
    (recency * SCORING_WEIGHTS.recency) +
    (frequency * SCORING_WEIGHTS.frequency) +
    (connectivity * SCORING_WEIGHTS.connectivity)
  );

  return {
    total: score,
    breakdown: {
      relevance: (relevance * SCORING_WEIGHTS.relevance).toFixed(3),
      recency: (recency * SCORING_WEIGHTS.recency).toFixed(3),
      frequency: (frequency * SCORING_WEIGHTS.frequency).toFixed(3),
      connectivity: (connectivity * SCORING_WEIGHTS.connectivity).toFixed(3)
    }
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// MEMORY CONSOLIDATION (Mem0 Core Innovation)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load memory graph
 */
function loadGraph() {
  if (fs.existsSync(GRAPH_FILE)) {
    return JSON.parse(fs.readFileSync(GRAPH_FILE, 'utf8'));
  }
  return { notes: {}, links: [], config: {} };
}

/**
 * Consolidate memories for a given query within token budget
 * This is the main Mem0 algorithm
 */
function consolidateForContext(query, tokenBudget = DEFAULT_TOKEN_BUDGET) {
  const graph = loadGraph();
  const totalNotes = Object.keys(graph.notes).length;

  if (totalNotes === 0) {
    return {
      memories: [],
      tokensUsed: 0,
      tokenBudget,
      tokensSaved: 0,
      savingsPercent: 0
    };
  }

  // Step 1: Recall all potentially relevant memories
  const queryKeywords = memoryLinker.extractKeywords(query);
  const candidates = [];

  for (const [id, note] of Object.entries(graph.notes)) {
    // Calculate relevance using Jaccard similarity
    const noteKeywords = note.keywords || [];
    const intersection = queryKeywords.filter(k => noteKeywords.includes(k)).length;
    const union = new Set([...queryKeywords, ...noteKeywords]).size;
    const relevance = union > 0 ? intersection / union : 0;

    // Also check content match
    const contentMatch = note.content.toLowerCase().includes(query.toLowerCase()) ? 0.3 : 0;
    const totalRelevance = Math.min(1.0, relevance + contentMatch);

    // Only include if minimally relevant
    if (totalRelevance > 0.05) {
      const mem0Score = calculateMem0Score(note, totalRelevance, totalNotes);
      candidates.push({
        note,
        relevance: totalRelevance,
        mem0Score,
        tokens: estimateNoteTokens(note)
      });
    }
  }

  // Step 2: Sort by Mem0 score
  candidates.sort((a, b) => b.mem0Score.total - a.mem0Score.total);

  // Step 3: Select within budget (greedy algorithm)
  let tokensUsed = 0;
  const selected = [];
  const excluded = [];

  for (const candidate of candidates) {
    if (tokensUsed + candidate.tokens <= tokenBudget) {
      selected.push(candidate);
      tokensUsed += candidate.tokens;
    } else {
      excluded.push(candidate);
    }
  }

  // Step 4: Calculate savings
  const totalPossibleTokens = candidates.reduce((sum, c) => sum + c.tokens, 0);
  const tokensSaved = totalPossibleTokens - tokensUsed;
  const savingsPercent = totalPossibleTokens > 0
    ? ((tokensSaved / totalPossibleTokens) * 100).toFixed(1)
    : 0;

  // Step 5: Log optimization decision
  logOptimization({
    query,
    tokenBudget,
    tokensUsed,
    tokensSaved,
    savingsPercent,
    selectedCount: selected.length,
    excludedCount: excluded.length,
    timestamp: new Date().toISOString()
  });

  return {
    memories: selected.map(s => ({
      id: s.note.id,
      type: s.note.type,
      content: s.note.content,
      relevance: s.relevance.toFixed(3),
      mem0Score: s.mem0Score.total.toFixed(3),
      scoreBreakdown: s.mem0Score.breakdown,
      tokens: s.tokens
    })),
    excluded: excluded.slice(0, 5).map(e => ({
      id: e.note.id,
      preview: e.note.content.slice(0, 40) + '...',
      reason: 'budget_exceeded'
    })),
    tokensUsed,
    tokenBudget,
    tokensSaved,
    savingsPercent: parseFloat(savingsPercent),
    totalCandidates: candidates.length
  };
}

/**
 * Log optimization decision for learning
 */
function logOptimization(decision) {
  const logLine = JSON.stringify(decision) + '\n';
  fs.appendFileSync(OPTIMIZATION_LOG, logLine);
}

// ═══════════════════════════════════════════════════════════════════════════
// MEMORY SUMMARIZATION (Advanced Consolidation)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Summarize multiple related memories into a single consolidated memory
 * Used when even selected memories exceed budget
 */
function summarizeMemories(memories, maxTokens = 500) {
  if (memories.length === 0) return null;
  if (memories.length === 1) return memories[0];

  // Group by type
  const byType = {};
  for (const mem of memories) {
    const type = mem.type || 'fact';
    if (!byType[type]) byType[type] = [];
    byType[type].push(mem);
  }

  // Build consolidated summary
  const summaryParts = [];

  for (const [type, mems] of Object.entries(byType)) {
    if (mems.length === 1) {
      summaryParts.push(`[${type}] ${mems[0].content}`);
    } else {
      // Extract key points from multiple memories
      const keyPoints = mems.map(m => {
        // Get first sentence or first 100 chars
        const firstSentence = m.content.split(/[.!?]/)[0];
        return firstSentence.length < 100 ? firstSentence : m.content.slice(0, 100);
      });
      summaryParts.push(`[${type}s: ${mems.length}] ${keyPoints.join('; ')}`);
    }
  }

  const summary = summaryParts.join('\n\n');
  const tokens = estimateTokens(summary);

  // If still over budget, truncate
  if (tokens > maxTokens) {
    const charLimit = maxTokens * CHARS_PER_TOKEN;
    return {
      consolidated: true,
      content: summary.slice(0, charLimit) + '...',
      originalCount: memories.length,
      tokens: maxTokens
    };
  }

  return {
    consolidated: true,
    content: summary,
    originalCount: memories.length,
    tokens
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CONTEXT INJECTION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Format memories for context injection
 * Returns a string ready to be injected into prompts
 */
function formatForInjection(consolidatedResult) {
  if (consolidatedResult.memories.length === 0) {
    return null;
  }

  const lines = ['<relevant_memories>'];

  for (const mem of consolidatedResult.memories) {
    lines.push(`[${mem.type}] ${mem.content}`);
  }

  lines.push('</relevant_memories>');
  lines.push(`<!-- Mem0: ${consolidatedResult.tokensUsed} tokens used, ${consolidatedResult.savingsPercent}% saved -->`);

  return lines.join('\n');
}

/**
 * Get optimization statistics
 */
function getOptimizationStats() {
  if (!fs.existsSync(OPTIMIZATION_LOG)) {
    return { totalOptimizations: 0, avgSavings: 0, totalTokensSaved: 0 };
  }

  const lines = fs.readFileSync(OPTIMIZATION_LOG, 'utf8').trim().split('\n');
  if (lines.length === 0 || (lines.length === 1 && lines[0] === '')) {
    return { totalOptimizations: 0, avgSavings: 0, totalTokensSaved: 0 };
  }

  let totalSavings = 0;
  let totalTokensSaved = 0;
  let count = 0;

  for (const line of lines) {
    try {
      const entry = JSON.parse(line);
      totalSavings += parseFloat(entry.savingsPercent) || 0;
      totalTokensSaved += entry.tokensSaved || 0;
      count++;
    } catch (e) {
      // Skip malformed lines
    }
  }

  return {
    totalOptimizations: count,
    avgSavings: count > 0 ? (totalSavings / count).toFixed(1) : 0,
    totalTokensSaved,
    estimatedCostSaved: (totalTokensSaved / 1000 * 0.003).toFixed(4) // Rough estimate
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'consolidate':
      // Consolidate memories: node token-optimizer.js consolidate "query" [budget]
      const query = args[1];
      const budget = parseInt(args[2]) || DEFAULT_TOKEN_BUDGET;
      if (!query) {
        console.error('Usage: token-optimizer.js consolidate "query" [token_budget]');
        process.exit(1);
      }
      const result = consolidateForContext(query, budget);
      console.log(JSON.stringify(result, null, 2));
      break;

    case 'inject':
      // Get injection-ready format: node token-optimizer.js inject "query" [budget]
      const injectQuery = args[1];
      const injectBudget = parseInt(args[2]) || DEFAULT_TOKEN_BUDGET;
      if (!injectQuery) {
        console.error('Usage: token-optimizer.js inject "query" [token_budget]');
        process.exit(1);
      }
      const consolidated = consolidateForContext(injectQuery, injectBudget);
      const formatted = formatForInjection(consolidated);
      if (formatted) {
        console.log(formatted);
      } else {
        console.log('<!-- No relevant memories found -->');
      }
      break;

    case 'score':
      // Score a single memory: node token-optimizer.js score "query" noteId
      const scoreQuery = args[1];
      const noteId = args[2];
      if (!scoreQuery || !noteId) {
        console.error('Usage: token-optimizer.js score "query" noteId');
        process.exit(1);
      }
      const graph = loadGraph();
      const note = graph.notes[noteId];
      if (!note) {
        console.error(`Note ${noteId} not found`);
        process.exit(1);
      }
      const queryKw = memoryLinker.extractKeywords(scoreQuery);
      const noteKw = note.keywords || [];
      const intersection = queryKw.filter(k => noteKw.includes(k)).length;
      const union = new Set([...queryKw, ...noteKw]).size;
      const relevance = union > 0 ? intersection / union : 0;
      const totalNotes = Object.keys(graph.notes).length;
      const mem0Score = calculateMem0Score(note, relevance, totalNotes);
      console.log(JSON.stringify({
        noteId,
        content: note.content.slice(0, 100) + '...',
        relevance: relevance.toFixed(3),
        mem0Score: mem0Score.total.toFixed(3),
        breakdown: mem0Score.breakdown
      }, null, 2));
      break;

    case 'stats':
      // Get optimization stats: node token-optimizer.js stats
      console.log(JSON.stringify(getOptimizationStats(), null, 2));
      break;

    case 'estimate':
      // Estimate tokens for text: node token-optimizer.js estimate "text"
      const text = args[1];
      if (!text) {
        console.error('Usage: token-optimizer.js estimate "text"');
        process.exit(1);
      }
      console.log(JSON.stringify({
        text: text.slice(0, 50) + '...',
        characters: text.length,
        estimatedTokens: estimateTokens(text)
      }, null, 2));
      break;

    default:
      console.log('Token Optimizer - Mem0-inspired Memory Consolidation');
      console.log('');
      console.log('Commands:');
      console.log('  consolidate "query" [budget]  - Get optimized memories for context');
      console.log('  inject "query" [budget]       - Get injection-ready formatted output');
      console.log('  score "query" noteId          - Score a specific memory');
      console.log('  stats                         - View optimization statistics');
      console.log('  estimate "text"               - Estimate token count for text');
      console.log('');
      console.log(`Default token budget: ${DEFAULT_TOKEN_BUDGET}`);
      console.log('');
      console.log('Scoring weights:');
      console.log(`  Relevance:    ${SCORING_WEIGHTS.relevance * 100}%`);
      console.log(`  Recency:      ${SCORING_WEIGHTS.recency * 100}%`);
      console.log(`  Frequency:    ${SCORING_WEIGHTS.frequency * 100}%`);
      console.log(`  Connectivity: ${SCORING_WEIGHTS.connectivity * 100}%`);
  }
}

module.exports = {
  consolidateForContext,
  formatForInjection,
  summarizeMemories,
  estimateTokens,
  calculateMem0Score,
  getOptimizationStats,
  SCORING_WEIGHTS,
  DEFAULT_TOKEN_BUDGET
};
