#!/bin/bash
# Test Observatory - Generate sample data for testing

echo "🧪 Testing Claude Observatory..."
echo ""

OBSERVATORY_DIR="$HOME/.claude/scripts/observatory"

# Source Observatory
source "$OBSERVATORY_DIR/init.sh"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "TEST 1: Session Tracking"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Simulate session
session-rate 5 "Test session - Observatory implementation"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 2: Cost Tracking"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Process current session
echo "Processing last 1 day of sessions..."
python3 "$OBSERVATORY_DIR/collectors/cost-tracker.py" process 1
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 3: Productivity Tracking"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Log productivity snapshot
python3 "$OBSERVATORY_DIR/collectors/productivity-analyzer.py" log
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 4: Tool Tracking"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Run some commands to generate tool data
echo "Testing bash success tracking..."
true  # Should log success
echo "Testing bash failure tracking..."
false || true  # Should log failure
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 5: Unified Analytics"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Generate unified report
python3 "$OBSERVATORY_DIR/analytics-engine.py" report 1
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 6: Cost Report"
echo "═══════════════════════════════════════════════════════════════"
echo ""

python3 "$OBSERVATORY_DIR/collectors/cost-tracker.py" report 1
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "TEST 7: Productivity Report"
echo "═══════════════════════════════════════════════════════════════"
echo ""

python3 "$OBSERVATORY_DIR/collectors/productivity-analyzer.py" report 7
echo ""

echo "✅ Observatory tests complete!"
echo ""
echo "Next steps:"
echo "  1. Source Observatory: source ~/.claude/init.sh"
echo "  2. Run 'obs' for unified report"
echo "  3. Run 'obs-help' for full command reference"
echo "  4. Open Command Center: ccc"
