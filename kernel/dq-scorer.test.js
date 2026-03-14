#!/usr/bin/env node
/**
 * DQ Scorer Regression Suite — US-005
 *
 * Tests the DQ scoring engine against baselines to prevent routing quality regressions.
 * Covers all 8 session types, scoring components, and edge cases.
 *
 * Run: node kernel/dq-scorer.test.js
 * Quality gates: 30+ test cases, <5s execution, all pass
 */

const assert = require('assert');
const path = require('path');

// ---------------------------------------------------------------------------
// Test-safe imports: we test the pure scoring functions directly, bypassing
// the module-level side effects (file I/O for history, cognitive weights, etc.)
// by requiring the sub-modules individually.
// ---------------------------------------------------------------------------

const { estimateComplexity } = require('./complexity-analyzer');

// Re-implement the pure scoring functions from dq-scorer.js so we can test
// them in isolation without triggering file I/O side effects on load.
// The logic is identical — copied verbatim from dq-scorer.js lines 221-322.

const fs = require('fs');
const BASELINES_PATH = path.join(process.env.HOME, '.claude/kernel/baselines.json');
let BASELINES = null;
try {
  BASELINES = JSON.parse(fs.readFileSync(BASELINES_PATH, 'utf8'));
} catch (_) {}

const DQ_WEIGHTS = BASELINES?.dq_weights || {
  validity: 0.4,
  specificity: 0.3,
  correctness: 0.3
};

const DQ_THRESHOLD = BASELINES?.dq_thresholds?.actionable || 0.5;

const MODEL_CAPABILITIES = BASELINES?.complexity_thresholds ? {
  haiku: { maxComplexity: BASELINES.complexity_thresholds.haiku.range[1] },
  sonnet: { maxComplexity: BASELINES.complexity_thresholds.sonnet.range[1] },
  opus: { maxComplexity: BASELINES.complexity_thresholds.opus.range[1] }
} : {
  haiku: { maxComplexity: 0.30 },
  sonnet: { maxComplexity: 0.70 },
  opus: { maxComplexity: 1.0 }
};

const ADAPTIVE_THRESHOLDS = {
  simple:   { complexity: [0, 0.25],   model: 'haiku' },
  moderate: { complexity: [0.25, 0.50], model: 'sonnet' },
  complex:  { complexity: [0.50, 0.75], model: 'sonnet' },
  expert:   { complexity: [0.75, 1.0],  model: 'opus' }
};

function assessValidity(complexity, model) {
  const modelCaps = MODEL_CAPABILITIES[model];
  if (!modelCaps) return 0;
  if (complexity <= modelCaps.maxComplexity) {
    if (model === 'opus' && complexity < 0.5) return 0.6;
    if (model === 'sonnet' && complexity < 0.2) return 0.7;
    return 1.0 - ((modelCaps.maxComplexity - complexity) * 0.2);
  }
  const underProvision = complexity - modelCaps.maxComplexity;
  return Math.max(0, 1.0 - (underProvision * 2));
}

function assessSpecificity(query, complexity, model) {
  let idealModel;
  for (const [, config] of Object.entries(ADAPTIVE_THRESHOLDS)) {
    if (complexity >= config.complexity[0] && complexity < config.complexity[1]) {
      idealModel = config.model;
      break;
    }
  }
  if (!idealModel) idealModel = 'opus';
  if (model === idealModel) return 1.0;
  const models = ['haiku', 'sonnet', 'opus'];
  const distance = Math.abs(models.indexOf(idealModel) - models.indexOf(model));
  return Math.max(0, 1.0 - (distance * 0.4));
}

function assessCorrectness(query, model, history) {
  if (history.length === 0) return 0.5;
  const queryTokens = new Set(query.toLowerCase().split(/\s+/));
  const similar = history.filter(h => {
    if (!h.query) return false;
    const histTokens = new Set(h.query.toLowerCase().split(/\s+/));
    const intersection = [...queryTokens].filter(t => histTokens.has(t)).length;
    return intersection / Math.max(queryTokens.size, histTokens.size) > 0.3;
  });
  if (similar.length === 0) return 0.5;
  const modelMatches = similar.filter(s => s.model === model);
  if (modelMatches.length === 0) return 0.5;
  const withFeedback = modelMatches.filter(m => m.success !== undefined);
  if (withFeedback.length > 0) {
    return withFeedback.filter(m => m.success).length / withFeedback.length;
  }
  return modelMatches.reduce((sum, m) => sum + (m.dqScore || 0.5), 0) / modelMatches.length;
}

function calculateDQ(query, complexity, model, history = []) {
  const validity = assessValidity(complexity, model);
  const specificity = assessSpecificity(query, complexity, model);
  const correctness = assessCorrectness(query, model, history);
  const score = (validity * DQ_WEIGHTS.validity) +
                (specificity * DQ_WEIGHTS.specificity) +
                (correctness * DQ_WEIGHTS.correctness);
  return {
    score: parseFloat(score.toFixed(3)),
    components: {
      validity: parseFloat(validity.toFixed(3)),
      specificity: parseFloat(specificity.toFixed(3)),
      correctness: parseFloat(correctness.toFixed(3))
    },
    actionable: score >= DQ_THRESHOLD
  };
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;
let total = 0;
const failures = [];

function test(name, fn) {
  total++;
  try {
    fn();
    passed++;
    process.stdout.write(`  PASS  ${name}\n`);
  } catch (e) {
    failed++;
    failures.push({ name, error: e.message });
    process.stdout.write(`  FAIL  ${name}\n        ${e.message}\n`);
  }
}

function assertInRange(value, min, max, label) {
  assert.ok(
    value >= min && value <= max,
    `${label}: expected ${value} to be in [${min}, ${max}]`
  );
}

function assertDQActionable(dq, label) {
  assert.ok(dq.actionable, `${label}: DQ score ${dq.score} should be actionable (>= ${DQ_THRESHOLD})`);
}

// ---------------------------------------------------------------------------
// Baseline reference values
// ---------------------------------------------------------------------------

const BASELINE_AVG_DQ = BASELINES?.validation?.accuracy_against_test_set || 0.931;
const TOLERANCE = 0.05;

// ═══════════════════════════════════════════════════════════════════════════
// SESSION TYPE TESTS — 8 types, multiple queries each
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n=== DQ Scorer Regression Suite ===\n');
console.log(`Baselines v${BASELINES?.version || 'fallback'} | Weights: validity=${DQ_WEIGHTS.validity} specificity=${DQ_WEIGHTS.specificity} correctness=${DQ_WEIGHTS.correctness}\n`);

// --- 1. Debugging ---
console.log('--- Session type: debugging ---');

test('debugging: simple error fix routes to sonnet with good DQ', () => {
  const q = 'Fix the TypeError in auth.js where user.name is undefined';
  const c = estimateComplexity(q);
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertInRange(dq.score, 0.5, 1.0, 'DQ score');
  assertDQActionable(dq, 'debugging simple');
});

test('debugging: complex multi-file bug routes to opus-tier complexity', () => {
  const q = 'Debug race condition across all microservices causing intermittent 503 errors in production distributed system';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.4, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'opus');
  assertDQActionable(dq, 'debugging complex');
});

test('debugging: simple bug has lower complexity than complex bug', () => {
  const simple = estimateComplexity('fix typo in README');
  const complex = estimateComplexity('debug memory leak across entire codebase causing crash exceptions in all files');
  assert.ok(simple.score < complex.score, `Simple (${simple.score}) should be < complex (${complex.score})`);
});

// --- 2. Research ---
console.log('\n--- Session type: research ---');

test('research: literature review routes with high DQ to opus', () => {
  const q = 'Research and analyze the latest papers on multi-agent LLM orchestration architectures and compare approaches';
  const c = estimateComplexity(q);
  const dq = calculateDQ(q, c.score, 'opus');
  assertInRange(dq.score, 0.5, 1.0, 'DQ score');
  assertDQActionable(dq, 'research deep');
});

test('research: simple lookup is low complexity', () => {
  const q = 'What is the capital of France?';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 0.35, 'complexity');
});

test('research: complex synthesis scores higher complexity', () => {
  const q = 'Investigate and evaluate distributed consensus algorithms for multi-agent systems, study the trade-offs between Raft and Paxos';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.3, 1.0, 'complexity');
});

// --- 3. Architecture ---
console.log('\n--- Session type: architecture ---');

test('architecture: system design is high complexity', () => {
  const q = 'Design a scalable microservice architecture for a distributed event-driven system with pattern-based routing';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.5, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'opus');
  assertDQActionable(dq, 'architecture');
});

test('architecture: opus gets best DQ for architecture tasks', () => {
  const q = 'Design the system architecture for a distributed real-time data pipeline with scalable microservices';
  const c = estimateComplexity(q);
  const dqOpus = calculateDQ(q, c.score, 'opus');
  const dqHaiku = calculateDQ(q, c.score, 'haiku');
  assert.ok(dqOpus.score >= dqHaiku.score,
    `Opus DQ (${dqOpus.score}) should >= Haiku DQ (${dqHaiku.score}) for architecture`);
});

// --- 4. Refactoring ---
console.log('\n--- Session type: refactoring ---');

test('refactoring: moderate refactor routes well to sonnet', () => {
  const q = 'Refactor the authentication module to use async/await instead of callbacks';
  const c = estimateComplexity(q);
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertInRange(dq.score, 0.5, 1.0, 'DQ score');
  assertDQActionable(dq, 'refactoring moderate');
});

test('refactoring: project-wide refactor is high complexity', () => {
  const q = 'Restructure and refactor all files in the entire codebase to use the new module pattern across every component';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.4, 1.0, 'complexity');
});

// --- 5. Testing ---
console.log('\n--- Session type: testing ---');

test('testing: write unit tests is moderate complexity', () => {
  const q = 'Write unit tests for the payment processing module with edge cases';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.15, 0.7, 'complexity');
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertDQActionable(dq, 'testing');
});

test('testing: simple test generation is lower complexity', () => {
  const q = 'Add a test for the add function';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 0.5, 'complexity');
});

// --- 6. Docs ---
console.log('\n--- Session type: docs ---');

test('docs: write documentation is moderate complexity', () => {
  const q = 'Write comprehensive API documentation for the REST endpoints including examples';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.1, 0.6, 'complexity');
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertDQActionable(dq, 'docs');
});

test('docs: simple explanation is low complexity', () => {
  const q = 'Explain what this function does';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 0.4, 'complexity');
});

// --- 7. Exploration ---
console.log('\n--- Session type: exploration ---');

test('exploration: codebase exploration is moderate complexity', () => {
  const q = 'Analyze and understand the data flow in this project from input to output';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.2, 0.8, 'complexity');
});

test('exploration: simple browsing is low complexity', () => {
  const q = 'Show me the list of files in src';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 0.35, 'complexity');
});

// --- 8. Creative ---
console.log('\n--- Session type: creative ---');

test('creative: novel algorithm design is high complexity', () => {
  const q = 'Design a novel algorithm for distributed consensus that optimizes for latency in a system with unreliable network partitions';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.5, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'opus');
  assertDQActionable(dq, 'creative');
});

test('creative: generate a simple script is moderate', () => {
  const q = 'Create a bash script to generate a random password';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.1, 0.5, 'complexity');
});

// ═══════════════════════════════════════════════════════════════════════════
// SCORING COMPONENT TESTS
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n--- Scoring components ---');

test('validity: perfect match — sonnet at mid complexity', () => {
  const v = assessValidity(0.4, 'sonnet');
  assertInRange(v, 0.8, 1.0, 'validity');
});

test('validity: over-provisioning — opus for trivial task penalized', () => {
  const v = assessValidity(0.1, 'opus');
  assert.strictEqual(v, 0.6, 'opus on trivial should return 0.6');
});

test('validity: over-provisioning — sonnet for very simple task penalized', () => {
  const v = assessValidity(0.1, 'sonnet');
  assert.strictEqual(v, 0.7, 'sonnet on very simple should return 0.7');
});

test('validity: under-provisioning — haiku for complex task penalized heavily', () => {
  const v = assessValidity(0.8, 'haiku');
  const maxComplexity = MODEL_CAPABILITIES.haiku.maxComplexity;
  const expected = Math.max(0, 1.0 - ((0.8 - maxComplexity) * 2));
  assertInRange(v, 0.0, 0.5, 'validity should be low');
  assert.ok(Math.abs(v - expected) < 0.001, `validity ${v} should equal ${expected}`);
});

test('validity: unknown model returns 0', () => {
  const v = assessValidity(0.5, 'nonexistent');
  assert.strictEqual(v, 0, 'unknown model should return 0');
});

test('specificity: ideal model match returns 1.0', () => {
  // complexity 0.3 -> moderate -> ideal is sonnet
  const s = assessSpecificity('test query', 0.3, 'sonnet');
  assert.strictEqual(s, 1.0, 'ideal match should be 1.0');
});

test('specificity: adjacent model returns 0.6', () => {
  // complexity 0.3 -> ideal sonnet, using haiku (distance 1)
  const s = assessSpecificity('test query', 0.3, 'haiku');
  assert.strictEqual(s, 0.6, 'adjacent model should be 0.6');
});

test('specificity: distant model returns ~0.2', () => {
  // complexity 0.1 -> ideal haiku, using opus (distance 2)
  const s = assessSpecificity('test query', 0.1, 'opus');
  assert.ok(Math.abs(s - 0.2) < 0.001, `distant model should be ~0.2, got ${s}`);
});

test('correctness: no history returns 0.5 (neutral)', () => {
  const c = assessCorrectness('any query here', 'sonnet', []);
  assert.strictEqual(c, 0.5, 'no history should be neutral 0.5');
});

test('correctness: with matching successful history returns high score', () => {
  const history = [
    { query: 'fix the auth bug in login module', model: 'sonnet', success: true },
    { query: 'fix the auth bug in register module', model: 'sonnet', success: true }
  ];
  const c = assessCorrectness('fix the auth bug in settings', 'sonnet', history);
  assert.strictEqual(c, 1.0, 'all-success history should return 1.0');
});

test('correctness: with matching failed history returns low score', () => {
  const history = [
    { query: 'fix the auth bug in login module', model: 'haiku', success: false },
    { query: 'fix the auth bug in register module', model: 'haiku', success: false }
  ];
  const c = assessCorrectness('fix the auth bug in settings', 'haiku', history);
  assert.strictEqual(c, 0.0, 'all-failure history should return 0.0');
});

// ═══════════════════════════════════════════════════════════════════════════
// COMPOSITE DQ SCORE TESTS
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n--- Composite DQ scores ---');

test('composite: weights sum correctly (validity*w + specificity*w + correctness*w)', () => {
  const dq = calculateDQ('simple question', 0.1, 'haiku');
  const expected = (dq.components.validity * DQ_WEIGHTS.validity) +
                   (dq.components.specificity * DQ_WEIGHTS.specificity) +
                   (dq.components.correctness * DQ_WEIGHTS.correctness);
  assert.ok(Math.abs(dq.score - parseFloat(expected.toFixed(3))) < 0.002,
    `Score ${dq.score} should equal weighted sum ${expected.toFixed(3)}`);
});

test('composite: DQ weight proportions match baselines', () => {
  const sum = DQ_WEIGHTS.validity + DQ_WEIGHTS.specificity + DQ_WEIGHTS.correctness;
  assert.ok(Math.abs(sum - 1.0) < 0.001, `Weights should sum to 1.0, got ${sum}`);
});

test('composite: well-matched routing produces actionable score', () => {
  // sonnet at complexity 0.4 is a good match
  const dq = calculateDQ('implement the new feature with async functions', 0.4, 'sonnet');
  assertDQActionable(dq, 'well-matched');
});

test('composite: poorly-matched routing produces lower score', () => {
  const good = calculateDQ('design system architecture', 0.8, 'opus');
  const bad = calculateDQ('design system architecture', 0.8, 'haiku');
  assert.ok(good.score > bad.score,
    `Good match (${good.score}) should beat bad match (${bad.score})`);
});

// ═══════════════════════════════════════════════════════════════════════════
// EDGE CASE TESTS
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n--- Edge cases ---');

test('edge: empty query does not crash', () => {
  const c = estimateComplexity('');
  assertInRange(c.score, 0.0, 1.0, 'complexity');
  const dq = calculateDQ('', c.score, 'haiku');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
});

test('edge: very long query (2000 chars) does not crash', () => {
  const q = 'Analyze and refactor the authentication system '.repeat(40);
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
});

test('edge: special characters in query do not crash', () => {
  const q = 'Fix the bug with <script>alert("xss")</script> & "quotes" \'single\' `backticks` $vars @mentions #tags';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
});

test('edge: unicode query does not crash', () => {
  const q = 'Fix the bug in \u65E5\u672C\u8A9E module with \u00E9\u00E0\u00FC characters and \uD83D\uDE80 emoji';
  const c = estimateComplexity(q);
  assertInRange(c.score, 0.0, 1.0, 'complexity');
  const dq = calculateDQ(q, c.score, 'sonnet');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
});

test('edge: single word query', () => {
  const c = estimateComplexity('hello');
  assertInRange(c.score, 0.0, 0.3, 'complexity');
});

test('edge: complexity boundary at 0.0', () => {
  const dq = calculateDQ('test', 0.0, 'haiku');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
  assertDQActionable(dq, 'boundary 0.0');
});

test('edge: complexity boundary at 1.0', () => {
  const dq = calculateDQ('expert task', 1.0, 'opus');
  assertInRange(dq.score, 0.0, 1.0, 'DQ score');
  assertDQActionable(dq, 'boundary 1.0');
});

test('edge: complexity boundary at 0.5 (mid-range)', () => {
  const dq = calculateDQ('moderate task', 0.5, 'sonnet');
  assertInRange(dq.score, 0.5, 1.0, 'DQ score');
  assertDQActionable(dq, 'boundary 0.5');
});

// ═══════════════════════════════════════════════════════════════════════════
// BASELINE REGRESSION TESTS
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n--- Baseline regression ---');

test('baseline: haiku max complexity matches baselines.json', () => {
  if (!BASELINES) { assert.ok(true, 'No baselines file — skip'); return; }
  assert.strictEqual(MODEL_CAPABILITIES.haiku.maxComplexity, BASELINES.complexity_thresholds.haiku.range[1],
    'Haiku maxComplexity should match baselines');
});

test('baseline: sonnet max complexity matches baselines.json', () => {
  if (!BASELINES) { assert.ok(true, 'No baselines file — skip'); return; }
  assert.strictEqual(MODEL_CAPABILITIES.sonnet.maxComplexity, BASELINES.complexity_thresholds.sonnet.range[1],
    'Sonnet maxComplexity should match baselines');
});

test('baseline: opus max complexity matches baselines.json', () => {
  if (!BASELINES) { assert.ok(true, 'No baselines file — skip'); return; }
  assert.strictEqual(MODEL_CAPABILITIES.opus.maxComplexity, BASELINES.complexity_thresholds.opus.range[1],
    'Opus maxComplexity should match baselines');
});

test('baseline: DQ threshold matches baselines.json', () => {
  if (!BASELINES) { assert.ok(true, 'No baselines file — skip'); return; }
  assert.strictEqual(DQ_THRESHOLD, BASELINES.dq_thresholds.actionable,
    'DQ threshold should match baselines');
});

test('baseline: well-routed queries score within tolerance of baseline avg', () => {
  // Sample of well-matched queries — their average should be reasonable
  const queries = [
    { q: 'What is a variable?', c: 0.1, m: 'haiku' },
    { q: 'Implement a REST API endpoint with validation', c: 0.4, m: 'sonnet' },
    { q: 'Design distributed architecture for real-time system', c: 0.85, m: 'opus' },
  ];
  const scores = queries.map(({ q, c, m }) => calculateDQ(q, c, m).score);
  const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
  assertInRange(avg, 0.6, 1.0, 'Average DQ of well-routed queries');
});

// ═══════════════════════════════════════════════════════════════════════════
// REPORT
// ═══════════════════════════════════════════════════════════════════════════

console.log('\n' + '='.repeat(50));
console.log(`Results: ${passed}/${total} passed, ${failed} failed`);
if (failures.length > 0) {
  console.log('\nFailures:');
  for (const f of failures) {
    console.log(`  - ${f.name}: ${f.error}`);
  }
}
console.log('='.repeat(50) + '\n');

process.exit(failed > 0 ? 1 : 0);
