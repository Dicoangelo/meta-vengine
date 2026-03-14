#!/usr/bin/env node
/**
 * Tests for computeGraphSignal (US-004: Multi-Feature Signal Composition)
 *
 * Verifies that entropy, Gini, subgraph density, and IRT difficulty compose
 * into a single graphComplexity score (0.0-1.0) with configurable weights.
 *
 * Run: node kernel/tests/test-graph-signal.js
 */

const { computeGraphSignal, loadGraphSignalWeights, computeDistributionalFeatures, computeSubgraphDensityFromLinks } = require('../dq-scorer');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
    console.log(`  \u2713 ${message}`);
  } else {
    failed++;
    console.error(`  \u2717 ${message}`);
  }
}

function assertClose(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, `${message} (expected ~${expected}, got ${actual})`);
}

// ─── Test 1: Returns null when no features available ───
console.log('\nTest 1: No features → null');
assert(computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: null }) === null,
  'All null inputs → null');
assert(computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: undefined }) === null,
  'All undefined/null → null');
assert(computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: NaN }) === null,
  'NaN IRT → null');

// ─── Test 2: Weights loaded from config file ───
console.log('\nTest 2: Weights from config/graph-signal-weights.json');
const weights = loadGraphSignalWeights();
assertClose(weights.entropy, 0.30, 0.001, 'Entropy weight = 0.30');
assertClose(weights.gini, 0.25, 0.001, 'Gini weight = 0.25');
assertClose(weights.subgraphDensity, 0.25, 0.001, 'Subgraph density weight = 0.25');
assertClose(weights.irtDifficulty, 0.20, 0.001, 'IRT difficulty weight = 0.20');
assertClose(weights.entropy + weights.gini + weights.subgraphDensity + weights.irtDifficulty,
  1.0, 0.001, 'Weights sum to 1.0');

// ─── Test 3: Known-simple query → lower complexity ───
console.log('\nTest 3: Simple query (high entropy, dense subgraph) → low complexity');
// High entropy = well-distributed knowledge = easy
// Dense subgraph = well-connected = easy
// Low IRT difficulty = easy
const simpleDistributional = computeDistributionalFeatures([1, 1, 1, 1, 1, 1, 1, 1, 1, 1]);
const simpleSubgraph = { density: 0.9, nodeCount: 10, edgeCount: 40, coverageRate: 0.95 };
const simpleSignal = computeGraphSignal({
  distributional: simpleDistributional,
  subgraph: simpleSubgraph,
  irtDifficulty: 0.1
});
assert(simpleSignal !== null, 'Simple signal computed');
assert(simpleSignal.graphComplexity < 0.3,
  `Simple query complexity < 0.3 (got ${simpleSignal.graphComplexity})`);
assert(simpleSignal.featureCount === 4, 'All 4 features present');

// ─── Test 4: Known-hard query → higher complexity ───
console.log('\nTest 4: Hard query (low entropy, sparse subgraph) → high complexity');
// Single-peak distribution = concentrated knowledge = hard
// Sparse subgraph = poorly connected = hard
// High IRT difficulty = hard
const hardDistributional = computeDistributionalFeatures([100, 0.01, 0.01, 0.01, 0.01]);
const hardSubgraph = { density: 0.05, nodeCount: 10, edgeCount: 2, coverageRate: 0.1 };
const hardSignal = computeGraphSignal({
  distributional: hardDistributional,
  subgraph: hardSubgraph,
  irtDifficulty: 0.95
});
assert(hardSignal !== null, 'Hard signal computed');
assert(hardSignal.graphComplexity > 0.7,
  `Hard query complexity > 0.7 (got ${hardSignal.graphComplexity})`);
assert(hardSignal.featureCount === 4, 'All 4 features present');

// ─── Test 5: Hard > Simple complexity (ordering) ───
console.log('\nTest 5: Complexity ordering');
assert(hardSignal.graphComplexity > simpleSignal.graphComplexity,
  `Hard (${hardSignal.graphComplexity}) > Simple (${simpleSignal.graphComplexity})`);

// ─── Test 6: Output range [0, 1] ───
console.log('\nTest 6: Output bounds');
assert(simpleSignal.graphComplexity >= 0 && simpleSignal.graphComplexity <= 1,
  'Simple complexity in [0, 1]');
assert(hardSignal.graphComplexity >= 0 && hardSignal.graphComplexity <= 1,
  'Hard complexity in [0, 1]');

// ─── Test 7: Partial features (graceful degradation) ───
console.log('\nTest 7: Partial feature availability');
const irtOnly = computeGraphSignal({
  distributional: null,
  subgraph: null,
  irtDifficulty: 0.8
});
assert(irtOnly !== null, 'IRT-only signal computed');
assert(irtOnly.featureCount === 1, 'Only 1 feature');
assertClose(irtOnly.graphComplexity, 0.8, 0.001, 'IRT-only complexity = IRT difficulty');

const distribOnly = computeGraphSignal({
  distributional: simpleDistributional,
  subgraph: null,
  irtDifficulty: null
});
assert(distribOnly !== null, 'Distributional-only signal computed');
assert(distribOnly.featureCount === 2, '2 features (entropy + gini)');

// ─── Test 8: Return shape validation ───
console.log('\nTest 8: Return shape');
assert(typeof simpleSignal.graphComplexity === 'number', 'graphComplexity is number');
assert(typeof simpleSignal.features === 'object', 'features is object');
assert(typeof simpleSignal.weights === 'object', 'weights is object');
assert(typeof simpleSignal.featureCount === 'number', 'featureCount is number');
assert('entropy' in simpleSignal.features, 'features has entropy');
assert('gini' in simpleSignal.features, 'features has gini');
assert('subgraphDensity' in simpleSignal.features, 'features has subgraphDensity');
assert('irtDifficulty' in simpleSignal.features, 'features has irtDifficulty');

// ─── Test 9: Feature normalization direction ───
console.log('\nTest 9: Feature normalization (inversion logic)');
// High entropy → low complexity contribution (inverted)
assert(simpleSignal.features.entropy < 0.2,
  `High entropy → low complexity feature (${simpleSignal.features.entropy})`);
// Low entropy → high complexity contribution (inverted)
assert(hardSignal.features.entropy > 0.7,
  `Low entropy → high complexity feature (${hardSignal.features.entropy})`);
// Dense subgraph → low complexity (inverted)
assert(simpleSignal.features.subgraphDensity < 0.2,
  `Dense subgraph → low complexity feature (${simpleSignal.features.subgraphDensity})`);
// Sparse subgraph → high complexity (inverted)
assert(hardSignal.features.subgraphDensity > 0.8,
  `Sparse subgraph → high complexity feature (${hardSignal.features.subgraphDensity})`);
// IRT is direct (not inverted)
assertClose(simpleSignal.features.irtDifficulty, 0.1, 0.001, 'IRT direct: 0.1 stays 0.1');
assertClose(hardSignal.features.irtDifficulty, 0.95, 0.001, 'IRT direct: 0.95 stays 0.95');

// ─── Test 10: Weight normalization with partial features ───
console.log('\nTest 10: Weight normalization');
// With only IRT (weight 0.20), the result should be normalized by 0.20/0.20 = 1.0
// So graphComplexity should equal the IRT feature value
const irt05 = computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: 0.5 });
assertClose(irt05.graphComplexity, 0.5, 0.001, 'Single feature: complexity = feature value');

// ─── Test 11: Extreme values ───
console.log('\nTest 11: Extreme values');
const maxIRT = computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: 1.0 });
assert(maxIRT.graphComplexity <= 1.0, 'IRT=1.0 → complexity ≤ 1.0');
const minIRT = computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: 0.0 });
assert(minIRT.graphComplexity >= 0.0, 'IRT=0.0 → complexity ≥ 0.0');
// Out-of-range IRT clamped
const overIRT = computeGraphSignal({ distributional: null, subgraph: null, irtDifficulty: 1.5 });
assert(overIRT.graphComplexity <= 1.0, 'IRT=1.5 clamped → complexity ≤ 1.0');

// ─── Test 12: Integration with computeSubgraphDensityFromLinks ───
console.log('\nTest 12: End-to-end with subgraph density from links');
const nodes = ['a', 'b', 'c', 'd', 'e'];
// Fully connected: 10 edges for 5 nodes
const fullyConnected = [];
for (let i = 0; i < nodes.length; i++) {
  for (let j = i + 1; j < nodes.length; j++) {
    fullyConnected.push({ from_id: nodes[i], to_id: nodes[j] });
  }
}
const denseSubgraph = computeSubgraphDensityFromLinks(nodes, fullyConnected);
const denseSignal = computeGraphSignal({
  distributional: simpleDistributional,
  subgraph: denseSubgraph,
  irtDifficulty: 0.1
});
assert(denseSignal.graphComplexity < 0.25,
  `Fully connected + uniform dist + low IRT → very low complexity (${denseSignal.graphComplexity})`);

// Isolated nodes: 0 edges
const isolatedSubgraph = computeSubgraphDensityFromLinks(nodes, []);
const sparseSignal = computeGraphSignal({
  distributional: hardDistributional,
  subgraph: isolatedSubgraph,
  irtDifficulty: 0.9
});
assert(sparseSignal.graphComplexity > 0.75,
  `Isolated nodes + peaked dist + high IRT → very high complexity (${sparseSignal.graphComplexity})`);

// ─── Summary ───
console.log(`\n${'═'.repeat(50)}`);
console.log(`Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`${'═'.repeat(50)}\n`);

process.exit(failed > 0 ? 1 : 0);
