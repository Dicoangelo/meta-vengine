# Routing System - Quick Reference Card

**Version:** 1.0.0 | **Status:** ✅ Active

---

## 🚀 Essential Commands

### Daily Use
```bash
claude -p "your query"              # Auto-routes (recommended)
routing-dash                        # Performance dashboard
routing-report 7                    # Weekly metrics
```

### Model Override
```bash
claude --model haiku -p "query"     # Force haiku (cheap)
claude --model sonnet -p "query"    # Force sonnet (standard)
claude --model opus -p "query"      # Force opus (complex)
```

### Feedback (Improves Routing)
```bash
ai-good "query prefix"              # Mark success
ai-bad "query prefix"               # Mark failure
ai-feedback-enable                  # Auto-learn from failures
```

---

## 📊 Monitoring

```bash
routing-dash                        # Real-time dashboard
routing-report 30                   # Monthly report
routing-targets                     # Check if targets met
routing-cron logs daily             # View automation logs
```

---

## 🧪 Testing & Optimization

```bash
# Test suite
python3 ~/researchgravity/routing-test-suite.py all

# Generate proposals
meta-analyzer propose --domain routing --days 30

# A/B testing
routing-metrics.py ab-test status
routing-metrics.py ab-test analyze --experiment exp-001
```

---

## 🔄 Automation

```bash
routing-cron status                 # Check automation
routing-auto status                 # Check auto-update readiness
routing-auto approve                # Approve updates (after 30d stable)
```

---

## 🎯 How Routing Works

```
Query → Complexity Analysis (0.0-1.0) → DQ Scoring → Model Selection
  ↓                                                         ↓
  Haiku  (0.00-0.30) Simple, quick, cheap                 ✓
  Sonnet (0.30-0.70) Code, analysis, moderate            [DQ:0.75]
  Opus   (0.70-1.00) Architecture, complex               ✓
```

**DQ Score = Validity (40%) + Specificity (30%) + Correctness (30%)**

---

## 📈 Performance Targets

| Metric | Target | Command |
|--------|--------|---------|
| Accuracy | ≥75% | `routing-report 7` |
| Cost Reduction | ≥20% | `routing-report 7` |
| Latency (p95) | <50ms | `routing-test-suite.py performance` |
| DQ Score | ≥0.70 | `routing-dash` |

---

## 🛠️ Troubleshooting

```bash
# Not routing?
type claude                         # Should show alias
source ~/.claude/init.sh            # Re-activate

# Test DQ scorer
node ~/.claude/kernel/dq-scorer.js route "test"

# Run diagnostics
python3 ~/researchgravity/routing-test-suite.py all
```

---

## 📁 Key Files

```
~/.claude/kernel/baselines.json     # Thresholds & config
~/.claude/data/routing-metrics.jsonl # All routing decisions
~/.claude/data/ai-routing.log       # Activity log
~/.claude/logs/routing-daily.log    # Daily reports
```

---

## 🔗 Full Documentation

- **Complete Guide:** `~/.claude/ROUTING_SYSTEM_README.md`
- **Research Workflow:** `~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md`
- **Implementation:** `~/ROUTING_PHASE_4_5_COMPLETE.md`

---

## 💡 Pro Tips

1. **Let it learn** - Use `ai-feedback-enable` for continuous improvement
2. **Check weekly** - Run `routing-dash` every Friday
3. **Trust the routing** - Avoid manual override unless necessary
4. **Wait 30 days** - System needs data before auto-updating

---

**Installation:** Already active via `~/.claude/init.sh`
**Support:** Run `routing-test-suite.py all` for diagnostics
**Last Updated:** 2026-01-18
