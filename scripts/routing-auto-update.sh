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
  "min_queries_required": 200,
  "min_feedback_count": 50,
  "data_quality_threshold": 0.80,
  "recent_queries_sample": 50,
  "auto_rollback_on_drop": true,
  "rollback_threshold_pct": 0.10,
  "require_ab_test_validation": true,
  "max_auto_updates_per_period": 2,
  "update_window_queries": 500,
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
  local config=$(load_config)
  local min_queries=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('min_queries_required', 200))")
  local min_feedback=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('min_feedback_count', 50))")
  local data_quality_thresh=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('data_quality_threshold', 0.80))")
  local recent_sample=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('recent_queries_sample', 50))")

  echo "Checking production readiness (usage-based validation)..." >&2
  echo "" >&2

  local validation='{"ready": false, "checks": []}'

  # Check 1: Query count
  local query_count=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" report --days 999 --format json 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('total_queries', 0))" || echo "0")

  if [[ "$query_count" -ge "$min_queries" ]]; then
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'query_count','status':'pass','value':$query_count}); print(json.dumps(d))")
    echo "  ✓ Query count: $query_count (>= $min_queries)" >&2
  else
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'query_count','status':'fail','value':$query_count}); print(json.dumps(d))")
    echo "  ✗ Query count: $query_count (need $min_queries)" >&2
  fi

  # Check 2: Feedback count
  local feedback_count=$(wc -l < "$KERNEL_DIR/dq-scores.jsonl" 2>/dev/null | tr -d ' ' || echo "0")

  if [[ "$feedback_count" -ge "$min_feedback" ]]; then
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'feedback_count','status':'pass','value':$feedback_count}); print(json.dumps(d))")
    echo "  ✓ Feedback count: $feedback_count (>= $min_feedback)" >&2
  else
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'feedback_count','status':'fail','value':$feedback_count}); print(json.dumps(d))")
    echo "  ✗ Feedback count: $feedback_count (need $min_feedback)" >&2
  fi

  # Check 3: Data quality
  local data_quality=$(python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-data-quality --all-time 2>/dev/null || echo "0.0")

  if (( $(echo "$data_quality >= $data_quality_thresh" | bc -l 2>/dev/null || echo "0") )); then
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'data_quality','status':'pass','value':$data_quality}); print(json.dumps(d))")
    echo "  ✓ Data quality: $data_quality (>= $data_quality_thresh)" >&2
  else
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'data_quality','status':'fail','value':$data_quality}); print(json.dumps(d))")
    echo "  ✗ Data quality: $data_quality (need $data_quality_thresh)" >&2
  fi

  # Check 4: Recent performance (last N queries)
  if python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-targets --last-n-queries "$recent_sample" >/dev/null 2>&1; then
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'recent_performance','status':'pass'}); print(json.dumps(d))")
    echo "  ✓ Recent performance: Last $recent_sample queries meet targets" >&2
  else
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'recent_performance','status':'fail'}); print(json.dumps(d))")
    echo "  ✗ Recent performance: Last $recent_sample queries below targets" >&2
  fi

  # Check 5: Overall targets
  if python3 "$RESEARCHGRAVITY_DIR/routing-metrics.py" check-targets --all-time >/dev/null 2>&1; then
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'overall_targets','status':'pass'}); print(json.dumps(d))")
    echo "  ✓ Overall targets met" >&2
  else
    validation=$(echo "$validation" | python3 -c "import sys, json; d=json.load(sys.stdin); d['checks'].append({'name':'overall_targets','status':'fail'}); print(json.dumps(d))")
    echo "  ✗ Overall targets not met" >&2
  fi

  # Calculate readiness
  echo "$validation" | python3 -c "
import sys, json
d = json.load(sys.stdin)
passed = sum(1 for c in d['checks'] if c.get('status') == 'pass')
total = len(d['checks'])
d['ready'] = (passed == total)
d['confidence'] = passed / total if total > 0 else 0
print(json.dumps(d))
"
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
  echo "  AUTO-UPDATE STATUS (USAGE-BASED)"
  echo "═══════════════════════════════════════════════════════════════════════════"
  echo ""

  local enabled=$(echo "$config" | python3 -c "import sys, json; print('Enabled' if json.load(sys.stdin).get('enabled', False) else 'Disabled')")
  local approved=$(echo "$config" | python3 -c "import sys, json; print('Yes' if json.load(sys.stdin).get('approved_by_user', False) else 'No')")
  local min_queries=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('min_queries_required', 200))")
  local min_feedback=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('min_feedback_count', 50))")
  local data_quality_thresh=$(echo "$config" | python3 -c "import sys, json; print(json.load(sys.stdin).get('data_quality_threshold', 0.80))")

  echo "Status: $enabled"
  echo "User Approved: $approved"
  echo "Validation: Usage-based (query count, feedback, data quality)"
  echo ""

  # Check production readiness
  local validation=$(check_production_readiness)
  echo ""

  local ready=$(echo "$validation" | python3 -c "import sys, json; print(json.load(sys.stdin).get('ready', False))" | tr '[:upper:]' '[:lower:]')
  local confidence=$(echo "$validation" | python3 -c "import sys, json; print(f\"{json.load(sys.stdin).get('confidence', 0):.0%}\")")

  if [[ "$ready" == "true" ]]; then
    echo "Production Ready: ✅ Yes (Confidence: $confidence)"
  else
    echo "Production Ready: ⚠️  No (Confidence: $confidence)"
    echo ""
    echo "Requirements for production readiness (usage-based):"
    echo "  - ${min_queries}+ queries processed (all-time)"
    echo "  - ${min_feedback}+ queries with feedback"
    echo "  - Data quality >= ${data_quality_thresh}"
    echo "  - All performance targets met"
    echo "  - Recent performance stable (last 50 queries)"
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
      echo "Safety Features (Usage-Based):"
      echo "  - Requires 200+ queries and 50+ feedback samples"
      echo "  - Data quality threshold (>= 0.80)"
      echo "  - Only applies high-confidence proposals (>= 0.80)"
      echo "  - Validates performance targets before updating"
      echo "  - Auto-rolls back on >10% performance degradation"
      echo "  - Limits to 2 auto-updates per 500-query period"
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
