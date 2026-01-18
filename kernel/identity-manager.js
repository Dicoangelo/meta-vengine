#!/usr/bin/env node
/**
 * Identity Manager - Sovereign AI Identity System
 *
 * Based on: "Sovereign AI Agents: Self-Sovereign Experiential AI"
 * arXiv: https://arxiv.org/abs/2505.14893
 *
 * Implements:
 * - DID-based sovereign identity
 * - Expertise tracking with confidence learning
 * - Experience logging and milestone tracking
 * - Statistics aggregation across all kernel components
 * - Preference learning from usage patterns
 */

const fs = require('fs');
const path = require('path');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const KERNEL_DIR = path.join(process.env.HOME, '.claude', 'kernel');
const DATA_DIR = path.join(process.env.HOME, '.claude', 'data');
const IDENTITY_FILE = path.join(KERNEL_DIR, 'identity.json');
const EXPERIENCE_LOG = path.join(KERNEL_DIR, 'experience-log.jsonl');
const MEMORY_GRAPH = path.join(KERNEL_DIR, 'memory-graph.json');
const DQ_SCORES = path.join(KERNEL_DIR, 'dq-scores.jsonl');
const ACTIVITY_EVENTS = path.join(DATA_DIR, 'activity-events.jsonl');

// Expertise domains and their signal keywords
const EXPERTISE_SIGNALS = {
  'react': ['react', 'jsx', 'component', 'hook', 'useState', 'useEffect', 'props'],
  'typescript': ['typescript', 'type', 'interface', 'generic', 'ts', 'tsx'],
  'node': ['node', 'npm', 'express', 'server', 'backend', 'api'],
  'python': ['python', 'pip', 'django', 'flask', 'pandas', 'numpy'],
  'ai-agents': ['agent', 'llm', 'prompt', 'claude', 'gpt', 'model', 'ai'],
  'research': ['arxiv', 'paper', 'study', 'research', 'methodology'],
  'devops': ['docker', 'kubernetes', 'ci', 'cd', 'deploy', 'pipeline'],
  'database': ['sql', 'postgres', 'mongodb', 'supabase', 'query', 'schema'],
  'testing': ['test', 'spec', 'vitest', 'jest', 'coverage', 'mock'],
  'architecture': ['architecture', 'design', 'pattern', 'system', 'structure']
};

// Achievement definitions
const ACHIEVEMENTS = {
  'first-query': { name: 'First Query', desc: 'Made your first DQ-routed query', threshold: 1 },
  'memory-master': { name: 'Memory Master', desc: 'Stored 50+ memories', threshold: 50 },
  'link-builder': { name: 'Link Builder', desc: 'Created 20+ memory links', threshold: 20 },
  'token-saver': { name: 'Token Saver', desc: 'Saved 10,000+ tokens', threshold: 10000 },
  'pattern-detector': { name: 'Pattern Detector', desc: 'Detected 10+ activity patterns', threshold: 10 },
  'opus-thinker': { name: 'Opus Thinker', desc: 'Used Opus for 10+ complex queries', threshold: 10 },
  'efficiency-expert': { name: 'Efficiency Expert', desc: 'Maintained DQ score > 0.8', threshold: 0.8 },
  'session-veteran': { name: 'Session Veteran', desc: 'Completed 100+ sessions', threshold: 100 }
};

// ═══════════════════════════════════════════════════════════════════════════
// IDENTITY OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════

function loadIdentity() {
  if (fs.existsSync(IDENTITY_FILE)) {
    return JSON.parse(fs.readFileSync(IDENTITY_FILE, 'utf8'));
  }
  return null;
}

function saveIdentity(identity) {
  identity.lastUpdated = new Date().toISOString();
  fs.writeFileSync(IDENTITY_FILE, JSON.stringify(identity, null, 2));
}

function initializeIdentity(owner = 'user') {
  const did = `did:claude:${owner}-sovereign-${Date.now().toString(36)}`;

  const identity = {
    did,
    version: '1.0.0',
    created: new Date().toISOString(),
    lastUpdated: new Date().toISOString(),
    profile: {
      owner,
      organization: '',
      instanceName: 'Sovereign Terminal OS',
      purpose: 'Agentic development assistant'
    },
    preferences: {
      defaultModel: 'sonnet',
      autoRoute: true,
      proactiveAssist: true,
      memoryEvolution: true,
      tokenOptimization: true,
      costAwareness: 'medium',
      verbosity: 'concise'
    },
    expertise: { domains: [], confidence: {} },
    statistics: {
      totalSessions: 0,
      totalQueries: 0,
      totalTokens: 0,
      avgDQScore: 0,
      tokensSaved: 0,
      patternsDetected: {},
      modelUsage: { haiku: 0, sonnet: 0, opus: 0 },
      skillsUsed: {},
      topKeywords: []
    },
    memory: { totalNotes: 0, totalLinks: 0, topTopics: [] },
    experience: { milestones: [], achievements: [], learnings: [] }
  };

  saveIdentity(identity);
  logExperience('identity_created', { did });

  return identity;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPERIENCE LOGGING
// ═══════════════════════════════════════════════════════════════════════════

function logExperience(type, data = {}) {
  const entry = {
    timestamp: Date.now(),
    datetime: new Date().toISOString(),
    type,
    ...data
  };

  fs.appendFileSync(EXPERIENCE_LOG, JSON.stringify(entry) + '\n');
  return entry;
}

function getExperienceLog(options = {}) {
  const { limit = 50, type = null } = options;

  if (!fs.existsSync(EXPERIENCE_LOG)) return [];

  const lines = fs.readFileSync(EXPERIENCE_LOG, 'utf8').trim().split('\n');
  let entries = [];

  for (const line of lines) {
    if (!line) continue;
    try {
      const entry = JSON.parse(line);
      if (type && entry.type !== type) continue;
      entries.push(entry);
    } catch (e) {
      // Skip malformed
    }
  }

  return entries.slice(-limit);
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPERTISE LEARNING
// ═══════════════════════════════════════════════════════════════════════════

function detectExpertise(text) {
  const lowerText = text.toLowerCase();
  const detected = {};

  for (const [domain, signals] of Object.entries(EXPERTISE_SIGNALS)) {
    let matches = 0;
    for (const signal of signals) {
      if (lowerText.includes(signal)) matches++;
    }
    if (matches > 0) {
      detected[domain] = matches / signals.length;
    }
  }

  return detected;
}

function updateExpertise(identity, newExpertise) {
  const LEARNING_RATE = 0.1;

  for (const [domain, score] of Object.entries(newExpertise)) {
    const currentScore = identity.expertise.confidence[domain] || 0;
    // Exponential moving average
    identity.expertise.confidence[domain] =
      currentScore + LEARNING_RATE * (score - currentScore);

    // Add to domains if new
    if (!identity.expertise.domains.includes(domain)) {
      identity.expertise.domains.push(domain);
    }
  }

  // Sort domains by confidence
  identity.expertise.domains.sort((a, b) =>
    (identity.expertise.confidence[b] || 0) - (identity.expertise.confidence[a] || 0)
  );

  identity.expertise.lastUpdated = new Date().toISOString();
}

function learnFromQuery(query, model, dqScore) {
  const identity = loadIdentity();
  if (!identity) return null;

  // Detect expertise from query
  const expertise = detectExpertise(query);
  if (Object.keys(expertise).length > 0) {
    updateExpertise(identity, expertise);
  }

  // Update statistics
  identity.statistics.totalQueries++;
  identity.statistics.modelUsage[model] =
    (identity.statistics.modelUsage[model] || 0) + 1;

  // Update average DQ score
  const totalQueries = identity.statistics.totalQueries;
  identity.statistics.avgDQScore =
    ((identity.statistics.avgDQScore * (totalQueries - 1)) + dqScore) / totalQueries;

  saveIdentity(identity);
  return identity;
}

// ═══════════════════════════════════════════════════════════════════════════
// STATISTICS AGGREGATION
// ═══════════════════════════════════════════════════════════════════════════

function aggregateStats() {
  const identity = loadIdentity();
  if (!identity) return null;

  // Aggregate from memory graph
  if (fs.existsSync(MEMORY_GRAPH)) {
    try {
      const graph = JSON.parse(fs.readFileSync(MEMORY_GRAPH, 'utf8'));
      identity.memory.totalNotes = Object.keys(graph.notes || {}).length;
      identity.memory.totalLinks = (graph.links || []).length;
      identity.memory.topTopics = (graph.metadata?.topKeywords || [])
        .slice(0, 10)
        .map(k => k.keyword);
    } catch (e) {}
  }

  // Aggregate from DQ scores
  if (fs.existsSync(DQ_SCORES)) {
    try {
      const lines = fs.readFileSync(DQ_SCORES, 'utf8').trim().split('\n');
      let totalDQ = 0;
      let count = 0;

      for (const line of lines) {
        if (!line) continue;
        try {
          const entry = JSON.parse(line);
          if (entry.score) {
            totalDQ += entry.score;
            count++;
          }
        } catch (e) {}
      }

      if (count > 0) {
        identity.statistics.avgDQScore = totalDQ / count;
        identity.statistics.totalQueries = count;
      }
    } catch (e) {}
  }

  // Aggregate from activity events
  if (fs.existsSync(ACTIVITY_EVENTS)) {
    try {
      const lines = fs.readFileSync(ACTIVITY_EVENTS, 'utf8').trim().split('\n');
      const keywords = {};
      const patterns = {};

      for (const line of lines) {
        if (!line) continue;
        try {
          const event = JSON.parse(line);

          // Count model usage
          if (event.model) {
            identity.statistics.modelUsage[event.model] =
              (identity.statistics.modelUsage[event.model] || 0) + 1;
          }

          // Extract keywords
          if (event.query) {
            const words = event.query.toLowerCase().split(/\s+/);
            for (const word of words) {
              if (word.length > 3) {
                keywords[word] = (keywords[word] || 0) + 1;
              }
            }
          }
        } catch (e) {}
      }

      // Top keywords
      identity.statistics.topKeywords = Object.entries(keywords)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20)
        .map(([word, count]) => ({ word, count }));

    } catch (e) {}
  }

  saveIdentity(identity);
  return identity;
}

// ═══════════════════════════════════════════════════════════════════════════
// ACHIEVEMENTS
// ═══════════════════════════════════════════════════════════════════════════

function checkAchievements() {
  const identity = loadIdentity();
  if (!identity) return [];

  const newAchievements = [];
  const earned = identity.experience.achievements.map(a => a.id);

  // Check each achievement
  for (const [id, def] of Object.entries(ACHIEVEMENTS)) {
    if (earned.includes(id)) continue;

    let unlocked = false;

    switch (id) {
      case 'first-query':
        unlocked = identity.statistics.totalQueries >= def.threshold;
        break;
      case 'memory-master':
        unlocked = identity.memory.totalNotes >= def.threshold;
        break;
      case 'link-builder':
        unlocked = identity.memory.totalLinks >= def.threshold;
        break;
      case 'token-saver':
        unlocked = identity.statistics.tokensSaved >= def.threshold;
        break;
      case 'opus-thinker':
        unlocked = (identity.statistics.modelUsage.opus || 0) >= def.threshold;
        break;
      case 'efficiency-expert':
        unlocked = identity.statistics.avgDQScore >= def.threshold;
        break;
      case 'session-veteran':
        unlocked = identity.statistics.totalSessions >= def.threshold;
        break;
    }

    if (unlocked) {
      const achievement = {
        id,
        name: def.name,
        desc: def.desc,
        unlockedAt: new Date().toISOString()
      };
      identity.experience.achievements.push(achievement);
      newAchievements.push(achievement);
      logExperience('achievement_unlocked', { achievement: id, name: def.name });
    }
  }

  if (newAchievements.length > 0) {
    saveIdentity(identity);
  }

  return newAchievements;
}

// ═══════════════════════════════════════════════════════════════════════════
// PREFERENCE LEARNING
// ═══════════════════════════════════════════════════════════════════════════

function updatePreference(key, value) {
  const identity = loadIdentity();
  if (!identity) return null;

  identity.preferences[key] = value;
  saveIdentity(identity);
  logExperience('preference_updated', { key, value });

  return identity.preferences;
}

function learnPreferences() {
  const identity = loadIdentity();
  if (!identity) return null;

  // Learn default model from usage patterns
  const usage = identity.statistics.modelUsage;
  const totalUsage = usage.haiku + usage.sonnet + usage.opus;

  if (totalUsage > 10) {
    // If using haiku > 50%, prefer cost efficiency
    if (usage.haiku / totalUsage > 0.5) {
      identity.preferences.costAwareness = 'high';
    }
    // If using opus > 30%, prefer quality
    else if (usage.opus / totalUsage > 0.3) {
      identity.preferences.costAwareness = 'low';
    }
  }

  saveIdentity(identity);
  return identity.preferences;
}

// ═══════════════════════════════════════════════════════════════════════════
// IDENTITY CARD
// ═══════════════════════════════════════════════════════════════════════════

function getIdentityCard() {
  const identity = aggregateStats();
  if (!identity) return null;

  // Check for new achievements
  const newAchievements = checkAchievements();

  return {
    did: identity.did,
    profile: identity.profile,
    expertise: {
      top: identity.expertise.domains.slice(0, 5),
      confidence: Object.fromEntries(
        identity.expertise.domains.slice(0, 5).map(d =>
          [d, (identity.expertise.confidence[d] * 100).toFixed(0) + '%']
        )
      )
    },
    stats: {
      queries: identity.statistics.totalQueries,
      avgDQ: identity.statistics.avgDQScore.toFixed(2),
      memories: identity.memory.totalNotes,
      links: identity.memory.totalLinks,
      tokensSaved: identity.statistics.tokensSaved
    },
    achievements: {
      total: identity.experience.achievements.length,
      recent: identity.experience.achievements.slice(-3),
      new: newAchievements
    },
    modelBreakdown: identity.statistics.modelUsage,
    topKeywords: identity.statistics.topKeywords.slice(0, 5),
    preferences: identity.preferences
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'init':
      // Initialize identity: node identity-manager.js init [owner]
      const owner = args[1] || 'user';
      const newId = initializeIdentity(owner);
      console.log(`Identity created: ${newId.did}`);
      break;

    case 'card':
      // Get identity card: node identity-manager.js card
      const card = getIdentityCard();
      if (card) {
        console.log(JSON.stringify(card, null, 2));
      } else {
        console.log('No identity found. Run: node identity-manager.js init');
      }
      break;

    case 'learn':
      // Learn from query: node identity-manager.js learn "query" [model] [dqScore]
      const query = args[1];
      const model = args[2] || 'sonnet';
      const dqScore = parseFloat(args[3]) || 0.7;
      if (!query) {
        console.error('Usage: identity-manager.js learn "query" [model] [dqScore]');
        process.exit(1);
      }
      learnFromQuery(query, model, dqScore);
      console.log('Learned from query');
      break;

    case 'expertise':
      // Get expertise: node identity-manager.js expertise
      const id = loadIdentity();
      if (id) {
        console.log(JSON.stringify({
          domains: id.expertise.domains,
          confidence: id.expertise.confidence
        }, null, 2));
      }
      break;

    case 'achievements':
      // Check achievements: node identity-manager.js achievements
      const achievements = checkAchievements();
      const identity = loadIdentity();
      console.log(JSON.stringify({
        total: identity?.experience.achievements.length || 0,
        all: identity?.experience.achievements || [],
        new: achievements
      }, null, 2));
      break;

    case 'aggregate':
      // Aggregate stats: node identity-manager.js aggregate
      const aggregated = aggregateStats();
      console.log(JSON.stringify({
        queries: aggregated?.statistics.totalQueries,
        avgDQ: aggregated?.statistics.avgDQScore,
        memories: aggregated?.memory.totalNotes,
        modelUsage: aggregated?.statistics.modelUsage
      }, null, 2));
      break;

    case 'pref':
      // Update preference: node identity-manager.js pref key value
      const prefKey = args[1];
      const prefValue = args[2];
      if (!prefKey || !prefValue) {
        console.error('Usage: identity-manager.js pref key value');
        process.exit(1);
      }
      updatePreference(prefKey, prefValue);
      console.log(`Preference updated: ${prefKey} = ${prefValue}`);
      break;

    case 'experience':
      // Get experience log: node identity-manager.js experience [limit]
      const limit = parseInt(args[1]) || 20;
      console.log(JSON.stringify(getExperienceLog({ limit }), null, 2));
      break;

    default:
      console.log('Identity Manager - Sovereign AI Identity System');
      console.log('');
      console.log('Commands:');
      console.log('  init [owner]                    - Initialize new identity');
      console.log('  card                            - Get identity card');
      console.log('  learn "query" [model] [dqScore] - Learn from query');
      console.log('  expertise                       - View expertise domains');
      console.log('  achievements                    - Check achievements');
      console.log('  aggregate                       - Aggregate all stats');
      console.log('  pref key value                  - Update preference');
      console.log('  experience [limit]              - View experience log');
      console.log('');
      console.log('DID: Decentralized Identifier for sovereign identity');
  }
}

module.exports = {
  loadIdentity,
  saveIdentity,
  initializeIdentity,
  logExperience,
  learnFromQuery,
  detectExpertise,
  updateExpertise,
  aggregateStats,
  checkAchievements,
  updatePreference,
  getIdentityCard,
  EXPERTISE_SIGNALS,
  ACHIEVEMENTS
};
