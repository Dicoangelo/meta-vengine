#!/bin/bash
# Claude Observatory - Git Activity Tracker
# Tracks commits, PRs, branches, and code review activity

# Clear conflicting aliases (prevents parse errors on re-source)
unalias git-stats gcommit gpush 2>/dev/null

DATA_FILE="$HOME/.claude/data/git-activity.jsonl"
mkdir -p "$(dirname "$DATA_FILE")"

# ═══════════════════════════════════════════════════════════════════════════
# GIT HOOKS
# ═══════════════════════════════════════════════════════════════════════════

__track_git_commit() {
  # Called after successful commit
  local commit_hash=$(git rev-parse HEAD 2>/dev/null)
  local commit_msg=$(git log -1 --pretty=format:"%s" 2>/dev/null)
  local files_changed=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | wc -l | tr -d ' ')
  local lines_changed=$(git diff-tree --no-commit-id --numstat HEAD 2>/dev/null | awk '{added+=$1; removed+=$2} END {print added+removed}')

  local entry=$(cat <<EOF
{"ts":$(date +%s),"event":"commit","commit_hash":"${commit_hash:0:8}","commit_msg":"$commit_msg","files_changed":$files_changed,"lines_changed":$lines_changed,"pwd":"$PWD"}
EOF
)

  echo "$entry" >> "$DATA_FILE"
  echo "✅ Git commit logged: ${commit_hash:0:8}"
}

__track_git_push() {
  local branch=$(git branch --show-current 2>/dev/null || echo "unknown")
  local commits=$(git log origin/$branch..HEAD --oneline 2>/dev/null | wc -l | tr -d ' ')

  local entry=$(cat <<EOF
{"ts":$(date +%s),"event":"push","branch":"$branch","commits_pushed":$commits,"pwd":"$PWD"}
EOF
)

  echo "$entry" >> "$DATA_FILE"
}

__track_git_pr() {
  local pr_number="$1"
  local pr_title="$2"

  local entry=$(cat <<EOF
{"ts":$(date +%s),"event":"pr_created","pr_number":"$pr_number","pr_title":"$pr_title","pwd":"$PWD"}
EOF
)

  echo "$entry" >> "$DATA_FILE"
  echo "✅ PR created logged: #$pr_number"
}

# ═══════════════════════════════════════════════════════════════════════════
# WRAPPED GIT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════

# Tracked git commit
gcommit() {
  git commit "$@"
  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    __track_git_commit
  fi
  return $exit_code
}

# Tracked git push
gpush() {
  git push "$@"
  local exit_code=$?
  if [[ $exit_code -eq 0 ]]; then
    __track_git_push
  fi
  return $exit_code
}

# Tracked gsave (existing alias)
alias gsave='git add -A && gcommit -m'

# Tracked gsync (existing alias)
alias gsync='git pull --rebase && gpush'

# ═══════════════════════════════════════════════════════════════════════════
# PR TRACKING (via gh CLI)
# ═══════════════════════════════════════════════════════════════════════════

create-tracked-pr() {
  local title="$1"
  local body="$2"

  # Create PR via gh
  local pr_url
  if [[ -n "$body" ]]; then
    pr_url=$(gh pr create --title "$title" --body "$body" 2>&1 | grep -o 'https://[^[:space:]]*')
  else
    pr_url=$(gh pr create --title "$title" --fill 2>&1 | grep -o 'https://[^[:space:]]*')
  fi

  # Extract PR number from URL
  local pr_number=$(echo "$pr_url" | grep -o '/[0-9]*$' | tr -d '/')

  if [[ -n "$pr_number" ]]; then
    __track_git_pr "$pr_number" "$title"
    echo "PR created: $pr_url"
  else
    echo "⚠️  Failed to create PR"
    return 1
  fi
}

# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

git-stats() {
  local days="${1:-7}"

  echo "📊 Git Activity (Last $days days)"
  echo "════════════════════════════════════════"

  python3 << EOF
import json
from datetime import datetime, timedelta
from collections import Counter

cutoff = datetime.now() - timedelta(days=$days)

try:
    with open("$DATA_FILE") as f:
        events = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    print("  No git activity data yet")
    exit()

# Filter to time range
recent = [e for e in events if datetime.fromtimestamp(e['ts']) > cutoff]

if not recent:
    print(f"  No git activity in last $days days")
    exit()

# Stats by event type
commits = [e for e in recent if e.get('event') == 'commit']
pushes = [e for e in recent if e.get('event') == 'push']
prs = [e for e in recent if e.get('event') == 'pr_created']

print(f"  Commits:      {len(commits)}")
print(f"  Pushes:       {len(pushes)}")
print(f"  PRs Created:  {len(prs)}")
print()

# Commit details
if commits:
    total_files = sum(c.get('files_changed', 0) for c in commits)
    total_lines = sum(c.get('lines_changed', 0) for c in commits)
    avg_files = total_files / len(commits)
    avg_lines = total_lines / len(commits)

    print("  Commit Details:")
    print(f"    Avg Files/Commit:  {avg_files:.1f}")
    print(f"    Avg Lines/Commit:  {avg_lines:.0f}")
    print(f"    Total Files:       {total_files}")
    print(f"    Total Lines:       {total_lines}")
    print()

# Recent commits
if commits:
    print("  Recent Commits:")
    for commit in commits[-5:]:
        commit_hash = commit.get('commit_hash', '?')
        commit_msg = commit.get('commit_msg', 'No message')[:60]
        timestamp = datetime.fromtimestamp(commit['ts']).strftime('%m-%d %H:%M')
        print(f"    {timestamp} {commit_hash} {commit_msg}")
EOF
}

# Note: export -f removed for zsh compatibility (bash-only feature)
