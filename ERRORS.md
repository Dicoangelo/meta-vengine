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
