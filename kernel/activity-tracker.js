#!/usr/bin/env node
/**
 * Activity Tracker - Event Logging for ProactiveVA
 *
 * Logs all Claude interactions for pattern detection.
 * Integrates with:
 * - smart-route.sh (DQ routing)
 * - Pattern detector
 * - Command Center dashboard
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const DATA_DIR = path.join(process.env.HOME, '.claude', 'data');
const ACTIVITY_FILE = path.join(DATA_DIR, 'activity-events.jsonl');
const SESSION_FILE = path.join(DATA_DIR, 'current-session.json');

// Ensure directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// ═══════════════════════════════════════════════════════════════════════════
// SESSION MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

function getOrCreateSession() {
  if (fs.existsSync(SESSION_FILE)) {
    try {
      const session = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
      // Check if session is from today
      const sessionDate = new Date(session.started).toDateString();
      const today = new Date().toDateString();
      if (sessionDate === today) {
        return session;
      }
    } catch (e) {
      // Create new session
    }
  }

  const session = {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    started: new Date().toISOString(),
    queryCount: 0,
    modelUsage: { haiku: 0, sonnet: 0, opus: 0 },
    patterns: {}
  };

  fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));
  return session;
}

function updateSession(updates) {
  const session = getOrCreateSession();
  Object.assign(session, updates);
  session.lastActivity = new Date().toISOString();
  fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));
  return session;
}

// ═══════════════════════════════════════════════════════════════════════════
// EVENT LOGGING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Log a query event
 */
function logQuery(query, options = {}) {
  const {
    model = 'sonnet',
    dqScore = null,
    complexity = null,
    source = 'cli'
  } = options;

  const session = getOrCreateSession();

  const event = {
    type: 'query',
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    sessionId: session.id,
    query,
    model,
    dqScore,
    complexity,
    source
  };

  // Append to activity log
  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(event) + '\n');

  // Update session
  session.queryCount++;
  session.modelUsage[model] = (session.modelUsage[model] || 0) + 1;
  updateSession(session);

  return event;
}

/**
 * Log a tool usage event
 */
function logToolUsage(tool, options = {}) {
  const session = getOrCreateSession();

  const event = {
    type: 'tool',
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    sessionId: session.id,
    tool,
    ...options
  };

  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(event) + '\n');
  return event;
}

/**
 * Log a skill invocation
 */
function logSkill(skill, options = {}) {
  const session = getOrCreateSession();

  const event = {
    type: 'skill',
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    sessionId: session.id,
    skill,
    ...options
  };

  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(event) + '\n');
  return event;
}

/**
 * Log a memory operation
 */
function logMemory(operation, options = {}) {
  const event = {
    type: 'memory',
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    operation,
    ...options
  };

  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(event) + '\n');
  return event;
}

// ═══════════════════════════════════════════════════════════════════════════
// RETRIEVAL
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get recent events
 */
function getRecentEvents(options = {}) {
  const { limit = 50, type = null, minutes = null } = options;

  if (!fs.existsSync(ACTIVITY_FILE)) return [];

  const lines = fs.readFileSync(ACTIVITY_FILE, 'utf8').trim().split('\n');
  let events = [];

  for (const line of lines) {
    if (!line) continue;
    try {
      const event = JSON.parse(line);
      if (type && event.type !== type) continue;
      if (minutes) {
        const cutoff = Date.now() - (minutes * 60 * 1000);
        if (event.timestamp < cutoff) continue;
      }
      events.push(event);
    } catch (e) {
      // Skip malformed
    }
  }

  // Return most recent
  return events.slice(-limit);
}

/**
 * Get session summary
 */
function getSessionSummary() {
  const session = getOrCreateSession();
  const recentEvents = getRecentEvents({ minutes: 60 });

  // Calculate activity breakdown
  const breakdown = {};
  for (const event of recentEvents) {
    breakdown[event.type] = (breakdown[event.type] || 0) + 1;
  }

  return {
    ...session,
    recentActivityCount: recentEvents.length,
    activityBreakdown: breakdown,
    activeMinutes: recentEvents.length > 0
      ? ((Date.now() - recentEvents[0].timestamp) / 60000).toFixed(0)
      : 0
  };
}

/**
 * Get activity for dashboard
 */
function getDashboardData() {
  const session = getSessionSummary();
  const recentQueries = getRecentEvents({ type: 'query', limit: 20 });

  // Model distribution
  const modelDist = { haiku: 0, sonnet: 0, opus: 0 };
  for (const q of recentQueries) {
    if (q.model) modelDist[q.model]++;
  }

  // Hourly activity
  const hourly = {};
  const allEvents = getRecentEvents({ minutes: 1440 }); // Last 24 hours
  for (const e of allEvents) {
    const hour = new Date(e.datetime).getHours();
    hourly[hour] = (hourly[hour] || 0) + 1;
  }

  return {
    session,
    recentQueries: recentQueries.map(q => ({
      query: q.query?.slice(0, 60) + (q.query?.length > 60 ? '...' : ''),
      model: q.model,
      dqScore: q.dqScore,
      time: new Date(q.datetime).toLocaleTimeString()
    })),
    modelDistribution: modelDist,
    hourlyActivity: hourly
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'query':
      // Log query: node activity-tracker.js query "text" [model] [dqScore] [complexity]
      const query = args[1];
      const model = args[2] || 'sonnet';
      const dqScore = args[3] ? parseFloat(args[3]) : null;
      const complexity = args[4] ? parseFloat(args[4]) : null;
      if (!query) {
        console.error('Usage: activity-tracker.js query "text" [model] [dqScore] [complexity]');
        process.exit(1);
      }
      const event = logQuery(query, { model, dqScore, complexity });
      console.log(JSON.stringify({ logged: true, timestamp: event.timestamp }));
      break;

    case 'tool':
      // Log tool: node activity-tracker.js tool "toolName" [success]
      const tool = args[1];
      const success = args[2] !== 'false';
      if (!tool) {
        console.error('Usage: activity-tracker.js tool "toolName" [success]');
        process.exit(1);
      }
      logToolUsage(tool, { success });
      console.log('Tool logged');
      break;

    case 'skill':
      // Log skill: node activity-tracker.js skill "skillName"
      const skill = args[1];
      if (!skill) {
        console.error('Usage: activity-tracker.js skill "skillName"');
        process.exit(1);
      }
      logSkill(skill);
      console.log('Skill logged');
      break;

    case 'recent':
      // Get recent events: node activity-tracker.js recent [limit] [type]
      const limit = parseInt(args[1]) || 20;
      const type = args[2] || null;
      console.log(JSON.stringify(getRecentEvents({ limit, type }), null, 2));
      break;

    case 'session':
      // Get session: node activity-tracker.js session
      console.log(JSON.stringify(getSessionSummary(), null, 2));
      break;

    case 'dashboard':
      // Get dashboard data: node activity-tracker.js dashboard
      console.log(JSON.stringify(getDashboardData(), null, 2));
      break;

    default:
      console.log('Activity Tracker - Event Logging');
      console.log('');
      console.log('Commands:');
      console.log('  query "text" [model] [dqScore] [complexity]  - Log a query');
      console.log('  tool "name" [success]                        - Log tool usage');
      console.log('  skill "name"                                 - Log skill invocation');
      console.log('  recent [limit] [type]                        - Get recent events');
      console.log('  session                                      - Get session summary');
      console.log('  dashboard                                    - Get dashboard data');
  }
}

module.exports = {
  logQuery,
  logToolUsage,
  logSkill,
  logMemory,
  getRecentEvents,
  getSessionSummary,
  getDashboardData,
  getOrCreateSession
};
