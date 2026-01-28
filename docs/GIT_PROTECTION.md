# Git Pull Protection System

**Status**: ✅ Active
**Last Updated**: 2026-01-28
**Version**: 1.0.0

## Problem Solved

Dashboard customizations (Memory tab 4-column layout, Tool Analytics tab, pattern detection) were being overwritten when `git pull --rebase` ran with 230+ uncommitted files in `~/.claude`.

## Protection Layers

### 1. Git Auto-Stash (CRITICAL)

**Status**: ✅ Enabled
**Location**: `~/.claude/.git/config`

```bash
[pull]
    rebase = true
[rebase]
    autostash = true
```

**How it works**:
- Before pull: Uncommitted changes → stashed automatically
- During pull: New code pulled in cleanly
- After pull: Stashed changes → re-applied automatically
- Result: Your customizations survive!

**Verify it's enabled**:
```bash
cd ~/.claude && git config rebase.autostash
# Should output: true
```

### 2. Safe Pull Wrapper

**Location**: `~/.claude/scripts/safe-git-pull.sh`

**Usage**:
```bash
bash ~/.claude/scripts/safe-git-pull.sh ~/.claude
```

**Features**:
- Warns about uncommitted changes
- Shows modified files
- Highlights dashboard customizations
- 3-second countdown to cancel
- Uses auto-stash automatically

### 3. Protected `gsync()` Command

**Location**: `~/.claude/scripts/git-auto.sh`

**Changes**:
- Auto-enables git auto-stash if not set
- Warns about uncommitted changes with 2s cancel window
- Safe for use with uncommitted work

**Usage** (unchanged):
```bash
gsync "your commit message"
```

### 4. Pre-Pull Hook (Optional)

**Location**: `~/.claude/.git/hooks/pre-pull`

**Note**: Git doesn't natively support pre-pull hooks, so this is informational. The protection comes from auto-stash.

### 5. Generated Files Protection

**Status**: ✅ Active

**What's protected**:
- `scripts/command-center.html` - **TRACKED** (your source template with customizations)
- `dashboard/claude-command-center.html` - **IGNORED** (generated output from `ccc`)

**Added to `.gitignore`**:
```
# Dashboard (generated from template)
dashboard/claude-command-center.html
```

**Why**:
- Template contains your customizations
- Generated file changes every time (live data)
- Only need to track source, not output
- Like tracking .c files but ignoring .exe files

## Current Protection Status

```bash
cd ~/.claude && git config rebase.autostash
# ✅ Should output: true

cd ~/.claude && git status --short | wc -l
# ℹ️  Currently: 231 uncommitted files

cd ~/.claude && git status --short | grep command-center
# ✅ Should NOT show dashboard/claude-command-center.html
# ✅ Should show scripts/command-center.html if you modified it
```

## What Happens on Next Pull

**Scenario**: You have uncommitted dashboard customizations

1. **You run**: `git pull` or `gsync`
2. **Git auto-stash**:
   ```
   Created autostash: a1b2c3d
   ```
3. **Git pulls**: New code comes in
4. **Git re-applies**:
   ```
   Applied autostash
   ```
5. **Result**: Your customizations + new code = 🎉

**If conflicts occur**:
```bash
# Check status
git status

# View stash
git stash list

# If needed, manually resolve
git stash show
git stash pop
```

## Emergency Recovery

**If dashboard gets overwritten anyway**:

```bash
# Check stash list
git stash list

# View stash contents
git stash show stash@{0} -p | grep -A20 "command-center"

# Apply specific stash
git stash apply stash@{0}

# Or regenerate from template (your customizations are in the template!)
ccc
```

## Testing the Protection

**Safe test** (doesn't modify anything):

```bash
# 1. Check current protection status
cd ~/.claude
echo "Auto-stash: $(git config rebase.autostash)"
echo "Uncommitted files: $(git status --short | wc -l)"

# 2. Make a test change
echo "# Test change $(date)" >> scripts/test-protection.txt

# 3. Dry-run to see what would happen
git pull --rebase --dry-run

# 4. Clean up test
rm scripts/test-protection.txt
```

## Maintenance

**Monthly check**:
```bash
cd ~/.claude
git config rebase.autostash  # Should be: true
git status --short | wc -l     # Monitor uncommitted file count
```

**Best practice**:
- Commit dashboard template changes regularly
- Let generated dashboard be regenerated
- Keep uncommitted count under 100 if possible

## Troubleshooting

### "Your changes would be overwritten"

**Cause**: Auto-stash is disabled or git version too old

**Fix**:
```bash
cd ~/.claude
git config rebase.autostash true
git config pull.rebase true
```

### "Auto-stashing not working"

**Check git version**:
```bash
git --version
# Need: git 2.6.0 or newer (released 2015)
```

**Manual stash workflow**:
```bash
git stash
git pull --rebase
git stash pop
```

### "Dashboard still got overwritten"

**Recovery**:
```bash
# Your customizations are in the TEMPLATE (scripts/command-center.html)
# Just regenerate:
ccc

# The template has:
# - 4-column memory layout
# - Reverse chronological sort
# - Separate Tool Analytics tab
# - Pattern detection fallback
```

## Files in This System

| File | Purpose | Tracked |
|------|---------|---------|
| `scripts/command-center.html` | Source template with your customizations | ✅ Yes |
| `dashboard/claude-command-center.html` | Generated output (live data) | ❌ No (.gitignore) |
| `scripts/safe-git-pull.sh` | Safe pull wrapper | ✅ Yes |
| `scripts/git-auto.sh` | Git aliases (gsync, gsave, etc.) | ✅ Yes |
| `.git/hooks/pre-pull` | Warning hook | ❌ No (hooks never tracked) |
| `.gitignore` | Ignore patterns | ✅ Yes |

## Summary

✅ **Auto-stash enabled** - Your work is protected
✅ **Generated files ignored** - No more conflicts
✅ **Template tracked** - Customizations preserved
✅ **Safe commands available** - Use `gsync` safely
✅ **Recovery documented** - Know what to do if issues arise

**Bottom line**: Your dashboard customizations will NOT be overwritten by git pull anymore.
