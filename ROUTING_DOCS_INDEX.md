# Routing System - Documentation Index

**Version:** 1.0.0
**Last Updated:** 2026-01-18
**Status:** ✅ Production-Ready

---

## 📚 Documentation Library

### Quick Start

- **[Quick Reference Card](ROUTING_QUICK_REFERENCE.md)** ← Start here for daily use
  - Essential commands
  - Common workflows
  - Troubleshooting shortcuts

### Complete Guides

- **[System README](ROUTING_SYSTEM_README.md)** ← Main documentation
  - Full architecture and design
  - All commands with examples
  - Configuration guide
  - Advanced usage

### Implementation Documentation

- **[Phase 1-3 Implementation](~/ROUTING_IMPLEMENTATION_COMPLETE.md)**
  - Initial routing activation
  - Metrics and baselines
  - Research integration
  - Setup and testing

- **[Phase 4-5 Implementation](~/ROUTING_PHASE_4_5_COMPLETE.md)**
  - A/B testing framework
  - Meta-analyzer optimization
  - Automation and auto-update
  - Production deployment

### Workflow Guides

- **[Research Integration Workflow](~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md)**
  - arXiv paper fetching
  - Insight extraction
  - Baseline updates
  - Lineage tracking

---

## 🎯 Documentation by Task

### I want to...

**Get started with routing**
→ Read: [Quick Reference](ROUTING_QUICK_REFERENCE.md)
→ Run: `routing-dash`

**Understand how it works**
→ Read: [System README - Architecture](ROUTING_SYSTEM_README.md#-architecture)
→ Run: `routing-test-suite.py all`

**Monitor performance**
→ Read: [System README - Monitoring](ROUTING_SYSTEM_README.md#-core-commands)
→ Run: `routing-report 7`

**Optimize routing decisions**
→ Read: [Phase 4-5 Docs - Optimization](~/ROUTING_PHASE_4_5_COMPLETE.md#phase-4-performance-optimization)
→ Run: `meta-analyzer propose --domain routing`

**Set up automation**
→ Read: [Phase 4-5 Docs - Automation](~/ROUTING_PHASE_4_5_COMPLETE.md#1-cron-automation-setup)
→ Run: `routing-cron install standard`

**Enable auto-updates**
→ Read: [Phase 4-5 Docs - Auto-Update](~/ROUTING_PHASE_4_5_COMPLETE.md#2-auto-update-system-with-production-validation)
→ Run: `routing-auto status`

**Integrate research papers**
→ Read: [Research Workflow Guide](~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md)
→ Run: `cd ~/researchgravity && python3 routing-research-sync.py fetch-papers`

**Run A/B tests**
→ Read: [System README - A/B Testing](ROUTING_SYSTEM_README.md#-ab-testing-guide)
→ Run: `routing-metrics.py ab-test create --config experiment.json`

**Troubleshoot issues**
→ Read: [System README - Troubleshooting](ROUTING_SYSTEM_README.md#-troubleshooting)
→ Run: `routing-test-suite.py all`

---

## 📖 Documentation by Level

### Beginner (Getting Started)
1. [Quick Reference Card](ROUTING_QUICK_REFERENCE.md)
2. [System README - Quick Start](ROUTING_SYSTEM_README.md#-quick-start)
3. [System README - Core Commands](ROUTING_SYSTEM_README.md#-core-commands)

### Intermediate (Daily Usage)
1. [System README - Monitoring](ROUTING_SYSTEM_README.md#-core-commands)
2. [System README - Configuration](ROUTING_SYSTEM_README.md#-configuration)
3. [System README - Understanding Metrics](ROUTING_SYSTEM_README.md#-understanding-metrics)

### Advanced (Optimization)
1. [Phase 4-5 Docs - A/B Testing](~/ROUTING_PHASE_4_5_COMPLETE.md#1-ab-testing-framework)
2. [Phase 4-5 Docs - Meta-Analyzer](~/ROUTING_PHASE_4_5_COMPLETE.md#2-meta-analyzer-routing-optimizer)
3. [System README - A/B Testing Guide](ROUTING_SYSTEM_README.md#-ab-testing-guide)

### Expert (Research & Automation)
1. [Research Workflow Guide](~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md)
2. [Phase 4-5 Docs - Automation](~/ROUTING_PHASE_4_5_COMPLETE.md#1-cron-automation-setup)
3. [Phase 4-5 Docs - Auto-Update](~/ROUTING_PHASE_4_5_COMPLETE.md#2-auto-update-system-with-production-validation)

---

## 🔍 Quick Access by Topic

### Architecture & Design
- [System README - Architecture](ROUTING_SYSTEM_README.md#-architecture)
- [Phase 1-3 - Implementation Details](~/ROUTING_IMPLEMENTATION_COMPLETE.md)

### Commands & Usage
- [Quick Reference Card](ROUTING_QUICK_REFERENCE.md)
- [System README - Core Commands](ROUTING_SYSTEM_README.md#-core-commands)

### Performance & Metrics
- [System README - Understanding Metrics](ROUTING_SYSTEM_README.md#-understanding-metrics)
- [System README - Performance Targets](ROUTING_SYSTEM_README.md#-overview)

### Configuration
- [System README - Configuration](ROUTING_SYSTEM_README.md#-configuration)
- [Phase 1-3 - Baselines](~/ROUTING_IMPLEMENTATION_COMPLETE.md#phase-2-mathematical-baselines--metrics)

### Testing & Validation
- [Phase 4-5 - Test Suite](~/ROUTING_PHASE_4_5_COMPLETE.md#3-comprehensive-testing-suite)
- [System README - Troubleshooting](ROUTING_SYSTEM_README.md#-troubleshooting)

### Optimization & A/B Testing
- [System README - A/B Testing Guide](ROUTING_SYSTEM_README.md#-ab-testing-guide)
- [Phase 4-5 - A/B Framework](~/ROUTING_PHASE_4_5_COMPLETE.md#1-ab-testing-framework)

### Automation
- [Phase 4-5 - Cron Setup](~/ROUTING_PHASE_4_5_COMPLETE.md#1-cron-automation-setup)
- [Phase 4-5 - Auto-Update](~/ROUTING_PHASE_4_5_COMPLETE.md#2-auto-update-system-with-production-validation)

### Research Integration
- [Research Workflow Guide](~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md)
- [Phase 1-3 - Research Enhancement](~/ROUTING_IMPLEMENTATION_COMPLETE.md#phase-3-research-enhancement)

---

## 📁 File Locations

### Documentation Files

```
~/.claude/
├── ROUTING_DOCS_INDEX.md              # This file
├── ROUTING_SYSTEM_README.md           # Main documentation
├── ROUTING_QUICK_REFERENCE.md         # Quick reference card
└── CLAUDE.md                          # Updated with routing info

~/
├── ROUTING_IMPLEMENTATION_COMPLETE.md # Phase 1-3 docs
└── ROUTING_PHASE_4_5_COMPLETE.md      # Phase 4-5 docs

~/researchgravity/
└── ROUTING_RESEARCH_WORKFLOW.md       # Research integration guide
```

### System Files

```
~/.claude/
├── kernel/
│   ├── dq-scorer.js
│   └── baselines.json
├── scripts/
│   ├── claude-wrapper.sh
│   ├── smart-route.sh
│   ├── routing-dashboard.sh
│   ├── routing-cron-setup.sh
│   ├── routing-auto-update.sh
│   └── meta-analyzer.py
├── data/
│   ├── routing-metrics.jsonl
│   └── ai-routing.log
└── logs/
    ├── routing-daily.log
    ├── routing-research.log
    └── routing-targets.log

~/researchgravity/
├── routing-metrics.py
├── routing-research-sync.py
└── routing-test-suite.py
```

---

## 🎓 Learning Path

### Week 1: Basics
- Day 1-2: Read [Quick Reference](ROUTING_QUICK_REFERENCE.md)
- Day 3-4: Try commands: `routing-dash`, `routing-report 7`
- Day 5-7: Enable feedback: `ai-feedback-enable`

### Week 2: Understanding
- Day 1-3: Read [System README - Architecture](ROUTING_SYSTEM_README.md#-architecture)
- Day 4-5: Run test suite: `routing-test-suite.py all`
- Day 6-7: Monitor metrics: `routing-report 7`, `routing-targets`

### Week 3: Optimization
- Day 1-3: Read [A/B Testing Guide](ROUTING_SYSTEM_README.md#-ab-testing-guide)
- Day 4-5: Generate proposals: `meta-analyzer propose --domain routing`
- Day 6-7: Review proposals and plan A/B tests

### Week 4: Automation
- Day 1-3: Read [Phase 4-5 - Automation](~/ROUTING_PHASE_4_5_COMPLETE.md#phase-5-continuous-improvement)
- Day 4-5: Install cron: `routing-cron install standard`
- Day 6-7: Check auto-update readiness: `routing-auto status`

### Month 2+: Production
- Monitor weekly: `routing-dash`, review logs
- After 30 days: Enable auto-updates: `routing-auto approve`
- Monthly: Review proposals, A/B tests, research sync
- Quarterly: Full audit: `routing-test-suite.py all`

---

## 🆘 Support Resources

### Quick Help

```bash
# Command help
routing-cron help
routing-auto help
routing-metrics.py --help

# System status
routing-dash
routing-auto status
routing-cron status

# Diagnostics
python3 ~/researchgravity/routing-test-suite.py all
```

### Common Issues

- **Routing not working?** → [Troubleshooting - Routing not activating](ROUTING_SYSTEM_README.md#issue-routing-not-activating)
- **Always same model?** → [Troubleshooting - Always routing to same model](ROUTING_SYSTEM_README.md#issue-always-routing-to-same-model)
- **High latency?** → [Troubleshooting - High routing latency](ROUTING_SYSTEM_README.md#issue-high-routing-latency)
- **Cron jobs not running?** → [Troubleshooting - Cron jobs](ROUTING_SYSTEM_README.md#issue-cron-jobs-not-running)

### Documentation Updates

This documentation is version-controlled. For the latest updates:

```bash
# Check version
head -5 ~/.claude/ROUTING_SYSTEM_README.md

# View documentation index
cat ~/.claude/ROUTING_DOCS_INDEX.md
```

---

## 📊 Documentation Coverage

| Topic | Quick Ref | README | Phase 1-3 | Phase 4-5 | Research |
|-------|-----------|--------|-----------|-----------|----------|
| Quick Start | ✅ | ✅ | ✅ | | |
| Architecture | | ✅ | ✅ | ✅ | |
| Commands | ✅ | ✅ | | | |
| Configuration | | ✅ | ✅ | | |
| Metrics | ✅ | ✅ | ✅ | | |
| A/B Testing | | ✅ | | ✅ | |
| Optimization | | ✅ | | ✅ | |
| Automation | ✅ | ✅ | | ✅ | |
| Auto-Update | | ✅ | | ✅ | |
| Research Sync | | ✅ | ✅ | | ✅ |
| Troubleshooting | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 🚀 Quick Navigation

**Just installed?** → [Quick Reference](ROUTING_QUICK_REFERENCE.md)

**Want details?** → [System README](ROUTING_SYSTEM_README.md)

**Setting up?** → [Phase 1-3 Implementation](~/ROUTING_IMPLEMENTATION_COMPLETE.md)

**Optimizing?** → [Phase 4-5 Implementation](~/ROUTING_PHASE_4_5_COMPLETE.md)

**Research?** → [Research Workflow](~/researchgravity/ROUTING_RESEARCH_WORKFLOW.md)

**Stuck?** → [Troubleshooting](ROUTING_SYSTEM_README.md#-troubleshooting)

---

**Documentation Version:** 1.0.0
**Last Updated:** 2026-01-18
**Next Update:** As needed based on system evolution

**For the latest information, run:** `routing-dash`
