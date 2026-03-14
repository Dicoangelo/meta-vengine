#!/usr/bin/env node
/**
 * US-003: IRT Difficulty Integration — Tests
 *
 * Tests the cross-runtime bridge (Python HSRGS → Node.js DQ scorer)
 * and the IRT_MOD modifier stacking in routing decisions.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// Resolve from kernel/ directory for correct require paths
process.chdir(path.join(__dirname, '..'));

const { loadIRTBridge, computeIRTModifier, route } = require(path.join(__dirname, '..', 'dq-scorer'));

const IRT_BRIDGE_PATH = path.join(process.env.HOME, '.claude/kernel/hsrgs/irt-bridge.json');

let passed = 0;
let failed = 0;
let total = 0;

function assert(condition, msg) {
  total++;
  if (condition) {
    passed++;
    console.log(`  ✓ ${msg}`);
  } else {
    failed++;
    console.error(`  ✗ ${msg}`);
  }
}

function assertClose(actual, expected, epsilon, msg) {
  assert(Math.abs(actual - expected) < epsilon, `${msg} (got ${actual}, expected ~${expected})`);
}

// Save original bridge file if it exists
let originalBridge = null;
if (fs.existsSync(IRT_BRIDGE_PATH)) {
  originalBridge = fs.readFileSync(IRT_BRIDGE_PATH, 'utf8');
}

function writeBridge(data) {
  const dir = path.dirname(IRT_BRIDGE_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(IRT_BRIDGE_PATH, JSON.stringify(data, null, 2));
}

function cleanup() {
  // Restore original bridge file
  if (originalBridge !== null) {
    fs.writeFileSync(IRT_BRIDGE_PATH, originalBridge);
  } else if (fs.existsSync(IRT_BRIDGE_PATH)) {
    fs.unlinkSync(IRT_BRIDGE_PATH);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// TEST SUITE: computeIRTModifier
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n=== computeIRTModifier ===\n');

// High difficulty tests
assert(computeIRTModifier(1.0) > 0, 'difficulty=1.0 → positive modifier');
assertClose(computeIRTModifier(1.0), 0.15, 0.001, 'difficulty=1.0 → +0.15');
assertClose(computeIRTModifier(0.85), 0.075, 0.001, 'difficulty=0.85 → +0.075');
assert(computeIRTModifier(0.7) === 0.0, 'difficulty=0.7 → 0.0 (boundary)');

// Low difficulty tests
assert(computeIRTModifier(0.0) < 0, 'difficulty=0.0 → negative modifier');
assertClose(computeIRTModifier(0.0), -0.15, 0.001, 'difficulty=0.0 → -0.15');
assertClose(computeIRTModifier(0.15), -0.075, 0.001, 'difficulty=0.15 → -0.075');
assert(computeIRTModifier(0.3) === 0.0, 'difficulty=0.3 → 0.0 (boundary)');

// Mid-range tests (no effect)
assert(computeIRTModifier(0.5) === 0.0, 'difficulty=0.5 → 0.0 (mid-range)');
assert(computeIRTModifier(0.4) === 0.0, 'difficulty=0.4 → 0.0');
assert(computeIRTModifier(0.6) === 0.0, 'difficulty=0.6 → 0.0');

// Edge cases
assert(computeIRTModifier(null) === 0.0, 'null → 0.0 (fallback)');
assert(computeIRTModifier(undefined) === 0.0, 'undefined → 0.0 (fallback)');
assert(computeIRTModifier(NaN) === 0.0, 'NaN → 0.0 (fallback)');
assert(computeIRTModifier('string') === 0.0, 'string → 0.0 (fallback)');
assertClose(computeIRTModifier(1.5), 0.15, 0.001, 'difficulty=1.5 clamped to 1.0 → +0.15');
assertClose(computeIRTModifier(-0.5), -0.15, 0.001, 'difficulty=-0.5 clamped to 0.0 → -0.15');

// Monotonicity: higher difficulty → higher (or equal) modifier
const diffs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0];
const mods = diffs.map(d => computeIRTModifier(d));
let monotonic = true;
for (let i = 1; i < mods.length; i++) {
  if (mods[i] < mods[i - 1]) { monotonic = false; break; }
}
assert(monotonic, 'modifier is monotonically non-decreasing with difficulty');

// ═══════════════════════════════════════════════════════════════════════════
// TEST SUITE: loadIRTBridge
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n=== loadIRTBridge ===\n');

// Fresh bridge data
const queryHash = crypto.createHash('md5').update('test query').digest('hex');
writeBridge({
  query_hash: queryHash,
  difficulty: 0.82,
  discrimination: 0.45,
  domain_signature: 'abc12345',
  irt_predictions: { opus: 0.95, sonnet: 0.78, haiku: 0.45 },
  selected_model: 'opus',
  timestamp: Date.now()
});

const bridge = loadIRTBridge();
assert(bridge !== null, 'fresh bridge data loads successfully');
assertClose(bridge.difficulty, 0.82, 0.001, 'difficulty read correctly');
assertClose(bridge.discrimination, 0.45, 0.001, 'discrimination read correctly');
assert(bridge.domain_signature === 'abc12345', 'domain_signature read correctly');
assert(bridge.irt_predictions.opus === 0.95, 'IRT predictions read correctly');

// Query hash matching
const matchedBridge = loadIRTBridge(queryHash);
assert(matchedBridge !== null, 'bridge loads when query hash matches');

const unmatchedBridge = loadIRTBridge('wrong_hash');
assert(unmatchedBridge === null, 'bridge returns null when query hash does not match');

// Stale bridge data (> 60 seconds old)
writeBridge({
  query_hash: queryHash,
  difficulty: 0.82,
  discrimination: 0.45,
  domain_signature: 'abc12345',
  irt_predictions: {},
  selected_model: 'opus',
  timestamp: Date.now() - 120000 // 2 minutes ago
});
const staleBridge = loadIRTBridge();
assert(staleBridge === null, 'stale bridge data (>60s) returns null');

// Missing bridge file
if (fs.existsSync(IRT_BRIDGE_PATH)) fs.unlinkSync(IRT_BRIDGE_PATH);
const missingBridge = loadIRTBridge();
assert(missingBridge === null, 'missing bridge file returns null');

// Invalid JSON
writeBridge({ difficulty: 'not-a-number', timestamp: Date.now() });
const invalidBridge = loadIRTBridge();
assert(invalidBridge === null, 'invalid difficulty type returns null');

// ═══════════════════════════════════════════════════════════════════════════
// TEST SUITE: Integration — IRT modifier in routing
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n=== Integration: IRT in routing ===\n');

// Test 1: High difficulty query → should bias toward more capable model
const highDiffQuery = 'design distributed fault-tolerant architecture for multi-region deployment with consistency guarantees';
const highDiffHash = crypto.createHash('md5').update(highDiffQuery).digest('hex');
writeBridge({
  query_hash: highDiffHash,
  difficulty: 0.92,
  discrimination: 0.7,
  domain_signature: 'highd123',
  irt_predictions: { opus: 0.95, sonnet: 0.55, haiku: 0.20 },
  selected_model: 'opus',
  timestamp: Date.now()
});

const highResult = route(highDiffQuery);
assert(highResult.model === 'opus' || highResult.model === 'sonnet',
  `high IRT difficulty (0.92) routes to capable model (got: ${highResult.model})`);

// Test 2: Low difficulty query → should bias toward cheaper model
const lowDiffQuery = 'hello how are you';
const lowDiffHash = crypto.createHash('md5').update(lowDiffQuery).digest('hex');
writeBridge({
  query_hash: lowDiffHash,
  difficulty: 0.08,
  discrimination: 0.1,
  domain_signature: 'lowd1234',
  irt_predictions: { opus: 0.99, sonnet: 0.97, haiku: 0.90 },
  selected_model: 'haiku',
  timestamp: Date.now()
});

const lowResult = route(lowDiffQuery);
assert(lowResult.model === 'haiku' || lowResult.model === 'sonnet',
  `low IRT difficulty (0.08) routes to cheaper model (got: ${lowResult.model})`);

// Test 3: No bridge data → graceful degradation (same routing as before)
if (fs.existsSync(IRT_BRIDGE_PATH)) fs.unlinkSync(IRT_BRIDGE_PATH);
const noBridgeResult = route('explain python decorators');
assert(noBridgeResult.model !== undefined, 'routes successfully without IRT bridge data');
assert(noBridgeResult.dq.score > 0, 'DQ score is positive without IRT data');

// Test 4: IRT data logged in decision record
writeBridge({
  query_hash: crypto.createHash('md5').update('test irt logging query').digest('hex'),
  difficulty: 0.65,
  discrimination: 0.5,
  domain_signature: 'logtest1',
  irt_predictions: { opus: 0.9, sonnet: 0.7, haiku: 0.4 },
  selected_model: 'sonnet',
  timestamp: Date.now()
});

route('test irt logging query');
// Read the last logged decision
const historyPath = path.join(process.env.HOME, '.claude/kernel/dq-scores.jsonl');
const lines = fs.readFileSync(historyPath, 'utf8').split('\n').filter(l => l.trim());
const lastDecision = JSON.parse(lines[lines.length - 1]);
assert(lastDecision.irt !== null && lastDecision.irt !== undefined,
  'IRT data logged in decision record when bridge available');
assert(lastDecision.irt.source === 'hsrgs-bridge', 'IRT source is hsrgs-bridge');
assertClose(lastDecision.irt.difficulty, 0.65, 0.001, 'IRT difficulty logged correctly');

// ═══════════════════════════════════════════════════════════════════════════
// CLEANUP & SUMMARY
// ═══════════════════════════════════════════════════════════════════════════

cleanup();

console.log(`\n${'═'.repeat(50)}`);
console.log(`Results: ${passed}/${total} passed, ${failed} failed`);
console.log(`${'═'.repeat(50)}\n`);

if (failed > 0) {
  process.exit(1);
}
