/**
 * Subscription Value Tracker
 * Tracks ROI and value metrics for fixed $200/month Claude Max subscription
 *
 * Metrics:
 * - Cost per message/session trends
 * - API equivalent savings
 * - Utilization alerts
 * - Model distribution value analysis
 */

const fs = require('fs');
const path = require('path');

// Import centralized pricing
const { PRICING, SUBSCRIPTION } = require(path.join(process.env.HOME, '.claude/config/pricing.js'));

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const CONFIG_FILE = path.join(__dirname, 'subscription-config.json');
const STATS_CACHE = path.join(__dirname, '..', 'stats-cache.json');
const HISTORY_FILE = path.join(__dirname, '..', 'history.jsonl');
const VALUE_LOG = path.join(__dirname, 'subscription-value.jsonl');

// Build default config from centralized pricing
const DEFAULT_CONFIG = {
  monthlyRate: SUBSCRIPTION.monthly_rate || 200,
  currency: SUBSCRIPTION.currency || 'USD',
  billingCycleStart: 1,  // Day of month billing resets
  apiPricing: {
    haiku: { input: PRICING.haiku.input, output: PRICING.haiku.output },
    sonnet: { input: PRICING.sonnet.input, output: PRICING.sonnet.output },
    opus: { input: PRICING.opus.input, output: PRICING.opus.output }
  },
  alerts: {
    lowUtilizationThreshold: 0.3,  // Alert if using < 30% of typical usage
    highValueThreshold: 100        // Celebrate if API equivalent > $X
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// CORE FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8')) };
    }
  } catch (e) {}
  return DEFAULT_CONFIG;
}

function saveConfig(config) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

function loadStatsCache() {
  try {
    if (fs.existsSync(STATS_CACHE)) {
      return JSON.parse(fs.readFileSync(STATS_CACHE, 'utf8'));
    }
  } catch (e) {}
  return null;
}

function getCurrentMonthStats() {
  const stats = loadStatsCache();
  if (!stats || !stats.dailyActivity) return null;

  const now = new Date();
  const currentMonth = now.getMonth();
  const currentYear = now.getFullYear();

  // Filter to current month
  const monthlyData = stats.dailyActivity.filter(day => {
    const date = new Date(day.date);
    return date.getMonth() === currentMonth && date.getFullYear() === currentYear;
  });

  const totals = monthlyData.reduce((acc, day) => {
    acc.messages += day.messageCount || 0;
    acc.sessions += day.sessionCount || 0;
    acc.toolCalls += day.toolCallCount || 0;
    acc.days++;
    return acc;
  }, { messages: 0, sessions: 0, toolCalls: 0, days: 0 });

  return {
    period: `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}`,
    ...totals,
    daysInMonth: new Date(currentYear, currentMonth + 1, 0).getDate(),
    daysRemaining: new Date(currentYear, currentMonth + 1, 0).getDate() - now.getDate()
  };
}

function getTokenEstimates() {
  const stats = loadStatsCache();
  if (!stats || !stats.modelUsage) return null;

  // Aggregate tokens across all models
  let totals = { inputTokens: 0, outputTokens: 0, cacheReads: 0 };
  let byModel = {};

  for (const [model, data] of Object.entries(stats.modelUsage)) {
    const modelName = model.includes('opus') ? 'opus' : model.includes('sonnet') ? 'sonnet' : 'haiku';

    totals.inputTokens += data.inputTokens || 0;
    totals.outputTokens += data.outputTokens || 0;
    totals.cacheReads += data.cacheReadInputTokens || 0;

    if (!byModel[modelName]) byModel[modelName] = { input: 0, output: 0 };
    byModel[modelName].input += data.inputTokens || 0;
    byModel[modelName].output += data.outputTokens || 0;
  }

  return { ...totals, byModel };
}

function calculateApiEquivalent(tokens, modelDistribution = { haiku: 0.6, sonnet: 0.35, opus: 0.05 }) {
  const config = loadConfig();
  const pricing = config.apiPricing;

  let totalCost = 0;
  const inputTokens = tokens.inputTokens / 1_000_000;
  const outputTokens = tokens.outputTokens / 1_000_000;

  for (const [model, ratio] of Object.entries(modelDistribution)) {
    if (pricing[model]) {
      totalCost += (inputTokens * ratio * pricing[model].input);
      totalCost += (outputTokens * ratio * pricing[model].output);
    }
  }

  return totalCost;
}

function calculateMetrics() {
  const config = loadConfig();
  const monthlyStats = getCurrentMonthStats();
  const stats = loadStatsCache();

  if (!monthlyStats) {
    return { error: 'No stats available' };
  }

  const rate = config.monthlyRate;

  // Basic efficiency metrics
  const costPerMessage = monthlyStats.messages > 0 ? rate / monthlyStats.messages : 0;
  const costPerSession = monthlyStats.sessions > 0 ? rate / monthlyStats.sessions : 0;

  // Projected monthly totals
  const avgDailyMessages = monthlyStats.messages / Math.max(monthlyStats.days, 1);
  const projectedMonthlyMessages = avgDailyMessages * monthlyStats.daysInMonth;
  const projectedCostPerMessage = projectedMonthlyMessages > 0 ? rate / projectedMonthlyMessages : 0;

  // API equivalent (using actual token data by model)
  let apiEquivalent = 0;
  let cacheValue = 0;
  let subscriptionMultiplier = 0;
  let tokenData = getTokenEstimates();

  if (tokenData && tokenData.byModel) {
    const pricing = config.apiPricing;
    for (const [model, tokens] of Object.entries(tokenData.byModel)) {
      if (pricing[model]) {
        apiEquivalent += (tokens.input / 1_000_000) * pricing[model].input;
        apiEquivalent += (tokens.output / 1_000_000) * pricing[model].output;
      }
    }
    // Cache reads would cost full input price on API (huge savings!)
    // Estimate cache value at blended rate (mostly Opus given usage pattern)
    cacheValue = (tokenData.cacheReads / 1_000_000) * 5; // Opus 4.5 input rate (Jan 2026)
    subscriptionMultiplier = (apiEquivalent + cacheValue) > 0 ? (apiEquivalent + cacheValue) / rate : 0;
  }

  // Utilization score (based on typical heavy usage ~3000 msgs/day)
  const typicalDailyUsage = 3000;
  const utilizationScore = avgDailyMessages / typicalDailyUsage;

  return {
    timestamp: new Date().toISOString(),
    period: monthlyStats.period,
    subscription: {
      rate,
      currency: config.currency
    },
    current: {
      messages: monthlyStats.messages,
      sessions: monthlyStats.sessions,
      toolCalls: monthlyStats.toolCalls,
      daysTracked: monthlyStats.days,
      daysRemaining: monthlyStats.daysRemaining
    },
    efficiency: {
      costPerMessage: parseFloat(costPerMessage.toFixed(4)),
      costPerSession: parseFloat(costPerSession.toFixed(2)),
      projectedCostPerMessage: parseFloat(projectedCostPerMessage.toFixed(4))
    },
    projected: {
      monthlyMessages: Math.round(projectedMonthlyMessages),
      dailyAverage: Math.round(avgDailyMessages)
    },
    value: {
      apiEquivalent: parseFloat(apiEquivalent.toFixed(2)),
      cacheValue: parseFloat(cacheValue.toFixed(2)),
      totalValue: parseFloat((apiEquivalent + cacheValue).toFixed(2)),
      subscriptionMultiplier: parseFloat(subscriptionMultiplier.toFixed(0)),
      savingsVsApi: parseFloat((apiEquivalent + cacheValue - rate).toFixed(2))
    },
    tokens: tokenData ? {
      input: tokenData.inputTokens,
      output: tokenData.outputTokens,
      cacheReads: tokenData.cacheReads
    } : null,
    utilization: {
      score: parseFloat(utilizationScore.toFixed(2)),
      status: utilizationScore >= 0.7 ? 'high' : utilizationScore >= 0.3 ? 'moderate' : 'low'
    }
  };
}

function formatReport(metrics) {
  if (metrics.error) return `Error: ${metrics.error}`;

  const m = metrics;
  const lines = [
    '╔═══════════════════════════════════════════════════════════╗',
    '║        SUBSCRIPTION VALUE TRACKER                         ║',
    '╚═══════════════════════════════════════════════════════════╝',
    '',
    `  Plan: Claude Max @ $${m.subscription.rate}/${m.subscription.currency}/month`,
    `  Period: ${m.period} (${m.current.daysRemaining} days remaining)`,
    '',
    '  ─── Current Usage ───',
    `  Messages:     ${m.current.messages.toLocaleString()}`,
    `  Sessions:     ${m.current.sessions}`,
    `  Tool Calls:   ${m.current.toolCalls.toLocaleString()}`,
    '',
    '  ─── Efficiency ───',
    `  Cost/Message: $${m.efficiency.costPerMessage}`,
    `  Cost/Session: $${m.efficiency.costPerSession}`,
    `  Projected:    $${m.efficiency.projectedCostPerMessage}/msg (${m.projected.monthlyMessages.toLocaleString()} msgs)`,
    '',
    '  ─── Value vs API ───',
    `  Token Costs:     $${m.value.apiEquivalent.toLocaleString()}`,
    `  Cache Value:     $${m.value.cacheValue.toLocaleString()} (${m.tokens ? (m.tokens.cacheReads / 1_000_000).toFixed(0) + 'M tokens' : 'N/A'})`,
    `  Total Value:     $${m.value.totalValue.toLocaleString()}`,
    `  Multiplier:      ${m.value.subscriptionMultiplier}x ROI`,
    `  Net Savings:     $${m.value.savingsVsApi.toLocaleString()}`,
    '',
    `  ─── Utilization: ${m.utilization.status.toUpperCase()} (${(m.utilization.score * 100).toFixed(0)}%) ───`,
  ];

  // Add alerts
  if (m.utilization.score < 0.3) {
    lines.push('  ⚠️  Low utilization - consider using Claude more to maximize value');
  }
  if (m.value.subscriptionMultiplier > 50) {
    lines.push(`  🎉 Excellent ROI! Getting ${m.value.subscriptionMultiplier}x value from subscription`);
  }

  return lines.join('\n');
}

function logValue() {
  const metrics = calculateMetrics();
  if (!metrics.error) {
    const entry = JSON.stringify(metrics) + '\n';
    fs.appendFileSync(VALUE_LOG, entry);
  }
  return metrics;
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

const command = process.argv[2];

switch (command) {
  case 'report':
    console.log(formatReport(calculateMetrics()));
    break;

  case 'json':
    console.log(JSON.stringify(calculateMetrics(), null, 2));
    break;

  case 'log':
    const logged = logValue();
    console.log('Value logged:', logged.timestamp);
    break;

  case 'config':
    if (process.argv[3] === 'set' && process.argv[4] && process.argv[5]) {
      const config = loadConfig();
      const key = process.argv[4];
      const value = parseFloat(process.argv[5]) || process.argv[5];
      config[key] = value;
      saveConfig(config);
      console.log(`Set ${key} = ${value}`);
    } else {
      console.log(JSON.stringify(loadConfig(), null, 2));
    }
    break;

  case 'init':
    saveConfig(DEFAULT_CONFIG);
    console.log('Config initialized with $200/month');
    break;

  default:
    // Return metrics object for programmatic use
    module.exports = {
      calculateMetrics,
      formatReport,
      loadConfig,
      saveConfig,
      logValue,
      getCurrentMonthStats
    };
}
