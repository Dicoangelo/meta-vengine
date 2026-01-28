#!/bin/bash
# Git automation for Claude terminal workflow

# Clear conflicting aliases (prevents parse errors on re-source)
unalias gsave gsync gquick gstage gcheckpoint 2>/dev/null

# Auto-stage and show status
gstage() {
  git add -A
  echo "✓ Staged all changes"
  git status -s
}

# Quick commit with auto-generated message based on changes
gquick() {
  local msg="${1:-}"

  if [[ -z "$msg" ]]; then
    # Auto-generate based on changed files
    local files=$(git diff --cached --name-only | head -5)
    local count=$(git diff --cached --name-only | wc -l | tr -d ' ')

    if [[ $count -eq 0 ]]; then
      echo "Nothing staged to commit"
      return 1
    fi

    if [[ $count -eq 1 ]]; then
      msg="update $(basename $files)"
    else
      local primary=$(echo "$files" | head -1 | xargs basename)
      msg="update $primary and $((count-1)) more files"
    fi
  fi

  git commit -m "$msg"
  echo "✓ Committed: $msg"
}

# Stage + commit in one step
gsave() {
  local msg="${1:-checkpoint $(date '+%H:%M')}"
  git add -A && git commit -m "$msg"
  echo "✓ Saved: $msg"
}

# Checkpoint with optional push
gcheckpoint() {
  local msg="${1:-checkpoint $(date '+%Y%m%d_%H%M')}"
  git add -A
  git commit -m "checkpoint: $msg"
  echo "✓ Checkpoint created"

  read -p "Push to remote? (y/N) " push
  if [[ "$push" == "y" || "$push" == "Y" ]]; then
    git push
    echo "✓ Pushed"
  fi
}

# Auto-sync: pull, add, commit, push (SAFE VERSION with auto-stash)
gsync() {
  local msg="${1:-sync $(date '+%H:%M')}"

  # Protection: Ensure auto-stash is enabled
  if [[ $(git config rebase.autoStash) != "true" ]]; then
    echo "⚠️  Enabling git auto-stash for safety..."
    git config rebase.autoStash true
  fi

  # Warn if uncommitted changes
  if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo "⚠️  Uncommitted changes detected - will auto-stash during pull"
    echo "    (Press Ctrl+C within 2s to cancel and commit manually)"
    sleep 2
  fi

  echo "→ Pulling with auto-stash..."
  git pull --rebase || { echo "✗ Pull failed"; return 1; }

  echo "→ Staging..."
  git add -A

  if git diff --cached --quiet; then
    echo "✓ Already in sync (no changes)"
    return 0
  fi

  echo "→ Committing..."
  git commit -m "$msg"

  echo "→ Pushing..."
  git push

  echo "✓ Synced"
}

# Show diff summary
gdiff-summary() {
  echo "═══ UNSTAGED ═══"
  git diff --stat
  echo ""
  echo "═══ STAGED ═══"
  git diff --cached --stat
}

# Undo last commit (keep changes)
gundo() {
  git reset --soft HEAD~1
  echo "✓ Undid last commit (changes preserved)"
}

# Smart branch: create and switch
gbranch() {
  local name="$1"
  if [[ -z "$name" ]]; then
    echo "Usage: gbranch <branch-name>"
    return 1
  fi
  git checkout -b "$name"
  echo "✓ Created and switched to: $name"
}

# List recent commits (compact)
glog() {
  local count="${1:-10}"
  git log --oneline -n "$count"
}

# Show today's commits
gtoday() {
  git log --oneline --since="midnight" --author="$(git config user.name)"
}
