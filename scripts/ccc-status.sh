#!/bin/bash
# CCC Infrastructure Status - Quick health check
# Usage: ccc-status

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo "${BOLD}         CCC INFRASTRUCTURE STATUS                         ${NC}"
echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check all daemons
DAEMONS=(
    "com.claude.watchdog:Watchdog (guardian)"
    "com.claude.dashboard-refresh:Dashboard Refresh (60s)"
    "com.claude.supermemory:Supermemory (daily)"
    "com.claude.session-analysis:Session Analysis (30m)"
    "com.claude.autonomous-maintenance:Auto Maintenance (1h)"
    "com.claude.self-heal:Self Heal (6h)"
    "com.claude.bootstrap:Bootstrap (login)"
    "com.claude.wake-hook:Wake Hook (sleep)"
)

echo "${BOLD}Daemons:${NC}"
all_ok=true
for entry in "${DAEMONS[@]}"; do
    daemon="${entry%%:*}"
    desc="${entry#*:}"

    if launchctl list 2>/dev/null | grep -q "$daemon"; then
        pid=$(launchctl list 2>/dev/null | grep "$daemon" | awk '{print $1}')
        if [[ "$pid" == "-" ]]; then
            echo -e "  ${GREEN}✓${NC} $desc ${YELLOW}(scheduled)${NC}"
        else
            echo -e "  ${GREEN}✓${NC} $desc ${GREEN}(PID: $pid)${NC}"
        fi
    else
        echo -e "  ${RED}✗${NC} $desc ${RED}(NOT LOADED)${NC}"
        all_ok=false
    fi
done

echo ""

# Check heartbeat
heartbeat="$HOME/.claude/.watchdog-heartbeat"
if [[ -f "$heartbeat" ]]; then
    last=$(cat "$heartbeat")
    echo -e "${BOLD}Watchdog Heartbeat:${NC} ${GREEN}$last${NC}"
else
    echo -e "${BOLD}Watchdog Heartbeat:${NC} ${RED}No heartbeat file${NC}"
fi

echo ""

# Check critical files
echo "${BOLD}Data Freshness:${NC}"
files=(
    "$HOME/.claude/dashboard/claude-command-center.html:Dashboard"
    "$HOME/.claude/kernel/session-state.json:Session State"
    "$HOME/.claude/memory/supermemory.db:Supermemory DB"
)

for entry in "${files[@]}"; do
    path="${entry%%:*}"
    name="${entry#*:}"

    if [[ -f "$path" ]]; then
        # Get age in minutes
        age_sec=$(($(date +%s) - $(stat -f %m "$path")))
        age_min=$((age_sec / 60))

        if [[ $age_min -lt 60 ]]; then
            echo -e "  ${GREEN}✓${NC} $name (${age_min}m ago)"
        elif [[ $age_min -lt 1440 ]]; then
            hours=$((age_min / 60))
            echo -e "  ${YELLOW}⚠${NC} $name (${hours}h ago)"
        else
            days=$((age_min / 1440))
            echo -e "  ${RED}✗${NC} $name (${days}d ago)"
        fi
    else
        echo -e "  ${RED}✗${NC} $name (MISSING)"
    fi
done

echo ""
echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"

if $all_ok; then
    echo -e "Status: ${GREEN}${BOLD}ALL SYSTEMS OPERATIONAL${NC}"
else
    echo -e "Status: ${RED}${BOLD}DEGRADED - Run: ccc-fix${NC}"
fi

echo "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""
