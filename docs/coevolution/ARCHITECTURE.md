<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=rect&color=0:0d1117,100:1a1a2e&height=100&section=header&text=ARCHITECTURE&fontSize=40&fontColor=00d9ff&fontAlignY=50" />
</p>

<p align="center">
  <strong>System Topology · Data Flow · Integration Points</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Meta--Vengine-Architecture-00d9ff?style=for-the-badge&labelColor=0d1117" alt="Architecture" />
  <img src="https://img.shields.io/badge/D--Ecosystem-Metaventions_AI-9945ff?style=for-the-badge&labelColor=0d1117" alt="D-Ecosystem" />
</p>

---

## System Topology

```
                              ┌─────────────────────────────────────┐
                              │         HUMAN OPERATOR              │
                              │     (Sovereign Terminal User)       │
                              └──────────────┬──────────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                           INTERACTION LAYER                                     │
│                                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │   Claude    │  │   Shell     │  │  Prefetch   │  │   Pattern Detector  │   │
│  │   Code CLI  │  │   Aliases   │  │   Context   │  │   (Proactive VA)    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │
│         │                │                │                     │              │
└─────────┼────────────────┼────────────────┼─────────────────────┼──────────────┘
          │                │                │                     │
          ▼                ▼                ▼                     ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                           KERNEL LAYER                                          │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                 │
│  │   DQ Scorer     │  │   Complexity    │  │   Identity      │                 │
│  │   (ACE Framework)│  │   Analyzer     │  │   Manager       │                 │
│  │                 │  │                 │  │                 │                 │
│  │  validity: 0.4  │  │  signals →      │  │  expertise →    │                 │
│  │  specific: 0.3  │  │  complexity     │  │  preferences    │                 │
│  │  correct:  0.3  │  │  score          │  │  achievements   │                 │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                 │
│           │                    │                    │                          │
│           └────────────────────┼────────────────────┘                          │
│                                │                                               │
│                                ▼                                               │
│                    ┌─────────────────────┐                                     │
│                    │   TELEMETRY BUS     │                                     │
│                    │                     │                                     │
│                    │  Events → JSONL     │                                     │
│                    │  Scores → JSONL     │                                     │
│                    │  Patterns → JSON    │                                     │
│                    └──────────┬──────────┘                                     │
│                               │                                                │
└───────────────────────────────┼────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                           DATA LAYER                                            │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         ~/.claude/                                        │  │
│  │                                                                           │  │
│  │  stats-cache.json ──────── Session counts, token usage, cache metrics    │  │
│  │  kernel/                                                                  │  │
│  │    ├── dq-scores.jsonl ── Decision quality history                       │  │
│  │    ├── identity.json ──── Expertise, preferences, achievements           │  │
│  │    ├── detected-patterns.json ── Current session patterns                │  │
│  │    ├── coevo-config.json ── Co-evolution configuration                   │  │
│  │    ├── modifications.jsonl ── Modification history                       │  │
│  │    └── effectiveness.jsonl ── Before/after metrics                       │  │
│  │  data/                                                                    │  │
│  │    └── activity-events.jsonl ── Query logs with timestamps               │  │
│  │  claude-md-history/                                                       │  │
│  │    └── .git/ ──────────── Version control for CLAUDE.md                  │  │
│  │                                                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                         ~/.agent-core/                                    │  │
│  │                                                                           │  │
│  │  memory/learnings.md ──── Extracted research learnings                   │  │
│  │  projects.json ────────── Project registry with lineage                  │  │
│  │  sessions/ ────────────── Archived research sessions                     │  │
│  │                                                                           │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│                           CO-EVOLUTION LAYER                                    │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                                                                          │   │
│  │                        META-ANALYZER                                     │   │
│  │                     (meta-analyzer.py)                                   │   │
│  │                                                                          │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │ Aggregate  │  │  Analyze   │  │  Generate  │  │  Evaluate  │        │   │
│  │  │ Telemetry  │─▶│  Patterns  │─▶│   Mods     │─▶│  Effect    │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘        │   │
│  │        │                                               │                │   │
│  │        │              ┌────────────┐                   │                │   │
│  │        └─────────────▶│   Apply    │◀──────────────────┘                │   │
│  │                       │   (Human   │                                    │   │
│  │                       │   Review)  │                                    │   │
│  │                       └─────┬──────┘                                    │   │
│  │                             │                                           │   │
│  └─────────────────────────────┼───────────────────────────────────────────┘   │
│                                │                                               │
│                                ▼                                               │
│                    ┌─────────────────────┐                                     │
│                    │     CLAUDE.md       │                                     │
│                    │   (Instructions)    │                                     │
│                    │                     │                                     │
│                    │  ┌───────────────┐  │                                     │
│                    │  │ Learned       │  │                                     │
│                    │  │ Patterns      │  │  ◀── Auto-generated section         │
│                    │  │ Section       │  │                                     │
│                    │  └───────────────┘  │                                     │
│                    └─────────────────────┘                                     │
│                                                                                 │
└────────────────────────────────────────────────────────────────────────────────┘
                                │
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
            ┌─────────────┐         ┌─────────────┐
            │   NEXT      │         │  FEEDBACK   │
            │   SESSION   │────────▶│   LOOP      │
            │   STARTS    │         │   CLOSES    │
            └─────────────┘         └─────────────┘
```

---

## Component Specifications

### 1. Meta-Analyzer (`meta-analyzer.py`)

The core engine of the co-evolution system.

**Responsibilities:**
- Aggregate telemetry from 6+ data sources
- Analyze patterns with confidence scoring
- Generate modification proposals
- Apply modifications with git-tracked rollback
- Evaluate effectiveness with statistical significance

**Data Flow:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     META-ANALYZER PIPELINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   INPUT                    PROCESS                    OUTPUT     │
│                                                                  │
│   stats-cache.json    ┌─────────────────┐                       │
│   dq-scores.jsonl ───▶│ aggregate_      │                       │
│   activity-events     │ telemetry()     │──▶ Unified View       │
│   patterns.json       └─────────────────┘                       │
│   identity.json                │                                │
│   learnings.md                 ▼                                │
│                       ┌─────────────────┐                       │
│                       │ analyze_        │                       │
│                       │ patterns()      │──▶ Insights +         │
│                       └─────────────────┘    Recommendations    │
│                                │                                │
│                                ▼                                │
│                       ┌─────────────────┐                       │
│                       │ generate_       │                       │
│                       │ modifications() │──▶ Proposals          │
│                       └─────────────────┘                       │
│                                │                                │
│                                ▼                                │
│                       ┌─────────────────┐                       │
│                       │ apply_          │                       │
│   Human Approval ────▶│ modification()  │──▶ CLAUDE.md Update   │
│                       └─────────────────┘                       │
│                                │                                │
│                                ▼                                │
│                       ┌─────────────────┐                       │
│                       │ evaluate_       │                       │
│                       │ effectiveness() │──▶ Before/After       │
│                       └─────────────────┘    Comparison         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Configuration Schema:**

```json
{
  "version": "1.0.0",
  "enabled": true,
  "autoApply": false,
  "minConfidence": 0.7,
  "maxModificationsPerDay": 3,
  "rollbackOnEfficiencyDrop": 0.5,
  "trackingWindow": {
    "analysis": 7,
    "effectiveness": 14,
    "selfReflection": 30
  },
  "weights": {
    "usagePatterns": 0.3,
    "dqScores": 0.25,
    "cacheEfficiency": 0.2,
    "sessionDiversity": 0.15,
    "feedbackCorrelation": 0.1
  },
  "evolution": {
    "selfReferential": true,
    "analyzeOwnModifications": true,
    "metaMetricsEnabled": true,
    "recursionDepth": 2
  }
}
```

---

### 2. Pattern Detector (`pattern-detector.js`)

Implements ProactiveVA for real-time session pattern detection.

**Pattern Taxonomy:**

```
┌─────────────────────────────────────────────────────────────────┐
│                      SESSION PATTERNS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  DEBUGGING         RESEARCH          REFACTORING                │
│  ─────────         ────────          ───────────                │
│  error, fix        arxiv, paper      refactor, clean            │
│  bug, debug        study, survey     extract, rename            │
│  broken, why       methodology       restructure                │
│                                                                  │
│  TESTING           ARCHITECTURE      PERFORMANCE                │
│  ───────           ────────────      ───────────                │
│  test, spec        design, system    optimize, slow             │
│  coverage          component, api    profile, memory            │
│  assert, mock      schema, pattern   bottleneck                 │
│                                                                  │
│  DEPLOYMENT        LEARNING                                      │
│  ──────────        ────────                                      │
│  deploy, release   learn, explain                               │
│  production, CI    tutorial, help                               │
│  docker, k8s       documentation                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Detection Algorithm:**

```
1. Load recent activity (configurable window, default 30 min)
2. For each pattern:
   a. Match query text against signal keywords
   b. Count matches across activity window
   c. Check threshold (minMatches, minEvents)
   d. Calculate confidence = matches / (threshold * 2)
3. Sort patterns by confidence
4. Return top patterns with suggestions
5. Notify co-evolution system (optional)
```

**Co-Evolution Integration:**

```javascript
// Pattern detection feeds meta-analyzer
function notifyCoEvolution(detection) {
  const event = {
    type: 'pattern_detected',
    timestamp: Date.now(),
    pattern: detection.patterns[0]?.id,
    confidence: detection.patterns[0]?.confidence,
    activityCount: detection.activityCount
  };
  appendToActivityLog(event);
}

// Suggestions enhanced by effectiveness history
function applyLearnedPatterns(suggestions, pattern) {
  const effectiveness = loadEffectivenessHistory();
  return suggestions.map(s => ({
    ...s,
    learnedWeight: calculateWeight(s, pattern, effectiveness),
    label: wasSuccessful(s) ? `${s.label} (proven)` : s.label
  }));
}
```

---

### 3. Context Prefetcher (`prefetch.py`)

Proactive context loading with pattern prediction.

**Prediction Model:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    PATTERN PREDICTION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  INPUT SIGNALS                         WEIGHTS                   │
│  ─────────────                         ───────                   │
│                                                                  │
│  1. Current Hour (temporal)            0.30                      │
│     06-10 → research, learning                                  │
│     10-12 → architecture, debugging                             │
│     14-17 → architecture, refactoring                           │
│     17-20 → debugging, testing, deployment                      │
│     20-24 → research, learning                                  │
│                                                                  │
│  2. Recently Detected Pattern          0.50                      │
│     (from pattern-detector.js)                                  │
│                                                                  │
│  3. Historical Distribution            0.20                      │
│     (from activity-events.jsonl)                                │
│                                                                  │
│  OUTPUT: Pattern with confidence ≥ 0.30                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Pattern-Specific Resources:**

```python
PATTERN_RESEARCH_PAPERS = {
    "debugging": {
        "papers": ["2512.20845", "2506.08410"],  # MAR, reflexion
        "focus": ["error patterns", "root cause analysis"],
        "tools": ["/debug", "git diff"]
    },
    "research": {
        "papers": ["2511.16931", "2512.12686"],  # OmniScientist, Memoria
        "focus": ["papers", "synthesis", "thesis gaps"],
        "tools": ["log_url.py", "archive_session.py"]
    },
    "architecture": {
        "papers": ["2507.14241", "2501.12689"],  # Promptomatix, IC-Cache
        "focus": ["system design", "trade-offs"],
        "tools": ["/arch", "prefetch --papers"]
    }
    # ... etc
}
```

---

### 4. DQ Scorer (`dq-scorer.js`)

Decision quality framework for intelligent model routing.

**Scoring Components:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    DQ SCORING FORMULA                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   DQ = (Validity × 0.4) + (Specificity × 0.3) + (Correctness × 0.3)
│                                                                  │
│   VALIDITY (0.4)                                                │
│   ──────────────                                                │
│   Does the model match the task complexity?                     │
│                                                                  │
│   Complexity   Ideal Model                                      │
│   0.00 - 0.25  haiku                                           │
│   0.25 - 0.50  sonnet                                          │
│   0.50 - 0.75  sonnet                                          │
│   0.75 - 1.00  opus                                            │
│                                                                  │
│   SPECIFICITY (0.3)                                             │
│   ─────────────────                                             │
│   How precise is the model selection?                           │
│   1.0 = exact match to ideal                                   │
│   0.6 = adjacent model (one step away)                         │
│   0.2 = distant model (two steps away)                         │
│                                                                  │
│   CORRECTNESS (0.3)                                             │
│   ─────────────────                                             │
│   Historical accuracy for similar queries                       │
│   Based on feedback (ai-good / ai-bad)                         │
│   Falls back to average DQ if no feedback                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Schemas

### Stats Cache (`stats-cache.json`)

```typescript
interface StatsCache {
  version: number;
  lastComputedDate: string;
  dailyActivity: Array<{
    date: string;
    messageCount: number;
    sessionCount: number;
    toolCallCount: number;
  }>;
  dailyModelTokens: Array<{
    date: string;
    tokensByModel: Record<string, number>;
  }>;
  modelUsage: Record<string, {
    inputTokens: number;
    outputTokens: number;
    cacheReadInputTokens: number;
    cacheCreationInputTokens: number;
  }>;
  totalSessions: number;
  totalMessages: number;
  hourCounts: Record<string, number>;
}
```

### Modification Log (`modifications.jsonl`)

```typescript
interface Modification {
  id: string;                    // mod-YYYYMMDD-NNN
  createdAt: string;             // ISO timestamp
  type: 'behavior' | 'context' | 'calibration' | 'efficiency' | 'claude_md_update';
  action: string;                // Human-readable description
  impact: string;                // Expected outcome
  confidence: number;            // 0.0 - 1.0
  status: 'proposed' | 'applied' | 'rolled_back';
  target: string;                // File to modify
  changes: {
    file: string;
    type: 'section_update' | 'weight_adjustment' | 'add_instruction';
    content: string;
  };
}
```

### Effectiveness Log (`effectiveness.jsonl`)

```typescript
interface EffectivenessEvaluation {
  mod_id: string;
  metric: string;
  before: number;
  after: number;
  improvement: number;
  sessionsCompared: number;
  statisticallySignificant: boolean;
  evaluatedAt: string;
}
```

---

## Security Model

### Principle: Sovereign by Default

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY BOUNDARIES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  LOCAL ONLY                                                      │
│  ──────────                                                      │
│  • All data stored in ~/.claude and ~/.agent-core               │
│  • No external API calls for co-evolution                       │
│  • No telemetry sent to cloud services                          │
│  • Git history local to machine                                 │
│                                                                  │
│  HUMAN IN THE LOOP                                               │
│  ─────────────────                                               │
│  • autoApply defaults to false                                  │
│  • All modifications require explicit approval                  │
│  • Dry-run available for preview                                │
│  • Rollback always possible                                     │
│                                                                  │
│  BOUNDED RECURSION                                               │
│  ─────────────────                                               │
│  • recursionDepth capped at 2                                   │
│  • Self-modification limited to instruction files               │
│  • Cannot modify its own core logic                             │
│                                                                  │
│  AUDIT TRAIL                                                     │
│  ───────────                                                     │
│  • All modifications logged with timestamps                     │
│  • Before/after metrics captured                                │
│  • Git history for CLAUDE.md changes                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Performance Characteristics

| Operation | Complexity | Typical Duration |
|-----------|------------|------------------|
| Aggregate telemetry | O(n) | 50-200ms |
| Pattern detection | O(n × p) | 10-50ms |
| Modification generation | O(r) | 100-500ms |
| Effectiveness evaluation | O(s) | 20-100ms |

Where:
- n = number of events in time window
- p = number of patterns (8)
- r = number of recommendations
- s = number of sessions for comparison

---

## Extension Points

### Adding New Patterns

```javascript
// In pattern-detector.js
const PATTERNS = {
  // Add new pattern
  security: {
    name: 'Security Session',
    icon: '🔒',
    signals: ['vulnerability', 'CVE', 'security', 'auth', 'permission'],
    minMatches: 2,
    windowMinutes: 20,
    suggestions: [
      { type: 'command', value: 'npm audit', label: 'Run audit' }
    ]
  }
};
```

### Adding New Metrics

```python
# In meta-analyzer.py
def aggregate_telemetry(days: int = 7) -> Dict[str, Any]:
    # Add new metric
    custom_metric = calculate_custom_metric()

    return {
        # ... existing metrics
        "customMetrics": {
            "yourMetric": custom_metric
        }
    }
```

### Custom Modification Types

```python
# In meta-analyzer.py
def _generate_changes(recommendation, telemetry):
    if recommendation['type'] == 'custom_action':
        return {
            "file": "~/.claude/custom/config.json",
            "type": "custom_modification",
            "content": generate_custom_content()
        }
```

---

<div align="center">

**Metaventions AI**

*Architecture for Sovereign Intelligence*

</div>
