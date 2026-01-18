#!/usr/bin/env node
/**
 * Memory Linker - A-MEM Zettelkasten Implementation
 *
 * Based on: "A-MEM: Agentic Memory for LLM Agents"
 * arXiv: https://arxiv.org/abs/2502.12110
 *
 * Implements:
 * - Dynamic note linking via semantic similarity
 * - Memory evolution (existing notes update when related notes added)
 * - Keyword/tag extraction
 * - Graph traversal and clustering
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const KERNEL_DIR = path.join(process.env.HOME, '.claude', 'kernel');
const GRAPH_FILE = path.join(KERNEL_DIR, 'memory-graph.json');
const LEGACY_FILE = path.join(process.env.HOME, '.claude', 'memory', 'knowledge.json');

const RELATIONSHIP_TYPES = ['enables', 'informs', 'contradicts', 'extends', 'related'];

const STOP_WORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
  'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
  'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these',
  'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
  'who', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
  'few', 'more', 'most', 'other', 'some', 'such', 'no', 'not', 'only',
  'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now'
]);

// ═══════════════════════════════════════════════════════════════════════════
// GRAPH OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════

function loadGraph() {
  if (fs.existsSync(GRAPH_FILE)) {
    return JSON.parse(fs.readFileSync(GRAPH_FILE, 'utf8'));
  }
  return {
    version: '1.0.0',
    schema: 'zettelkasten',
    created: new Date().toISOString(),
    lastUpdated: new Date().toISOString(),
    metadata: { totalNotes: 0, totalLinks: 0, clusters: [], topKeywords: [] },
    notes: {},
    links: [],
    config: {
      autoLink: true,
      evolutionEnabled: true,
      minSimilarityForLink: 0.3,
      maxLinksPerNote: 10
    }
  };
}

function saveGraph(graph) {
  graph.lastUpdated = new Date().toISOString();
  graph.metadata.totalNotes = Object.keys(graph.notes).length;
  graph.metadata.totalLinks = graph.links.length;
  fs.writeFileSync(GRAPH_FILE, JSON.stringify(graph, null, 2));
}

function generateId() {
  return crypto.randomBytes(8).toString('hex');
}

// ═══════════════════════════════════════════════════════════════════════════
// TEXT ANALYSIS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Extract keywords from text
 */
function extractKeywords(text, limit = 10) {
  const words = text.toLowerCase()
    .replace(/[^\w\s]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 2 && !STOP_WORDS.has(w));

  // Count frequency
  const freq = {};
  for (const word of words) {
    freq[word] = (freq[word] || 0) + 1;
  }

  // Sort by frequency and return top keywords
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([word]) => word);
}

/**
 * Generate context description for a note
 */
function generateContext(content, type) {
  const keywords = extractKeywords(content, 5);
  const preview = content.slice(0, 100).replace(/\n/g, ' ');
  return `[${type}] ${preview}... Keywords: ${keywords.join(', ')}`;
}

/**
 * Calculate Jaccard similarity between two sets of keywords
 */
function calculateSimilarity(keywords1, keywords2) {
  const set1 = new Set(keywords1);
  const set2 = new Set(keywords2);

  const intersection = [...set1].filter(k => set2.has(k)).length;
  const union = new Set([...set1, ...set2]).size;

  return union > 0 ? intersection / union : 0;
}

/**
 * Infer relationship type based on content analysis
 */
function inferRelationship(note1, note2) {
  const content1 = note1.content.toLowerCase();
  const content2 = note2.content.toLowerCase();

  // Check for contradiction signals
  if (content1.includes('not') || content1.includes("don't") ||
      content2.includes('instead') || content2.includes('rather than')) {
    return 'contradicts';
  }

  // Check for extension signals
  if (content2.includes('also') || content2.includes('additionally') ||
      content2.includes('furthermore') || content2.includes('moreover')) {
    return 'extends';
  }

  // Check for enablement signals
  if (content2.includes('because') || content2.includes('therefore') ||
      content2.includes('enables') || content2.includes('allows')) {
    return 'enables';
  }

  // Check for informational relationship
  if (content2.includes('means') || content2.includes('refers to') ||
      content2.includes('is defined') || content2.includes('explains')) {
    return 'informs';
  }

  // Default to related
  return 'related';
}

// ═══════════════════════════════════════════════════════════════════════════
// CORE OPERATIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a new memory note
 */
function createNote(content, type = 'fact', tags = []) {
  const id = generateId();
  const keywords = extractKeywords(content);
  const context = generateContext(content, type);

  return {
    id,
    type,
    content,
    context,
    keywords: [...new Set([...keywords, ...tags])],
    tags,
    links: [],
    created: new Date().toISOString(),
    evolved: new Date().toISOString(),
    accessCount: 0,
    decayFactor: 1.0
  };
}

/**
 * Find related notes based on keyword similarity
 */
function findRelatedNotes(note, graph, minSimilarity = 0.3, limit = 10) {
  const related = [];

  for (const [id, existingNote] of Object.entries(graph.notes)) {
    if (id === note.id) continue;

    const similarity = calculateSimilarity(note.keywords, existingNote.keywords);
    if (similarity >= minSimilarity) {
      related.push({
        note: existingNote,
        similarity
      });
    }
  }

  // Sort by similarity and limit
  return related
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, limit);
}

/**
 * Create a link between two notes
 */
function createLink(sourceId, targetId, relationship, strength, graph) {
  // Check if link already exists
  const existing = graph.links.find(
    l => l.source === sourceId && l.target === targetId
  );

  if (existing) {
    // Update existing link
    existing.strength = Math.max(existing.strength, strength);
    existing.updated = new Date().toISOString();
    return existing;
  }

  const link = {
    id: generateId(),
    source: sourceId,
    target: targetId,
    relationship,
    strength,
    created: new Date().toISOString()
  };

  graph.links.push(link);

  // Update note's link references
  if (graph.notes[sourceId]) {
    graph.notes[sourceId].links.push({ targetId, relationship, strength });
  }
  if (graph.notes[targetId]) {
    graph.notes[targetId].links.push({ targetId: sourceId, relationship: inverseRelationship(relationship), strength });
  }

  return link;
}

/**
 * Get inverse relationship
 */
function inverseRelationship(rel) {
  const inverses = {
    'enables': 'enabled_by',
    'enabled_by': 'enables',
    'informs': 'informed_by',
    'informed_by': 'informs',
    'contradicts': 'contradicts',
    'extends': 'extended_by',
    'extended_by': 'extends',
    'related': 'related'
  };
  return inverses[rel] || 'related';
}

/**
 * Evolve a note's context based on new information (A-MEM key innovation)
 */
function evolveNote(noteId, triggeringNote, graph) {
  const note = graph.notes[noteId];
  if (!note) return false;

  // Add evolution marker to context
  const evolutionMarker = `[Evolved ${new Date().toISOString().slice(0, 10)}]: Now connected to "${triggeringNote.content.slice(0, 40)}..."`;

  // Merge keywords
  const newKeywords = [...new Set([...note.keywords, ...triggeringNote.keywords.slice(0, 3)])];

  // Update note
  note.context = `${note.context}\n${evolutionMarker}`;
  note.keywords = newKeywords.slice(0, 15); // Cap at 15 keywords
  note.evolved = new Date().toISOString();

  return true;
}

/**
 * Store a note with automatic linking and evolution
 */
function storeWithEvolution(content, type = 'fact', tags = []) {
  const graph = loadGraph();

  // Create the new note
  const note = createNote(content, type, tags);

  // Find related notes
  const minSimilarity = graph.config.minSimilarityForLink || 0.3;
  const related = findRelatedNotes(note, graph, minSimilarity);

  // Create links and evolve related notes
  for (const { note: relatedNote, similarity } of related) {
    const relationship = inferRelationship(note, relatedNote);

    // Create bidirectional links
    createLink(note.id, relatedNote.id, relationship, similarity, graph);

    // Evolve the related note (A-MEM innovation)
    if (graph.config.evolutionEnabled) {
      evolveNote(relatedNote.id, note, graph);
    }
  }

  // Store the note
  graph.notes[note.id] = note;

  // Update metadata
  updateMetadata(graph);

  saveGraph(graph);

  return {
    note,
    linksCreated: related.length,
    relatedNotes: related.map(r => ({
      id: r.note.id,
      preview: r.note.content.slice(0, 50),
      similarity: r.similarity.toFixed(3)
    }))
  };
}

/**
 * Recall notes by query
 */
function recallNotes(query, options = {}) {
  const graph = loadGraph();
  const { type, limit = 10, includeLinks = true } = options;

  const queryKeywords = extractKeywords(query);
  const results = [];

  for (const [id, note] of Object.entries(graph.notes)) {
    // Filter by type if specified
    if (type && note.type !== type) continue;

    // Calculate relevance
    const similarity = calculateSimilarity(queryKeywords, note.keywords);
    const contentMatch = note.content.toLowerCase().includes(query.toLowerCase()) ? 0.3 : 0;
    const relevance = similarity + contentMatch;

    if (relevance > 0.1) {
      // Increment access count
      note.accessCount = (note.accessCount || 0) + 1;

      results.push({
        ...note,
        relevance,
        linkedNotes: includeLinks ? note.links.length : undefined
      });
    }
  }

  // Sort by relevance
  results.sort((a, b) => b.relevance - a.relevance);

  // Save access counts
  saveGraph(graph);

  return results.slice(0, limit);
}

/**
 * Get graph visualization data
 */
function getGraphData(centerId = null, depth = 2) {
  const graph = loadGraph();

  if (!centerId) {
    // Return full graph summary
    return {
      nodes: Object.values(graph.notes).map(n => ({
        id: n.id,
        type: n.type,
        preview: n.content.slice(0, 50),
        keywords: n.keywords.slice(0, 5),
        linkCount: n.links.length
      })),
      links: graph.links.map(l => ({
        source: l.source,
        target: l.target,
        relationship: l.relationship,
        strength: l.strength
      })),
      metadata: graph.metadata
    };
  }

  // BFS to get subgraph around center
  const visited = new Set();
  const nodes = [];
  const links = [];
  const queue = [{ id: centerId, depth: 0 }];

  while (queue.length > 0) {
    const { id, depth: currentDepth } = queue.shift();
    if (visited.has(id) || currentDepth > depth) continue;
    visited.add(id);

    const note = graph.notes[id];
    if (!note) continue;

    nodes.push({
      id: note.id,
      type: note.type,
      preview: note.content.slice(0, 50),
      keywords: note.keywords.slice(0, 5),
      depth: currentDepth
    });

    // Add connected nodes to queue
    for (const link of note.links) {
      if (!visited.has(link.targetId)) {
        queue.push({ id: link.targetId, depth: currentDepth + 1 });
        links.push({
          source: id,
          target: link.targetId,
          relationship: link.relationship,
          strength: link.strength
        });
      }
    }
  }

  return { nodes, links, center: centerId };
}

/**
 * Update graph metadata
 */
function updateMetadata(graph) {
  // Count keywords across all notes
  const keywordCounts = {};
  for (const note of Object.values(graph.notes)) {
    for (const keyword of note.keywords) {
      keywordCounts[keyword] = (keywordCounts[keyword] || 0) + 1;
    }
  }

  // Top keywords
  graph.metadata.topKeywords = Object.entries(keywordCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20)
    .map(([keyword, count]) => ({ keyword, count }));

  // Simple clustering by type
  graph.metadata.clusters = Object.entries(
    Object.values(graph.notes).reduce((acc, note) => {
      acc[note.type] = (acc[note.type] || 0) + 1;
      return acc;
    }, {})
  ).map(([type, count]) => ({ type, count }));
}

/**
 * Migrate from legacy flat memory to graph
 */
function migrateFromLegacy() {
  if (!fs.existsSync(LEGACY_FILE)) {
    return { migrated: 0, message: 'No legacy memory found' };
  }

  const legacy = JSON.parse(fs.readFileSync(LEGACY_FILE, 'utf8'));
  const graph = loadGraph();
  let migrated = 0;

  // Migrate facts
  for (const fact of legacy.facts || []) {
    storeWithEvolution(fact.content, 'fact', fact.tags || []);
    migrated++;
  }

  // Migrate decisions
  for (const decision of legacy.decisions || []) {
    storeWithEvolution(decision.content, 'decision', decision.tags || []);
    migrated++;
  }

  // Migrate patterns
  for (const pattern of legacy.patterns || []) {
    storeWithEvolution(pattern.content, 'pattern', pattern.tags || []);
    migrated++;
  }

  return { migrated, message: `Migrated ${migrated} notes to graph` };
}

/**
 * Get memory statistics
 */
function getStats() {
  const graph = loadGraph();

  const typeBreakdown = {};
  let totalLinks = 0;
  let totalAccess = 0;

  for (const note of Object.values(graph.notes)) {
    typeBreakdown[note.type] = (typeBreakdown[note.type] || 0) + 1;
    totalLinks += note.links.length;
    totalAccess += note.accessCount || 0;
  }

  return {
    totalNotes: Object.keys(graph.notes).length,
    totalLinks: graph.links.length,
    avgLinksPerNote: Object.keys(graph.notes).length > 0
      ? (totalLinks / Object.keys(graph.notes).length).toFixed(2)
      : 0,
    typeBreakdown,
    topKeywords: graph.metadata.topKeywords.slice(0, 10),
    totalAccess,
    graphDensity: Object.keys(graph.notes).length > 1
      ? (graph.links.length / (Object.keys(graph.notes).length * (Object.keys(graph.notes).length - 1))).toFixed(4)
      : 0
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════════════════════

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'store':
      // Store a note: node memory-linker.js store "content" [type] [tags...]
      const content = args[1];
      const type = args[2] || 'fact';
      const tags = args.slice(3);
      if (!content) {
        console.error('Usage: memory-linker.js store "content" [type] [tags...]');
        process.exit(1);
      }
      const result = storeWithEvolution(content, type, tags);
      console.log(JSON.stringify(result, null, 2));
      break;

    case 'recall':
      // Recall notes: node memory-linker.js recall "query" [limit]
      const query = args[1];
      const limit = parseInt(args[2]) || 10;
      if (!query) {
        console.error('Usage: memory-linker.js recall "query" [limit]');
        process.exit(1);
      }
      const notes = recallNotes(query, { limit });
      console.log(JSON.stringify(notes, null, 2));
      break;

    case 'graph':
      // Get graph: node memory-linker.js graph [centerId] [depth]
      const centerId = args[1] || null;
      const depth = parseInt(args[2]) || 2;
      const graphData = getGraphData(centerId, depth);
      console.log(JSON.stringify(graphData, null, 2));
      break;

    case 'stats':
      // Get stats: node memory-linker.js stats
      console.log(JSON.stringify(getStats(), null, 2));
      break;

    case 'migrate':
      // Migrate from legacy: node memory-linker.js migrate
      const migration = migrateFromLegacy();
      console.log(JSON.stringify(migration, null, 2));
      break;

    case 'keywords':
      // Extract keywords: node memory-linker.js keywords "text"
      const text = args[1];
      if (!text) {
        console.error('Usage: memory-linker.js keywords "text"');
        process.exit(1);
      }
      console.log(JSON.stringify(extractKeywords(text), null, 2));
      break;

    default:
      console.log('Memory Linker - A-MEM Zettelkasten Implementation');
      console.log('');
      console.log('Commands:');
      console.log('  store "content" [type] [tags...]  - Store note with auto-linking');
      console.log('  recall "query" [limit]            - Search notes by relevance');
      console.log('  graph [centerId] [depth]          - Get graph visualization data');
      console.log('  stats                             - Memory statistics');
      console.log('  migrate                           - Migrate from legacy flat memory');
      console.log('  keywords "text"                   - Extract keywords from text');
      console.log('');
      console.log('Types: fact, decision, pattern, insight');
  }
}

module.exports = {
  storeWithEvolution,
  recallNotes,
  getGraphData,
  getStats,
  migrateFromLegacy,
  extractKeywords,
  createNote,
  findRelatedNotes
};
