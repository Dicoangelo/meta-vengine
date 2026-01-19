#!/bin/zsh
# Check automated feedback status

if [[ " ${precmd_functions[@]} " =~ " __ai_feedback_auto " ]]; then
  echo "✓ Automated feedback is ACTIVE"
  echo ""
  echo "How it works:"
  echo "  - Monitors command exit codes after AI queries"
  echo "  - Records failures within 30 seconds of query"
  echo "  - Automatically improves routing decisions"
  echo "  - Logs to: ~/.claude/data/ai-routing.log"
  echo ""
  echo "To disable: ai-feedback-disable"
else
  echo "✗ Automated feedback is NOT active"
  echo ""
  echo "To enable: ai-feedback-enable"
  echo ""
  echo "Then reload: source ~/.claude/init.sh"
fi
