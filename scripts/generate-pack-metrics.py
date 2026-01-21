#!/usr/bin/env python3
"""
GENERATE PACK METRICS
Reads from ~/.agent-core/context-packs/ and generates pack-metrics.json
for the Command Center dashboard.
"""

import json
from datetime import datetime
from pathlib import Path

CONTEXT_PACKS_DIR = Path.home() / ".agent-core/context-packs"
OUTPUT_FILE = Path.home() / ".claude/data/pack-metrics.json"

def main():
    # Initialize output structure
    output = {
        "status": "not_configured",
        "generated": datetime.now().isoformat(),
        "global": {
            "total_sessions": 0,
            "total_token_savings": 0,
            "total_cost_savings": 0,
            "avg_reduction_rate": 0,
            "cache_hit_rate": 0
        },
        "top_packs": [],
        "daily_trend": [],
        "pack_inventory": []
    }

    # Check if context packs directory exists
    if not CONTEXT_PACKS_DIR.exists():
        print(f"Context packs directory not found: {CONTEXT_PACKS_DIR}")
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        return

    # Load registry.json
    registry_file = CONTEXT_PACKS_DIR / "registry.json"
    if registry_file.exists():
        try:
            registry = json.loads(registry_file.read_text())
            output["status"] = "active"

            # Build pack inventory from registry
            packs = registry.get("packs", {})
            for pack_name, pack_info in packs.items():
                output["pack_inventory"].append({
                    "name": pack_name,
                    "type": pack_info.get("type", "unknown"),
                    "tokens": pack_info.get("size_tokens", 0),
                    "version": pack_info.get("version", "1.0.0"),
                    "created": pack_info.get("created", ""),
                    "file": pack_info.get("file", "")
                })

            # Get totals from metadata
            metadata = registry.get("metadata", {})
            output["global"]["total_packs"] = metadata.get("total_packs", len(packs))
            output["global"]["total_tokens"] = metadata.get("total_size_tokens", 0)

            print(f"Loaded {len(packs)} packs from registry ({metadata.get('total_size_tokens', 0)} tokens)")
        except Exception as e:
            print(f"Error loading registry: {e}")

    # Load metrics.json for usage stats
    metrics_file = CONTEXT_PACKS_DIR / "metrics.json"
    if metrics_file.exists():
        try:
            metrics = json.loads(metrics_file.read_text())

            # Global stats
            global_stats = metrics.get("global_stats", {})
            output["global"]["total_sessions"] = global_stats.get("total_sessions", 0)
            output["global"]["total_token_savings"] = global_stats.get("total_token_savings", 0)
            output["global"]["total_cost_savings"] = global_stats.get("total_cost_savings", 0)
            output["global"]["avg_reduction_rate"] = global_stats.get("avg_reduction_rate", 0)
            output["global"]["cache_hit_rate"] = global_stats.get("cache_hit_rate", 0)

            # Top packs by usage
            pack_stats = metrics.get("pack_stats", {})
            top_packs = []
            for pack_name, stats in pack_stats.items():
                top_packs.append({
                    "name": pack_name,
                    "times_selected": stats.get("times_selected", 0),
                    "total_tokens_loaded": stats.get("total_tokens_loaded", 0),
                    "avg_dq_score": stats.get("avg_dq_score", 0),
                    "avg_consensus_score": stats.get("avg_consensus_score", 0),
                    "combined_with": list(stats.get("combined_with", {}).keys())
                })

            # Sort by times_selected
            top_packs.sort(key=lambda x: x["times_selected"], reverse=True)
            output["top_packs"] = top_packs[:10]  # Top 10

            # Daily trend
            daily_stats = metrics.get("daily_stats", {})
            daily_trend = []
            for date, stats in sorted(daily_stats.items()):
                daily_trend.append({
                    "date": date,
                    "sessions": stats.get("sessions", 0),
                    "token_savings": stats.get("token_savings", 0),
                    "cost_savings": stats.get("cost_savings", 0)
                })
            output["daily_trend"] = daily_trend[-30:]  # Last 30 days

            # Session history summary
            session_history = metrics.get("session_history", [])
            output["global"]["recent_sessions"] = len(session_history)

            print(f"Loaded metrics: {global_stats.get('total_sessions', 0)} sessions, ${global_stats.get('total_cost_savings', 0):.2f} saved")
        except Exception as e:
            print(f"Error loading metrics: {e}")

    # Enrich pack inventory with usage stats
    pack_stats = {}
    if metrics_file.exists():
        try:
            metrics = json.loads(metrics_file.read_text())
            pack_stats = metrics.get("pack_stats", {})
        except:
            pass

    for pack in output["pack_inventory"]:
        pack_name = pack["name"]
        if pack_name in pack_stats:
            stats = pack_stats[pack_name]
            pack["times_used"] = stats.get("times_selected", 0)
            pack["last_used"] = stats.get("sessions", [""])[0] if stats.get("sessions") else ""
            pack["avg_dq_score"] = stats.get("avg_dq_score", 0)
        else:
            pack["times_used"] = 0
            pack["last_used"] = ""
            pack["avg_dq_score"] = 0

    # Preserve existing daily_trend and global totals from fix-all-dashboard-data.py
    if OUTPUT_FILE.exists():
        try:
            existing = json.loads(OUTPUT_FILE.read_text())
            existing_trend = existing.get("daily_trend", [])
            # Keep existing daily_trend if it has more data than what we generated
            if len(existing_trend) > len(output.get("daily_trend", [])):
                output["daily_trend"] = existing_trend
            # Preserve global totals if they're higher (from fix-all-dashboard-data.py)
            existing_global = existing.get("global", {})
            if existing_global.get("total_cost_savings", 0) > output["global"].get("total_cost_savings", 0):
                output["global"]["total_cost_savings"] = existing_global["total_cost_savings"]
            if existing_global.get("total_sessions", 0) > output["global"].get("total_sessions", 0):
                output["global"]["total_sessions"] = existing_global["total_sessions"]
        except:
            pass

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"Wrote pack metrics to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
