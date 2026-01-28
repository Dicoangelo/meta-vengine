#!/usr/bin/env python3
"""
Capability Status - Unified health check for all new Claude capabilities.

Checks:
- Cognitive OS (accuracy, weights export)
- Expertise Routing (state freshness, domain coverage)
- Pattern Orchestrator (pattern detection)
- Predictive Recovery (prevention stats)
- Learning Hub (last sync, insights)
- Flow Shield (flow state)
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Paths
CLAUDE_DIR = Path.home() / ".claude"
KERNEL_DIR = CLAUDE_DIR / "kernel"
DATA_DIR = CLAUDE_DIR / "data"
COS_DIR = KERNEL_DIR / "cognitive-os"

# Files to check
FILES = {
    "cognitive_weights": COS_DIR / "cognitive-dq-weights.json",
    "learned_weights": COS_DIR / "learned-weights.json",
    "flow_state": COS_DIR / "flow-state.json",
    "expertise_state": KERNEL_DIR / "expertise-routing-state.json",
    "learning_hub": KERNEL_DIR / "learning-hub.json",
    "detected_patterns": KERNEL_DIR / "detected-patterns.json",
    "predictive_state": KERNEL_DIR / "predictive-state.json",
    "dq_scores": KERNEL_DIR / "dq-scores.jsonl",
    "recovery_outcomes": DATA_DIR / "recovery-outcomes.jsonl",
}


def load_json(path: Path) -> Dict:
    """Load JSON file safely."""
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            return {"error": "parse_failed"}
    return {"error": "not_found"}


def check_file_freshness(path: Path, max_age_minutes: int = 60) -> Dict:
    """Check if file exists and is fresh."""
    if not path.exists():
        return {"exists": False, "fresh": False, "age": None}

    try:
        data = json.loads(path.read_text())
        ts = data.get("timestamp") or data.get("last_sync") or data.get("lastUpdated")
        if ts:
            age = datetime.now() - datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+00:00", ""))
            age_minutes = age.total_seconds() / 60
            return {
                "exists": True,
                "fresh": age_minutes < max_age_minutes,
                "age_minutes": round(age_minutes, 1)
            }
    except:
        pass

    return {"exists": True, "fresh": None, "age": None}


def check_cognitive_os() -> Dict:
    """Check Cognitive OS health."""
    status = {"name": "Cognitive OS", "components": {}}

    # Check learned weights
    learned = load_json(FILES["learned_weights"])
    if "error" not in learned:
        accuracy_history = learned.get("accuracy_history", [])
        recent = accuracy_history[-20:] if accuracy_history else []
        correct = sum(1 for a in recent if a.get("correct", False))
        accuracy = correct / len(recent) if recent else 0
        status["components"]["accuracy"] = {
            "value": f"{accuracy:.0%}",
            "predictions": len(accuracy_history),
            "healthy": accuracy > 0.5 or len(accuracy_history) < 10  # Allow warmup
        }
    else:
        status["components"]["accuracy"] = {"error": learned.get("error")}

    # Check DQ weights export
    weights_status = check_file_freshness(FILES["cognitive_weights"], max_age_minutes=60)
    status["components"]["dq_weights_export"] = {
        "fresh": weights_status.get("fresh"),
        "age_minutes": weights_status.get("age_minutes"),
        "healthy": weights_status.get("fresh", False)
    }

    # Check flow state
    flow = load_json(FILES["flow_state"])
    if "error" not in flow:
        status["components"]["flow_state"] = {
            "in_flow": flow.get("in_flow", False),
            "score": flow.get("flow_score", 0),
            "healthy": True
        }
    else:
        status["components"]["flow_state"] = {"healthy": True, "note": "No active flow"}

    status["healthy"] = all(c.get("healthy", True) for c in status["components"].values())
    return status


def check_expertise_routing() -> Dict:
    """Check Expertise Routing health."""
    status = {"name": "Expertise Routing", "components": {}}

    state_status = check_file_freshness(FILES["expertise_state"], max_age_minutes=120)

    if state_status["exists"]:
        state = load_json(FILES["expertise_state"])
        high_domains = state.get("high_expertise_domains", [])
        low_domains = state.get("low_expertise_domains", [])

        status["components"]["state"] = {
            "fresh": state_status.get("fresh"),
            "age_minutes": state_status.get("age_minutes"),
            "high_expertise_count": len(high_domains),
            "low_expertise_count": len(low_domains),
            "healthy": state_status.get("fresh", False)
        }

        # Check expertise coverage
        status["components"]["coverage"] = {
            "domains_tracked": len(high_domains) + len(low_domains),
            "top_domains": high_domains[:3],
            "healthy": len(high_domains) > 0
        }
    else:
        status["components"]["state"] = {"exists": False, "healthy": False}

    status["healthy"] = all(c.get("healthy", True) for c in status["components"].values())
    return status


def check_pattern_orchestrator() -> Dict:
    """Check Pattern Orchestrator health."""
    status = {"name": "Pattern Orchestrator", "components": {}}

    patterns = load_json(FILES["detected_patterns"])
    if "error" not in patterns:
        status["components"]["detection"] = {
            "current_pattern": patterns.get("current_session_type", "unknown"),
            "confidence": patterns.get("session_type_confidence", 0),
            "healthy": True
        }
    else:
        status["components"]["detection"] = {"note": "No patterns detected yet", "healthy": True}

    # Check orchestration log
    log_path = DATA_DIR / "pattern-orchestrate.jsonl"
    if log_path.exists():
        lines = log_path.read_text().strip().split('\n')
        status["components"]["orchestrations"] = {
            "total": len(lines),
            "healthy": True
        }
    else:
        status["components"]["orchestrations"] = {"total": 0, "healthy": True}

    status["healthy"] = True
    return status


def check_predictive_recovery() -> Dict:
    """Check Predictive Recovery health."""
    status = {"name": "Predictive Recovery", "components": {}}

    state = load_json(FILES["predictive_state"])
    if "error" not in state:
        status["components"]["state"] = {
            "predictions": len(state.get("predictions", [])),
            "prevented": state.get("prevented_count", 0),
            "healthy": True
        }
    else:
        status["components"]["state"] = {"note": "No predictions yet", "healthy": True}

    # Check recovery outcomes for patterns
    if FILES["recovery_outcomes"].exists():
        lines = FILES["recovery_outcomes"].read_text().strip().split('\n')
        recent = []
        cutoff = (datetime.now() - timedelta(days=7)).timestamp()
        for line in lines:
            try:
                o = json.loads(line)
                if o.get("ts", 0) > cutoff:
                    recent.append(o)
            except:
                pass

        if recent:
            success = sum(1 for o in recent if o.get("success", False))
            status["components"]["recovery_rate"] = {
                "total": len(recent),
                "success_rate": f"{success/len(recent):.0%}" if recent else "N/A",
                "healthy": success/len(recent) > 0.7 if recent else True
            }

    status["healthy"] = all(c.get("healthy", True) for c in status["components"].values())
    return status


def check_learning_hub() -> Dict:
    """Check Learning Hub health."""
    status = {"name": "Learning Hub", "components": {}}

    hub = load_json(FILES["learning_hub"])
    if "error" not in hub:
        last_sync = hub.get("last_sync")
        if last_sync:
            age = datetime.now() - datetime.fromisoformat(last_sync)
            age_hours = age.total_seconds() / 3600
            status["components"]["sync"] = {
                "last_sync": last_sync[:16],
                "age_hours": round(age_hours, 1),
                "healthy": age_hours < 24  # Should sync at least daily
            }
        else:
            status["components"]["sync"] = {"note": "Never synced", "healthy": False}

        insights = hub.get("cross_domain_insights", [])
        suggestions = hub.get("improvement_suggestions", [])
        status["components"]["insights"] = {
            "count": len(insights),
            "suggestions": len(suggestions),
            "healthy": True
        }

        summaries = hub.get("weekly_summaries", [])
        if summaries:
            latest = summaries[-1]
            status["components"]["metrics"] = {
                "routing_dq": latest.get("key_metrics", {}).get("routing_dq", 0),
                "recovery_success": latest.get("key_metrics", {}).get("recovery_success", 0),
                "healthy": True
            }
    else:
        status["components"]["sync"] = {"error": hub.get("error"), "healthy": False}

    status["healthy"] = all(c.get("healthy", True) for c in status["components"].values())
    return status


def check_integrations() -> Dict:
    """Check system integrations."""
    status = {"name": "Integrations", "components": {}}

    # Check if hooks are registered
    settings_path = CLAUDE_DIR / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {})

        session_start = hooks.get("SessionStart", [{}])[0].get("hooks", [])
        session_end = hooks.get("SessionEnd", [{}])[0].get("hooks", [])

        hook_commands = [h.get("command", "") for h in session_start + session_end]

        status["components"]["hooks"] = {
            "intelligence_advisor": any("intelligence-advisor" in c for c in hook_commands),
            "predictive_recovery": any("predictive-recovery" in c for c in hook_commands),
            "expertise_export": any("expertise-router" in c for c in hook_commands),
            "auto_archive": any("auto-archive" in c for c in hook_commands),
            "healthy": True
        }

    # Check LaunchAgent
    launch_agent = Path.home() / "Library/LaunchAgents/com.claude.autonomous-maintenance.plist"
    if launch_agent.exists():
        content = launch_agent.read_text()
        status["components"]["launch_agent"] = {
            "learning_hub_sync": "learning-hub-sync" in content,
            "expertise_export": "expertise-router" in content,
            "healthy": True
        }

    status["healthy"] = True
    return status


def run_health_check() -> Dict:
    """Run full health check."""
    checks = [
        check_cognitive_os(),
        check_expertise_routing(),
        check_pattern_orchestrator(),
        check_predictive_recovery(),
        check_learning_hub(),
        check_integrations(),
    ]

    all_healthy = all(c["healthy"] for c in checks)

    return {
        "timestamp": datetime.now().isoformat(),
        "overall_healthy": all_healthy,
        "systems": checks
    }


def print_status(result: Dict):
    """Print formatted status."""
    print()
    print("=" * 60)
    print("  Claude Capability Status Dashboard")
    print("=" * 60)
    print()

    overall = "HEALTHY" if result["overall_healthy"] else "ISSUES DETECTED"
    icon = "✅" if result["overall_healthy"] else "⚠️"
    print(f"  Overall Status: {icon} {overall}")
    print()

    for system in result["systems"]:
        status_icon = "✅" if system["healthy"] else "❌"
        print(f"  {status_icon} {system['name']}")

        for comp_name, comp_data in system.get("components", {}).items():
            if isinstance(comp_data, dict):
                healthy = comp_data.get("healthy", True)
                comp_icon = "  ✓" if healthy else "  ✗"

                # Format the key metrics
                details = []
                for k, v in comp_data.items():
                    if k not in ["healthy", "error", "note"]:
                        if isinstance(v, bool):
                            details.append(f"{k}={'yes' if v else 'no'}")
                        elif isinstance(v, list):
                            details.append(f"{k}={len(v)}")
                        else:
                            details.append(f"{k}={v}")

                if comp_data.get("note"):
                    details.append(f"({comp_data['note']})")
                if comp_data.get("error"):
                    details.append(f"ERROR: {comp_data['error']}")

                detail_str = ", ".join(details[:4])  # Limit details
                print(f"    {comp_icon} {comp_name}: {detail_str}")
        print()

    print("=" * 60)
    print(f"  Last checked: {result['timestamp'][:19]}")
    print("=" * 60)
    print()


def run_doctor() -> Dict:
    """Run doctor mode with recommendations and auto-fixes."""
    import subprocess

    result = run_health_check()
    recommendations = []
    fixes_applied = []

    for system in result["systems"]:
        for comp_name, comp_data in system.get("components", {}).items():
            if isinstance(comp_data, dict) and not comp_data.get("healthy", True):
                # Generate recommendation
                rec = {
                    "system": system["name"],
                    "component": comp_name,
                    "issue": comp_data.get("error") or comp_data.get("note") or "unhealthy"
                }

                # Attempt auto-fix for known issues
                if system["name"] == "Expertise Routing" and not comp_data.get("fresh"):
                    rec["fix"] = "python3 ~/.claude/kernel/expertise-router.py export"
                    rec["auto_fixable"] = True
                elif system["name"] == "Learning Hub" and comp_data.get("note") == "Never synced":
                    rec["fix"] = "python3 ~/.claude/scripts/learning-hub-sync.py sync"
                    rec["auto_fixable"] = True
                elif system["name"] == "Cognitive OS" and "dq_weights" in comp_name:
                    rec["fix"] = "python3 ~/.claude/kernel/cognitive-os.py start"
                    rec["auto_fixable"] = True

                recommendations.append(rec)

    return {
        "timestamp": datetime.now().isoformat(),
        "overall_healthy": result["overall_healthy"],
        "recommendations": recommendations,
        "fixes_applied": fixes_applied
    }


def print_doctor(result: Dict, auto_fix: bool = False):
    """Print doctor results."""
    import subprocess

    print()
    print("=" * 60)
    print("  Claude Capability Doctor")
    print("=" * 60)
    print()

    if result["overall_healthy"] and not result["recommendations"]:
        print("  All systems healthy! No issues found.")
        print()
        return

    print(f"  Found {len(result['recommendations'])} issue(s):")
    print()

    for rec in result["recommendations"]:
        print(f"  [{rec['system']}] {rec['component']}")
        print(f"    Issue: {rec['issue']}")
        if rec.get("fix"):
            print(f"    Fix: {rec['fix']}")
            if auto_fix and rec.get("auto_fixable"):
                print(f"    Applying fix...")
                try:
                    subprocess.run(rec["fix"], shell=True, capture_output=True, timeout=30)
                    print(f"    ✓ Fix applied")
                except Exception as e:
                    print(f"    ✗ Fix failed: {e}")
        print()

    if not auto_fix and any(r.get("auto_fixable") for r in result["recommendations"]):
        print("  Run with --fix to auto-apply fixes")
        print()

    print("=" * 60)
    print()


# CLI Interface
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "status":
        result = run_health_check()
        print_status(result)
    elif args[0] == "json":
        result = run_health_check()
        print(json.dumps(result, indent=2))
    elif args[0] == "doctor":
        auto_fix = "--fix" in args
        result = run_doctor()
        print_doctor(result, auto_fix=auto_fix)
    elif args[0] == "check":
        system = args[1] if len(args) > 1 else None
        if system == "cognitive":
            print(json.dumps(check_cognitive_os(), indent=2))
        elif system == "expertise":
            print(json.dumps(check_expertise_routing(), indent=2))
        elif system == "patterns":
            print(json.dumps(check_pattern_orchestrator(), indent=2))
        elif system == "predictive":
            print(json.dumps(check_predictive_recovery(), indent=2))
        elif system == "hub":
            print(json.dumps(check_learning_hub(), indent=2))
        elif system == "integrations":
            print(json.dumps(check_integrations(), indent=2))
        else:
            print("Usage: capability-status.py check [cognitive|expertise|patterns|predictive|hub|integrations]")
    else:
        print("Capability Status Dashboard")
        print()
        print("Commands:")
        print("  status              - Show full status dashboard")
        print("  doctor [--fix]      - Diagnose issues and optionally auto-fix")
        print("  json                - Output status as JSON")
        print("  check <system>      - Check specific system")
        print()
        print("Systems: cognitive, expertise, patterns, predictive, hub, integrations")
