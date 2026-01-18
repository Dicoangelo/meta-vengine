#!/bin/bash
# Routing Performance Dashboard
# Real-time view of autonomous routing system

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  🤖 AUTONOMOUS ROUTING DASHBOARD"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check if routing is active
if [[ -f "$HOME/.claude/scripts/claude-wrapper.sh" ]]; then
  echo "✓ Status: Active"
else
  echo "✗ Status: Inactive"
fi

echo ""

# Show last 24h stats
if command -v python3 &> /dev/null; then
  python3 ~/researchgravity/routing-metrics.py report --days 1 2>/dev/null
else
  echo "⚠️  Python3 not found - metrics unavailable"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Commands:"
echo "  routing-dash           This dashboard"
echo "  routing-report 7       Weekly report"
echo "  routing-targets        Check target compliance"
echo "  ai \"query\"            DQ-powered routing"
echo "  ai-good \"prefix\"      Record success feedback"
echo "  ai-bad \"prefix\"       Record failure feedback"
echo ""
echo "Files:"
echo "  ~/.claude/kernel/baselines.json       Configuration"
echo "  ~/.claude/data/routing-metrics.jsonl  Metrics log"
echo "  ~/.claude/kernel/dq-scores.jsonl      Routing decisions"
echo ""
