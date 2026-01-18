#!/bin/bash
# Claude Code Stats - Quick profile overview

STATS_FILE="$HOME/.claude/stats-cache.json"
HISTORY_FILE="$HOME/.claude/history.jsonl"

if [[ ! -f "$STATS_FILE" ]]; then
  echo "No stats cache found."
  exit 1
fi

# Parse stats
total_sessions=$(jq -r '.totalSessions' "$STATS_FILE")
total_messages=$(jq -r '.totalMessages' "$STATS_FILE")
first_date=$(jq -r '.firstSessionDate' "$STATS_FILE" | cut -d'T' -f1)
longest_session=$(jq -r '.longestSession.messageCount' "$STATS_FILE")

# Token stats
output_tokens=$(jq -r '.modelUsage["claude-opus-4-5-20251101"].outputTokens // 0' "$STATS_FILE")
input_tokens=$(jq -r '.modelUsage["claude-opus-4-5-20251101"].inputTokens // 0' "$STATS_FILE")
cache_read=$(jq -r '.modelUsage["claude-opus-4-5-20251101"].cacheReadInputTokens // 0' "$STATS_FILE")

# Format numbers with jq (more portable)
format_num() {
  local n=$1
  if [[ $n -ge 1000000 ]]; then
    echo "$n" | jq -r '. / 1000000 | . * 10 | floor | . / 10 | "\(.)M"'
  elif [[ $n -ge 1000 ]]; then
    echo "$n" | jq -r '. / 1000 | . * 10 | floor | . / 10 | "\(.)K"'
  else
    echo "$n"
  fi
}

# Calculate days since start
days_active=$(( ($(date +%s) - $(date -j -f "%Y-%m-%d" "$first_date" +%s 2>/dev/null || date -d "$first_date" +%s)) / 86400 ))

# Today's sessions from history
today=$(date +%Y-%m-%d)
today_sessions=$(jq -s "[.[] | select((.timestamp/1000 | strftime(\"%Y-%m-%d\")) == \"$today\")] | group_by(.sessionId) | length" "$HISTORY_FILE" 2>/dev/null || echo "?")

echo ""
echo "╭─────────────────────────────────────────╮"
echo "│         CLAUDE CODE PROFILE             │"
echo "╰─────────────────────────────────────────╯"
echo ""
echo "  Started:        $first_date ($days_active days ago)"
echo "  Sessions:       $total_sessions total │ $today_sessions today"
echo "  Messages:       $total_messages"
echo "  Longest:        $longest_session msgs"
echo ""
echo "  ─── Tokens ───"
echo "  Output:         $(format_num $output_tokens)"
echo "  Input:          $(format_num $input_tokens)"
echo "  Cache Reads:    $(format_num $cache_read)"
echo ""

# Recent daily activity
echo "  ─── Recent ───"
jq -r '.dailyActivity | reverse | .[0:5] | reverse | .[] | "  \(.date): \(.messageCount) msgs, \(.toolCallCount) tools"' "$STATS_FILE"
echo ""
