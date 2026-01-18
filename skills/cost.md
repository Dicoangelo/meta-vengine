---
name: cost
description: Activate cost-aware mode with session management reminders
---

# Cost-Aware Mode

When the user runs `/cost`, activate cost-efficiency protocols for this session.

## Acknowledge Activation

Respond with:
```
Cost-aware mode activated.

I'll help you save credits by:
- Suggesting /clear every ~50 messages
- Recommending Sonnet (cc) for standard tasks
- Encouraging batched prompts
- Providing checkpoint summaries

Current session: [model name]
Tip: Use `cc` for most coding, `co` only for complex architecture.
```

## Behaviors to Enable

### 1. Message Count Awareness
- Track approximate message count in the session
- At ~50 messages, remind: "We're at ~50 messages. Good time to `/clear` if switching tasks."
- At ~100 messages, warn: "Context is getting large (~100 msgs). Consider a fresh session to save credits."

### 2. Model Suggestions
- If user is on Opus doing routine coding, suggest: "This task could use Sonnet (`cc`) - 5x cheaper."
- Reserve Opus recommendations for: complex architecture, multi-file refactors, novel algorithms

### 3. Batching Encouragement
- If user sends 3+ small sequential requests, offer: "Want me to handle these together? Batching saves tokens."

### 4. Checkpoint Summaries
After completing a major task, proactively offer:
```
Checkpoint summary (save this for fresh sessions):
- Completed: [what was done]
- Files changed: [list]
- Next steps: [what remains]
```

### 5. Session Health Indicators
Periodically mention:
- Estimated message count
- Whether context is "light" (<30 msgs), "moderate" (30-70), or "heavy" (70+)

## User Context

- Plan: Claude Max (limited API credits)
- Style: Marathon coder, intensive sessions
- Projects: OS-App, Agentic Kernel, Antigravity ecosystem
- History: Burned through credits with 1,129-message session on Jan 9

## Available Aliases (remind user)

- `cq` = Haiku (quick questions, cheapest)
- `cc` = Sonnet (standard coding, recommended)
- `co` = Opus (complex reasoning, expensive)
- `cstats` = Show usage statistics
