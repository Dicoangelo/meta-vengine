# HSRGS Build Log

**Date:** 2026-01-18
**Session:** Homeomorphic Self-Routing Gödel System
**Status:** Complete + A/B Testing Active

---

## Executive Summary

Built a research-backed routing system (HSRGS) to replace keyword-based DQ scoring in uni-ai. Now running A/B test to empirically validate if embeddings beat heuristics.

---

## Research Foundation

### Papers Analyzed (January 2026)

| Paper | arXiv | Key Innovation |
|-------|-------|----------------|
| **ZeroRouter** | [2601.06220](https://arxiv.org/abs/2601.06220) | Universal latent space, zero-shot model onboarding |
| **ULHM** | [2601.09025](https://arxiv.org/abs/2601.09025) | Homeomorphic manifolds, cross-domain unification |
| **DLCM** | [2512.24617](https://arxiv.org/abs/2512.24617) | Dynamic concept boundaries from latent space |
| **Darwin Gödel Machine** | [2505.22954](https://arxiv.org/abs/2505.22954) | Open-ended evolution of self-improving agents |
| **Gödel Agent** | [2410.04444](https://arxiv.org/abs/2410.04444) | Self-referential recursive improvement |
| **IRT-Router** | [2506.01048](https://arxiv.org/abs/2506.01048) | Item Response Theory for routing |
| **Emergent Coordination** | [2601.08129](https://arxiv.org/abs/2601.08129) | Pressure gradients beat hierarchical control |
| **ICLR 2026 RSI Workshop** | [link](https://iclr.cc/virtual/2026/workshop/10000796) | RSI moving from theory to deployment |

### Convergence Pattern Identified

Three threads converging that nobody had unified:
1. **Universal Latent Spaces** (ZeroRouter + ULHM)
2. **Self-Referential Self-Improvement** (Gödel Agent + Darwin GM)
3. **Emergent Coordination** (Pressure Fields + DLCM)

### The Gap (Novel Contribution)

> A router that self-improves its own routing algorithm through open-ended evolution in a universal homeomorphic latent space, using emergent pressure gradients instead of explicit rules.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           HSRGS                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Query ──→ Homeomorphic Encoder ──→ Universal Latent Space      │
│                                            │                     │
│                                            ▼                     │
│                                     IRT Predictor               │
│                                    P(success|model)              │
│                                            │                     │
│                                            ▼                     │
│                                  Pressure Field Selector         │
│                                   (emergent, no thresholds)      │
│                                            │                     │
│                                            ▼                     │
│                                    Gödel Engine                  │
│                                  (self-modification)             │
│                                            │                     │
│                                            ▼                     │
│                                    Coevo Pipeline                │
│                                      (learning)                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Homeomorphic Encoder
- Uses `sentence-transformers` (all-MiniLM-L6-v2)
- Encodes queries into 384-dim dense vectors
- Estimates difficulty from embedding properties + technical term density
- Computes domain signature for domain-specific routing

#### 2. IRT Predictor
- Item Response Theory model: P(success) = c + (1-c) * sigmoid(a * (θ - b))
- θ = model ability, b = query difficulty, a = discrimination, c = guessing
- Updates parameters from feedback (continuous learning)

#### 3. Pressure Field Selector
- **Cost pressure:** Exponential decay with difficulty (complex queries tolerate cost)
- **Quality pressure:** Quadratic penalty for capability gap (model capability < query difficulty)
- **Latency pressure:** Tolerance increases with difficulty
- Selection = argmin(total_pressure) — emergent, not rule-based

#### 4. Gödel Engine
- Proposes mutations based on recent outcomes
- Applies mutations with empirical validation
- Rollback on regression
- Maintains evolution archive

---

## Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `~/.claude/kernel/hsrgs.py` | HSRGS core engine | ~950 |
| `~/.claude/scripts/ab-test-analyzer.py` | A/B test analysis | ~200 |
| `~/.claude/docs/HSRGS_BUILD_LOG.md` | This document | - |

## Files Modified

| File | Changes |
|------|---------|
| `~/bin/uni-ai` | Added HSRGS integration, A/B test mode |
| `~/.claude/init.sh` | Added `ab-test` aliases |

---

## A/B Test Configuration

### Setup
```python
DEFAULT_CONFIG = {
    "use_hsrgs": True,
    "ab_test_mode": True,
    "ab_test_ratio": 0.5,  # 50% HSRGS, 50% keyword DQ
}
```

### What's Being Compared

| Aspect | Keyword DQ | HSRGS |
|--------|------------|-------|
| Scoring | Regex + keyword lists | Sentence embeddings |
| Thresholds | Hardcoded (0.3, 0.5, 0.7) | Emergent pressure gradients |
| Learning | None | IRT updates + Gödel mutations |
| Complexity | ~200 lines | ~950 lines |

### Commands
```bash
ab-test              # View A/B test results
ab-test-detailed     # With query breakdown
ai-good              # Mark last query successful
ai-bad               # Mark last query failed
```

### Success Criteria
- Need 30+ queries per variant for significance
- Compare feedback rate (ai-good / ai-bad)
- Compare model distribution
- Compare average complexity estimation

---

## Data Pipeline

```
uni-ai query
    │
    ├─→ A/B random assignment
    │
    ├─→ HSRGS or Keyword DQ scoring
    │
    ├─→ Model selection
    │
    ├─→ Log to ~/.claude/kernel/dq-scores.jsonl
    │       {
    │         "source": "hsrgs" | "uni-ai",
    │         "ab_variant": "hsrgs" | "keyword_dq",
    │         "complexity": 0.xx,
    │         "model": "...",
    │         ...
    │       }
    │
    └─→ Coevo system picks up for analysis
            │
            └─→ coevo-analyze sees patterns
            └─→ ab-test compares variants
```

---

## Dependencies

Installed in `~/.uni-ai/venv/`:
- sentence-transformers 5.2.0
- torch 2.9.1
- numpy 2.4.1

---

## Usage

### Normal Usage (A/B test runs automatically)
```bash
uni-ai "your query"
```

### Check A/B Results
```bash
ab-test
```

### Disable A/B Test (use HSRGS only)
```bash
uni-ai /config ab_test_mode=false
```

### Disable HSRGS (use keyword DQ only)
```bash
uni-ai /config use_hsrgs=false
```

### View HSRGS Decision Details
```bash
~/.uni-ai/venv/bin/python ~/.claude/kernel/hsrgs.py "your query"
```

---

## Next Steps

1. **Collect data** — Run uni-ai normally for 1 week
2. **Provide feedback** — Use ai-good/ai-bad after queries
3. **Analyze** — Run `ab-test` to see which method wins
4. **Decide** — If HSRGS wins, disable A/B test and use HSRGS only
5. **Evolve** — Let Gödel engine propose improvements based on data

---

## Research Session Logging

```bash
# Log to ResearchGravity
python3 ~/researchgravity/init_session.py "HSRGS-build" --impl-project os-app
python3 ~/researchgravity/log_url.py "https://arxiv.org/abs/2601.06220" --tier 1 --category research
python3 ~/researchgravity/log_url.py "https://arxiv.org/abs/2601.09025" --tier 1 --category research
python3 ~/researchgravity/log_url.py "https://arxiv.org/abs/2505.22954" --tier 1 --category research
python3 ~/researchgravity/log_url.py "https://arxiv.org/abs/2506.01048" --tier 1 --category research
python3 ~/researchgravity/log_url.py "https://arxiv.org/abs/2601.08129" --tier 1 --category research
```

---

## Changelog

### 2026-01-18
- Initial HSRGS implementation
- Integrated with uni-ai
- Added A/B test mode
- Added ab-test-analyzer.py
- Connected to coevo data pipeline
