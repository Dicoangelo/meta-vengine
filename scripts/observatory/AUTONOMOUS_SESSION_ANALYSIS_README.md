# Autonomous Session Analysis System

**The meta-learning loop that closes itself.**

A multi-agent system that automatically analyzes Claude Code session transcripts using ACE (Adaptive Consensus Engine) + DQ scoring to determine session quality, outcome, and model efficiency—then feeds insights back to improve routing decisions.

## Overview

This system implements a complete autonomous feedback loop:

```
Session Ends → 6 Agents Analyze → ACE Consensus → Results Logged
                                         ↓
                                    Patterns Detected
                                         ↓
                                  Routing Baselines Updated
                                         ↓
                                  Better Future Sessions
```

### What It Does

- **Autonomous Analysis**: Automatically evaluates every Claude Code session
- **Multi-Agent Architecture**: 6 specialized agents analyze different aspects
- **ACE Consensus**: Adaptive Consensus Engine synthesizes agent results
- **Pattern Detection**: Identifies routing inefficiencies across sessions
- **Self-Improvement**: Automatically updates routing baselines
- **Zero Human Intervention**: Runs completely autonomously

## Architecture

### The 6 Agents

1. **OutcomeDetectorAgent** - Detects session outcome
   - success, partial, error, research, abandoned
   - Analyzes git commits, errors, completion signals

2. **QualityScorerAgent** - Scores session quality (1-5)
   - Based on LOC, file changes, tool success rate
   - Productivity metrics and session flow

3. **ComplexityAnalyzerAgent** - Calculates average complexity (0-1)
   - Query-level complexity analysis
   - Architecture/research/multi-step indicators

4. **ModelEfficiencyAgent** - Evaluates model selection
   - Was optimal model used?
   - Over/under-provisioning detection

5. **ProductivityAnalyzerAgent** - Productivity metrics
   - Read/write ratios
   - LOC velocity (lines per hour)
   - Tool efficiency

6. **RoutingQualityAgent** - Analyzes routing decisions
   - DQ score analysis
   - Routing accuracy trends

### ACE Consensus Engine

Synthesizes agent results using DQ-weighted voting:
- **Validity** (40%): Correctness of analysis
- **Specificity** (30%): Precision of conclusions
- **Correctness** (30%): Accuracy of predictions

## Files

### Core Components

```
~/.claude/scripts/observatory/
├── agents/
│   ├── __init__.py                  # Base agent class
│   ├── outcome_detector.py          # Outcome detection
│   ├── quality_scorer.py            # Quality scoring
│   ├── complexity_analyzer.py       # Complexity analysis
│   ├── model_efficiency.py          # Model efficiency
│   ├── productivity_analyzer.py     # Productivity metrics
│   └── routing_quality.py           # Routing quality
├── ace_consensus.py                 # ACE consensus engine
├── post-session-analyzer.py         # Main orchestrator
├── routing-feedback-loop.py         # Pattern detection & updates
├── auto-trigger.sh                  # Automatic triggering
└── init.sh                          # Observatory initialization (updated)
```

### Data Files

```
~/.claude/data/
├── session-outcomes.jsonl           # Analysis results
└── .last-feedback-loop              # Feedback loop timestamp
```

## Usage

### Manual Analysis

```bash
# Analyze single session
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --session-id <session-id>

# Analyze 10 most recent sessions
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --recent 10

# Analyze all sessions (use with caution!)
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --all

# Save detailed results
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --session-id <session-id> \
  --output /tmp/analysis.json
```

### Feedback Loop

```bash
# Detect routing patterns
python3 ~/.claude/scripts/observatory/routing-feedback-loop.py \
  --detect --days 30

# Generate update proposals
python3 ~/.claude/scripts/observatory/routing-feedback-loop.py \
  --propose --days 30

# Auto-apply high-confidence updates (>=75%)
python3 ~/.claude/scripts/observatory/routing-feedback-loop.py \
  --auto-apply --days 30

# Dry-run mode (show what would happen)
python3 ~/.claude/scripts/observatory/routing-feedback-loop.py \
  --auto-apply --dry-run --days 30
```

### Auto-Trigger Script

```bash
# Post-session hook
~/.claude/scripts/observatory/auto-trigger.sh hook <session-id>

# Batch analysis
~/.claude/scripts/observatory/auto-trigger.sh batch 10

# Run feedback loop
~/.claude/scripts/observatory/auto-trigger.sh feedback 30
```

## Integration

### Automatic Monthly Feedback Loop

The system automatically runs the feedback loop once per month via `init.sh`:

```bash
# Checks if >30 days since last run
# Runs feedback loop in background
# Updates baselines if high-confidence patterns detected
```

### Session-End Trigger (Optional)

To trigger analysis after every session, add to `~/.claude/init.sh`:

```bash
trap '~/.claude/scripts/observatory/auto-trigger.sh hook $CLAUDE_SESSION_ID' EXIT
```

### Periodic Batch Analysis (Optional)

Add to crontab for regular analysis:

```bash
# Analyze 10 recent sessions daily at 2 AM
0 2 * * * ~/.claude/scripts/observatory/auto-trigger.sh batch 10

# Run feedback loop monthly at 3 AM on 1st
0 3 1 * * ~/.claude/scripts/observatory/auto-trigger.sh feedback 30
```

## Data Format

### session-outcomes.jsonl

```json
{
  "ts": 1768815012,
  "event": "session_analysis_complete",
  "session_id": "abc123...",
  "outcome": "success",
  "quality": 4,
  "complexity": 0.65,
  "model_efficiency": 0.89,
  "dq_score": 0.847,
  "confidence": 0.91,
  "optimal_model": "sonnet",
  "auto_analyzed": true
}
```

### Feedback Loop Updates

Updates are tracked in `~/.claude/kernel/baselines.json`:

```json
{
  "feedback_lineage": [
    {
      "update_id": "feedback-20260119-043000-01",
      "applied": "2026-01-19T04:30:00",
      "parameter": "complexity_thresholds.haiku.range[1]",
      "old_value": 0.30,
      "new_value": 0.33,
      "change": 0.03,
      "rationale": "23/67 low-complexity sessions over-provisioned",
      "confidence": 0.82,
      "samples": 67,
      "source": "automated_feedback_loop"
    }
  ]
}
```

## Pattern Detection

The system detects 4 types of routing patterns:

### 1. Over-Provisioning
**Detection**: Low-complexity sessions with low model efficiency
**Action**: Increase Haiku threshold (allow Haiku for more tasks)

### 2. Haiku Struggles
**Detection**: High-complexity sessions on Haiku with low quality
**Action**: Decrease Haiku threshold (route complex tasks to Sonnet/Opus)

### 3. Opus Overuse
**Detection**: Moderate-complexity sessions over-provisioned to Opus
**Action**: Increase Sonnet threshold (allow Sonnet for more tasks)

### 4. Efficiency Issues
**Detection**: Specific complexity ranges with consistently low efficiency
**Action**: Adjust relevant threshold to optimize routing

## Requirements

- Python 3.8+
- Access to `~/.claude/projects/` (session transcripts)
- Access to `~/.claude/kernel/baselines.json` (routing baselines)

## Performance

### Targets

| Metric | Target | Status |
|--------|--------|--------|
| Analysis Coverage | 100% of sessions | 🔄 Building |
| ACE Consensus Confidence | >80% | ✅ ~87% |
| Pattern Detection Rate | ≥1 pattern/month | 🔄 Collecting |
| Model Efficiency Improvement | +10% over 3 months | 🔄 Collecting |
| Routing Accuracy Improvement | +5% over 3 months | 🔄 Collecting |

### Analysis Speed

- Single session: ~5-10 seconds
- 10 sessions: ~1-2 minutes
- 100 sessions: ~10-15 minutes

## Examples

### Example 1: Successful Session

```
🔬 Analyzing session: abc123...
   📄 Loaded transcript: 327 events, 45 messages, 28 tools
   🤖 Running outcome agent...
      ✓ Outcome: success
   🤖 Running quality agent...
      ✓ Quality: 5/5
   🤖 Running complexity agent...
      ✓ Complexity: 0.42
   🤖 Running model_efficiency agent...
      ✓ Efficiency: 89.0% (optimal)
   🤖 Running productivity agent...
      ✓ High productivity (LOC: 1065, velocity: 213/hr)
   🤖 Running routing_quality agent...
      ✓ Avg DQ: 0.87, Accuracy: 92.5%
   🧠 Applying ACE consensus...
      ✓ Consensus reached (confidence: 0.93)
   ✅ Analysis complete: success (quality: 5/5, efficiency: 89.0%)
```

### Example 2: Feedback Loop Detecting Pattern

```
📊 Analyzing 67 sessions from last 30 days...
   ✓ Detected: 23/67 low-complexity sessions over-provisioned

🤖 Auto-applying 1 high-confidence updates...

✅ Applied update: feedback-20260119-043000-01
   complexity_thresholds.haiku.range[1]: 0.300 → 0.330 (+0.030)

✅ Applied 1/1 updates successfully
```

## Troubleshooting

### No sessions found

Check that session files exist:
```bash
ls ~/.claude/projects/
```

### Analysis fails

Check logs:
```bash
tail -50 ~/.claude/logs/auto-analysis.log
```

### Feedback loop doesn't detect patterns

Ensure enough sessions analyzed:
```bash
wc -l ~/.claude/data/session-outcomes.jsonl
# Need at least 30 sessions
```

### Baselines not updating

Check lineage:
```bash
jq '.feedback_lineage' ~/.claude/kernel/baselines.json
```

## Theory

### Why Multi-Agent?

Single-agent analysis is prone to bias. By having 6 specialized agents that each focus on one aspect, we get:
- **Diversity**: Different perspectives on session quality
- **Robustness**: Failures in one agent don't break the system
- **Accuracy**: Consensus emerges from multiple signals

### Why ACE?

ACE (Adaptive Consensus Engine) uses DQ scoring to weight agent contributions. Agents with higher validity/specificity/correctness get more weight in the final decision. This ensures:
- **Quality**: Better analyses influence decisions more
- **Flexibility**: Agent weights adapt based on confidence
- **Transparency**: Full lineage of how consensus was reached

### Why DQ Scoring?

DQ (Data Quality) scoring quantifies analysis quality across 3 dimensions:
- **Validity** (40%): Is the analysis method sound?
- **Specificity** (30%): Is the conclusion precise?
- **Correctness** (30%): Are the results accurate?

This allows mathematical comparison and weighting of analyses.

## Future Enhancements

### Phase 1 (Current)
- ✅ 6-agent analysis
- ✅ ACE consensus
- ✅ Pattern detection
- ✅ Automatic baseline updates

### Phase 2 (Planned)
- [ ] Real-time analysis (file watcher)
- [ ] Dashboard integration
- [ ] Advanced visualizations
- [ ] Per-user pattern learning

### Phase 3 (Future)
- [ ] Cross-project learning
- [ ] Predictive routing
- [ ] A/B testing framework
- [ ] Research paper integration

## Credits

**Author**: Dicoangelo
**System**: Antigravity Ecosystem
**Framework**: ACE (Adaptive Consensus Engine) from OS-App
**Inspiration**: The Meta-Vengine - "The invention is hidden in your vision"

## License

Part of the Antigravity ecosystem.

---

**The engine that teaches itself.**
