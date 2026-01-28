---
name: flow-shield
description: Protect deep work by suppressing non-critical interrupts during flow states
triggers:
  - pattern: deep work flow protection
  - pattern: protect my focus
  - pattern: enter flow mode
  - pattern: deep work session
---

# Adaptive Flow Shield

Protect flow states from interruptions when flow score > 0.75. This skill activates automatic flow protection to help you maintain deep work.

## When Activated

1. **Check Flow State**
   - Query `~/.claude/kernel/cognitive-os/flow-state.json` for current score
   - Activation threshold: flow_score > 0.75

2. **If In Flow (score > 0.75)**
   - Queue non-critical alerts (cost warnings, checkpoint suggestions)
   - Lock model selection (prevent mid-flow downgrades)
   - Defer routine notifications to session end
   - Only allow through: errors, security alerts, explicit user requests

3. **If Not In Flow (score <= 0.75)**
   - Allow all alerts and notifications normally
   - Suggest entering flow mode if task seems complex

## Protected Categories (Deferred When In Flow)

- Cost warnings (unless CRITICAL tier)
- Context saturation reminders
- Routine checkpoint suggestions
- Model switch recommendations
- Session optimization tips

## Always Pass Through

- Errors and failures
- Security alerts
- User explicit requests
- Budget CRITICAL/EXHAUSTED warnings
- Flow state queries (paradox: checking flow shouldn't break flow)

## Commands

```bash
# Check current flow state
python3 ~/.claude/kernel/cognitive-os.py check-flow

# Enter flow mode manually
python3 ~/.claude/kernel/cognitive-os.py enter-flow

# Exit flow mode
python3 ~/.claude/kernel/cognitive-os.py exit-flow

# Check if notification should be deferred
bash ~/.claude/hooks/flow-protection.sh && echo "NOT in flow" || echo "IN flow"
```

## Integration Points

1. **Hook Integration**: Use `flow-protection.sh` as guard before alert hooks
2. **Cognitive OS**: Reads flow state from flow-state.json
3. **Session Optimizer**: Respects flow state for model switch suggestions

## Flow State Structure

```json
{
  "timestamp": "2026-01-23T15:30:00Z",
  "flow_score": 0.82,
  "in_flow": true,
  "entry_time": "2026-01-23T15:00:00Z",
  "duration_minutes": 30,
  "task_type": "deep_coding",
  "protection_active": true
}
```

## Auto-Activation Triggers

The pattern-detector identifies deep-work patterns and can auto-activate flow shield when:
- Multiple consecutive code edits without context switches
- Extended read-analyze-edit cycles
- Architecture or refactoring sessions detected
- User explicitly requests focus protection

## Deferred Alert Queue

When flow protection is active, deferred alerts are stored in:
`~/.claude/kernel/cognitive-os/deferred-alerts.json`

On session end or flow exit, these are displayed with:
```bash
python3 ~/.claude/kernel/cognitive-os.py flush-deferred
```

## Best Practices

- Don't check flow state too frequently (it's memoized for 5 min)
- Critical alerts always pass through
- Flow protection is session-scoped, not persistent
- Manual override always available via explicit user request
