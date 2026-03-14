#!/usr/bin/env node
/**
 * Tests for US-002: computeSubgraphDensity and computeSubgraphDensityFromLinks
 *
 * Tests the in-memory variant (computeSubgraphDensityFromLinks) for deterministic unit tests
 * and the live DB variant (computeSubgraphDensity) for integration verification.
 */

const path = require('path');
process.chdir(path.join(__dirname, '..'));

const { computeSubgraphDensity, computeSubgraphDensityFromLinks } = require('../dq-scorer');

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
    console.log(`  PASS: ${message}`);
  } else {
    failed++;
    console.error(`  FAIL: ${message}`);
  }
}

function assertClose(actual, expected, tolerance, message) {
  const close = Math.abs(actual - expected) < tolerance;
  if (close) {
    passed++;
    console.log(`  PASS: ${message} (${actual} ≈ ${expected})`);
  } else {
    failed++;
    console.error(`  FAIL: ${message} (got ${actual}, expected ~${expected})`);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Test: Null/invalid inputs
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Null/Invalid Input Tests ---');

assert(computeSubgraphDensityFromLinks(null, []) === null, 'null nodes returns null');
assert(computeSubgraphDensityFromLinks([], []) === null, 'empty nodes returns null');
assert(computeSubgraphDensityFromLinks(['a'], []) === null, 'single node returns null');
assert(computeSubgraphDensityFromLinks(['a', 'a'], []) === null, 'duplicate single node returns null');
assert(computeSubgraphDensityFromLinks(['a', 'b'], null) === null, 'null links returns null');
assert(computeSubgraphDensityFromLinks(undefined, []) === null, 'undefined nodes returns null');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Fully connected subgraph (density = 1.0)
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Fully Connected Subgraph Tests ---');

// 3 nodes, all connected: 3 edges, max = 3*(3-1)/2 = 3 → density = 1.0
const fullLinks3 = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'b', to_id: 'c' },
  { from_id: 'a', to_id: 'c' }
];
const full3 = computeSubgraphDensityFromLinks(['a', 'b', 'c'], fullLinks3);
assert(full3 !== null, 'fully connected 3-node returns result');
assertClose(full3.density, 1.0, 0.001, 'fully connected 3-node density = 1.0');
assert(full3.nodeCount === 3, 'fully connected 3-node count = 3');
assert(full3.edgeCount === 3, 'fully connected 3-node edge count = 3');

// 4 nodes, all connected: 6 edges, max = 4*3/2 = 6 → density = 1.0
const fullLinks4 = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'a', to_id: 'c' },
  { from_id: 'a', to_id: 'd' },
  { from_id: 'b', to_id: 'c' },
  { from_id: 'b', to_id: 'd' },
  { from_id: 'c', to_id: 'd' }
];
const full4 = computeSubgraphDensityFromLinks(['a', 'b', 'c', 'd'], fullLinks4);
assertClose(full4.density, 1.0, 0.001, 'fully connected 4-node density = 1.0');
assert(full4.edgeCount === 6, 'fully connected 4-node edge count = 6');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Isolated nodes (density = 0.0)
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Isolated Node Tests ---');

const isolated = computeSubgraphDensityFromLinks(['a', 'b', 'c'], []);
assert(isolated !== null, 'isolated nodes returns result');
assertClose(isolated.density, 0.0, 0.001, 'isolated 3-node density = 0.0');
assert(isolated.edgeCount === 0, 'isolated nodes edge count = 0');
assert(isolated.nodeCount === 3, 'isolated nodes node count = 3');

// Links exist but between OTHER nodes (not in retrieved set)
const externalLinks = [
  { from_id: 'x', to_id: 'y' },
  { from_id: 'y', to_id: 'z' }
];
const isolatedExternal = computeSubgraphDensityFromLinks(['a', 'b', 'c'], externalLinks);
assertClose(isolatedExternal.density, 0.0, 0.001, 'external-only links → density 0.0');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Partial connectivity
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Partial Connectivity Tests ---');

// 4 nodes, 2 edges → max 6 → density = 2/6 = 0.333
const partialLinks = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'c', to_id: 'd' }
];
const partial = computeSubgraphDensityFromLinks(['a', 'b', 'c', 'd'], partialLinks);
assertClose(partial.density, 2 / 6, 0.001, 'partial 4-node 2-edge density = 0.333');
assert(partial.edgeCount === 2, 'partial edge count = 2');

// Linear chain: a-b-c-d → 3 edges / 6 max = 0.5
const chainLinks = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'b', to_id: 'c' },
  { from_id: 'c', to_id: 'd' }
];
const chain = computeSubgraphDensityFromLinks(['a', 'b', 'c', 'd'], chainLinks);
assertClose(chain.density, 3 / 6, 0.001, 'chain 4-node density = 0.5');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Bidirectional edges counted once
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Edge Deduplication Tests ---');

// Same edge in both directions should count as one
const biLinks = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'b', to_id: 'a' }  // reverse
];
const biResult = computeSubgraphDensityFromLinks(['a', 'b'], biLinks);
assertClose(biResult.density, 1.0, 0.001, 'bidirectional edge counted once → density 1.0');
assert(biResult.edgeCount === 1, 'bidirectional deduplication → 1 edge');

// Multiple link types for same node pair
const multiTypeLinks = [
  { from_id: 'a', to_id: 'b' },
  { from_id: 'a', to_id: 'b' },  // duplicate
  { from_id: 'b', to_id: 'a' }   // reverse
];
const multiType = computeSubgraphDensityFromLinks(['a', 'b'], multiTypeLinks);
assert(multiType.edgeCount === 1, 'duplicate + reverse links → 1 unique edge');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Self-loops ignored
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Self-Loop Tests ---');

const selfLoopLinks = [
  { from_id: 'a', to_id: 'a' },  // self-loop
  { from_id: 'b', to_id: 'b' }   // self-loop
];
const selfLoop = computeSubgraphDensityFromLinks(['a', 'b'], selfLoopLinks);
assertClose(selfLoop.density, 0.0, 0.001, 'self-loops not counted → density 0.0');
assert(selfLoop.edgeCount === 0, 'self-loops → 0 edges');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Node deduplication
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Node Deduplication Tests ---');

const dedupLinks = [{ from_id: 'a', to_id: 'b' }];
const dedup = computeSubgraphDensityFromLinks(['a', 'b', 'a', 'b'], dedupLinks);
assert(dedup.nodeCount === 2, 'duplicate node IDs deduplicated → 2 nodes');
assertClose(dedup.density, 1.0, 0.001, 'deduplicated 2-node with edge → density 1.0');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Coverage rate defaults to 1.0 for in-memory variant
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Coverage Rate Tests ---');

const coverageResult = computeSubgraphDensityFromLinks(['a', 'b'], [{ from_id: 'a', to_id: 'b' }]);
assert(coverageResult.coverageRate === 1.0, 'in-memory variant coverage = 1.0');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Return shape
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Return Shape Tests ---');

const shape = computeSubgraphDensityFromLinks(['a', 'b', 'c'], [{ from_id: 'a', to_id: 'b' }]);
assert(typeof shape.density === 'number', 'density is number');
assert(typeof shape.nodeCount === 'number', 'nodeCount is number');
assert(typeof shape.edgeCount === 'number', 'edgeCount is number');
assert(typeof shape.coverageRate === 'number', 'coverageRate is number');
assert(Object.keys(shape).length === 4, 'return has exactly 4 keys');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Large subgraph (5 nodes, star topology)
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Star Topology Test ---');

// Star: center connected to 4 others, 4 edges / 10 max = 0.4
const starLinks = [
  { from_id: 'center', to_id: 'a' },
  { from_id: 'center', to_id: 'b' },
  { from_id: 'center', to_id: 'c' },
  { from_id: 'center', to_id: 'd' }
];
const star = computeSubgraphDensityFromLinks(['center', 'a', 'b', 'c', 'd'], starLinks);
assertClose(star.density, 4 / 10, 0.001, 'star 5-node density = 0.4');
assert(star.edgeCount === 4, 'star edge count = 4');

// ═══════════════════════════════════════════════════════════════════════════
// Test: Live DB integration (computeSubgraphDensity)
// ═══════════════════════════════════════════════════════════════════════════
console.log('\n--- Live DB Integration Tests ---');

// Test with real node IDs from supermemory.db
const fs = require('fs');
const dbPath = path.join(process.env.HOME, '.claude/memory/supermemory.db');

if (fs.existsSync(dbPath)) {
  // Get some real node IDs
  const { execSync } = require('child_process');
  try {
    const sampleNodes = execSync(
      `sqlite3 "${dbPath}" "SELECT id FROM memory_items LIMIT 10"`,
      { encoding: 'utf8', timeout: 5000 }
    ).trim().split('\n').filter(Boolean);

    if (sampleNodes.length >= 3) {
      const testNodes = sampleNodes.slice(0, 5);
      const start = Date.now();
      const liveResult = computeSubgraphDensity(testNodes);
      const elapsed = Date.now() - start;

      assert(liveResult !== null, 'live DB query returns result');
      assert(liveResult.density >= 0 && liveResult.density <= 1, `live density in [0,1]: ${liveResult.density}`);
      assert(liveResult.nodeCount === testNodes.length, `live nodeCount = ${testNodes.length}`);
      assert(liveResult.edgeCount >= 0, `live edgeCount >= 0: ${liveResult.edgeCount}`);
      assert(elapsed < 100, `live query < 100ms: ${elapsed}ms`);
      console.log(`  INFO: Live query returned density=${liveResult.density}, edges=${liveResult.edgeCount}, time=${elapsed}ms`);

      // Test with topic for coverage rate
      const withTopic = computeSubgraphDensity(testNodes, 'python');
      assert(withTopic !== null, 'live DB with topic returns result');
      assert(withTopic.coverageRate >= 0 && withTopic.coverageRate <= 1, `coverage rate in [0,1]: ${withTopic.coverageRate}`);
      console.log(`  INFO: Coverage rate for "python": ${withTopic.coverageRate}`);
    } else {
      console.log('  SKIP: Not enough items in supermemory.db for live test');
    }
  } catch (e) {
    console.log(`  SKIP: Could not query supermemory.db: ${e.message}`);
  }
} else {
  console.log('  SKIP: supermemory.db not found');
}

// ═══════════════════════════════════════════════════════════════════════════
// Results
// ═══════════════════════════════════════════════════════════════════════════
console.log(`\n═══════════════════════════════════════`);
console.log(`Results: ${passed} passed, ${failed} failed, ${passed + failed} total`);
console.log(`═══════════════════════════════════════\n`);

if (failed > 0) {
  process.exit(1);
}
