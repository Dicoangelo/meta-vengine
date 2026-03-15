/**
 * US-102: Thompson Sampling Bandit — Unit Tests
 */

'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');
const { ThompsonBandit, sampleBeta, computeReward } = require('./bandit-engine');
const { ParamRegistry, resetRegistry } = require('./param-registry');

const TEST_REGISTRY = {
  version: '1.0.0',
  banditEnabled: true,
  parameters: [
    { id: 'w1', configFile: 'a.json', jsonPath: 'x.y', value: 0.6, min: 0.1, max: 0.9, learnRate: 0.02, group: 'test_group' },
    { id: 'w2', configFile: 'a.json', jsonPath: 'x.z', value: 0.4, min: 0.1, max: 0.9, learnRate: 0.02, group: 'test_group' },
    { id: 'ind1', configFile: 'b.json', jsonPath: 'y', value: 5.0, min: 1.0, max: 10.0, learnRate: 0.05, group: 'ind_group' }
  ],
  groups: {
    test_group: { constraint: 'sumMustEqual', target: 1.0, description: 'Test' },
    ind_group: { constraint: 'independent', description: 'Test' }
  }
};

let tmpFiles = [];
let passed = 0;
let failed = 0;

function tmpPath(name) {
  const p = path.join(os.tmpdir(), `bandit-test-${name}-${Date.now()}`);
  tmpFiles.push(p);
  return p;
}

function createTestBandit(opts = {}) {
  resetRegistry();
  const regPath = tmpPath('registry.json');
  fs.writeFileSync(regPath, JSON.stringify(TEST_REGISTRY));
  const registry = new ParamRegistry(regPath);
  return new ThompsonBandit({
    statePath: tmpPath('state.json'),
    historyPath: tmpPath('history.jsonl'),
    registry,
    ...opts
  });
}

function cleanup() {
  for (const f of tmpFiles) {
    try { fs.unlinkSync(f); } catch (_) {}
  }
  tmpFiles = [];
  resetRegistry();
}

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  PASS: ${name}`);
  } catch (err) {
    failed++;
    console.log(`  FAIL: ${name}`);
    console.log(`        ${err.message}`);
  }
}

function assert(condition, msg) {
  if (!condition) throw new Error(msg || 'Assertion failed');
}

// --- Tests ---

console.log('ThompsonBandit Tests\n');

test('sampleBeta returns values in [0, 1]', () => {
  for (let i = 0; i < 100; i++) {
    const v = sampleBeta(2, 3);
    assert(v >= 0 && v <= 1, `sampleBeta out of range: ${v}`);
  }
});

test('sample returns weights within bounds', () => {
  const bandit = createTestBandit();
  for (let i = 0; i < 50; i++) {
    const result = bandit.sample();
    assert(result.weights.w1 >= 0.1 && result.weights.w1 <= 0.9, `w1 out of bounds: ${result.weights.w1}`);
    assert(result.weights.w2 >= 0.1 && result.weights.w2 <= 0.9, `w2 out of bounds: ${result.weights.w2}`);
    assert(result.weights.ind1 >= 1.0 && result.weights.ind1 <= 10.0, `ind1 out of bounds: ${result.weights.ind1}`);
  }
});

test('sample returns sampleId', () => {
  const bandit = createTestBandit();
  const r = bandit.sample();
  assert(typeof r.sampleId === 'string');
  assert(r.sampleId.startsWith('sample-'));
});

test('sample returns exploring flag', () => {
  const bandit = createTestBandit({ explorationRate: 1.0 });
  const r = bandit.sample();
  assert(r.exploring === true, 'Should be exploring with rate 1.0');
});

test('sample enforces sumMustEqual constraint', () => {
  const bandit = createTestBandit();
  for (let i = 0; i < 30; i++) {
    const r = bandit.sample();
    const sum = r.weights.w1 + r.weights.w2;
    assert(Math.abs(sum - 1.0) < 0.02, `Sum constraint violated: ${sum}`);
  }
});

test('perturbation range bounded by learnRate', () => {
  const bandit = createTestBandit();
  const params = bandit.registry.getAllParams();
  for (let i = 0; i < 50; i++) {
    const r = bandit.sample();
    for (const p of params) {
      if (p.group !== 'ind_group') continue; // Only check independent (no normalization)
      const delta = Math.abs(r.weights[p.id] - p.value);
      assert(delta <= p.learnRate + 0.001, `Delta ${delta} exceeds learnRate ${p.learnRate} for ${p.id}`);
    }
  }
});

test('update shifts distribution', () => {
  const bandit = createTestBandit();
  const before = bandit.getBelief('ind1');
  const r = bandit.sample();
  bandit.update(r.sampleId, r.weights, 0.9);
  const after = bandit.getBelief('ind1');
  assert(
    after.alpha !== before.alpha || after.beta !== before.beta,
    'Beliefs should change after update'
  );
});

test('update rejects invalid reward', () => {
  const bandit = createTestBandit();
  const r = bandit.sample();
  try {
    bandit.update(r.sampleId, r.weights, 1.5);
    assert(false, 'Should have thrown');
  } catch (e) {
    assert(e.message.includes('reward must be in [0, 1]'));
  }
});

test('state persists across instances', () => {
  const statePath = tmpPath('persist-state.json');
  const historyPath = tmpPath('persist-history.jsonl');

  const regPath = tmpPath('persist-registry.json');
  fs.writeFileSync(regPath, JSON.stringify(TEST_REGISTRY));

  resetRegistry();
  const reg1 = new ParamRegistry(regPath);
  const bandit1 = new ThompsonBandit({ statePath, historyPath, registry: reg1 });
  const r = bandit1.sample();
  bandit1.update(r.sampleId, r.weights, 0.8);
  const beliefs1 = bandit1.getBeliefs();

  resetRegistry();
  const reg2 = new ParamRegistry(regPath);
  const bandit2 = new ThompsonBandit({ statePath, historyPath, registry: reg2 });
  const beliefs2 = bandit2.getBeliefs();

  assert(beliefs2.ind1.alpha === beliefs1.ind1.alpha, 'Alpha should persist');
  assert(beliefs2.ind1.beta === beliefs1.ind1.beta, 'Beta should persist');
});

test('history is appended to JSONL', () => {
  const bandit = createTestBandit();
  const r1 = bandit.sample();
  bandit.update(r1.sampleId, r1.weights, 0.7);
  const r2 = bandit.sample();
  bandit.update(r2.sampleId, r2.weights, 0.3);

  const lines = fs.readFileSync(bandit.historyPath, 'utf8').trim().split('\n');
  assert(lines.length === 2, `Expected 2 history lines, got ${lines.length}`);
  const entry = JSON.parse(lines[0]);
  assert(entry.reward === 0.7);
  assert(entry.sampleId === r1.sampleId);
});

test('exploration rate 0 never explores', () => {
  const bandit = createTestBandit({ explorationRate: 0 });
  let exploringCount = 0;
  for (let i = 0; i < 20; i++) {
    if (bandit.sample().exploring) exploringCount++;
  }
  assert(exploringCount === 0, `Should never explore, but explored ${exploringCount} times`);
});

test('initial beliefs are uniform Beta(1,1)', () => {
  const bandit = createTestBandit();
  const b = bandit.getBelief('w1');
  assert(b.alpha === 1.0, `Initial alpha should be 1.0, got ${b.alpha}`);
  assert(b.beta === 1.0, `Initial beta should be 1.0, got ${b.beta}`);
});

// --- computeReward tests ---

test('perfect routing gives reward ~1.0', () => {
  const reward = computeReward(
    { dqScore: 1.0, modelUsed: 'haiku', queryTier: 'trivial' },
    { compositeScore: 1.0, actualCost: 0.0 }
  );
  assert(reward >= 0.95, `Expected ~1.0, got ${reward}`);
});

test('worst routing gives reward ~0.0', () => {
  const reward = computeReward(
    { dqScore: 0.0, modelUsed: 'opus', queryTier: 'trivial' },
    { compositeScore: 0.0, actualCost: 25.0 },
    { providers: { anthropic: { models: { opus: { output: 25.0 } } } } }
  );
  assert(reward <= 0.05, `Expected ~0.0, got ${reward}`);
});

test('reward always in [0, 1]', () => {
  for (let i = 0; i < 50; i++) {
    const reward = computeReward(
      { dqScore: Math.random(), queryTier: 'moderate' },
      { compositeScore: Math.random(), actualCost: Math.random() * 30 }
    );
    assert(reward >= 0 && reward <= 1, `Reward out of range: ${reward}`);
  }
});

test('reward without cost data uses default', () => {
  const reward = computeReward(
    { dqScore: 0.8, queryTier: 'simple' },
    { compositeScore: 0.7 }
  );
  assert(typeof reward === 'number' && reward > 0);
});

// Cleanup
cleanup();

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
