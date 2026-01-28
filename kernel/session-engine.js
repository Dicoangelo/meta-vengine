#!/usr/bin/env node
/**
 * Session Engine - Core state engine for the Session Optimizer
 *
 * Manages:
 * - Window tracking (reset pattern detection)
 * - Budget management (token allocation)
 * - Capacity prediction (remaining estimates)
 * - Task queue (DQ-weighted priority)
 *
 * Integrates with:
 * - activity-tracker.js (activity events)
 * - subscription-tracker.js (budget data)
 * - baselines.json (learned thresholds)
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const KERNEL_DIR = path.join(process.env.HOME, '.claude', 'kernel');
const DATA_DIR = path.join(process.env.HOME, '.claude', 'data');
const LOGS_DIR = path.join(process.env.HOME, '.claude', 'logs');

// New session optimizer files
const STATE_FILE = path.join(KERNEL_DIR, 'session-state.json');
const BASELINES_FILE = path.join(KERNEL_DIR, 'session-baselines.json');
const PATTERNS_FILE = path.join(KERNEL_DIR, 'window-patterns.json');
const QUEUE_FILE = path.join(KERNEL_DIR, 'task-queue.json');
const WINDOWS_LOG = path.join(DATA_DIR, 'session-windows.jsonl');
const OPTIMIZER_LOG = path.join(DATA_DIR, 'session-optimizer.jsonl');
const CAPACITY_LOG = path.join(DATA_DIR, 'capacity-snapshots.jsonl');
const LOG_FILE = path.join(LOGS_DIR, 'session-optimizer.log');

// Integration with existing infrastructure
const ACTIVITY_FILE = path.join(DATA_DIR, 'activity-events.jsonl');
const STATS_CACHE = path.join(KERNEL_DIR, '..', 'stats-cache.json');
const DETECTED_PATTERNS = path.join(KERNEL_DIR, 'detected-patterns.json');
const SESSION_EVENTS = path.join(DATA_DIR, 'session-events.jsonl');
const EXISTING_BASELINES = path.join(KERNEL_DIR, 'baselines.json');

// Ensure directories exist
[KERNEL_DIR, DATA_DIR, LOGS_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// DEFAULT STATE & BASELINES
// ═══════════════════════════════════════════════════════════════════════════

const DEFAULT_STATE = {
  version: "1.0.0",
  lastUpdated: new Date().toISOString(),

  window: {
    id: null,
    startedAt: null,
    estimatedEndAt: null,
    positionPercent: 0,
    remainingMinutes: 300,
    confidence: 0.5
  },

  budget: {
    windowCapacity: 5000000,
    used: { opus: 0, sonnet: 0, haiku: 0 },
    allocated: { opus: 2000000, sonnet: 2000000, haiku: 500000, reserve: 500000 },
    utilizationPercent: 0,
    recommendedModel: "sonnet"
  },

  capacity: {
    tier: "COMFORTABLE",
    remaining: { opus: 10, sonnet: 100, haiku: 400 },
    projectedWindowEnd: 5000000,
    switchThresholds: { downgradeAt: 0.85, upgradeAt: 0.30 }
  },

  context: {
    messages: 0,
    saturation: 0,
    cacheEfficiency: 0.93,
    clearRecommended: false,
    nextCheckpoint: 50
  },

  predictions: {
    optimalNextStart: null,
    peakHoursRemaining: [],
    workPattern: "general",
    batchWindow: null
  }
};

const DEFAULT_BASELINES = {
  version: "1.0.0",
  confidence: 0.5,

  windowPatterns: {
    typicalDurationMs: 18000000, // 5 hours
    resetTimes: [
      { hour: 7, reliability: 0.80 },
      { hour: 12, reliability: 0.75 },
      { hour: 17, reliability: 0.70 }
    ]
  },

  budgetThresholds: {
    opusReservePercent: 0.20,
    downgradeThreshold: 0.85,
    emergencyReserve: 0.10
  },

  checkpointThresholds: {
    messageCount: 50,
    saturationLevel: 0.70
  },

  researchLineage: []
};

// ═══════════════════════════════════════════════════════════════════════════
// FILE I/O
// ═══════════════════════════════════════════════════════════════════════════

function loadJSON(filepath, defaultValue) {
  try {
    if (fs.existsSync(filepath)) {
      return JSON.parse(fs.readFileSync(filepath, 'utf8'));
    }
  } catch (e) {
    log(`Error loading ${filepath}: ${e.message}`);
  }
  return defaultValue;
}

function saveJSON(filepath, data) {
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2));
}

function appendJSONL(filepath, data) {
  fs.appendFileSync(filepath, JSON.stringify(data) + '\n');
}

function log(message) {
  const timestamp = new Date().toISOString();
  fs.appendFileSync(LOG_FILE, `${timestamp} ${message}\n`);
}

// ═══════════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

function loadState() {
  return loadJSON(STATE_FILE, DEFAULT_STATE);
}

function saveState(state) {
  state.lastUpdated = new Date().toISOString();
  saveJSON(STATE_FILE, state);
}

function loadBaselines() {
  return loadJSON(BASELINES_FILE, DEFAULT_BASELINES);
}

function saveBaselines(baselines) {
  saveJSON(BASELINES_FILE, baselines);
}

function loadTaskQueue() {
  return loadJSON(QUEUE_FILE, { version: "1.0.0", tasks: [] });
}

function saveTaskQueue(queue) {
  saveJSON(QUEUE_FILE, queue);
}

// ═══════════════════════════════════════════════════════════════════════════
// WINDOW TRACKING
// ═══════════════════════════════════════════════════════════════════════════

function initializeWindow() {
  const state = loadState();
  const baselines = loadBaselines();
  const now = new Date();

  // Generate window ID
  const windowId = `window-${now.toISOString().slice(0, 10)}-${String(now.getHours()).padStart(2, '0')}00`;

  // Estimate window end based on patterns
  const typicalDuration = baselines.windowPatterns.typicalDurationMs;
  const estimatedEnd = new Date(now.getTime() + typicalDuration);

  // Find next reset time
  const resetTimes = baselines.windowPatterns.resetTimes;
  let nextResetHour = null;
  let reliability = 0.5;

  for (const reset of resetTimes.sort((a, b) => a.hour - b.hour)) {
    if (reset.hour > now.getHours()) {
      nextResetHour = reset.hour;
      reliability = reset.reliability;
      break;
    }
  }

  if (nextResetHour) {
    const nextReset = new Date(now);
    nextReset.setHours(nextResetHour, 0, 0, 0);
    if (nextReset.getTime() < estimatedEnd.getTime()) {
      state.window.estimatedEndAt = nextReset.toISOString();
      state.window.remainingMinutes = Math.round((nextReset.getTime() - now.getTime()) / 60000);
      state.window.confidence = reliability;
    } else {
      state.window.estimatedEndAt = estimatedEnd.toISOString();
      state.window.remainingMinutes = Math.round(typicalDuration / 60000);
      state.window.confidence = baselines.confidence;
    }
  } else {
    state.window.estimatedEndAt = estimatedEnd.toISOString();
    state.window.remainingMinutes = Math.round(typicalDuration / 60000);
    state.window.confidence = baselines.confidence;
  }

  state.window.id = windowId;
  state.window.startedAt = now.toISOString();
  state.window.positionPercent = 0;

  // Log window start
  appendJSONL(WINDOWS_LOG, {
    event: 'window_start',
    windowId,
    timestamp: now.toISOString(),
    estimatedEnd: state.window.estimatedEndAt,
    confidence: state.window.confidence
  });

  saveState(state);
  log(`Window initialized: ${windowId}`);

  return state;
}

function updateWindowPosition() {
  const state = loadState();

  if (!state.window.startedAt || !state.window.estimatedEndAt) {
    return state;
  }

  const now = Date.now();
  const start = new Date(state.window.startedAt).getTime();
  const end = new Date(state.window.estimatedEndAt).getTime();
  const total = end - start;
  const elapsed = now - start;

  state.window.positionPercent = Math.min(100, Math.round((elapsed / total) * 100));
  state.window.remainingMinutes = Math.max(0, Math.round((end - now) / 60000));

  saveState(state);
  return state;
}

// ═══════════════════════════════════════════════════════════════════════════
// BUDGET MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

function updateBudget(model, tokens = 0) {
  const state = loadState();
  const baselines = loadBaselines();

  // Update used tokens
  if (model && tokens > 0) {
    state.budget.used[model] = (state.budget.used[model] || 0) + tokens;
  }

  // Calculate total usage
  const totalUsed = Object.values(state.budget.used).reduce((a, b) => a + b, 0);
  state.budget.utilizationPercent = Math.round((totalUsed / state.budget.windowCapacity) * 100);

  // Determine recommended model based on budget
  const thresholds = baselines.budgetThresholds;

  if (state.budget.utilizationPercent >= thresholds.downgradeThreshold * 100) {
    state.budget.recommendedModel = 'haiku';
  } else if (state.budget.utilizationPercent >= 50) {
    state.budget.recommendedModel = 'sonnet';
  } else {
    state.budget.recommendedModel = 'opus'; // Can still use opus
  }

  // Update capacity tier
  if (state.budget.utilizationPercent >= 85) {
    state.capacity.tier = 'CRITICAL';
  } else if (state.budget.utilizationPercent >= 70) {
    state.capacity.tier = 'LOW';
  } else if (state.budget.utilizationPercent >= 40) {
    state.capacity.tier = 'MODERATE';
  } else {
    state.capacity.tier = 'COMFORTABLE';
  }

  // Estimate remaining tasks by model
  const remaining = state.budget.windowCapacity - totalUsed;
  const avgOpusTask = 200000;  // ~200k tokens per Opus task
  const avgSonnetTask = 50000; // ~50k tokens per Sonnet task
  const avgHaikuTask = 10000;  // ~10k tokens per Haiku task

  state.capacity.remaining = {
    opus: Math.floor(remaining / avgOpusTask),
    sonnet: Math.floor(remaining / avgSonnetTask),
    haiku: Math.floor(remaining / avgHaikuTask)
  };

  state.capacity.projectedWindowEnd = totalUsed + remaining;

  saveState(state);
  return state;
}

// ═══════════════════════════════════════════════════════════════════════════
// CONTEXT TRACKING
// ═══════════════════════════════════════════════════════════════════════════

function updateContext(messageCount, saturation = null) {
  const state = loadState();
  const baselines = loadBaselines();

  state.context.messages = messageCount;

  if (saturation !== null) {
    state.context.saturation = saturation;
  } else {
    // Estimate saturation from message count (rough: 200k context, ~500 tokens/msg)
    const estimatedTokens = messageCount * 500;
    state.context.saturation = Math.min(1, estimatedTokens / 200000);
  }

  // Check if checkpoint or clear is recommended
  const thresholds = baselines.checkpointThresholds;

  if (messageCount >= thresholds.messageCount) {
    state.context.nextCheckpoint = messageCount + thresholds.messageCount;
  }

  state.context.clearRecommended =
    state.context.saturation >= thresholds.saturationLevel ||
    messageCount >= 100;

  saveState(state);
  return state;
}

// ═══════════════════════════════════════════════════════════════════════════
// PREDICTIONS
// ═══════════════════════════════════════════════════════════════════════════

function updatePredictions() {
  const state = loadState();
  const baselines = loadBaselines();
  const now = new Date();

  // Predict optimal next start based on patterns
  const resetTimes = baselines.windowPatterns.resetTimes.sort((a, b) => b.reliability - a.reliability);
  const currentHour = now.getHours();

  // Find next reliable reset time
  for (const reset of resetTimes) {
    if (reset.hour > currentHour) {
      const nextStart = new Date(now);
      nextStart.setHours(reset.hour, 15, 0, 0); // 15 min after reset
      state.predictions.optimalNextStart = nextStart.toISOString();
      break;
    }
  }

  // Peak hours remaining today
  const peakHours = [14, 15, 16]; // From CLAUDE.md patterns
  state.predictions.peakHoursRemaining = peakHours.filter(h => h > currentHour);

  // Detect work pattern from recent activity
  state.predictions.workPattern = detectWorkPattern();

  // Suggest batch window (evening low-priority)
  const batchStart = new Date(now);
  batchStart.setHours(17, 0, 0, 0);
  const batchEnd = new Date(now);
  batchEnd.setHours(19, 0, 0, 0);

  if (now.getHours() < 17) {
    state.predictions.batchWindow = `${batchStart.getHours()}:00-${batchEnd.getHours()}:00`;
  } else {
    state.predictions.batchWindow = null;
  }

  saveState(state);
  return state;
}

function detectWorkPattern() {
  // First try to use existing detected-patterns.json (from pattern-detector.js)
  try {
    if (fs.existsSync(DETECTED_PATTERNS)) {
      const detected = JSON.parse(fs.readFileSync(DETECTED_PATTERNS, 'utf8'));
      if (detected.patterns && detected.patterns.length > 0) {
        // Return the highest confidence pattern
        const sorted = detected.patterns.sort((a, b) => b.confidence - a.confidence);
        return sorted[0].id || sorted[0].name || 'general';
      }
    }
  } catch (e) {
    // Fall through to activity-based detection
  }

  // Fallback: Load recent activity to detect pattern
  try {
    if (!fs.existsSync(ACTIVITY_FILE)) return 'general';

    const content = fs.readFileSync(ACTIVITY_FILE, 'utf8');
    const lines = content.trim().split('\n').slice(-100);
    const events = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

    // Count patterns in queries
    const patterns = { debugging: 0, coding: 0, research: 0, general: 0 };

    for (const event of events) {
      if (event.type === 'query') {
        const q = (event.query || '').toLowerCase();
        if (q.includes('debug') || q.includes('error') || q.includes('fix')) patterns.debugging++;
        else if (q.includes('implement') || q.includes('create') || q.includes('add')) patterns.coding++;
        else if (q.includes('research') || q.includes('explain') || q.includes('how')) patterns.research++;
        else patterns.general++;
      }
    }

    // Return dominant pattern
    return Object.entries(patterns).sort((a, b) => b[1] - a[1])[0][0];
  } catch {
    return 'general';
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// INTEGRATION WITH EXISTING INFRASTRUCTURE
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load usage data from stats-cache.json (updated by subscription-tracker.js)
 */
function loadStatsCache() {
  try {
    if (fs.existsSync(STATS_CACHE)) {
      return JSON.parse(fs.readFileSync(STATS_CACHE, 'utf8'));
    }
  } catch (e) {
    log(`Error loading stats-cache: ${e.message}`);
  }
  return null;
}

/**
 * Sync budget data from stats-cache (actual token usage)
 * Calculates window position based on time and reset patterns
 */
function syncFromStatsCache() {
  const state = loadState();
  const baselines = loadBaselines();
  const stats = loadStatsCache();
  const now = new Date();

  // ═══ WINDOW POSITION CALCULATION ═══
  // Calculate position based on time since last reset
  const resetTimes = baselines.windowPatterns?.resetTimes || [
    { hour: 7, reliability: 0.80 },
    { hour: 12, reliability: 0.75 },
    { hour: 17, reliability: 0.70 }
  ];

  // Find the most recent reset time that has passed
  const currentHour = now.getHours();
  let windowStart = new Date(now);
  windowStart.setHours(0, 0, 0, 0); // Default to midnight

  let nextReset = null;
  let windowConfidence = 0.5;

  // Sort reset times and find boundaries
  const sortedResets = resetTimes.sort((a, b) => a.hour - b.hour);

  for (let i = sortedResets.length - 1; i >= 0; i--) {
    if (sortedResets[i].hour <= currentHour) {
      windowStart = new Date(now);
      windowStart.setHours(sortedResets[i].hour, 0, 0, 0);
      windowConfidence = sortedResets[i].reliability;
      // Next reset is the following one or first of next day
      nextReset = sortedResets[i + 1] || { hour: sortedResets[0].hour + 24, reliability: sortedResets[0].reliability };
      break;
    }
  }

  // If no reset has passed today, use last reset from yesterday
  if (windowStart.getHours() === 0 && sortedResets.length > 0) {
    const lastReset = sortedResets[sortedResets.length - 1];
    windowStart = new Date(now);
    windowStart.setDate(windowStart.getDate() - 1);
    windowStart.setHours(lastReset.hour, 0, 0, 0);
    nextReset = sortedResets[0];
    windowConfidence = lastReset.reliability;
  }

  // Calculate window end
  let windowEnd = new Date(now);
  if (nextReset) {
    const nextResetHour = nextReset.hour > 24 ? nextReset.hour - 24 : nextReset.hour;
    windowEnd.setHours(nextResetHour, 0, 0, 0);
    if (windowEnd <= now) {
      windowEnd.setDate(windowEnd.getDate() + 1);
    }
  } else {
    // Default 5-hour window
    windowEnd = new Date(windowStart.getTime() + baselines.windowPatterns?.typicalDurationMs || 18000000);
  }

  // Calculate position percentage
  const totalWindowMs = windowEnd.getTime() - windowStart.getTime();
  const elapsedMs = now.getTime() - windowStart.getTime();
  const positionPercent = Math.min(100, Math.max(0, Math.round((elapsedMs / totalWindowMs) * 100)));
  const remainingMinutes = Math.max(0, Math.round((windowEnd.getTime() - now.getTime()) / 60000));

  state.window = {
    id: `window-${now.toISOString().slice(0, 10)}-${String(windowStart.getHours()).padStart(2, '0')}00`,
    startedAt: windowStart.toISOString(),
    estimatedEndAt: windowEnd.toISOString(),
    positionPercent,
    remainingMinutes,
    confidence: windowConfidence
  };

  // ═══ BUDGET CALCULATION FROM TODAY'S USAGE ═══
  if (stats && stats.dailyActivity && stats.dailyActivity.length > 0) {
    // Get today's and yesterday's activity (stats are cumulative)
    const today = now.toISOString().slice(0, 10);
    const yesterday = new Date(now.getTime() - 86400000).toISOString().slice(0, 10);

    const dailyData = stats.dailyActivity;
    const todayActivity = dailyData.find(d => d.date === today) || {};
    const yesterdayActivity = dailyData.find(d => d.date === yesterday) || {};

    // Calculate TODAY'S actual usage (difference from yesterday)
    const todayMessages = Math.max(0, (todayActivity.messageCount || 0) - (yesterdayActivity.messageCount || 0));
    const todayTools = Math.max(0, (todayActivity.toolCallCount || 0) - (yesterdayActivity.toolCallCount || 0));

    // Estimate tokens from today's actual usage
    // Rough estimate: each message ~2000 tokens, each tool ~500 tokens
    const estimatedTodayTokens = (todayMessages * 2000) + (todayTools * 500);

    // Daily budget allocation
    const dailyBudget = state.budget.windowCapacity;
    const utilizationPercent = Math.min(100, Math.round((estimatedTodayTokens / dailyBudget) * 100));

    state.budget.utilizationPercent = utilizationPercent;
    state.budget.used = {
      opus: Math.round(estimatedTodayTokens * 0.8),  // Most usage is Opus
      sonnet: Math.round(estimatedTodayTokens * 0.15),
      haiku: Math.round(estimatedTodayTokens * 0.05)
    };

    // Update context with today's actual messages
    state.context.messages = todayMessages;
    state.context.saturation = Math.min(1, todayMessages / 100);
  }

  // ═══ CAPACITY TIER CALCULATION ═══
  const utilization = state.budget.utilizationPercent;
  if (utilization >= 85 || remainingMinutes < 30) {
    state.capacity.tier = 'CRITICAL';
  } else if (utilization >= 70 || remainingMinutes < 60) {
    state.capacity.tier = 'LOW';
  } else if (utilization >= 40 || remainingMinutes < 120) {
    state.capacity.tier = 'MODERATE';
  } else {
    state.capacity.tier = 'COMFORTABLE';
  }

  // ═══ REMAINING CAPACITY ESTIMATION ═══
  const budgetRemaining = state.budget.windowCapacity - (state.budget.used.opus + state.budget.used.sonnet + state.budget.used.haiku);
  const avgOpusTask = 200000;
  const avgSonnetTask = 50000;
  const avgHaikuTask = 10000;

  state.capacity.remaining = {
    opus: Math.max(0, Math.floor(budgetRemaining / avgOpusTask)),
    sonnet: Math.max(0, Math.floor(budgetRemaining / avgSonnetTask)),
    haiku: Math.max(0, Math.floor(budgetRemaining / avgHaikuTask))
  };

  // ═══ CACHE EFFICIENCY FROM STATS ═══
  if (stats && stats.modelUsage) {
    let totalCacheReads = 0;
    let totalInputs = 0;
    for (const data of Object.values(stats.modelUsage)) {
      totalCacheReads += data.cacheReadInputTokens || 0;
      totalInputs += (data.cacheReadInputTokens || 0) + (data.cacheCreationInputTokens || 0) + (data.inputTokens || 0);
    }
    if (totalInputs > 0) {
      state.context.cacheEfficiency = Math.round((totalCacheReads / totalInputs) * 100) / 100;
    }
  }

  // ═══ RECOMMENDED MODEL ═══
  const thresholds = baselines.budgetThresholds || {};
  if (utilization >= (thresholds.downgradeThreshold || 0.85) * 100) {
    state.budget.recommendedModel = 'haiku';
  } else if (utilization >= 50 || state.capacity.tier === 'LOW') {
    state.budget.recommendedModel = 'sonnet';
  } else {
    state.budget.recommendedModel = 'opus';
  }

  saveState(state);
  return state;
}

/**
 * Load existing routing baselines for DQ weights
 */
function loadExistingBaselines() {
  try {
    if (fs.existsSync(EXISTING_BASELINES)) {
      return JSON.parse(fs.readFileSync(EXISTING_BASELINES, 'utf8'));
    }
  } catch (e) {
    log(`Error loading existing baselines: ${e.message}`);
  }
  return null;
}

/**
 * Get peak hours from CLAUDE.md patterns (auto-generated section)
 */
function getPeakHoursFromPatterns() {
  const baselines = loadBaselines();
  const existingBaselines = loadExistingBaselines();

  // Use session baselines if available
  if (baselines.peakHours) {
    return baselines.peakHours;
  }

  // Default peak hours from CLAUDE.md observation
  return [14, 15, 16];
}

// ═══════════════════════════════════════════════════════════════════════════
// TASK QUEUE
// ═══════════════════════════════════════════════════════════════════════════

function addTask(description, complexity = 0.5, priority = null) {
  const queue = loadTaskQueue();

  // Calculate DQ-weighted priority
  const dqPriority = priority !== null ? priority : complexity * 0.7 + 0.3;

  const task = {
    id: Date.now().toString(36),
    description,
    complexity,
    priority: dqPriority,
    addedAt: new Date().toISOString(),
    status: 'pending'
  };

  queue.tasks.push(task);

  // Sort by priority (highest first)
  queue.tasks.sort((a, b) => b.priority - a.priority);

  saveTaskQueue(queue);
  log(`Task added: ${description} (priority: ${dqPriority.toFixed(2)})`);

  return task;
}

function getNextTask() {
  const queue = loadTaskQueue();
  const state = loadState();

  // Find best task for current capacity
  for (const task of queue.tasks) {
    if (task.status !== 'pending') continue;

    // Check if we have capacity for this task
    if (task.complexity >= 0.7 && state.capacity.remaining.opus < 1) continue;
    if (task.complexity >= 0.3 && state.capacity.remaining.sonnet < 1) continue;

    return task;
  }

  return null;
}

function completeTask(taskId) {
  const queue = loadTaskQueue();

  const task = queue.tasks.find(t => t.id === taskId);
  if (task) {
    task.status = 'completed';
    task.completedAt = new Date().toISOString();
    saveTaskQueue(queue);
    log(`Task completed: ${task.description}`);
  }

  return task;
}

function listTasks(status = null) {
  const queue = loadTaskQueue();

  if (status) {
    return queue.tasks.filter(t => t.status === status);
  }
  return queue.tasks;
}

// ═══════════════════════════════════════════════════════════════════════════
// STATUS DISPLAY
// ═══════════════════════════════════════════════════════════════════════════

function getStatusDisplay() {
  const state = loadState();

  // Progress bar
  const filled = Math.round(state.window.positionPercent / 10);
  const progressBar = '█'.repeat(filled) + '░'.repeat(10 - filled);

  // Time remaining
  const hours = Math.floor(state.window.remainingMinutes / 60);
  const mins = state.window.remainingMinutes % 60;
  const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;

  // Capacity emoji
  const tierEmoji = {
    'COMFORTABLE': '🟢',
    'MODERATE': '🟡',
    'LOW': '🟠',
    'CRITICAL': '🔴'
  }[state.capacity.tier] || '⚪';

  // Build display
  const lines = [
    ``,
    `━━━ Session Window ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`,
    `Position: ${progressBar} ${state.window.positionPercent}% | ${timeStr} remaining`,
    `Capacity: ${tierEmoji} ${state.capacity.tier} | Opus: ${state.capacity.remaining.opus} | Sonnet: ${state.capacity.remaining.sonnet} | Haiku: ${state.capacity.remaining.haiku}`,
    `Budget:   ${state.budget.utilizationPercent}% utilized | Recommended: ${state.budget.recommendedModel}`,
    `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
  ];

  // Add queue info if tasks exist
  const pendingTasks = listTasks('pending');
  if (pendingTasks.length > 0) {
    const nextTask = getNextTask();
    lines.push(`Queue: ${pendingTasks.length} tasks | Next: ${nextTask ? nextTask.description.slice(0, 30) : 'none'}`);
  }

  // Add predictions
  if (state.predictions.optimalNextStart) {
    const nextTime = new Date(state.predictions.optimalNextStart).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    lines.push(`Prediction: Optimal next window ${nextTime} | Pattern: ${state.predictions.workPattern}`);
  }

  return lines.join('\n');
}

function getCompactStatus() {
  const state = loadState();
  const pendingTasks = listTasks('pending').length;

  return `[Window ${state.window.positionPercent}% | ${state.window.remainingMinutes}m | ${state.capacity.tier} Opus:${state.capacity.remaining.opus} Sonnet:${state.capacity.remaining.sonnet} | Queue:${pendingTasks}]`;
}

// ═══════════════════════════════════════════════════════════════════════════
// OPTIMIZER EVENTS
// ═══════════════════════════════════════════════════════════════════════════

function logOptimizerEvent(eventType, data = {}) {
  appendJSONL(OPTIMIZER_LOG, {
    event: eventType,
    timestamp: new Date().toISOString(),
    ...data
  });
}

function logCapacitySnapshot() {
  const state = loadState();

  appendJSONL(CAPACITY_LOG, {
    timestamp: new Date().toISOString(),
    windowId: state.window.id,
    positionPercent: state.window.positionPercent,
    budgetUtilization: state.budget.utilizationPercent,
    capacityTier: state.capacity.tier,
    remaining: state.capacity.remaining,
    contextMessages: state.context.messages,
    saturation: state.context.saturation
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

const command = process.argv[2];

switch (command) {
  case 'start':
    // Initialize new session window
    const initState = initializeWindow();
    updateBudget();
    updatePredictions();
    console.log(getStatusDisplay());
    break;

  case 'end':
    // End session, log final state
    const endState = loadState();
    logOptimizerEvent('session_end', {
      windowId: endState.window.id,
      finalPosition: endState.window.positionPercent,
      budgetUtilization: endState.budget.utilizationPercent,
      contextMessages: endState.context.messages
    });
    log('Session ended');
    break;

  case 'status':
    // Show current status
    updateWindowPosition();
    console.log(getStatusDisplay());
    break;

  case 'compact':
    // Compact status for prompt integration
    updateWindowPosition();
    console.log(getCompactStatus());
    break;

  case 'update':
    // Update state (called by hooks)
    const model = process.argv[3];
    const tokens = parseInt(process.argv[4]) || 0;
    updateWindowPosition();
    updateBudget(model, tokens);
    logCapacitySnapshot();
    break;

  case 'context':
    // Update context tracking
    const messages = parseInt(process.argv[3]) || 0;
    updateContext(messages);
    break;

  case 'queue':
    // Task queue operations
    const queueOp = process.argv[3];
    switch (queueOp) {
      case 'add':
        const desc = process.argv[4];
        const comp = parseFloat(process.argv[5]) || 0.5;
        addTask(desc, comp);
        console.log('Task added');
        break;
      case 'next':
        const next = getNextTask();
        console.log(next ? JSON.stringify(next, null, 2) : 'No tasks');
        break;
      case 'complete':
        completeTask(process.argv[4]);
        console.log('Task completed');
        break;
      case 'list':
        console.log(JSON.stringify(listTasks(), null, 2));
        break;
      default:
        console.log('Usage: session-engine.js queue [add|next|complete|list]');
    }
    break;

  case 'json':
    // Return full state as JSON
    console.log(JSON.stringify(loadState(), null, 2));
    break;

  case 'init':
    // Initialize default baselines
    saveBaselines(DEFAULT_BASELINES);
    saveState(DEFAULT_STATE);
    console.log('Session optimizer initialized with default baselines');
    break;

  case 'sync':
    // Sync data from existing infrastructure (stats-cache, etc.)
    syncFromStatsCache();
    updateWindowPosition();
    updatePredictions();
    console.log('Synced from existing infrastructure');
    console.log(getCompactStatus());
    break;

  case 'dashboard':
    // Full dashboard view with existing infrastructure data
    syncFromStatsCache();
    updateWindowPosition();
    updatePredictions();
    console.log(getStatusDisplay());
    console.log('');
    const statsCache = loadStatsCache();
    if (statsCache && statsCache.dailyActivity) {
      const todayActivity = statsCache.dailyActivity.slice(-1)[0];
      if (todayActivity) {
        console.log(`Today: ${todayActivity.messageCount || 0} messages | ${todayActivity.toolCallCount || 0} tools`);
      }
    }
    break;

  default:
    console.log('Session Engine - Sovereign Session Optimizer');
    console.log('');
    console.log('Commands:');
    console.log('  start                    - Initialize session window');
    console.log('  end                      - End session');
    console.log('  status                   - Show current status');
    console.log('  compact                  - Compact status line');
    console.log('  dashboard                - Full dashboard with stats');
    console.log('  sync                     - Sync from existing infrastructure');
    console.log('  update [model] [tokens]  - Update budget/position');
    console.log('  context [messages]       - Update context tracking');
    console.log('  queue [add|next|complete|list] - Task queue operations');
    console.log('  json                     - Full state as JSON');
    console.log('  init                     - Initialize with defaults');
}

// ═══════════════════════════════════════════════════════════════════════════
// MODULE EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

module.exports = {
  loadState,
  saveState,
  loadBaselines,
  saveBaselines,
  initializeWindow,
  updateWindowPosition,
  updateBudget,
  updateContext,
  updatePredictions,
  addTask,
  getNextTask,
  completeTask,
  listTasks,
  getStatusDisplay,
  getCompactStatus,
  logOptimizerEvent,
  logCapacitySnapshot,
  // Integration functions
  loadStatsCache,
  syncFromStatsCache,
  loadExistingBaselines,
  getPeakHoursFromPatterns,
  detectWorkPattern
};
