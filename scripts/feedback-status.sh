#!/bin/zsh
# Check automated feedback status
# Note: This must be run as a sourced function, not a script

# Check if running in zsh
if [[ -z "$ZSH_VERSION" ]]; then
  echo "⚠️  This checker requires zsh"
  echo ""
  echo "Run directly in your terminal:"
  echo "  echo \${precmd_functions[@]}"
  echo ""
  echo "If you see '__ai_feedback_auto', feedback is active."
  exit 1
fi

# Instructions for user to check manually
echo "To check if automated feedback is active, run:"
echo ""
echo "  echo \${precmd_functions[@]}"
echo ""
echo "If you see '__ai_feedback_auto' in the output, feedback is ACTIVE ✓"
echo "If you don't see it, run: ai-feedback-enable"
echo ""
echo "Based on typical setup, feedback should be:"
if [[ -f ~/.claude/kernel/dq-scorer.js ]] && [[ -f ~/.claude/scripts/smart-route.sh ]]; then
  echo "  ✓ Ready to enable (kernel and scripts present)"
else
  echo "  ✗ Missing required files"
fi
