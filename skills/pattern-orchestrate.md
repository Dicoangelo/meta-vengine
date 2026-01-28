---
name: pattern-orchestrate
description: Auto-suggest coordinator strategies based on detected session patterns
triggers:
  - pattern: suggest coordination strategy
  - pattern: what agents should I use
  - pattern: orchestrate this task
  - pattern: multi-agent approach
---

# Proactive Pattern Orchestrator

When the pattern-detector identifies a session type, automatically suggest or spawn the optimal coordinator strategy and pre-load relevant context packs.

## Pattern to Strategy Mapping

| Detected Pattern | Coordinator Strategy | Agents | Use Case |
|------------------|---------------------|--------|----------|
| `debugging` | `coord review-build` | builder + reviewer | Fix with verification |
| `research` | `coord research` | 3 explore (parallel) | Understanding, investigation |
| `architecture` | `coord full` | research → build → review | Complete feature pipeline |
| `refactoring` | `coord implement` | N builders (file locks) | Multi-file changes |
| `feature` | `coord implement` | N builders (file locks) | New functionality |
| `testing` | `coord review-build` | builder + reviewer | Write tests with verification |
| `documentation` | `coord research` | 3 explore (parallel) | Gather before writing |
| `performance` | `coord full` | research → build → review | Profile, optimize, verify |

## Activation Flow

1. **Read Pattern Detection**
   ```bash
   cat ~/.claude/kernel/detected-patterns.json
   ```

2. **Match to Strategy**
   - Extract `current_session_type` from patterns
   - Map to coordinator strategy using table above

3. **Check Existing Agents**
   ```bash
   coord status
   ```
   - If matching strategy already running, join rather than spawn new

4. **Suggest or Auto-Spawn**
   - If confidence > 0.8: Auto-spawn strategy
   - If confidence 0.5-0.8: Suggest strategy with reasoning
   - If confidence < 0.5: Ask user for guidance

5. **Pre-Load Context Packs**
   ```bash
   python3 ~/.claude/scripts/select_packs.py --auto
   ```
   - Load relevant packs based on detected pattern

## Commands

```bash
# Get current pattern detection
cat ~/.claude/kernel/detected-patterns.json | jq '.current_session_type'

# Suggest coordination strategy
python3 ~/.claude/scripts/pattern-orchestrate.py suggest

# Auto-spawn optimal strategy
python3 ~/.claude/scripts/pattern-orchestrate.py spawn

# Status check
coord status
```

## Integration Points

1. **pattern-detector.js**: Source of session patterns
2. **coordinator**: Multi-agent orchestration
3. **context-packs**: Pre-loading relevant context

## Pattern Detection Sources

The orchestrator reads patterns from:
- `detected-patterns.json`: Real-time session patterns
- `activity-events.jsonl`: Historical activity
- First user message: Intent classification

## Strategy Details

### Research Strategy (`coord research`)
- 3 parallel explore agents
- Each explores different aspect
- Synthesizes findings
- Best for: understanding codebase, investigating issues

### Implement Strategy (`coord implement`)
- N builders with file locks
- Prevents conflicts on same files
- Best for: multi-file changes, new features

### Review Strategy (`coord review-build`)
- Builder + reviewer concurrent
- Catches issues early
- Best for: bug fixes, tests, critical code

### Full Strategy (`coord full`)
- Research → Build → Review pipeline
- Complete development cycle
- Best for: complex features, architecture changes

## Auto-Activation Triggers

The orchestrator can auto-activate when:

1. **Pattern confidence > 0.8**: Strong pattern match
2. **Task complexity > 0.7**: Complex task detected
3. **Multi-file scope**: Changes span 3+ files
4. **User history**: Previous similar tasks used this strategy

## Example Session Flow

```
User: "I need to refactor the authentication system"

Pattern Detected: refactoring (0.85 confidence)
Suggested Strategy: coord implement (parallel builders with file locks)

Pre-loaded Context:
- auth-patterns.md (from context packs)
- security-guidelines.md
- Recent auth-related learnings

Spawned Agents:
- Builder 1: Token management
- Builder 2: Session handling
- Builder 3: Password validation
(with file locks on shared files)
```

## Configuration

Edit `~/.claude/kernel/pattern-orchestrate-config.json`:

```json
{
  "auto_spawn_threshold": 0.8,
  "suggest_threshold": 0.5,
  "max_parallel_agents": 5,
  "preload_context": true,
  "patterns": {
    "debugging": "review-build",
    "research": "research",
    "architecture": "full",
    "refactoring": "implement",
    "feature": "implement",
    "testing": "review-build"
  }
}
```

## Best Practices

- Always check existing agents before spawning new
- Don't spawn for simple single-file tasks
- Monitor agent token usage
- Collect feedback for pattern learning
