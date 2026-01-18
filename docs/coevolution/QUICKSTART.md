# QUICKSTART

**Get the Closed Loop running in 60 seconds.**

D-Ecosystem · Metaventions AI

---

## PREREQUISITES

```bash
# The system lives in your Claude environment
~/.claude/                  # Core directory
~/researchgravity/          # Research tools
~/.agent-core/              # Memory layer

# Required tools
python3                     # For meta-analyzer
node                        # For pattern detection
```

---

## ACTIVATION

### 1. Load the aliases

```bash
source ~/.claude/init.sh
```

You'll see:

```
╔═══════════════════════════════════════════════════════════╗
║     D-ECOSYSTEM :: SOVEREIGN TERMINAL OS v1.5.0           ║
║     "Let the invention be hidden in your vision"          ║
╚═══════════════════════════════════════════════════════════╝

Kernel: ✓ Active | Sovereign by design

Core:
  ai "query"    DQ-powered routing (haiku/sonnet/opus)
  ai-kernel     Full kernel status
  ai-identity   Sovereign identity card
  ai-suggest    Proactive suggestions

Co-Evolution (Bidirectional Learning):
  coevo-analyze    Analyze patterns & generate insights
  coevo-propose    Generate modification proposals
  coevo-dashboard  View effectiveness over time

Dashboard: ccc | Models: cq, cc, co | Git: gsave, gsync
```

---

## FIRST RUN

### 2. See what the system knows

```bash
coevo-analyze
```

Output:

```
============================================================
META-ANALYZER: Co-Evolution Analysis
============================================================

Sessions: 104 | Messages: 27521
Cache Efficiency: 99.88%
DQ Score Avg: 0.839 (stable)
Confidence: 0.85

--- Insights ---
  [+] Excellent cache efficiency at 99.88%. Context reuse is optimal.
  [*] Dominant pattern: architecture (35% of activity)
  [*] Peak productivity hours: 15:00, 14:00, 20:00

--- Recommendations ---
  -> Pre-load architecture-specific context via prefetch --pattern architecture
     Impact: Faster session starts, more relevant suggestions
```

---

## EVOLUTION CYCLE

### 3. Generate modification proposals

```bash
coevo-propose
```

Output:

```
Generated 4 modification proposals:

  mod-20260117-000: Batch related queries into fewer sessions
     Type: behavior | Target: CLAUDE.md
     Confidence: 0.85 | Impact: Could improve cache efficiency by 2-5%

  mod-20260117-001: Pre-load architecture-specific context
     Type: context | Target: prefetch.py
     Confidence: 0.85 | Impact: Faster session starts

  mod-20260117-claude-md: Update CLAUDE.md with learned patterns
     Type: claude_md_update | Target: CLAUDE.md
     Confidence: 0.9 | Impact: Better session initialization

Apply with: coevo-apply <mod_id>
Preview with: coevo-apply <mod_id> --dry-run
```

### 4. Preview before applying

```bash
coevo-apply mod-20260117-claude-md --dry-run
```

Output:

```json
{
  "mod_id": "mod-20260117-claude-md",
  "dry_run": true,
  "backup": "/Users/you/.claude/claude-md-history/CLAUDE.md.20260117_120000",
  "success": true,
  "message": "Would update CLAUDE.md",
  "preview": "## Learned Patterns\n\n<!-- AUTO-GENERATED -->\n..."
}
```

### 5. Apply the modification

```bash
coevo-apply mod-20260117-claude-md
```

The loop closes. Your next session benefits.

---

## PROACTIVE CONTEXT

### 6. Let the system predict what you need

```bash
prefetch --proactive
```

Based on time and recent patterns, loads the right context.

### 7. Or specify a pattern

```bash
prefetch --pattern debugging    # When debugging
prefetch --pattern research     # When researching
prefetch --pattern architecture # When designing
```

### 8. See what the system recommends

```bash
prefetch --suggest
```

Output:

```
Proactive Suggestions for: architecture
========================================
Focus: system design, component boundaries, trade-offs
Tools: /arch, prefetch --papers
Research Papers:
  - https://arxiv.org/abs/2507.14241
  - https://arxiv.org/abs/2501.12689
```

---

## ROLLBACK

### 9. If something goes wrong

```bash
coevo-rollback mod-20260117-claude-md
```

Output:

```json
{
  "success": true,
  "message": "Rolled back mod-20260117-claude-md from backup"
}
```

All modifications are reversible. Sovereignty by design.

---

## DASHBOARD

### 10. View the system state

```bash
coevo-dashboard
```

Output:

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
Evaluations: 0
Avg Improvement: 0.000
```

---

## CONFIGURATION

### 11. Adjust settings

```bash
# View current config
coevo-config

# Enable auto-apply (for the brave)
coevo-config --set autoApply true

# Adjust confidence threshold
coevo-config --set minConfidence 0.8
```

---

## THE LOOP

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   1. WORK                                                                   │
│      Use Claude as normal. Telemetry accumulates.                          │
│                                                                             │
│   2. ANALYZE                                                                │
│      Run `coevo-analyze` periodically (daily/weekly).                      │
│                                                                             │
│   3. PROPOSE                                                                │
│      Run `coevo-propose` to see improvement suggestions.                   │
│                                                                             │
│   4. APPLY                                                                  │
│      Apply high-confidence modifications (with --dry-run first).           │
│                                                                             │
│   5. EVALUATE                                                               │
│      After 10+ sessions, check `coevo-dashboard` for effectiveness.        │
│                                                                             │
│   6. REPEAT                                                                 │
│      The loop never fully closes. Keep evolving.                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## COMMANDS CHEATSHEET

```bash
# Analysis
coevo-analyze                    # See insights
coevo-dashboard                  # View system state

# Evolution
coevo-propose                    # Generate proposals
coevo-apply <id>                 # Apply modification
coevo-apply <id> --dry-run       # Preview first
coevo-rollback <id>              # Undo if needed

# Context
prefetch --proactive             # Auto-predict pattern
prefetch --pattern <type>        # Specific pattern
prefetch --suggest               # See recommendations

# Configuration
coevo-config                     # View settings
coevo-config --set <key> <val>   # Change setting
```

---

<div align="center">

**The loop is now running.**

Every session makes the next one better.

D-Ecosystem · Metaventions AI

*"Let the invention be hidden in your vision"*

</div>
