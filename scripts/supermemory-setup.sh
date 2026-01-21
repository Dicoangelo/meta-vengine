#!/bin/bash
# Supermemory One-Time Setup
# Initializes the database and all automations

set -e

echo "🧠 Supermemory Setup"
echo "===================="
echo ""

# 1. Run initial sync
echo "📊 Running initial sync..."
python3 ~/.claude/supermemory/cli.py sync

# 2. Load LaunchD plist (daily sync)
PLIST="$HOME/Library/LaunchAgents/com.claude.supermemory.plist"
if [ -f "$PLIST" ]; then
    echo ""
    echo "⏰ Loading LaunchD plist for daily sync..."
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "   ✓ Daily sync at 6am enabled"
fi

# 3. Check cron jobs
echo ""
echo "📅 Checking cron jobs..."
if crontab -l 2>/dev/null | grep -q "supermemory-cron.sh weekly"; then
    echo "   ✓ Weekly rollup (Sunday 8pm) enabled"
else
    echo "   ⚠ Weekly rollup not in crontab - adding..."
    (crontab -l 2>/dev/null; echo "# Supermemory weekly rollup"; echo "0 20 * * 0 ~/.claude/scripts/supermemory-cron.sh weekly >> ~/.claude/logs/supermemory-cron.log 2>&1") | crontab -
    echo "   ✓ Added weekly rollup"
fi

if crontab -l 2>/dev/null | grep -q "supermemory-cron.sh monthly"; then
    echo "   ✓ Monthly rollup (1st 9am) enabled"
else
    echo "   ⚠ Monthly rollup not in crontab - adding..."
    (crontab -l 2>/dev/null; echo "# Supermemory monthly tasks"; echo "0 9 1 * * ~/.claude/scripts/supermemory-cron.sh monthly >> ~/.claude/logs/supermemory-cron.log 2>&1") | crontab -
    echo "   ✓ Added monthly rollup"
fi

# 4. Verify hooks
echo ""
echo "🔗 Checking hooks..."
if grep -q "supermemory" ~/.claude/hooks/session-optimizer-stop.sh 2>/dev/null; then
    echo "   ✓ Session sync hook enabled"
else
    echo "   ⚠ Session sync hook not configured"
fi

if grep -q "supermemory" ~/.claude/hooks/error-capture.sh 2>/dev/null; then
    echo "   ✓ Error lookup hook enabled"
else
    echo "   ⚠ Error lookup hook not configured"
fi

# 5. Show stats
echo ""
echo "📈 Current Stats:"
python3 ~/.claude/supermemory/cli.py stats

echo ""
echo "✅ Setup complete!"
echo ""
echo "Commands:"
echo "  sm stats     - View statistics"
echo "  sm context   - Get session context"
echo "  sm review    - Start spaced repetition"
echo "  sm sync      - Rebuild indexes"
echo "  ccc          - Open Command Center (Tab S for Supermemory)"
