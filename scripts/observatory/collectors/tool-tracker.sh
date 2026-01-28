#!/bin/bash
# Claude Observatory - Tool Success Tracker
# Tracks Bash exit codes, test results, build success, and tool effectiveness

# Clear conflicting aliases (prevents parse errors on re-source)
unalias tool-stats tool-report 2>/dev/null

DATA_FILE="$HOME/.claude/data/tool-success.jsonl"
mkdir -p "$(dirname "$DATA_FILE")"

# ═══════════════════════════════════════════════════════════════════════════
# BASH COMMAND TRACKING
# ═══════════════════════════════════════════════════════════════════════════

# Track the last command for monitoring
export OBSERVATORY_LAST_CMD=""
export OBSERVATORY_LAST_CMD_TIME=0

# Pre-command hook (capture command before execution)
__observatory_preexec() {
  if [[ -n "$1" ]]; then
    OBSERVATORY_LAST_CMD="$1"
    OBSERVATORY_LAST_CMD_TIME=$(date +%s)
  fi
}

# Post-command hook (capture exit code after execution)
__observatory_track_bash_result() {
  local exit_code=$?
  local end_time=$(date +%s)

  # Skip if no command tracked
  [[ -z "$OBSERVATORY_LAST_CMD" ]] && return

  # Skip observatory's own commands
  [[ "$OBSERVATORY_LAST_CMD" == __observatory* ]] && return
  [[ "$OBSERVATORY_LAST_CMD" == session-* ]] && return

  # Calculate duration
  local duration=$((end_time - OBSERVATORY_LAST_CMD_TIME))

  # Hash command for privacy (if needed)
  local cmd_hash
  if command -v md5 &> /dev/null; then
    cmd_hash=$(echo -n "$OBSERVATORY_LAST_CMD" | md5 | cut -d' ' -f1)
  else
    cmd_hash=$(echo -n "$OBSERVATORY_LAST_CMD" | md5sum | cut -d' ' -f1)
  fi

  # Extract command type
  local cmd_type="bash"
  if [[ "$OBSERVATORY_LAST_CMD" =~ ^npm ]]; then
    cmd_type="npm"
  elif [[ "$OBSERVATORY_LAST_CMD" =~ ^(python|pytest) ]]; then
    cmd_type="python"
  elif [[ "$OBSERVATORY_LAST_CMD" =~ ^git ]]; then
    cmd_type="git"
  elif [[ "$OBSERVATORY_LAST_CMD" =~ ^(make|build) ]]; then
    cmd_type="build"
  elif [[ "$OBSERVATORY_LAST_CMD" =~ (test|spec) ]]; then
    cmd_type="test"
  fi

  # Log entry with dual-write to JSONL + SQLite
  local success_bool=$([ $exit_code -eq 0 ] && echo "true" || echo "false")
  local entry=$(cat <<EOF
{"ts":$end_time,"tool":"bash","cmd_hash":"$cmd_hash","cmd_type":"$cmd_type","success":$success_bool,"exit_code":$exit_code,"duration_sec":$duration}
EOF
)

  echo "$entry" >> "$DATA_FILE"

  # NOTE: Individual bash events logged to JSONL only.
  # Daily aggregates for tool_success table are generated separately.

  # Clear tracking
  OBSERVATORY_LAST_CMD=""
}

# Hook into zsh
if [[ -n "$ZSH_VERSION" ]]; then
  # zsh hooks
  autoload -U add-zsh-hook
  add-zsh-hook preexec __observatory_preexec
  add-zsh-hook precmd __observatory_track_bash_result
fi

# ═══════════════════════════════════════════════════════════════════════════
# TEST RESULT TRACKING
# ═══════════════════════════════════════════════════════════════════════════

__track_test_result() {
  local test_framework="$1"  # pytest, jest, vitest, etc.
  local exit_code="$2"
  local output="$3"

  # Parse test results from output
  local tests_passed=0
  local tests_failed=0
  local tests_total=0

  case "$test_framework" in
    pytest)
      tests_passed=$(echo "$output" | grep -o "[0-9]* passed" | awk '{print $1}' || echo 0)
      tests_failed=$(echo "$output" | grep -o "[0-9]* failed" | awk '{print $1}' || echo 0)
      ;;
    jest|vitest)
      tests_passed=$(echo "$output" | grep -o "Tests:.*passed" | grep -o "[0-9]* passed" | awk '{print $1}' || echo 0)
      tests_failed=$(echo "$output" | grep -o "[0-9]* failed" | awk '{print $1}' || echo 0)
      ;;
  esac

  tests_total=$((tests_passed + tests_failed))

  local entry=$(cat <<EOF
{"ts":$(date +%s),"tool":"test","framework":"$test_framework","success":$([ $exit_code -eq 0 ] && echo true || echo false),"tests_total":$tests_total,"tests_passed":$tests_passed,"tests_failed":$tests_failed}
EOF
)

  echo "$entry" >> "$DATA_FILE"
  echo "✅ Test results logged: $tests_passed/$tests_total passed"
}

# Wrapper for test commands
run-tracked-tests() {
  local framework="${1:-pytest}"
  shift

  echo "🧪 Running tests with $framework..."
  local output
  local exit_code

  case "$framework" in
    pytest)
      output=$(pytest "$@" 2>&1)
      exit_code=$?
      ;;
    jest)
      output=$(npm test "$@" 2>&1)
      exit_code=$?
      ;;
    vitest)
      output=$(npm run test "$@" 2>&1)
      exit_code=$?
      ;;
    *)
      echo "Unknown framework: $framework"
      return 1
      ;;
  esac

  echo "$output"
  __track_test_result "$framework" "$exit_code" "$output"

  return $exit_code
}

# ═══════════════════════════════════════════════════════════════════════════
# BUILD RESULT TRACKING
# ═══════════════════════════════════════════════════════════════════════════

__track_build_result() {
  local build_system="$1"  # npm, make, cargo, etc.
  local exit_code="$2"
  local duration="$3"

  local entry=$(cat <<EOF
{"ts":$(date +%s),"tool":"build","system":"$build_system","success":$([ $exit_code -eq 0 ] && echo true || echo false),"duration_sec":$duration}
EOF
)

  echo "$entry" >> "$DATA_FILE"
}

# Wrapper for build commands
run-tracked-build() {
  local build_system="${1:-npm}"
  shift

  echo "🔨 Building with $build_system..."
  local start_time=$(date +%s)
  local exit_code

  case "$build_system" in
    npm)
      npm run build "$@"
      exit_code=$?
      ;;
    make)
      make "$@"
      exit_code=$?
      ;;
    cargo)
      cargo build "$@"
      exit_code=$?
      ;;
    *)
      echo "Unknown build system: $build_system"
      return 1
      ;;
  esac

  local end_time=$(date +%s)
  local duration=$((end_time - start_time))

  __track_build_result "$build_system" "$exit_code" "$duration"

  return $exit_code
}

# ═══════════════════════════════════════════════════════════════════════════
# ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════

tool-stats() {
  local days="${1:-7}"

  echo "🔧 Tool Success Rates (Last $days days)"
  echo "════════════════════════════════════════"

  python3 << EOF
import json
from datetime import datetime, timedelta
from collections import defaultdict

cutoff = datetime.now() - timedelta(days=$days)

try:
    with open("$DATA_FILE") as f:
        events = [json.loads(line) for line in f if line.strip()]
except FileNotFoundError:
    print("  No tool data yet")
    exit()

# Filter to time range
recent = [e for e in events if datetime.fromtimestamp(e['ts']) > cutoff]

if not recent:
    print(f"  No tool usage in last $days days")
    exit()

# Stats by tool
tools = defaultdict(lambda: {"total": 0, "success": 0})
for e in recent:
    tool = e.get('tool', 'unknown')
    tools[tool]['total'] += 1
    if e.get('success', False):
        tools[tool]['success'] += 1

# Overall stats
total = len(recent)
successful = sum(1 for e in recent if e.get('success', False))
success_rate = (successful / total * 100) if total > 0 else 0

print(f"  Total Operations: {total}")
print(f"  Overall Success:  {success_rate:.1f}%")
print()
print("  By Tool Type:")
for tool, stats in sorted(tools.items()):
    rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"    {tool:10s}: {stats['success']:3d}/{stats['total']:3d} ({rate:5.1f}%)")

# Bash command types
bash_events = [e for e in recent if e.get('tool') == 'bash']
if bash_events:
    cmd_types = defaultdict(lambda: {"total": 0, "success": 0})
    for e in bash_events:
        cmd_type = e.get('cmd_type', 'unknown')
        cmd_types[cmd_type]['total'] += 1
        if e.get('success', False):
            cmd_types[cmd_type]['success'] += 1

    print()
    print("  Bash Command Types:")
    for cmd_type, stats in sorted(cmd_types.items(), key=lambda x: x[1]['total'], reverse=True):
        rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"    {cmd_type:10s}: {stats['success']:3d}/{stats['total']:3d} ({rate:5.1f}%)")
EOF
}

# Note: export -f removed for zsh compatibility (bash-only feature)
