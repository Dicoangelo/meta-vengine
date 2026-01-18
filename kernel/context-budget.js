#!/usr/bin/env node
/**
 * Context Budget Manager - Dynamic Token Allocation
 *
 * Manages token budgets based on:
 * - Query complexity (from complexity-analyzer.js)
 * - Selected model context limits
 * - Memory importance tiers
 * - Session state
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// MODEL CONTEXT LIMITS
// ═══════════════════════════════════════════════════════════════════════════

const MODEL_LIMITS = {
  haiku: {
    name: 'claude-haiku-4',
    maxContext: 200000,
    recommendedMemoryBudget: 2000,  // Conservative for fast model
    costPer1kTokens: 0.00025
  },
  sonnet: {
    name: 'claude-sonnet-4',
    maxContext: 200000,
    recommendedMemoryBudget: 4000,  // Standard allocation
    costPer1kTokens: 0.003
  },
  opus: {
    name: 'claude-opus-4',
    maxContext: 200000,
    recommendedMemoryBudget: 8000,  // Generous for complex tasks
    costPer1kTokens: 0.015
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// BUDGET ALLOCATION STRATEGIES
// ═══════════════════════════════════════════════════════════════════════════

const ALLOCATION_STRATEGIES = {
  // Conservative: Minimize token usage
  conservative: {
    memoryPercent: 0.10,  // 10% of available context for memories
    systemPercent: 0.05,  // 5% for system prompts
    responseReserve: 0.20 // 20% reserved for response
  },
  // Balanced: Standard allocation
  balanced: {
    memoryPercent: 0.15,
    systemPercent: 0.05,
    responseReserve: 0.25
  },
  // Rich: Maximum context for complex tasks
  rich: {
    memoryPercent: 0.25,
    systemPercent: 0.10,
    responseReserve: 0.30
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// BUDGET CALCULATOR
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Calculate optimal memory budget based on context
 */
function calculateBudget(options = {}) {
  const {
    model = 'sonnet',
    complexity = 0.5,
    queryTokens = 100,
    strategy = 'balanced'
  } = options;

  const modelConfig = MODEL_LIMITS[model] || MODEL_LIMITS.sonnet;
  const strategyConfig = ALLOCATION_STRATEGIES[strategy] || ALLOCATION_STRATEGIES.balanced;

  // Available context after query
  const availableContext = modelConfig.maxContext - queryTokens;

  // Calculate allocations
  const responseReserve = Math.floor(availableContext * strategyConfig.responseReserve);
  const systemReserve = Math.floor(availableContext * strategyConfig.systemPercent);
  const memoryBudget = Math.floor(availableContext * strategyConfig.memoryPercent);

  // Adjust memory budget based on complexity
  // Higher complexity = more memory context useful
  const complexityMultiplier = 0.5 + (complexity * 0.5); // Range: 0.5x - 1.0x
  const adjustedMemoryBudget = Math.floor(memoryBudget * complexityMultiplier);

  // Cap at recommended budget for model
  const finalMemoryBudget = Math.min(adjustedMemoryBudget, modelConfig.recommendedMemoryBudget);

  return {
    model,
    modelMaxContext: modelConfig.maxContext,
    availableContext,
    strategy,
    complexity,
    allocations: {
      query: queryTokens,
      system: systemReserve,
      memory: finalMemoryBudget,
      responseReserve
    },
    recommendations: {
      memoryBudget: finalMemoryBudget,
      suggestedNotes: Math.floor(finalMemoryBudget / 100), // ~100 tokens per note
      maxContentLength: finalMemoryBudget * 4 // chars
    },
    cost: {
      perThousandTokens: modelConfig.costPer1kTokens,
      estimatedMemoryCost: (finalMemoryBudget / 1000 * modelConfig.costPer1kTokens).toFixed(6)
    }
  };
}

/**
 * Get budget based on DQ routing decision
 */
function getBudgetFromComplexity(complexityScore) {
  // Map complexity to strategy
  let strategy;
  if (complexityScore < 0.3) {
    strategy = 'conservative';
  } else if (complexityScore < 0.7) {
    strategy = 'balanced';
  } else {
    strategy = 'rich';
  }

  // Map complexity to model
  let model;
  if (complexityScore < 0.25) {
    model = 'haiku';
  } else if (complexityScore < 0.75) {
    model = 'sonnet';
  } else {
    model = 'opus';
  }

  return calculateBudget({ model, complexity: complexityScore, strategy });
}

// ═══════════════════════════════════════════════════════════════════════════
// MEMORY TIER ALLOCATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Allocate budget across memory tiers
 * Tiered approach ensures most important memories always fit
 */
function allocateTiers(totalBudget) {
  return {
    // Tier 1: Critical (always included)
    critical: {
      budget: Math.floor(totalBudget * 0.40),
      description: 'Highly relevant recent memories',
      minScore: 0.7
    },
    // Tier 2: Important (included if space)
    important: {
      budget: Math.floor(totalBudget * 0.35),
      description: 'Moderately relevant memories',
      minScore: 0.4
    },
    // Tier 3: Contextual (included if space remains)
    contextual: {
      budget: Math.floor(totalBudget * 0.25),
      description: 'Background context memories',
      minScore: 0.1
    }
  };
}

/**
 * Select memories by tier priority
 */
function selectByTiers(scoredMemories, totalBudget) {
  const tiers = allocateTiers(totalBudget);
  const selected = { critical: [], important: [], contextual: [] };
  let usedBudget = 0;

  // Sort memories by score descending
  const sorted = [...scoredMemories].sort((a, b) => b.score - a.score);

  for (const memory of sorted) {
    const tokens = memory.tokens || 100;

    // Determine tier based on score
    let tier;
    if (memory.score >= tiers.critical.minScore) {
      tier = 'critical';
    } else if (memory.score >= tiers.important.minScore) {
      tier = 'important';
    } else if (memory.score >= tiers.contextual.minScore) {
      tier = 'contextual';
    } else {
      continue; // Below all thresholds
    }

    // Check if tier has budget and overall budget allows
    const tierUsed = selected[tier].reduce((sum, m) => sum + (m.tokens || 100), 0);
    if (tierUsed + tokens <= tiers[tier].budget && usedBudget + tokens <= totalBudget) {
      selected[tier].push(memory);
      usedBudget += tokens;
    }
  }

  return {
    tiers: selected,
    summary: {
      critical: selected.critical.length,
      important: selected.important.length,
      contextual: selected.contextual.length,
      total: selected.critical.length + selected.important.length + selected.contextual.length,
      usedBudget,
      remainingBudget: totalBudget - usedBudget
    }
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// SESSION BUDGET TRACKING
// ═══════════════════════════════════════════════════════════════════════════

const SESSION_FILE = path.join(process.env.HOME, '.claude', 'kernel', 'session-budget.json');

function loadSessionBudget() {
  if (fs.existsSync(SESSION_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
    } catch (e) {
      return createNewSession();
    }
  }
  return createNewSession();
}

function createNewSession() {
  return {
    sessionId: Date.now().toString(36),
    started: new Date().toISOString(),
    totalTokensUsed: 0,
    memoryTokensUsed: 0,
    queryCount: 0,
    avgSavings: 0,
    history: []
  };
}

function saveSessionBudget(session) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));
}

function trackUsage(memoryTokens, totalTokens, savings) {
  const session = loadSessionBudget();

  session.totalTokensUsed += totalTokens;
  session.memoryTokensUsed += memoryTokens;
  session.queryCount++;

  // Running average of savings
  session.avgSavings = (
    (session.avgSavings * (session.queryCount - 1) + savings) / session.queryCount
  );

  session.history.push({
    timestamp: new Date().toISOString(),
    memoryTokens,
    totalTokens,
    savings
  });

  // Keep only last 100 entries
  if (session.history.length > 100) {
    session.history = session.history.slice(-100);
  }

  saveSessionBudget(session);
  return session;
}

function getSessionStats() {
  return loadSessionBudget();
}

function resetSession() {
  const newSession = createNewSession();
  saveSessionBudget(newSession);
  return newSession;
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'calculate':
      // Calculate budget: node context-budget.js calculate [model] [complexity] [strategy]
      const model = args[1] || 'sonnet';
      const complexity = parseFloat(args[2]) || 0.5;
      const strategy = args[3] || 'balanced';
      const budget = calculateBudget({ model, complexity, strategy });
      console.log(JSON.stringify(budget, null, 2));
      break;

    case 'auto':
      // Auto budget from complexity: node context-budget.js auto [complexity]
      const comp = parseFloat(args[1]) || 0.5;
      const autoBudget = getBudgetFromComplexity(comp);
      console.log(JSON.stringify(autoBudget, null, 2));
      break;

    case 'tiers':
      // Show tier allocation: node context-budget.js tiers [totalBudget]
      const totalBudget = parseInt(args[1]) || 4000;
      const tiers = allocateTiers(totalBudget);
      console.log(JSON.stringify(tiers, null, 2));
      break;

    case 'session':
      // Get session stats: node context-budget.js session
      console.log(JSON.stringify(getSessionStats(), null, 2));
      break;

    case 'reset':
      // Reset session: node context-budget.js reset
      const newSession = resetSession();
      console.log('Session reset:', newSession.sessionId);
      break;

    case 'models':
      // List model limits: node context-budget.js models
      console.log(JSON.stringify(MODEL_LIMITS, null, 2));
      break;

    default:
      console.log('Context Budget Manager - Dynamic Token Allocation');
      console.log('');
      console.log('Commands:');
      console.log('  calculate [model] [complexity] [strategy]  - Calculate budget');
      console.log('  auto [complexity]                          - Auto budget from complexity');
      console.log('  tiers [totalBudget]                        - Show tier allocation');
      console.log('  session                                    - Get session statistics');
      console.log('  reset                                      - Reset session tracking');
      console.log('  models                                     - List model limits');
      console.log('');
      console.log('Models: haiku, sonnet, opus');
      console.log('Strategies: conservative, balanced, rich');
      console.log('');
      console.log('Examples:');
      console.log('  node context-budget.js calculate sonnet 0.7 balanced');
      console.log('  node context-budget.js auto 0.85');
  }
}

module.exports = {
  calculateBudget,
  getBudgetFromComplexity,
  allocateTiers,
  selectByTiers,
  trackUsage,
  getSessionStats,
  resetSession,
  MODEL_LIMITS,
  ALLOCATION_STRATEGIES
};
