#!/usr/bin/env node
/**
 * Pattern Detector - ProactiveVA Implementation
 *
 * Based on: "ProactiveVA: Proactive Virtual Assistant"
 * arXiv: https://arxiv.org/abs/2507.18165
 *
 * Implements:
 * - Interaction pattern detection (debugging, research, refactoring, etc.)
 * - Proactive suggestion generation
 * - Activity stream analysis
 * - Session context awareness
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const KERNEL_DIR = path.join(process.env.HOME, '.claude', 'kernel');
const DATA_DIR = path.join(process.env.HOME, '.claude', 'data');
const ACTIVITY_FILE = path.join(DATA_DIR, 'activity-events.jsonl');
const PATTERNS_FILE = path.join(KERNEL_DIR, 'detected-patterns.json');
const COEVO_CONFIG = path.join(KERNEL_DIR, 'coevo-config.json');
const EFFECTIVENESS_LOG = path.join(KERNEL_DIR, 'effectiveness.jsonl');

// Ensure directories exist
[KERNEL_DIR, DATA_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
});

// ═══════════════════════════════════════════════════════════════════════════
// CO-EVOLUTION INTEGRATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load co-evolution configuration
 */
function loadCoevoConfig() {
  if (fs.existsSync(COEVO_CONFIG)) {
    try {
      return JSON.parse(fs.readFileSync(COEVO_CONFIG, 'utf8'));
    } catch (e) {
      return { enabled: true };
    }
  }
  return { enabled: true };
}

/**
 * Apply learned patterns from meta-analyzer to enhance suggestions
 */
function applyLearnedPatterns(suggestions, detectedPattern) {
  const config = loadCoevoConfig();

  if (!config.evolution?.selfReferential) {
    return suggestions;
  }

  // Load effectiveness history to weight suggestions
  const effectiveness = loadEffectivenessHistory();

  // Enhance suggestions based on what worked before
  return suggestions.map(s => {
    const pastSuccess = effectiveness.filter(e =>
      e.pattern === detectedPattern && e.suggestion === s.value
    );

    if (pastSuccess.length > 0) {
      const avgImprovement = pastSuccess.reduce((sum, e) =>
        sum + (e.improvement || 0), 0) / pastSuccess.length;

      return {
        ...s,
        learnedWeight: avgImprovement > 0 ? 1.2 : 0.8,
        pastSuccess: pastSuccess.length,
        label: avgImprovement > 0 ? `${s.label} (proven)` : s.label
      };
    }

    return { ...s, learnedWeight: 1.0, pastSuccess: 0 };
  }).sort((a, b) => (b.learnedWeight * b.confidence) - (a.learnedWeight * a.confidence));
}

/**
 * Load effectiveness history for learning
 */
function loadEffectivenessHistory() {
  if (!fs.existsSync(EFFECTIVENESS_LOG)) return [];

  try {
    const lines = fs.readFileSync(EFFECTIVENESS_LOG, 'utf8').trim().split('\n');
    return lines.filter(l => l).map(l => JSON.parse(l));
  } catch (e) {
    return [];
  }
}

/**
 * Notify co-evolution system of detected pattern
 * This feeds the meta-analyzer's analysis loop
 */
function notifyCoEvolution(detection) {
  const config = loadCoevoConfig();

  if (!config.enabled || !config.evolution?.analyzeOwnModifications) {
    return;
  }

  // Log pattern detection event for meta-analyzer
  const event = {
    type: 'pattern_detected',
    timestamp: Date.now(),
    pattern: detection.patterns[0]?.id || null,
    confidence: detection.patterns[0]?.confidence || 0,
    activityCount: detection.activityCount,
    suggestionCount: detection.patterns.reduce((sum, p) =>
      sum + (p.suggestions?.length || 0), 0)
  };

  // Append to activity events for meta-analyzer consumption
  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(event) + '\n');
}

/**
 * Get learned suggestions enhanced by effectiveness data
 */
function getLearnedSuggestions(limit = 5) {
  const detection = detectPatterns();

  if (detection.patterns.length === 0) {
    return {
      hasContext: false,
      message: 'No active patterns detected',
      suggestions: [],
      learned: false
    };
  }

  // Notify co-evolution system
  notifyCoEvolution(detection);

  // Collect and enhance suggestions
  let allSuggestions = [];

  for (const pattern of detection.patterns) {
    const enhanced = applyLearnedPatterns(
      pattern.suggestions.map(s => ({
        ...s,
        confidence: pattern.confidence,
        fromPattern: pattern.id
      })),
      pattern.id
    );
    allSuggestions.push(...enhanced);
  }

  // Deduplicate by value, keeping highest weighted
  const seen = new Map();
  for (const s of allSuggestions) {
    const existing = seen.get(s.value);
    if (!existing || (s.learnedWeight * s.confidence) > (existing.learnedWeight * existing.confidence)) {
      seen.set(s.value, s);
    }
  }

  const unique = Array.from(seen.values())
    .sort((a, b) => (b.learnedWeight * b.confidence) - (a.learnedWeight * a.confidence))
    .slice(0, limit);

  return {
    hasContext: true,
    topPattern: detection.patterns[0],
    activityCount: detection.activityCount,
    suggestions: unique,
    learned: unique.some(s => s.pastSuccess > 0)
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// PATTERN DEFINITIONS (ProactiveVA)
// ═══════════════════════════════════════════════════════════════════════════

const PATTERNS = {
  debugging: {
    name: 'Debugging Session',
    icon: '🔍',
    signals: [
      'error', 'fix', 'bug', 'debug', 'why', 'not working', 'broken',
      'undefined', 'null', 'exception', 'crash', 'fail', 'issue', 'wrong'
    ],
    minMatches: 2,
    windowMinutes: 15,
    suggestions: [
      { type: 'skill', value: '/debug', label: 'Run systematic debug', desc: 'Comprehensive debugging workflow' },
      { type: 'model', value: 'opus', label: 'Switch to Opus', desc: 'Better for complex analysis' },
      { type: 'memory', value: 'error patterns', label: 'Recall error patterns', desc: 'Load related debugging memories' },
      { type: 'command', value: 'git diff', label: 'View recent changes', desc: 'Check what changed recently' }
    ]
  },

  research: {
    name: 'Research Session',
    icon: '📚',
    signals: [
      'arxiv', 'paper', 'research', 'compare', 'survey', 'study',
      'literature', 'citation', 'reference', 'methodology', 'approach'
    ],
    minMatches: 2,
    windowMinutes: 30,
    suggestions: [
      { type: 'command', value: 'python3 ~/researchgravity/status.py', label: 'Check research status', desc: 'View current research session' },
      { type: 'memory', value: 'research papers', label: 'Recall papers', desc: 'Load research context' },
      { type: 'model', value: 'opus', label: 'Switch to Opus', desc: 'Deep analysis capability' }
    ]
  },

  refactoring: {
    name: 'Refactoring Session',
    icon: '🔧',
    signals: [
      'refactor', 'clean', 'reorganize', 'split', 'extract', 'rename',
      'move', 'restructure', 'simplify', 'abstract', 'deduplicate'
    ],
    minMatches: 2,
    windowMinutes: 20,
    suggestions: [
      { type: 'skill', value: '/refactor', label: 'Smart Refactor', desc: 'Guided refactoring workflow' },
      { type: 'command', value: 'npm run lint', label: 'Run linter', desc: 'Check code quality' },
      { type: 'command', value: 'npm test', label: 'Run tests', desc: 'Verify refactoring' }
    ]
  },

  testing: {
    name: 'Testing Session',
    icon: '🧪',
    signals: [
      'test', 'spec', 'assert', 'expect', 'mock', 'stub', 'coverage',
      'unit', 'integration', 'e2e', 'vitest', 'jest', 'pytest'
    ],
    minMatches: 2,
    windowMinutes: 20,
    suggestions: [
      { type: 'skill', value: '/test', label: 'Comprehensive Testing', desc: 'Full test workflow' },
      { type: 'command', value: 'npm run test:coverage', label: 'Coverage report', desc: 'Check test coverage' },
      { type: 'memory', value: 'testing patterns', label: 'Recall test patterns', desc: 'Load testing best practices' }
    ]
  },

  architecture: {
    name: 'Architecture Session',
    icon: '🏗️',
    signals: [
      'architecture', 'design', 'system', 'component', 'module', 'service',
      'api', 'database', 'schema', 'structure', 'pattern', 'layer'
    ],
    minMatches: 3,
    windowMinutes: 30,
    suggestions: [
      { type: 'skill', value: '/arch', label: 'Architecture Analysis', desc: 'Analyze codebase structure' },
      { type: 'model', value: 'opus', label: 'Switch to Opus', desc: 'Complex architectural decisions' },
      { type: 'memory', value: 'architecture decisions', label: 'Recall decisions', desc: 'Load past architecture choices' }
    ]
  },

  performance: {
    name: 'Performance Session',
    icon: '⚡',
    signals: [
      'performance', 'optimize', 'slow', 'fast', 'speed', 'memory',
      'cpu', 'profile', 'benchmark', 'latency', 'bottleneck', 'cache'
    ],
    minMatches: 2,
    windowMinutes: 20,
    suggestions: [
      { type: 'command', value: 'npm run build', label: 'Build & analyze', desc: 'Check bundle size' },
      { type: 'memory', value: 'performance patterns', label: 'Recall optimizations', desc: 'Load performance tips' }
    ]
  },

  deployment: {
    name: 'Deployment Session',
    icon: '🚀',
    signals: [
      'deploy', 'release', 'production', 'staging', 'docker', 'kubernetes',
      'ci', 'cd', 'pipeline', 'build', 'vercel', 'netlify', 'aws'
    ],
    minMatches: 2,
    windowMinutes: 30,
    suggestions: [
      { type: 'command', value: 'git status', label: 'Check git status', desc: 'Verify clean state' },
      { type: 'skill', value: '/pr', label: 'Create PR', desc: 'Prepare for deployment' },
      { type: 'command', value: 'npm run build', label: 'Production build', desc: 'Verify build succeeds' }
    ]
  },

  learning: {
    name: 'Learning Session',
    icon: '🎓',
    signals: [
      'learn', 'understand', 'explain', 'how does', 'what is', 'why does',
      'tutorial', 'example', 'documentation', 'guide', 'help'
    ],
    minMatches: 3,
    windowMinutes: 30,
    suggestions: [
      { type: 'model', value: 'haiku', label: 'Switch to Haiku', desc: 'Quick answers, lower cost' },
      { type: 'memory', value: 'store as fact', label: 'Remember this', desc: 'Store learnings in memory' }
    ]
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// ACTIVITY LOGGING
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Log an activity event
 */
function logActivity(event) {
  const entry = {
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    ...event
  };

  fs.appendFileSync(ACTIVITY_FILE, JSON.stringify(entry) + '\n');
  return entry;
}

/**
 * Load recent activity within time window
 */
function loadRecentActivity(windowMinutes = 30) {
  if (!fs.existsSync(ACTIVITY_FILE)) return [];

  const cutoff = Date.now() - (windowMinutes * 60 * 1000);
  const lines = fs.readFileSync(ACTIVITY_FILE, 'utf8').trim().split('\n');
  const events = [];

  for (const line of lines) {
    if (!line) continue;
    try {
      const event = JSON.parse(line);
      if (event.timestamp >= cutoff) {
        events.push(event);
      }
    } catch (e) {
      // Skip malformed lines
    }
  }

  return events;
}

/**
 * Get all activity for stats
 */
function getAllActivity() {
  if (!fs.existsSync(ACTIVITY_FILE)) return [];

  const lines = fs.readFileSync(ACTIVITY_FILE, 'utf8').trim().split('\n');
  const events = [];

  for (const line of lines) {
    if (!line) continue;
    try {
      events.push(JSON.parse(line));
    } catch (e) {
      // Skip malformed lines
    }
  }

  return events;
}

// ═══════════════════════════════════════════════════════════════════════════
// PATTERN DETECTION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Check if text matches pattern signals
 */
function matchesPattern(text, pattern) {
  const lowerText = text.toLowerCase();
  let matches = 0;

  for (const signal of pattern.signals) {
    if (lowerText.includes(signal.toLowerCase())) {
      matches++;
    }
  }

  return matches;
}

/**
 * Detect active patterns from recent activity
 */
function detectPatterns(options = {}) {
  const { windowMinutes = 30 } = options;
  const recentActivity = loadRecentActivity(windowMinutes);

  if (recentActivity.length === 0) {
    return { patterns: [], activity: [] };
  }

  const detected = [];

  for (const [patternId, pattern] of Object.entries(PATTERNS)) {
    let totalMatches = 0;
    const matchingEvents = [];

    for (const event of recentActivity) {
      const text = event.query || event.content || event.message || '';
      const matches = matchesPattern(text, pattern);

      if (matches > 0) {
        totalMatches += matches;
        matchingEvents.push({
          timestamp: event.timestamp,
          text: text.slice(0, 50),
          matches
        });
      }
    }

    // Check if pattern threshold is met
    if (totalMatches >= pattern.minMatches && matchingEvents.length >= 2) {
      detected.push({
        id: patternId,
        name: pattern.name,
        icon: pattern.icon,
        confidence: Math.min(1.0, totalMatches / (pattern.minMatches * 2)),
        totalMatches,
        matchingEvents: matchingEvents.slice(-5),
        suggestions: pattern.suggestions
      });
    }
  }

  // Sort by confidence
  detected.sort((a, b) => b.confidence - a.confidence);

  // Save detected patterns
  const result = {
    detectedAt: new Date().toISOString(),
    windowMinutes,
    activityCount: recentActivity.length,
    patterns: detected
  };

  fs.writeFileSync(PATTERNS_FILE, JSON.stringify(result, null, 2));

  return result;
}

/**
 * Get proactive suggestions based on current patterns
 */
function getProactiveSuggestions(limit = 5) {
  const detection = detectPatterns();

  if (detection.patterns.length === 0) {
    return {
      hasContext: false,
      message: 'No active patterns detected',
      suggestions: []
    };
  }

  // Collect all suggestions from detected patterns
  const allSuggestions = [];

  for (const pattern of detection.patterns) {
    for (const suggestion of pattern.suggestions) {
      allSuggestions.push({
        ...suggestion,
        fromPattern: pattern.id,
        patternName: pattern.name,
        patternIcon: pattern.icon,
        confidence: pattern.confidence
      });
    }
  }

  // Deduplicate by value
  const seen = new Set();
  const unique = allSuggestions.filter(s => {
    if (seen.has(s.value)) return false;
    seen.add(s.value);
    return true;
  });

  return {
    hasContext: true,
    topPattern: detection.patterns[0],
    activityCount: detection.activityCount,
    suggestions: unique.slice(0, limit)
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// ACTIVITY STATS
// ═══════════════════════════════════════════════════════════════════════════

function getActivityStats() {
  const allActivity = getAllActivity();

  if (allActivity.length === 0) {
    return { totalEvents: 0, patterns: {}, timeRange: null };
  }

  // Count pattern occurrences
  const patternCounts = {};
  for (const event of allActivity) {
    const text = event.query || event.content || event.message || '';
    for (const [patternId, pattern] of Object.entries(PATTERNS)) {
      if (matchesPattern(text, pattern) > 0) {
        patternCounts[patternId] = (patternCounts[patternId] || 0) + 1;
      }
    }
  }

  // Time range
  const timestamps = allActivity.map(e => e.timestamp).filter(t => t);
  const oldest = Math.min(...timestamps);
  const newest = Math.max(...timestamps);

  // Hourly distribution
  const hourCounts = {};
  for (const event of allActivity) {
    if (event.datetime) {
      const hour = new Date(event.datetime).getHours();
      hourCounts[hour] = (hourCounts[hour] || 0) + 1;
    }
  }

  return {
    totalEvents: allActivity.length,
    patterns: patternCounts,
    timeRange: {
      oldest: new Date(oldest).toISOString(),
      newest: new Date(newest).toISOString(),
      durationHours: ((newest - oldest) / (1000 * 60 * 60)).toFixed(1)
    },
    hourlyDistribution: hourCounts,
    topPatterns: Object.entries(patternCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([id, count]) => ({
        id,
        name: PATTERNS[id]?.name || id,
        icon: PATTERNS[id]?.icon || '❓',
        count
      }))
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'log':
      // Log activity: node pattern-detector.js log "query text" [type]
      const query = args[1];
      const type = args[2] || 'query';
      if (!query) {
        console.error('Usage: pattern-detector.js log "query" [type]');
        process.exit(1);
      }
      const logged = logActivity({ type, query });
      console.log(JSON.stringify({ logged: true, timestamp: logged.timestamp }));
      break;

    case 'detect':
      // Detect patterns: node pattern-detector.js detect [windowMinutes]
      const window = parseInt(args[1]) || 30;
      const detection = detectPatterns({ windowMinutes: window });
      console.log(JSON.stringify(detection, null, 2));
      break;

    case 'suggest':
      // Get suggestions: node pattern-detector.js suggest [limit]
      const limit = parseInt(args[1]) || 5;
      const suggestions = getProactiveSuggestions(limit);
      console.log(JSON.stringify(suggestions, null, 2));
      break;

    case 'learned':
      // Get learned suggestions: node pattern-detector.js learned [limit]
      const learnedLimit = parseInt(args[1]) || 5;
      const learned = getLearnedSuggestions(learnedLimit);
      console.log(JSON.stringify(learned, null, 2));
      break;

    case 'stats':
      // Get stats: node pattern-detector.js stats
      console.log(JSON.stringify(getActivityStats(), null, 2));
      break;

    case 'patterns':
      // List available patterns: node pattern-detector.js patterns
      const patternList = Object.entries(PATTERNS).map(([id, p]) => ({
        id,
        name: p.name,
        icon: p.icon,
        signals: p.signals.slice(0, 5).join(', ') + '...',
        suggestionCount: p.suggestions.length
      }));
      console.log(JSON.stringify(patternList, null, 2));
      break;

    case 'clear':
      // Clear activity log: node pattern-detector.js clear
      if (fs.existsSync(ACTIVITY_FILE)) {
        const backup = ACTIVITY_FILE + '.' + Date.now();
        fs.renameSync(ACTIVITY_FILE, backup);
        console.log(`Activity cleared. Backup: ${backup}`);
      } else {
        console.log('No activity to clear');
      }
      break;

    default:
      console.log('Pattern Detector - ProactiveVA Implementation');
      console.log('');
      console.log('Commands:');
      console.log('  log "query" [type]      - Log an activity event');
      console.log('  detect [windowMinutes]  - Detect active patterns');
      console.log('  suggest [limit]         - Get proactive suggestions');
      console.log('  stats                   - View activity statistics');
      console.log('  patterns                - List available patterns');
      console.log('  clear                   - Clear activity log');
      console.log('');
      console.log('Patterns detected:');
      for (const [id, p] of Object.entries(PATTERNS)) {
        console.log(`  ${p.icon} ${p.name} (${p.signals.length} signals)`);
      }
  }
}

module.exports = {
  logActivity,
  loadRecentActivity,
  detectPatterns,
  getProactiveSuggestions,
  getActivityStats,
  // Co-evolution integration
  applyLearnedPatterns,
  getLearnedSuggestions,
  notifyCoEvolution,
  loadCoevoConfig,
  PATTERNS
};
