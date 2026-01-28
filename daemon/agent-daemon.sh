#!/bin/bash
# Meta-Vengine Background Agent Daemon Manager
#
# Usage:
#   daemon-start   - Start the daemon
#   daemon-stop    - Stop the daemon
#   daemon-status  - Check daemon status
#   daemon-restart - Restart the daemon
#   brief          - View today's daily brief

DAEMON_DIR="$HOME/.claude/daemon"
DAEMON_PID="$DAEMON_DIR/agent.pid"
DAEMON_LOG="$HOME/.claude/logs/daemon.log"
DAEMON_SCRIPT="$DAEMON_DIR/agent-runner.py"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RESET='\033[0m'

ensure_dirs() {
    mkdir -p "$DAEMON_DIR"
    mkdir -p "$HOME/.claude/logs"
    mkdir -p "$HOME/.claude/briefs"
}

start_daemon() {
    ensure_dirs

    # Check if already running
    if [[ -f "$DAEMON_PID" ]] && kill -0 "$(cat "$DAEMON_PID")" 2>/dev/null; then
        echo -e "${YELLOW}Daemon already running (PID: $(cat "$DAEMON_PID"))${RESET}"
        return 0
    fi

    # Start daemon in background
    nohup python3 "$DAEMON_SCRIPT" start >> "$DAEMON_LOG" 2>&1 &
    local pid=$!

    # Wait a moment and check if started
    sleep 1

    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$DAEMON_PID"
        echo -e "${GREEN}Daemon started (PID: $pid)${RESET}"
        echo "Log: $DAEMON_LOG"
    else
        echo -e "${RED}Daemon failed to start${RESET}"
        echo "Check log: $DAEMON_LOG"
        return 1
    fi
}

stop_daemon() {
    if [[ -f "$DAEMON_PID" ]]; then
        local pid=$(cat "$DAEMON_PID")

        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping daemon (PID: $pid)..."
            kill "$pid"

            # Wait for graceful shutdown
            local count=0
            while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
                sleep 1
                ((count++))
            done

            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo "Force killing..."
                kill -9 "$pid" 2>/dev/null
            fi

            rm -f "$DAEMON_PID"
            echo -e "${GREEN}Daemon stopped${RESET}"
        else
            echo -e "${YELLOW}Daemon not running (stale PID file)${RESET}"
            rm -f "$DAEMON_PID"
        fi
    else
        echo -e "${YELLOW}Daemon not running (no PID file)${RESET}"
    fi
}

status_daemon() {
    echo -e "${CYAN}Meta-Vengine Background Agent Daemon${RESET}"
    echo "========================================"

    if [[ -f "$DAEMON_PID" ]] && kill -0 "$(cat "$DAEMON_PID")" 2>/dev/null; then
        local pid=$(cat "$DAEMON_PID")
        echo -e "Status: ${GREEN}Running${RESET} (PID: $pid)"

        # Show uptime if possible
        if command -v ps &>/dev/null; then
            local started=$(ps -o lstart= -p "$pid" 2>/dev/null)
            if [[ -n "$started" ]]; then
                echo "Started: $started"
            fi
        fi
    else
        echo -e "Status: ${RED}Not running${RESET}"
    fi

    echo ""
    echo "Log file: $DAEMON_LOG"

    # Show recent log entries
    if [[ -f "$DAEMON_LOG" ]]; then
        echo ""
        echo "Recent activity:"
        tail -5 "$DAEMON_LOG" 2>/dev/null | while read line; do
            echo "  $line"
        done
    fi

    # Show today's brief if exists
    local today=$(date +%Y-%m-%d)
    local brief_file="$HOME/.claude/briefs/brief-$today.md"
    if [[ -f "$brief_file" ]]; then
        echo ""
        echo -e "${GREEN}Today's brief available:${RESET} brief-$today.md"
    fi
}

restart_daemon() {
    stop_daemon
    sleep 1
    start_daemon
}

view_brief() {
    local date="${1:-$(date +%Y-%m-%d)}"
    local brief_file="$HOME/.claude/briefs/brief-$date.md"

    if [[ -f "$brief_file" ]]; then
        cat "$brief_file"
    else
        echo -e "${YELLOW}No brief found for $date${RESET}"
        echo ""
        echo "Available briefs:"
        ls -1 "$HOME/.claude/briefs/" 2>/dev/null | head -10
    fi
}

run_agent() {
    local agent="$1"
    if [[ -z "$agent" ]]; then
        echo "Usage: agent-daemon.sh run <agent>"
        echo "Agents: brief, research, pattern"
        return 1
    fi

    python3 "$DAEMON_SCRIPT" run "$agent"
}

# Main command handler
case "${1:-}" in
    start)
        start_daemon
        ;;
    stop)
        stop_daemon
        ;;
    status)
        status_daemon
        ;;
    restart)
        restart_daemon
        ;;
    brief)
        view_brief "$2"
        ;;
    run)
        run_agent "$2"
        ;;
    log)
        tail -f "$DAEMON_LOG"
        ;;
    test)
        python3 "$DAEMON_SCRIPT" test
        ;;
    help|*)
        echo "Meta-Vengine Background Agent Daemon"
        echo ""
        echo "Usage: agent-daemon.sh <command> [args]"
        echo ""
        echo "Commands:"
        echo "  start           Start the daemon"
        echo "  stop            Stop the daemon"
        echo "  status          Show daemon status"
        echo "  restart         Restart the daemon"
        echo "  brief [date]    View daily brief (default: today)"
        echo "  run <agent>     Run single agent manually"
        echo "  log             Tail daemon log"
        echo "  test            Test all agents once"
        echo ""
        echo "Agents:"
        echo "  brief           Daily brief generator"
        echo "  research        arXiv research crawler"
        echo "  pattern         Pattern predictor"
        ;;
esac
