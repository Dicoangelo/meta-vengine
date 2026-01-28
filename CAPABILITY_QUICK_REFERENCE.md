# Claude Capability Quick Reference

*Version 2.4.0 - January 2026*

## Status Dashboard

```bash
cap-status           # Full status dashboard
cap-doctor           # Diagnose issues
cap-fix              # Auto-fix issues
cap-json             # JSON output
```

---

## Cognitive-Aware DQ Routing

**Purpose:** Adjusts DQ weights based on cognitive mode (peak/dip/deep_night)

```bash
cos state            # Current cognitive mode
cos fate             # Session outcome prediction
```

**How it works:**
- During `dip`: Less reliance on validity (conserve energy)
- During `deep_night`: More reliance on correctness (use history)
- Exports weights to `cognitive-dq-weights.json` for dq-scorer

---

## Expertise-Aware Routing

**Purpose:** Route based on your tracked expertise domains

```bash
exp-detect "query"   # Detect domain and expertise
exp-route "query" 0.5  # Route with complexity
exp-stats            # Routing statistics
exp-export           # Export expertise state
```

**How it works:**
- High expertise (>70%): DOWNGRADE model (you need less help)
- Low expertise (<30%): UPGRADE model (unfamiliar territory)

**Your Top Domains:**
- react: 100%
- typescript: 100%
- architecture: 100%

---

## Pattern Orchestrator

**Purpose:** Auto-suggest coordinator strategies based on session pattern

```bash
orchestrate-suggest  # Get strategy suggestion
orchestrate-spawn    # Get spawn command
orchestrate-stats    # Pattern statistics
```

**Pattern → Strategy Mapping:**

| Pattern | Strategy | Agents |
|---------|----------|--------|
| debugging | coord review-build | builder + reviewer |
| research | coord research | 3 explore (parallel) |
| architecture | coord full | research → build → review |
| refactoring | coord implement | N builders (file locks) |

---

## Predictive Error Prevention

**Purpose:** Fix errors BEFORE they occur based on patterns

```bash
predict-run          # Run predictions and prevent
predict-dry          # Dry run (show actions)
predict-stats        # Prevention statistics
```

**Auto-fixes:**
- Git locks: Cleared when 2+ failures in 24h
- Permissions: Fixed when 3+ failures in 48h
- Cache: Cleared when stale

---

## Learning Hub

**Purpose:** Unified aggregation of all learning systems

```bash
hub-sync             # Run weekly sync
hub-status           # Current status
hub-insights         # Cross-domain insights
hub-suggestions      # Improvement suggestions
```

**Runs automatically:** 6am and 6pm via LaunchAgent

**Cross-Domain Insights:**
- Correlates routing DQ with expertise
- Links recovery patterns to cognitive state
- Identifies improvement opportunities

---

## Flow Shield

**Purpose:** Protect deep work from interruptions

```bash
cos flow             # Check flow state
```

**When flow score > 0.75:**
- Non-critical alerts deferred
- Model selection locked
- Cost warnings queued

---

## Key Files

| File | Purpose |
|------|---------|
| `~/.claude/kernel/cognitive-os/cognitive-dq-weights.json` | DQ weight adjustments |
| `~/.claude/kernel/expertise-routing-state.json` | Expertise levels |
| `~/.claude/kernel/learning-hub.json` | Aggregated insights |
| `~/.claude/kernel/predictive-state.json` | Error predictions |

---

## Daily Workflow

1. **Session Start** (automatic):
   - Cognitive state detected
   - DQ weights exported
   - Expertise state exported
   - Predictive recovery runs

2. **During Session**:
   - DQ scorer uses cognitive + expertise weights
   - Pattern detection suggests strategies
   - Flow shield protects deep work

3. **Session End** (automatic):
   - Session analyzed
   - Research archived
   - Learnings synced

4. **Twice Daily** (LaunchAgent):
   - Learning Hub sync
   - Cross-domain analysis
   - Improvement suggestions

---

## Troubleshooting

```bash
# Check overall health
cap-status

# Diagnose and fix issues
cap-fix

# Check specific system
cap-check cognitive
cap-check expertise
cap-check hub

# Manual refreshes
exp-export           # Refresh expertise state
cos start            # Refresh cognitive state
hub-sync             # Force learning hub sync
```

---

## Performance Metrics

| Metric | Target | Check |
|--------|--------|-------|
| DQ Score | >0.6 | `hub-status` |
| Cognitive Accuracy | >50% | `cos fate` |
| Recovery Success | >80% | `predict-stats` |
| Expertise Coverage | >5 domains | `exp-stats` |
