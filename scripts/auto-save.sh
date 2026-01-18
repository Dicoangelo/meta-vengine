#!/bin/bash
# Auto-checkpoint system
# Monitors session activity and prompts for checkpoints

CHECKPOINT_DIR="$HOME/.claude/checkpoints"
mkdir -p "$CHECKPOINT_DIR"

checkpoint() {
  local name="${1:-$(date '+%Y%m%d_%H%M%S')}"
  local file="$CHECKPOINT_DIR/$name.md"

  echo "# Checkpoint: $name" > "$file"
  echo "Time: $(date)" >> "$file"
  echo "Directory: $(pwd)" >> "$file"
  echo "" >> "$file"
  echo "## Recent Activity" >> "$file"
  tail -20 ~/.claude/activity.log >> "$file" 2>/dev/null
  echo "" >> "$file"
  echo "## Notes" >> "$file"
  echo "(Add notes here)" >> "$file"

  echo "✓ Checkpoint saved: $file"
}

list_checkpoints() {
  ls -la "$CHECKPOINT_DIR"/*.md 2>/dev/null || echo "No checkpoints yet"
}
