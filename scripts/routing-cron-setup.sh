#!/bin/bash
# Routing System - Cron Automation Setup
# Handles: weekly research sync, daily metrics, monthly optimization

set -e

SCRIPTS_DIR="$HOME/.claude/scripts"
LOGS_DIR="$HOME/.claude/logs"
RESEARCHGRAVITY_DIR="$HOME/researchgravity"
VENV_PYTHON="$HOME/.claude/venv/bin/python3"

# Ensure log directory exists
mkdir -p "$LOGS_DIR"

# ═══════════════════════════════════════════════════════════════════════════
# CRON JOB TEMPLATES
# ═══════════════════════════════════════════════════════════════════════════

# Weekly: Fetch new routing papers (Mondays 9 AM) - uses venv for arxiv package
WEEKLY_RESEARCH='0 9 * * 1 cd '"$RESEARCHGRAVITY_DIR"' && '"$VENV_PYTHON"' routing-research-sync.py fetch-papers --query "LLM routing OR model selection OR adaptive inference" --days 7 --output /tmp/routing-papers-weekly.json >> '"$LOGS_DIR"'/routing-research.log 2>&1'

# Daily: Generate metrics report (6 PM)
DAILY_METRICS='0 18 * * * python3 '"$RESEARCHGRAVITY_DIR"'/routing-metrics.py report --days 1 --format text >> '"$LOGS_DIR"'/routing-daily.log 2>&1'

# Weekly: Check targets (Fridays 5 PM)
WEEKLY_TARGETS='0 17 * * 5 python3 '"$RESEARCHGRAVITY_DIR"'/routing-metrics.py check-targets --days 7 >> '"$LOGS_DIR"'/routing-targets.log 2>&1'

# Monthly: Generate meta-analyzer proposals (1st of month, 10 AM)
MONTHLY_PROPOSALS='0 10 1 * * python3 '"$SCRIPTS_DIR"'/meta-analyzer.py propose --domain routing --days 30 --json > '"$LOGS_DIR"'/routing-proposals-$(date +\%Y\%m).json 2>&1'

# Monthly: Full research cycle (1st of month, 11 AM) - uses venv for arxiv package
MONTHLY_RESEARCH='0 11 1 * * cd '"$RESEARCHGRAVITY_DIR"' && bash -c '\''python3 init_session.py "Monthly routing research $(date +\%Y-\%m)" --impl-project cli-routing && '"$VENV_PYTHON"' routing-research-sync.py fetch-papers --query "LLM routing" --days 30 --output /tmp/routing-papers-monthly.json'\'' >> '"$LOGS_DIR"'/routing-research-monthly.log 2>&1'

# ═══════════════════════════════════════════════════════════════════════════
# INSTALLATION FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

install_cron_job() {
  local job="$1"
  local job_id="$2"

  # Check if job already exists
  if crontab -l 2>/dev/null | grep -q "$job_id"; then
    echo "  ⊘ $job_id already installed"
    return 0
  fi

  # Add job to crontab
  (crontab -l 2>/dev/null || true; echo "# $job_id"; echo "$job") | crontab -

  echo "  ✓ Installed: $job_id"
}

remove_cron_job() {
  local job_id="$1"

  # Remove job from crontab
  (crontab -l 2>/dev/null || true) | grep -v "$job_id" | crontab -

  echo "  ✓ Removed: $job_id"
}

list_routing_cron_jobs() {
  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo "  ROUTING SYSTEM - CRON JOBS"
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo ""

  local cron_jobs=$(crontab -l 2>/dev/null || echo "")

  echo "Installed Jobs:"
  echo ""

  for job_id in "routing-weekly-research" "routing-daily-metrics" "routing-weekly-targets" "routing-monthly-proposals" "routing-monthly-research"; do
    if echo "$cron_jobs" | grep -q "$job_id"; then
      echo "  ✓ $job_id"
    else
      echo "  ✗ $job_id (not installed)"
    fi
  done

  echo ""
  echo "Logs:"
  echo "  $LOGS_DIR/routing-research.log         # Weekly research sync"
  echo "  $LOGS_DIR/routing-daily.log            # Daily metrics reports"
  echo "  $LOGS_DIR/routing-targets.log          # Weekly target checks"
  echo "  $LOGS_DIR/routing-proposals-*.json     # Monthly proposals"
  echo "  $LOGS_DIR/routing-research-monthly.log # Monthly research cycle"
  echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

cmd_install() {
  local profile="${1:-standard}"

  echo ""
  echo "Installing routing automation (profile: $profile)..."
  echo ""

  case "$profile" in
    minimal)
      # Only essential jobs
      install_cron_job "$DAILY_METRICS" "routing-daily-metrics"
      install_cron_job "$WEEKLY_TARGETS" "routing-weekly-targets"
      ;;

    standard)
      # Recommended jobs
      install_cron_job "$DAILY_METRICS" "routing-daily-metrics"
      install_cron_job "$WEEKLY_TARGETS" "routing-weekly-targets"
      install_cron_job "$WEEKLY_RESEARCH" "routing-weekly-research"
      install_cron_job "$MONTHLY_PROPOSALS" "routing-monthly-proposals"
      ;;

    full)
      # All jobs including monthly research cycle
      install_cron_job "$DAILY_METRICS" "routing-daily-metrics"
      install_cron_job "$WEEKLY_TARGETS" "routing-weekly-targets"
      install_cron_job "$WEEKLY_RESEARCH" "routing-weekly-research"
      install_cron_job "$MONTHLY_PROPOSALS" "routing-monthly-proposals"
      install_cron_job "$MONTHLY_RESEARCH" "routing-monthly-research"
      ;;

    *)
      echo "Unknown profile: $profile"
      echo "Available: minimal, standard, full"
      exit 1
      ;;
  esac

  echo ""
  echo "✓ Installation complete!"
  echo ""
  echo "View status: routing-cron-setup.sh status"
  echo "View logs:   tail -f $LOGS_DIR/routing-daily.log"
  echo ""
}

cmd_uninstall() {
  echo ""
  echo "Uninstalling routing automation..."
  echo ""

  remove_cron_job "routing-weekly-research"
  remove_cron_job "routing-daily-metrics"
  remove_cron_job "routing-weekly-targets"
  remove_cron_job "routing-monthly-proposals"
  remove_cron_job "routing-monthly-research"

  echo ""
  echo "✓ Uninstallation complete!"
  echo ""
}

cmd_status() {
  list_routing_cron_jobs
}

cmd_test() {
  local job_type="${1:-daily}"

  echo ""
  echo "Testing $job_type job..."
  echo ""

  case "$job_type" in
    daily)
      python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days 1
      ;;

    weekly-research)
      cd "$RESEARCHGRAVITY_DIR"
      python3 routing-research-sync.py fetch-papers --query "LLM routing" --days 7 --max-results 5
      ;;

    weekly-targets)
      python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-targets --days 7
      ;;

    monthly-proposals)
      python3 "$SCRIPTS_DIR/meta-analyzer.py" propose --domain routing --days 30
      ;;

    *)
      echo "Unknown job type: $job_type"
      echo "Available: daily, weekly-research, weekly-targets, monthly-proposals"
      exit 1
      ;;
  esac

  echo ""
  echo "✓ Test complete!"
  echo ""
}

cmd_logs() {
  local log_type="${1:-daily}"

  case "$log_type" in
    daily)
      tail -f "$LOGS_DIR/routing-daily.log"
      ;;

    research)
      tail -f "$LOGS_DIR/routing-research.log"
      ;;

    targets)
      tail -f "$LOGS_DIR/routing-targets.log"
      ;;

    proposals)
      ls -t "$LOGS_DIR"/routing-proposals-*.json | head -1 | xargs cat | python3 -m json.tool
      ;;

    all)
      echo "=== Daily Metrics (last 10 lines) ==="
      tail -10 "$LOGS_DIR/routing-daily.log" 2>/dev/null || echo "No logs yet"
      echo ""
      echo "=== Weekly Research (last 10 lines) ==="
      tail -10 "$LOGS_DIR/routing-research.log" 2>/dev/null || echo "No logs yet"
      echo ""
      echo "=== Targets (last 10 lines) ==="
      tail -10 "$LOGS_DIR/routing-targets.log" 2>/dev/null || echo "No logs yet"
      ;;

    *)
      echo "Unknown log type: $log_type"
      echo "Available: daily, research, targets, proposals, all"
      exit 1
      ;;
  esac
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

main() {
  local command="${1:-status}"

  case "$command" in
    install)
      cmd_install "${2:-standard}"
      ;;

    uninstall)
      cmd_uninstall
      ;;

    status)
      cmd_status
      ;;

    test)
      cmd_test "$2"
      ;;

    logs)
      cmd_logs "$2"
      ;;

    help)
      echo ""
      echo "Routing System - Cron Automation Setup"
      echo ""
      echo "Usage: routing-cron-setup.sh <command> [options]"
      echo ""
      echo "Commands:"
      echo "  install [profile]   Install cron jobs (minimal|standard|full)"
      echo "  uninstall           Remove all routing cron jobs"
      echo "  status              Show installation status"
      echo "  test <job>          Test a specific job manually"
      echo "  logs <type>         View logs (daily|research|targets|proposals|all)"
      echo "  help                Show this help message"
      echo ""
      echo "Profiles:"
      echo "  minimal    - Daily metrics + weekly targets only"
      echo "  standard   - + weekly research + monthly proposals (recommended)"
      echo "  full       - + monthly research cycle"
      echo ""
      echo "Examples:"
      echo "  routing-cron-setup.sh install standard"
      echo "  routing-cron-setup.sh test daily"
      echo "  routing-cron-setup.sh logs daily"
      echo ""
      ;;

    *)
      echo "Unknown command: $command"
      echo "Run 'routing-cron-setup.sh help' for usage"
      exit 1
      ;;
  esac
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
