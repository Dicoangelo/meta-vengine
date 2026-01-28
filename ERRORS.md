# ERRORS.md

Tracking mistakes to avoid repeating them. Auto-updated by error-tracker.

---

## Summary (139 total errors from all sessions)

| Category | Count | Severity | Status |
|----------|-------|----------|--------|
| **Git** | 112 | High | Top issue |
| Concurrency | 11 | High | Identified |
| Permissions | 8 | High | Recurring |
| Quota | 3 | High | Managed |
| Crash | 3 | Critical | Resolved |
| Syntax | 1 | High | One-off |
| Recursion | 1 | High | Prevented |

---

## Git Errors (112) - YOUR #1 ISSUE

### Repository Not Found (most common)
```
fatal: repository 'https://github.com/dicoangelo/...' not found
fatal: repository 'https://github.com/Blackamethyst-ai/...' not found
```
**Causes:**
- Case sensitivity: `dicoangelo` vs `Dicoangelo`
- Non-existent repos referenced in scripts
- Old URLs that no longer exist

**Prevention:**
- Always use exact GitHub username: `Dicoangelo`
- Verify repo exists: `gh repo view owner/repo` before cloning
- Update old references in scripts

### Tag/Branch Conflicts
```
fatal: tag 'v1.1.0' already exists
fatal: destination path 'OS-App' already exists
```
**Prevention:**
- Check before creating: `git tag -l | grep v1.1.0`
- Check before cloning: `[ -d OS-App ] || git clone ...`

### Wrong Directory
```
fatal: not a git repository
```
**Prevention:**
- Verify with `git rev-parse --git-dir` before operations

---

## Concurrency Errors (11)

**2026-01-19 - Parallel Claude Sessions**
- 5+ sessions running simultaneously
- Race conditions corrupting shared files
- Sessions overwriting each other's data

**Prevention:**
- Check for other sessions: `pgrep -f "claude"` at start
- Use file locks for critical writes
- Close other Claude instances before heavy work

---

## Permissions Errors (8)

```
Permission denied
EACCES
(eval):1: permission denied
```

**Causes:**
- Running commands without proper permissions
- Accessing protected files/directories

**Prevention:**
- Check permissions first: `ls -la <file>`
- Use `sudo` when appropriate
- Ensure scripts are executable: `chmod +x`

---

## Quota/Rate Limit (3)

```
API quota exceeded
RATE_LIMITED: waiting...
```

**Prevention:**
- DQ routing already handles this (use Haiku/Sonnet for simple tasks)
- Exponential backoff implemented in code

---

## Crashes (3)

```
SIGKILL (exit code 144)
Process terminated unexpectedly
```

**Causes:**
- Force-killing processes without graceful shutdown
- Resource exhaustion

**Prevention:**
- Use SIGTERM before SIGKILL
- Monitor resource usage

---


## Backfilled Errors (Historical)

### 2026-01-26 - memory (2 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `"ruleContent": "git -C ~/Metaventions-AI-Landing commit -m \"$(cat <<''EOF''\nAdd Genesis Sequence -...`
**Source:** debug:5462b2be-0b61-4ade-9b31-f96eb3

### 2026-01-19 - memory (27 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `"text": "Forge - collision creates artifacts\\n- Act IV: Assembly Dock - components lock together\\n...`
**Source:** agent-core:backfill--real-time-voice-n-n-20260119-174108-7b4f5a

### 2026-01-19 - git (1 occurrences)
**Category:** git | **Severity:** high
**Sample:** `fatal: tag 'v1.1.0' already exists...`
**Source:** agent-core:backfill-where-we-left-off-20260119-042140-a1a488

### 2026-01-19 - concurrency (10 occurrences)
**Category:** concurrency | **Severity:** high
**Sample:** `"text": "5+ parallel Claude sessions causing race conditions. User closed other sessions.",...`
**Source:** agent-core:backfill-data-extraction-to-c-20260119-134858-acb29c

### 2026-01-18 - memory (5 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `144→- Glow bloom on each creation...`
**Source:** agent-core:backfill-studio-focused-on-20260118-015036-15417d

### 2026-01-17 - memory (10 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `70→> Partner Operations & Systems Leader with deep partner-ecosystem fluency. I sit at the intersect...`
**Source:** agent-core:backfill-the-11-apps-through--20260117-174445-fa339c

### 2026-01-17 - git (1 occurrences)
**Category:** git | **Severity:** high
**Sample:** `fatal: not a git repository (or any of the parent directories): .git...`
**Source:** agent-core:backfill-analyzer-core-engine-20260117-223421-3ddaa1

### 2026-01-17 - recursion (1 occurrences)
**Category:** recursion | **Severity:** high
**Sample:** `224→- [ ] No infinite loops (MAX_ROUNDS enforced)...`
**Source:** agent-core:backfill-directions-include--20260117-162046-1c8f51

### 2026-01-16 - memory (18 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `- Post-processing (Bloom, Chromatic Aberration, Vignette)...`
**Source:** agent-core:backfill-from-old-claude-sess-20260116-082220-9262b5

### 2026-01-16 - recursion (1 occurrences)
**Category:** recursion | **Severity:** high
**Sample:** `74→│  │  Max rounds: 15 (prevents infinite loops)                    │   │...`
**Source:** agent-core:backfill--compounding--20260116-171841-dcaf19

### 2026-01-15 - memory (15 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `/Users/dicoangelo/OS-App/components/ImageGenParts/ScreeningRoom.tsx...`
**Source:** agent-core:backfill-summary-for-your-rec-20260115-221712-8825cd

### 2026-01-15 - quota (1 occurrences)
**Category:** quota | **Severity:** high
**Sample:** `375→            // This prevents "Quota Exceeded" on high-end models for simple tasks...`
**Source:** agent-core:backfill-large-session-recove-20260115-095747-bbe957

### 2026-01-14 - memory (97 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `"context": "y 2026\"  Links: [{\"title\":\"NVIDIA Debuts Nemotron 3 Family of Open Models | NVIDIA N...`
**Source:** agent-core:backfill-components-orphaned--20260114-135258-18b718

### 2026-01-13 - memory (18 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `"url": "https://newsroom.paypal-corp.com/2025-01-11-From-Search-to-Checkout-PayPal-Supports-Trusted-...`
**Source:** agent-core:backfill-on-the-most-recent-b-20260113-071302-fb60d5

### 2026-01-13 - concurrency (1 occurrences)
**Category:** concurrency | **Severity:** high
**Sample:** `Race conditions are the hardest to find, averaging 5.1 years to discovery because they're non-determ...`
**Source:** agent-core:backfill-on-the-most-recent-b-20260113-071302-fb60d5

### 2026-01-13 - git (1 occurrences)
**Category:** git | **Severity:** high
**Sample:** `fatal: destination path 'OS-App' already exists and is not an empty directory....`
**Source:** agent-core:backfill-up-to-4-hours-total--20260113-081323-5c707f

### 2026-01-13 - crash (2 occurrences)
**Category:** crash | **Severity:** critical
**Sample:** `The exit code 144 = SIGKILL (128 + 16), which was our `pkill` command terminating the test server....`
**Source:** agent-core:backfill-up-to-4-hours-total--20260113-081323-5c707f

### 2026-01-13 - permissions (1 occurrences)
**Category:** permissions | **Severity:** high
**Sample:** `(eval):1: permission denied:...`
**Source:** agent-core:backfill-resume-jan-13-20260113-115350-e7f6d1

### 2026-01-10 - memory (10 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `"context": " (2) Future - Cinderella (Visualizer) Feat. Metro Boomin & Travis Scott - YouTube    272...`
**Source:** agent-core:backfill-process-this-morning-20260110-105526-48e160

### 2026-01-10 - permissions (1 occurrences)
**Category:** permissions | **Severity:** high
**Sample:** `"Permission denied"...`
**Source:** agent-core:backfill-process-this-morning-20260110-105526-48e160

### 2026-01-09 - memory (9 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `/Users/dicoangelo/Desktop/OS-App/components/ImageGenParts/ScreeningRoom.tsx...`
**Source:** agent-core:backfill-subagent-research-20260109-082911-e4d425

### 2026-01-09 - quota (1 occurrences)
**Category:** quota | **Severity:** high
**Sample:** `186→                console.warn(`⚠️ RATE_LIMITED: API quota exceeded, waiting ${delay}ms...`);...`
**Source:** agent-core:backfill-session-recovery-jan-20260109-132008-4c14b9

### 0086-20-26 - memory (1 occurrences)
**Category:** memory | **Severity:** critical
**Sample:** `212→If you're searching for a **multidisciplinary operator** with equal parts creative vision and an...`
**Source:** agent-core:backfill-session-from-d3f0086-20260109-111039-e3e1fe

---

## Patterns to Watch

### Active Issues
- [x] **Git case sensitivity** - Use `Dicoangelo` not `dicoangelo`
- [x] **Parallel sessions** - One Claude instance at a time for writes
- [x] **API rate limits** - DQ routing handles this

### Prevented
- [x] Recursion limits enforced (MAX_ROUNDS)
- [x] Rate limit backoff implemented

### Monitor
- [ ] Permission errors (8 occurrences)
- [ ] Stale repo references in scripts

---

## Quick Fixes

```bash
# Fix git username case sensitivity
git remote set-url origin https://github.com/Dicoangelo/repo.git

# Check for parallel Claude sessions
pgrep -fa "claude"

# Verify repo exists before clone
gh repo view Dicoangelo/repo && git clone ...

# Check tag before creating
git tag -l | grep -q "v1.0" || git tag v1.0
```

---

## Commands

```bash
error-log "context" "message" "cause" "fix"  # Manual log
error-stats                                   # View statistics
error-analyze                                 # Pattern analysis
error-scan                                    # Scan recent activity
```

---

## Data Sources Scanned

- `~/.claude/history.jsonl` (2,288 conversations)
- `~/.claude/debug/` (204 files)
- `~/.claude/session-env/` (163 files)
- `~/.claude/todos/` (211 files)
- `~/.claude/plans/` (20 files)
- `~/.claude/logs/` (23 files)
- `~/.agent-core/sessions/` (118 sessions, deep scan)
- `~/.claude/session-summaries/` (15 files)
- `~/.claude/activity.log` (6,466 lines)

**Total: All historical session data scanned.**
