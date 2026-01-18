# API REFERENCE

**Complete command and integration reference.**

D-Ecosystem · Metaventions AI

---

## META-ANALYZER

### `meta-analyzer analyze`

Aggregate telemetry and analyze patterns.

```bash
meta-analyzer analyze [--days N] [--json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--days`, `-d` | 7 | Days of telemetry to analyze |
| `--json` | false | Output as JSON |

**Output (default):**
```
============================================================
META-ANALYZER: Co-Evolution Analysis
============================================================

Sessions: 104 | Messages: 27521
Cache Efficiency: 99.88%
DQ Score Avg: 0.839 (stable)
Confidence: 0.85

--- Insights ---
  [+] Excellent cache efficiency...

--- Recommendations ---
  -> Pre-load architecture-specific context...
```

**Output (JSON):**
```json
{
  "telemetry": {
    "aggregatedAt": "2026-01-17T12:00:00",
    "summary": {
      "totalMessages": 27521,
      "totalSessions": 104,
      "cacheEfficiency": 99.88,
      "dqScoreAvg": 0.839
    },
    "patterns": { ... },
    "temporal": { ... }
  },
  "analysis": {
    "insights": [ ... ],
    "recommendations": [ ... ],
    "confidence": 0.85
  }
}
```

---

### `meta-analyzer propose`

Generate modification proposals from analysis.

```bash
meta-analyzer propose [--json]
```

**Output:**
```
Generated 4 modification proposals:

  mod-20260117-000: Batch related queries into fewer sessions
     Type: behavior | Target: CLAUDE.md
     Confidence: 0.85 | Impact: Could improve cache efficiency

Apply with: meta-analyzer apply <mod_id>
```

**Modification Schema:**
```json
{
  "id": "mod-20260117-000",
  "createdAt": "2026-01-17T12:00:00",
  "type": "behavior | context | calibration | efficiency | claude_md_update",
  "action": "Human-readable description",
  "impact": "Expected outcome",
  "confidence": 0.85,
  "status": "proposed | applied | rolled_back",
  "target": "CLAUDE.md | prefetch.py | dq-scorer.js",
  "changes": {
    "file": "~/.claude/CLAUDE.md",
    "type": "section_update",
    "content": "..."
  }
}
```

---

### `meta-analyzer apply`

Apply a modification.

```bash
meta-analyzer apply <mod_id> [--dry-run]
```

| Option | Description |
|--------|-------------|
| `mod_id` | Modification ID (e.g., `mod-20260117-000`) |
| `--dry-run` | Preview without applying |

**Output (dry-run):**
```json
{
  "mod_id": "mod-20260117-claude-md",
  "dry_run": true,
  "backup": "/Users/you/.claude/claude-md-history/CLAUDE.md.20260117_120000",
  "success": true,
  "message": "Would update CLAUDE.md",
  "preview": "## Learned Patterns\n..."
}
```

**Output (apply):**
```json
{
  "mod_id": "mod-20260117-claude-md",
  "dry_run": false,
  "backup": "/Users/you/.claude/claude-md-history/CLAUDE.md.20260117_120000",
  "success": true,
  "message": "CLAUDE.md updated with learned patterns"
}
```

---

### `meta-analyzer rollback`

Revert a modification.

```bash
meta-analyzer rollback <mod_id>
```

**Output:**
```json
{
  "success": true,
  "message": "Rolled back mod-20260117-claude-md from backup"
}
```

---

### `meta-analyzer evaluate`

Evaluate modification effectiveness.

```bash
meta-analyzer evaluate <mod_id> [--sessions N]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--sessions` | 10 | Minimum sessions for comparison |

**Output:**
```json
{
  "mod_id": "mod-20260117-claude-md",
  "metric": "dq_score_avg",
  "before": 0.78,
  "after": 0.82,
  "improvement": 0.04,
  "sessionsCompared": 20,
  "statisticallySignificant": true,
  "evaluatedAt": "2026-01-17T15:00:00"
}
```

---

### `meta-analyzer dashboard`

View system state.

```bash
meta-analyzer dashboard [--json]
```

**Output:**
```
============================================================
CO-EVOLUTION DASHBOARD
============================================================

Status: ENABLED
Auto-Apply: OFF
Min Confidence: 0.7

--- Metrics ---
Cache Efficiency: 99.88%
DQ Score Avg: 0.839

--- Modifications ---
Total: 4 | Applied: 1 | Rolled Back: 0

--- Effectiveness ---
Evaluations: 3
Avg Improvement: 0.025
```

---

### `meta-analyzer config`

View or modify configuration.

```bash
meta-analyzer config [--set KEY VALUE]
```

**View config:**
```json
{
  "version": "1.0.0",
  "enabled": true,
  "autoApply": false,
  "minConfidence": 0.7,
  "maxModificationsPerDay": 3,
  "trackingWindow": {
    "analysis": 7,
    "effectiveness": 14
  },
  "evolution": {
    "selfReferential": true,
    "recursionDepth": 2
  }
}
```

**Set config:**
```bash
meta-analyzer config --set autoApply true
meta-analyzer config --set minConfidence 0.8
```

---

## CONTEXT PREFETCHER

### `prefetch --pattern`

Load pattern-specific context.

```bash
python3 ~/researchgravity/prefetch.py --pattern <pattern>
```

**Patterns:**
| Pattern | Focus Areas | Suggested Tools |
|---------|-------------|-----------------|
| `debugging` | error patterns, root cause | `/debug`, `git diff` |
| `research` | papers, synthesis, gaps | `log_url.py`, `archive_session.py` |
| `architecture` | system design, trade-offs | `/arch`, `prefetch --papers` |
| `refactoring` | code patterns, coverage | `/refactor`, `npm test` |
| `testing` | coverage, edge cases | `/test`, `npm run test:coverage` |
| `performance` | profiling, bottlenecks | `npm run build`, `lighthouse` |
| `deployment` | CI/CD, production | `/pr`, `git status` |
| `learning` | concepts, examples | `prefetch --topic` |

---

### `prefetch --proactive`

Auto-predict pattern and load context.

```bash
python3 ~/researchgravity/prefetch.py --proactive
```

Prediction based on:
1. Current hour (temporal patterns)
2. Recently detected patterns
3. Historical distribution

---

### `prefetch --suggest`

Show proactive suggestions.

```bash
python3 ~/researchgravity/prefetch.py --suggest [--json]
```

**Output:**
```
Proactive Suggestions for: architecture
========================================
Focus: system design, component boundaries, trade-offs
Tools: /arch, prefetch --papers
Research Papers:
  - https://arxiv.org/abs/2507.14241
  - https://arxiv.org/abs/2501.12689
```

**JSON Output:**
```json
{
  "predicted_pattern": "architecture",
  "confidence": 0.7,
  "suggestions": ["/arch", "prefetch --papers"],
  "focus_areas": ["system design", "trade-offs"],
  "research_papers": [
    {"id": "2507.14241", "url": "https://arxiv.org/abs/2507.14241"}
  ]
}
```

---

## PATTERN DETECTOR

### `pattern-detector detect`

Detect active session patterns.

```bash
node ~/.claude/kernel/pattern-detector.js detect [windowMinutes]
```

**Output:**
```json
{
  "detectedAt": "2026-01-17T12:00:00",
  "windowMinutes": 30,
  "activityCount": 15,
  "patterns": [
    {
      "id": "architecture",
      "name": "Architecture Session",
      "icon": "🏗️",
      "confidence": 0.85,
      "totalMatches": 12,
      "suggestions": [...]
    }
  ]
}
```

---

### `pattern-detector learned`

Get suggestions enhanced by effectiveness data.

```bash
node ~/.claude/kernel/pattern-detector.js learned [limit]
```

**Output:**
```json
{
  "hasContext": true,
  "topPattern": {...},
  "activityCount": 15,
  "suggestions": [
    {
      "type": "skill",
      "value": "/arch",
      "label": "Architecture Analysis (proven)",
      "learnedWeight": 1.2,
      "pastSuccess": 5
    }
  ],
  "learned": true
}
```

---

### `pattern-detector log`

Log an activity event.

```bash
node ~/.claude/kernel/pattern-detector.js log "query text" [type]
```

---

### `pattern-detector stats`

View activity statistics.

```bash
node ~/.claude/kernel/pattern-detector.js stats
```

**Output:**
```json
{
  "totalEvents": 500,
  "patterns": {
    "debugging": 45,
    "architecture": 120,
    "research": 80
  },
  "topPatterns": [
    {"id": "architecture", "name": "Architecture Session", "count": 120}
  ],
  "hourlyDistribution": {...}
}
```

---

## SHELL ALIASES

Quick access aliases defined in `~/.claude/init.sh`:

```bash
# Meta-Analyzer
meta-analyzer            # Full command
coevo-analyze            # Analyze patterns
coevo-propose            # Generate proposals
coevo-apply              # Apply modification
coevo-rollback           # Rollback modification
coevo-dashboard          # View dashboard
coevo-config             # Configuration

# Prefetcher
prefetch-pattern         # Pattern-specific context
prefetch-proactive       # Auto-predict pattern
prefetch-suggest         # Show suggestions

# Pattern Detector
suggest-learned          # Enhanced suggestions
```

---

## DATA FILES

### Telemetry Sources

| File | Description |
|------|-------------|
| `~/.claude/stats-cache.json` | Session statistics, token usage, cache metrics |
| `~/.claude/kernel/dq-scores.jsonl` | Decision quality history |
| `~/.claude/data/activity-events.jsonl` | Query logs with timestamps |
| `~/.claude/kernel/detected-patterns.json` | Current session patterns |
| `~/.claude/kernel/identity.json` | Expertise, preferences, achievements |
| `~/.agent-core/memory/learnings.md` | Research synthesis |

### Evolution Outputs

| File | Description |
|------|-------------|
| `~/.claude/kernel/coevo-config.json` | Co-evolution configuration |
| `~/.claude/kernel/modifications.jsonl` | Modification history |
| `~/.claude/kernel/effectiveness.jsonl` | Before/after evaluations |
| `~/.claude/claude-md-history/` | Git-tracked CLAUDE.md backups |

---

## INTEGRATION POINTS

### From Pattern Detector to Meta-Analyzer

```javascript
// pattern-detector.js
function notifyCoEvolution(detection) {
  const event = {
    type: 'pattern_detected',
    timestamp: Date.now(),
    pattern: detection.patterns[0]?.id,
    confidence: detection.patterns[0]?.confidence
  };
  appendToActivityLog(event);
}
```

### From Meta-Analyzer to CLAUDE.md

```python
# meta-analyzer.py
def _update_claude_md_section(new_content):
    # Replaces content between markers
    # <!-- AUTO-GENERATED BY META-ANALYZER -->
    # ...
    # <!-- END AUTO-GENERATED -->
```

### From Effectiveness to Learned Patterns

```javascript
// pattern-detector.js
function applyLearnedPatterns(suggestions, pattern) {
  const effectiveness = loadEffectivenessHistory();
  return suggestions.map(s => ({
    ...s,
    learnedWeight: calculateFromHistory(s, effectiveness)
  }));
}
```

---

<div align="center">

**The complete interface.**

D-Ecosystem · Metaventions AI

</div>
