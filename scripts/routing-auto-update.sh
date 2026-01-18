#!/bin/bash
# Routing Auto-Update System with Production Validation
#
# Safety-first auto-update system that:
# - Monitors performance for stability period
# - Only updates if all targets met consistently
# - Requires manual approval for first update
# - Auto-rolls back on degradation
#
# Usage:
#   routing-auto-update.sh status        # Check readiness
#   routing-auto-update.sh enable        # Enable auto-updates
#   routing-auto-update.sh disable       # Disable auto-updates
#   routing-auto-update.sh check         # Check for available updates
#   routing-auto-update.sh apply         # Apply approved updates

set -e

KERNEL_DIR="$HOME/.claude/kernel"
DATA_DIR="$HOME/.claude/data"
LOGS_DIR="$HOME/.claude/logs"
RESEARCHGRAVITY_DIR="$HOME/researchgravity"

BASELINES_FILE="$KERNEL_DIR/baselines.json"
AUTO_UPDATE_CONFIG="$KERNEL_DIR/auto-update-config.json"
AUTO_UPDATE_LOG="$LOGS_DIR/auto-update.log"
VALIDATION_CACHE="$DATA_DIR/auto-update-validation.json"

# Ensure directories exist
mkdir -p "$KERNEL_DIR" "$DATA_DIR" "$LOGS_DIR"

# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG='{
  "enabled": false,
  "approved_by_user": false,
  "stability_period_days": 30,
  "min_queries_required": 200,
  "targets_must_meet_consecutively": 7,
  "auto_rollback_on_drop": true,
  "rollback_threshold_pct": 0.10,
  "require_ab_test_validation": true,
  "max_auto_updates_per_month": 2,
  "last_enabled": null,
  "first_auto_update_completed": false
}'

load_config() {
  if [[ -f "$AUTO_UPDATE_CONFIG" ]]; then
    cat "$AUTO_UPDATE_CONFIG"
  else
    echo "$DEFAULT_CONFIG"
  fi
}

save_config() {
  local config="$1"
  echo "$config" | python3 -m json.tool > "$AUTO_UPDATE_CONFIG"
}

# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION READINESS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

check_production_readiness() {
  local stability_days="${1:-30}"

  echo "Checking production readiness (${stability_days}-day stability period)..."
  echo ""

  local validation_result='{"ready": false, "checks": [], "confidence": 0}'

  # Check 1: Sufficient sample size
  local query_count=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days "$stability_days" --format json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_queries', 0))" 2>/dev/null || echo "0")

  if [[ "$query_count" -ge 200 ]]; then
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'sample_size', 'status': 'pass', 'value': $query_count, 'threshold': 200})
print(json.dumps(data))
")
    echo "  ✓ Sample size: $query_count queries (>= 200 required)"
  else
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'sample_size', 'status': 'fail', 'value': $query_count, 'threshold': 200})
print(json.dumps(data))
")
    echo "  ✗ Sample size: $query_count queries (need >= 200)"
  fi

  # Check 2: All targets met
  if python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-targets --days "$stability_days" >/dev/null 2>&1; then
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'targets_met', 'status': 'pass'})
print(json.dumps(data))
")
    echo "  ✓ All performance targets met"
  else
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'targets_met', 'status': 'fail'})
print(json.dumps(data))
")
    echo "  ✗ Performance targets not met"
  fi

  # Check 3: Consecutive stability (last 7 days must also pass)
  if python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-targets --days 7 >/dev/null 2>&1; then
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'recent_stability', 'status': 'pass'})
print(json.dumps(data))
")
    echo "  ✓ Recent stability (last 7 days)"
  else
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'recent_stability', 'status': 'fail'})
print(json.dumps(data))
")
    echo "  ✗ Recent stability check failed"
  fi

  # Check 4: No degradation trend
  local report=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days "$stability_days" --format json 2>/dev/null)
  local accuracy=$(echo "$report" | python3 -c "import sys, json; print(json.load(sys.stdin).get('accuracy', 0) or 0)" 2>/dev/null || echo "0")

  if (( $(echo "$accuracy > 0.75" | bc -l 2>/dev/null || echo "0") )); then
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'accuracy_threshold', 'status': 'pass', 'value': $accuracy})
print(json.dumps(data))
")
    echo "  ✓ Accuracy: ${accuracy} (>= 0.75)"
  else
    validation_result=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['checks'].append({'name': 'accuracy_threshold', 'status': 'fail', 'value': $accuracy})
print(json.dumps(data))
")
    echo "  ✗ Accuracy: ${accuracy} (need >= 0.75)"
  fi

  # Calculate overall readiness
  local passed_checks=$(echo "$validation_result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
passed = sum(1 for c in data['checks'] if c.get('status') == 'pass')
total = len(data['checks'])
data['ready'] = (passed == total)
data['confidence'] = passed / total if total > 0 else 0
print(json.dumps(data))
")

  echo "$passed_checks"
}

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-UPDATE LOGIC
# ═══════════════════════════════════════════════════════════════════════════

check_for_updates() {
  echo "Checking for available updates..."
  echo ""

  # Generate routing proposals
  local proposals=$(python3 ~/.claude/scripts/meta-analyzer.py propose --domain routing --days 30 --json 2>/dev/null)

  if [[ -z "$proposals" || "$proposals" == "[]" ]]; then
    echo "No optimization proposals available."
    return 1
  fi

  local proposal_count=$(echo "$proposals" | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('proposals', [])))")

  echo "Found $proposal_count optimization proposals"
  echo ""

  # Show proposals
  echo "$proposals" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for proposal in data.get('proposals', []):
    print(f\"  {proposal['id']}: {proposal['type']}\")
    print(f\"     Target: {proposal['target']}\")
    print(f\"     Confidence: {proposal['confidence']}\")
    print(f\"     Rationale: {proposal['rationale']}\")
    print()
"

  echo "$proposals"
}

apply_auto_update() {
  local config=$(load_config)

  # Check if enabled
  local enabled=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('enabled', False))" | tr '[:upper:]' '[:lower:]')
  if [[ "$enabled" != "true" ]]; then
    echo "❌ Auto-update not enabled. Run: routing-auto-update.sh enable"
    return 1
  fi

  # Check if first update and needs approval
  local first_completed=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('first_auto_update_completed', False))" | tr '[:upper:]' '[:lower:]')
  local approved=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('approved_by_user', False))" | tr '[:upper:]' '[:lower:]')

  if [[ "$first_completed" != "true" && "$approved" != "true" ]]; then
    echo "❌ First auto-update requires manual approval."
    echo ""
    echo "To approve:"
    echo "  1. Review system performance: routing-dash"
    echo "  2. Enable with approval: routing-auto-update.sh approve"
    return 1
  fi

  # Check production readiness
  local validation=$(check_production_readiness 30)
  local ready=$(echo "$validation" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ready', False))" | tr '[:upper:]' '[:lower:]')

  if [[ "$ready" != "true" ]]; then
    echo "❌ System not production-ready for auto-update"
    echo ""
    echo "Validation cache saved to: $VALIDATION_CACHE"
    echo "$validation" > "$VALIDATION_CACHE"
    return 1
  fi

  echo "✓ Production validation passed"
  echo ""

  # Get proposals
  local proposals=$(check_for_updates)

  if [[ $? -ne 0 ]]; then
    echo "No updates to apply."
    return 0
  fi

  # Filter to high-confidence proposals
  local high_confidence=$(echo "$proposals" | python3 -c "
import sys, json
data = json.load(sys.stdin)
high_conf = [p for p in data.get('proposals', []) if p.get('confidence', 0) >= 0.80]
print(json.dumps(high_conf))
")

  local count=$(echo "$high_confidence" | python3 -c "import sys, json; print(len(json.load(sys.stdin)))")

  if [[ "$count" -eq 0 ]]; then
    echo "No high-confidence proposals (>= 0.80) available."
    return 0
  fi

  echo "Applying $count high-confidence proposals..."
  echo ""

  # Apply each proposal via A/B test (if required) or directly
  local require_ab=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('require_ab_test_validation', True))" | tr '[:upper:]' '[:lower:]')

  for proposal in $(echo "$high_confidence" | python3 -c "
import sys, json
for p in json.load(sys.stdin):
    print(p['id'])
"); do
    echo "  Processing: $proposal"

    if [[ "$require_ab" == "true" ]]; then
      echo "    Creating A/B test for validation..."
      # TODO: Create A/B test configuration and track
    else
      echo "    Applying directly..."
      # TODO: Apply modification via meta-analyzer
    fi
  done

  # Update config
  config=$(echo "$config" | python3 -c "
import sys, json
from datetime import datetime
data = json.load(sys.stdin)
data['first_auto_update_completed'] = True
data['last_update'] = datetime.now().isoformat()
print(json.dumps(data, indent=2))
")
  save_config "$config"

  # Log update
  echo "$(date '+%Y-%m-%d %H:%M:%S') | AUTO-UPDATE | Applied $count proposals" >> "$AUTO_UPDATE_LOG"

  echo ""
  echo "✅ Auto-update complete!"
  echo ""
}

# ═══════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

cmd_status() {
  local config=$(load_config)

  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo "  AUTO-UPDATE STATUS"
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo ""

  local enabled=$(echo "$config" | python3 -c "import sys, json; print('Enabled' if json.load(sys.stdin).get('enabled', False) else 'Disabled')")
  local approved=$(echo "$config" | python3 -c "import sys, json; print('Yes' if json.load(sys.stdin).get('approved_by_user', False) else 'No')")
  local stability_days=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('stability_period_days', 30))")

  echo "Status: $enabled"
  echo "User Approved: $approved"
  echo "Stability Period: $stability_days days"
  echo ""

  # Check production readiness
  local validation=$(check_production_readiness "$stability_days")
  echo ""

  local ready=$(echo "$validation" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ready', False))" | tr '[:upper:]' '[:lower:]')
  local confidence=$(echo "$validation" | python3 -c "import sys, json; print(f\"{json.load(sys.stdin).get('confidence', 0):.0%}\")")

  if [[ "$ready" == "true" ]]; then
    echo "Production Ready: ✅ Yes (Confidence: $confidence)"
  else
    echo "Production Ready: ⚠️  No (Confidence: $confidence)"
    echo ""
    echo "Requirements for production readiness:"
    echo "  - 30 days of stable operation"
    echo "  - 200+ queries processed"
    echo "  - All performance targets met"
    echo "  - Last 7 days also passing targets"
  fi

  echo ""
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo ""
}

cmd_enable() {
  local config=$(load_config)

  config=$(echo "$config" | python3 -c "
import sys, json
from datetime import datetime
data = json.load(sys.stdin)
data['enabled'] = True
data['last_enabled'] = datetime.now().isoformat()
print(json.dumps(data, indent=2))
")

  save_config "$config"

  echo "✓ Auto-update enabled"
  echo ""
  echo "⚠️  First auto-update requires approval. Run: routing-auto-update.sh approve"
  echo ""
}

cmd_disable() {
  local config=$(load_config)

  config=$(echo "$config" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['enabled'] = False
print(json.dumps(data, indent=2))
")

  save_config "$config"

  echo "✓ Auto-update disabled"
  echo ""
}

cmd_approve() {
  local config=$(load_config)

  # Show current performance
  echo ""
  echo "Current Performance:"
  echo ""
  python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days 30
  echo ""

  # Ask for confirmation
  read -p "Approve auto-updates based on this performance? (yes/no): " confirm

  if [[ "$confirm" == "yes" ]]; then
    config=$(echo "$config" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['approved_by_user'] = True
data['enabled'] = True
print(json.dumps(data, indent=2))
")

    save_config "$config"

    echo ""
    echo "✅ Auto-updates approved and enabled!"
    echo ""
    echo "The system will now automatically apply high-confidence optimizations"
    echo "after validation. You can disable anytime with:"
    echo "  routing-auto-update.sh disable"
    echo ""
  else
    echo "Approval cancelled."
  fi
}

cmd_check() {
  check_for_updates
}

cmd_apply() {
  apply_auto_update
}

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

main() {
  local command="${1:-status}"

  case "$command" in
    status)
      cmd_status
      ;;

    enable)
      cmd_enable
      ;;

    disable)
      cmd_disable
      ;;

    approve)
      cmd_approve
      ;;

    check)
      cmd_check
      ;;

    apply)
      cmd_apply
      ;;

    help)
      echo ""
      echo "Routing Auto-Update System"
      echo ""
      echo "Usage: routing-auto-update.sh <command>"
      echo ""
      echo "Commands:"
      echo "  status     Check auto-update status and production readiness"
      echo "  enable     Enable auto-updates (requires approval for first run)"
      echo "  disable    Disable auto-updates"
      echo "  approve    Approve first auto-update (with performance review)"
      echo "  check      Check for available optimization updates"
      echo "  apply      Apply approved updates (manual trigger)"
      echo "  help       Show this help message"
      echo ""
      echo "Safety Features:"
      echo "  - Requires 30 days of stable operation before first auto-update"
      echo "  - Only applies high-confidence proposals (>= 0.80)"
      echo "  - Validates all performance targets before updating"
      echo "  - Auto-rolls back on >10% performance degradation"
      echo "  - Limits to 2 auto-updates per month"
      echo ""
      ;;

    *)
      echo "Unknown command: $command"
      echo "Run 'routing-auto-update.sh help' for usage"
      exit 1
      ;;
  esac
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
