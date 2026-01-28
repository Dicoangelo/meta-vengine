#!/usr/bin/env python3
"""
CCC Autopilot - Fully Autonomous Operations

Combines all autonomous capabilities for hands-off operation:
1. Brain thinks → identifies issues/opportunities
2. Intelligence predicts → optimal actions
3. Self-heal fixes → reactive repairs
4. Feedback validates → learns from outcomes

Can run indefinitely, maintaining the entire CCC ecosystem.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
LOGS_DIR = CLAUDE_DIR / "logs"
AUTOPILOT_LOG = LOGS_DIR / "autopilot.log"


def log(msg: str, level: str = "INFO"):
    """Log to autopilot log."""
    ts = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    try:
        AUTOPILOT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(AUTOPILOT_LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass


def run_script(script: str, args: list = None) -> dict:
    """Run a CCC script and capture output."""
    cmd = ["python3", str(SCRIPTS_DIR / script)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def autopilot_cycle() -> dict:
    """Run one complete autopilot cycle."""
    cycle_start = datetime.now(LOCAL_TZ)
    results = {
        "timestamp": cycle_start.isoformat(),
        "brain": None,
        "intelligence": None,
        "health": None,
        "actions_taken": [],
    }
    
    # 1. Brain thinks
    log("Brain: analyzing patterns...")
    brain_result = run_script("ccc-autonomous-brain.py", ["--think", "--json"])
    if brain_result["success"]:
        try:
            results["brain"] = json.loads(brain_result["stdout"])
            if results["brain"].get("anomalies"):
                log(f"Brain: detected {len(results['brain']['anomalies'])} anomalies", "WARN")
                results["actions_taken"].append("anomaly_detection")
            if results["brain"].get("preventions"):
                log(f"Brain: applied {len(results['brain']['preventions'])} preventions")
                results["actions_taken"].append("proactive_prevention")
        except:
            pass
    
    # 2. Intelligence assessment
    log("Intelligence: assessing system state...")
    intel_result = run_script("ccc-intelligence-layer.py", ["--dashboard"])
    if intel_result["success"]:
        try:
            results["intelligence"] = json.loads(intel_result["stdout"])
            cost = results["intelligence"].get("cost_prediction", {})
            if cost.get("status") == "warning":
                log(f"Intelligence: cost warning - ${cost.get('predicted_total', 0):.2f} predicted", "WARN")
                results["actions_taken"].append("cost_warning")
        except:
            pass
    
    # 3. Health check & repair
    log("Self-heal: checking health...")
    health_result = run_script("ccc-self-heal.py", ["--fix", "--json"])
    if health_result["success"]:
        try:
            results["health"] = json.loads(health_result["stdout"])
            if results["health"].get("fixes_applied", 0) > 0:
                log(f"Self-heal: applied {results['health']['fixes_applied']} fixes")
                results["actions_taken"].append("auto_repair")
        except:
            pass
    
    # 4. Summary
    duration = (datetime.now(LOCAL_TZ) - cycle_start).total_seconds()
    log(f"Cycle complete in {duration:.1f}s: {len(results['actions_taken'])} actions")
    
    return results


def run_autopilot(cycles: int = None, interval: int = 300):
    """Run autopilot for N cycles or indefinitely."""
    log("=" * 60)
    log("CCC AUTOPILOT STARTING")
    log(f"Interval: {interval}s | Cycles: {'infinite' if cycles is None else cycles}")
    log("=" * 60)
    
    cycle_count = 0
    try:
        while cycles is None or cycle_count < cycles:
            cycle_count += 1
            log(f"--- Cycle {cycle_count} ---")
            
            results = autopilot_cycle()
            
            if cycles is None or cycle_count < cycles:
                log(f"Sleeping {interval}s until next cycle...")
                time.sleep(interval)
    
    except KeyboardInterrupt:
        log("Autopilot stopped by user")
    
    log(f"Autopilot completed: {cycle_count} cycles")


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == "--once":
            # Single cycle
            results = autopilot_cycle()
            print(json.dumps(results, indent=2))
        elif sys.argv[1] == "--daemon":
            # Run indefinitely
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            run_autopilot(cycles=None, interval=interval)
        elif sys.argv[1] == "--cycles":
            # Run N cycles
            n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            interval = int(sys.argv[3]) if len(sys.argv) > 3 else 60
            run_autopilot(cycles=n, interval=interval)
        else:
            print("Usage:")
            print("  ccc-autopilot.py --once           # Single cycle")
            print("  ccc-autopilot.py --cycles N [interval]  # N cycles")
            print("  ccc-autopilot.py --daemon [interval]    # Run forever")
    else:
        # Default: single cycle
        results = autopilot_cycle()
        print(f"\nActions taken: {results['actions_taken']}")


if __name__ == "__main__":
    main()
