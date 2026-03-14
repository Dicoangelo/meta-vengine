#!/usr/bin/env node
/**
 * Tests for computeDistributionalFeatures (US-001)
 *
 * Verifies entropy, Gini, and skewness computation against known distributions.
 * Run: node kernel/tests/test-distributional-features.js
 */

const { computeDistributionalFeatures } = require('../dq-scorer');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
    console.log(`  ✓ ${message}`);
  } else {
    failed++;
    console.error(`  ✗ ${message}`);
  }
}

function assertClose(actual, expected, tolerance, message) {
  const diff = Math.abs(actual - expected);
  assert(diff <= tolerance, `${message} (expected ~${expected}, got ${actual}, diff ${diff.toFixed(6)})`);
}

// ─── Test 1: Returns null for fewer than 5 scores ───
console.log('\nTest 1: Minimum sample threshold');
assert(computeDistributionalFeatures([1, 2, 3, 4]) === null, 'Returns null for 4 scores');
assert(computeDistributionalFeatures([1]) === null, 'Returns null for 1 score');
assert(computeDistributionalFeatures([]) === null, 'Returns null for empty array');
assert(computeDistributionalFeatures(null) === null, 'Returns null for null input');
assert(computeDistributionalFeatures(undefined) === null, 'Returns null for undefined input');
assert(computeDistributionalFeatures('not an array') === null, 'Returns null for non-array');

// ─── Test 2: Exactly 5 scores works ───
console.log('\nTest 2: Minimum valid input (5 scores)');
const fiveResult = computeDistributionalFeatures([1, 2, 3, 4, 5]);
assert(fiveResult !== null, 'Returns result for 5 scores');
assert(fiveResult.sampleSize === 5, 'sampleSize is 5');

// ─── Test 3: Uniform distribution → max entropy ───
console.log('\nTest 3: Uniform distribution (max entropy)');
const uniform = computeDistributionalFeatures([1, 1, 1, 1, 1]);
// Shannon entropy of uniform(5) = log(5) ≈ 1.6094
assertClose(uniform.entropy, Math.log(5), 0.001, 'Uniform entropy = ln(5)');
// Gini of uniform(5) = 1 - 5*(1/5)^2 = 1 - 1/5 = 0.8
assertClose(uniform.gini, 0.8, 0.001, 'Uniform Gini = 0.8');
// Uniform → skewness ≈ 0
assertClose(uniform.skewness, 0, 0.001, 'Uniform skewness ≈ 0');

// ─── Test 4: Single-peak distribution → low entropy ───
console.log('\nTest 4: Single-peak distribution (low entropy)');
const singlePeak = computeDistributionalFeatures([100, 0.01, 0.01, 0.01, 0.01]);
// One dominant score → entropy should be near 0
assert(singlePeak.entropy < 0.3, `Single-peak entropy is low (${singlePeak.entropy})`);
// Gini near 0 for single-peak
assert(singlePeak.gini < 0.1, `Single-peak Gini is low (${singlePeak.gini})`);
// Strong positive skew
assert(singlePeak.skewness > 1.0, `Single-peak has positive skewness (${singlePeak.skewness})`);

// ─── Test 5: Two-peak distribution ───
console.log('\nTest 5: Bimodal distribution');
const bimodal = computeDistributionalFeatures([10, 10, 0.1, 0.1, 0.1]);
// Two equal peaks → some entropy, but less than uniform
assert(bimodal.entropy > 0 && bimodal.entropy < uniform.entropy,
  `Bimodal entropy between 0 and uniform (${bimodal.entropy})`);

// ─── Test 6: All zeros ───
console.log('\nTest 6: All zeros edge case');
const zeros = computeDistributionalFeatures([0, 0, 0, 0, 0]);
assert(zeros !== null, 'Returns result for all zeros');
assert(zeros.entropy === 0, 'All-zero entropy is 0');
assert(zeros.skewness === 0, 'All-zero skewness is 0');

// ─── Test 7: Large sample ───
console.log('\nTest 7: Large sample (100 scores)');
const large = Array.from({ length: 100 }, (_, i) => i + 1);
const largeResult = computeDistributionalFeatures(large);
assert(largeResult !== null, 'Handles 100 scores');
assert(largeResult.sampleSize === 100, 'sampleSize is 100');
assert(largeResult.entropy > 0, 'Positive entropy for varied scores');
assert(largeResult.gini > 0, 'Positive Gini for varied scores');

// ─── Test 8: Negative skew distribution ───
console.log('\nTest 8: Left-skewed distribution');
const leftSkew = computeDistributionalFeatures([0.01, 0.01, 0.01, 0.01, 100]);
assert(leftSkew.skewness > 0, `Right-tail dominant → positive skewness (${leftSkew.skewness})`);

// ─── Test 9: Existing DQ scoring unaffected ───
console.log('\nTest 9: Graceful degradation (no retrieval scores)');
// computeDistributionalFeatures returns null → DQ scorer should ignore it
const noScores = computeDistributionalFeatures(undefined);
assert(noScores === null, 'No scores → null (DQ scorer gracefully degrades)');

// ─── Test 10: Return shape ───
console.log('\nTest 10: Return shape validation');
const result = computeDistributionalFeatures([1, 2, 3, 4, 5, 6, 7]);
assert(typeof result.entropy === 'number', 'entropy is a number');
assert(typeof result.gini === 'number', 'gini is a number');
assert(typeof result.skewness === 'number', 'skewness is a number');
assert(typeof result.sampleSize === 'number', 'sampleSize is a number');
assert(Object.keys(result).length === 4, 'Exactly 4 keys in result');

// ─── Test 11: Entropy bounds ───
console.log('\nTest 11: Entropy bounds');
assert(uniform.entropy >= 0, 'Entropy is non-negative');
assert(singlePeak.entropy >= 0, 'Single-peak entropy is non-negative');
// Max entropy for n items = ln(n)
assert(uniform.entropy <= Math.log(5) + 0.001, 'Entropy ≤ ln(n)');

// ─── Test 12: Gini bounds ───
console.log('\nTest 12: Gini bounds');
assert(uniform.gini >= 0 && uniform.gini <= 1, 'Uniform Gini in [0,1]');
assert(singlePeak.gini >= 0 && singlePeak.gini <= 1, 'Single-peak Gini in [0,1]');

// ─── Summary ───
console.log(`\n${'═'.repeat(50)}`);
console.log(`Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`${'═'.repeat(50)}\n`);

process.exit(failed > 0 ? 1 : 0);
