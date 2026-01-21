#!/usr/bin/env node
/**
 * Error Tracker for Claude Code
 * Automatically detects, categorizes, and logs errors to ERRORS.md
 *
 * Usage:
 *   node error-tracker.js log "context" "error message" "cause" "fix"
 *   node error-tracker.js scan [--session <id>]
 *   node error-tracker.js analyze
 *   node error-tracker.js stats
 */

const fs = require('fs');
const path = require('path');

const CLAUDE_DIR = path.join(process.env.HOME, '.claude');
const ERRORS_FILE = path.join(CLAUDE_DIR, 'ERRORS.md');
const ERROR_LOG = path.join(CLAUDE_DIR, 'data', 'errors.jsonl');
const ACTIVITY_LOG = path.join(CLAUDE_DIR, 'activity.log');
const TOOL_USAGE_LOG = path.join(CLAUDE_DIR, 'data', 'tool-usage.jsonl');

// Error patterns to detect
const ERROR_PATTERNS = [
  { pattern: /error:/i, category: 'general', severity: 'medium' },
  { pattern: /failed/i, category: 'failure', severity: 'medium' },
  { pattern: /permission denied/i, category: 'permissions', severity: 'high' },
  { pattern: /not found/i, category: 'missing', severity: 'low' },
  { pattern: /ENOENT/i, category: 'file_not_found', severity: 'medium' },
  { pattern: /EACCES/i, category: 'permissions', severity: 'high' },
  { pattern: /timeout/i, category: 'timeout', severity: 'medium' },
  { pattern: /syntax error/i, category: 'syntax', severity: 'high' },
  { pattern: /type error/i, category: 'type', severity: 'high' },
  { pattern: /reference error/i, category: 'reference', severity: 'high' },
  { pattern: /npm ERR!/i, category: 'npm', severity: 'medium' },
  { pattern: /git.*fatal/i, category: 'git', severity: 'high' },
  { pattern: /command not found/i, category: 'missing_command', severity: 'medium' },
  { pattern: /CORS/i, category: 'cors', severity: 'medium' },
  { pattern: /401|403|404|500|502|503/i, category: 'http', severity: 'medium' },
  { pattern: /segmentation fault/i, category: 'crash', severity: 'critical' },
  { pattern: /out of memory/i, category: 'memory', severity: 'critical' },
  { pattern: /\bOOM\b/, category: 'memory', severity: 'critical' },  // \b for word boundary, not "Bloom"
  { pattern: /maximum call stack/i, category: 'recursion', severity: 'high' },
];

// Cost-related error patterns
const COST_PATTERNS = [
  { pattern: /opus.*simple|haiku.*complex/i, category: 'model_mismatch', severity: 'low' },
  { pattern: /context.*too large|token limit/i, category: 'context_overflow', severity: 'medium' },
];

function ensureDir(filepath) {
  const dir = path.dirname(filepath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function getDate() {
  return new Date().toISOString().split('T')[0];
}

function getTimestamp() {
  return new Date().toISOString();
}

function detectErrorCategory(errorText) {
  const allPatterns = [...ERROR_PATTERNS, ...COST_PATTERNS];
  for (const { pattern, category, severity } of allPatterns) {
    if (pattern.test(errorText)) {
      return { category, severity };
    }
  }
  return { category: 'unknown', severity: 'low' };
}

function logErrorToJsonl(error) {
  ensureDir(ERROR_LOG);
  const entry = {
    ts: Date.now(),
    timestamp: getTimestamp(),
    ...error
  };
  fs.appendFileSync(ERROR_LOG, JSON.stringify(entry) + '\n');
}

function appendToErrorsMd(error) {
  const { context, message, cause, fix, prevention, category, severity } = error;
  const date = getDate();

  let content = fs.readFileSync(ERRORS_FILE, 'utf-8');

  // Find the "## Patterns to Watch" section to insert before it
  const insertPoint = content.indexOf('## Patterns to Watch');

  const newEntry = `
## ${date} - ${context}
**Category:** ${category} | **Severity:** ${severity}
**Context:** ${context}
**Error:** ${message}
**Root Cause:** ${cause || 'Under investigation'}
**Fix:** ${fix || 'Pending'}
**Prevention:** ${prevention || 'TBD'}

---
`;

  if (insertPoint > 0) {
    content = content.slice(0, insertPoint) + newEntry + content.slice(insertPoint);
  } else {
    // Append to end if section not found
    content += newEntry;
  }

  fs.writeFileSync(ERRORS_FILE, content);
}

function updateStats() {
  if (!fs.existsSync(ERROR_LOG)) return;

  const lines = fs.readFileSync(ERROR_LOG, 'utf-8').trim().split('\n').filter(Boolean);
  const errors = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

  const month = new Date().toISOString().slice(0, 7).replace('-', ' ');
  const monthErrors = errors.filter(e => e.timestamp && e.timestamp.startsWith(new Date().toISOString().slice(0, 7)));

  // Count repeated errors (same category within the month)
  const categoryCounts = {};
  monthErrors.forEach(e => {
    categoryCounts[e.category] = (categoryCounts[e.category] || 0) + 1;
  });
  const repeated = Object.values(categoryCounts).filter(c => c > 1).length;

  const total = monthErrors.length;
  const preventionRate = total > 0 ? Math.round(((total - repeated) / total) * 100) : 100;

  // Update the stats table in ERRORS.md
  let content = fs.readFileSync(ERRORS_FILE, 'utf-8');
  const statsRegex = /\| Jan 2026 \| \d+ \| \d+ \| [\d-]+% \|/;
  const newStats = `| Jan 2026 | ${total} | ${repeated} | ${preventionRate}% |`;

  if (statsRegex.test(content)) {
    content = content.replace(statsRegex, newStats);
  }

  fs.writeFileSync(ERRORS_FILE, content);
}

function scanRecentActivity() {
  const errors = [];

  // Scan activity log for recent errors
  if (fs.existsSync(ACTIVITY_LOG)) {
    const lines = fs.readFileSync(ACTIVITY_LOG, 'utf-8').split('\n').slice(-100);
    for (const line of lines) {
      const { category, severity } = detectErrorCategory(line);
      if (category !== 'unknown' && severity !== 'low') {
        errors.push({
          source: 'activity_log',
          line,
          category,
          severity
        });
      }
    }
  }

  return errors;
}

function printStats() {
  if (!fs.existsSync(ERROR_LOG)) {
    console.log('No errors logged yet.');
    return;
  }

  const lines = fs.readFileSync(ERROR_LOG, 'utf-8').trim().split('\n').filter(Boolean);
  const errors = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

  const categoryCounts = {};
  const severityCounts = { critical: 0, high: 0, medium: 0, low: 0 };

  errors.forEach(e => {
    categoryCounts[e.category] = (categoryCounts[e.category] || 0) + 1;
    if (e.severity) severityCounts[e.severity]++;
  });

  console.log('\n=== Error Statistics ===');
  console.log(`Total errors: ${errors.length}`);
  console.log('\nBy Category:');
  Object.entries(categoryCounts)
    .sort((a, b) => b[1] - a[1])
    .forEach(([cat, count]) => console.log(`  ${cat}: ${count}`));
  console.log('\nBy Severity:');
  Object.entries(severityCounts)
    .filter(([_, count]) => count > 0)
    .forEach(([sev, count]) => console.log(`  ${sev}: ${count}`));
}

// Main CLI
const [,, command, ...args] = process.argv;

switch (command) {
  case 'log': {
    const [context, message, cause, fix, prevention] = args;
    if (!context || !message) {
      console.error('Usage: error-tracker.js log "context" "error message" ["cause"] ["fix"] ["prevention"]');
      process.exit(1);
    }
    const { category, severity } = detectErrorCategory(message);
    const error = { context, message, cause, fix, prevention, category, severity };

    logErrorToJsonl(error);
    appendToErrorsMd(error);
    updateStats();

    console.log(`Logged ${severity} ${category} error: ${context}`);
    break;
  }

  case 'scan': {
    const errors = scanRecentActivity();
    if (errors.length === 0) {
      console.log('No errors detected in recent activity.');
    } else {
      console.log(`Found ${errors.length} potential errors:`);
      errors.forEach(e => console.log(`  [${e.severity}] ${e.category}: ${e.line.slice(0, 80)}...`));
    }
    break;
  }

  case 'analyze': {
    // Analyze patterns and suggest preventions
    if (!fs.existsSync(ERROR_LOG)) {
      console.log('No error data to analyze.');
      break;
    }

    const lines = fs.readFileSync(ERROR_LOG, 'utf-8').trim().split('\n').filter(Boolean);
    const errors = lines.map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);

    const categoryCounts = {};
    errors.forEach(e => {
      categoryCounts[e.category] = (categoryCounts[e.category] || 0) + 1;
    });

    console.log('\n=== Error Analysis ===');
    const topCategories = Object.entries(categoryCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    topCategories.forEach(([cat, count]) => {
      console.log(`\n${cat} (${count} occurrences):`);
      switch (cat) {
        case 'file_not_found':
          console.log('  → Always verify file paths before operations');
          break;
        case 'permissions':
          console.log('  → Check file permissions, consider sudo or chmod');
          break;
        case 'git':
          console.log('  → Run git status before destructive operations');
          break;
        case 'npm':
          console.log('  → Clear node_modules and reinstall on persistent issues');
          break;
        case 'type':
          console.log('  → Run typecheck before commits');
          break;
        default:
          console.log('  → Review error context for patterns');
      }
    });
    break;
  }

  case 'stats': {
    printStats();
    break;
  }

  case 'detect': {
    // Called by hooks with tool output
    const errorText = args.join(' ');
    const { category, severity } = detectErrorCategory(errorText);

    if (category !== 'unknown' && (severity === 'high' || severity === 'critical')) {
      const error = {
        context: 'Auto-detected from tool output',
        message: errorText.slice(0, 500),
        category,
        severity,
        auto: true
      };
      logErrorToJsonl(error);
      console.log(`AUTO-LOGGED: [${severity}] ${category}`);
    }
    break;
  }

  default:
    console.log(`
Error Tracker - Automated error logging for Claude Code

Commands:
  log "context" "message" ["cause"] ["fix"]  - Log an error manually
  scan                                        - Scan recent activity for errors
  analyze                                     - Analyze error patterns
  stats                                       - Show error statistics
  detect "text"                               - Auto-detect errors (used by hooks)
`);
}
