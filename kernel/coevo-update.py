"""
US-211: Co-Evolution Feedback Loop

Auto-patches CLAUDE.md with live weight state after each BO cycle.
Called by the bo-monthly daemon as its final step. Pure stdlib Python.

Usage:
    python3 kernel/coevo-update.py           # Patch CLAUDE.md in place
    python3 kernel/coevo-update.py --dry-run # Print patch without writing
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CLAUDE_MD = BASE_DIR / "CLAUDE.md"
PARAMS_PATH = BASE_DIR / "config" / "learnable-params.json"
LRF_CLUSTERS_PATH = BASE_DIR / "data" / "lrf-clusters.json"
BO_REPORTS_DIR = BASE_DIR / "data" / "bo-reports"
SESSION_MULTIPLIERS_PATH = BASE_DIR / "config" / "session-reward-multipliers.json"
COEVO_LOG_PATH = BASE_DIR / "data" / "coevo-updates.jsonl"

MARKER_START = "<!-- COEVO-START -->"
MARKER_END = "<!-- COEVO-END -->"
SECTION_ANCHOR = "Learnable Weight System"


def load_json(path):
    """Load a JSON file, return None on any failure."""
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def load_params():
    """Load learnable-params.json and return (params_list, groups_dict)."""
    data = load_json(PARAMS_PATH)
    if not data:
        return [], {}
    return data.get("parameters", []), data.get("groups", {})


def load_lrf_clusters():
    """Load LRF cluster state. Returns dict or None."""
    return load_json(LRF_CLUSTERS_PATH)


def load_latest_bo_report():
    """Find the most recent BO report by filename and load it."""
    if not BO_REPORTS_DIR.is_dir():
        return None
    reports = sorted(BO_REPORTS_DIR.glob("*.json"))
    if not reports:
        return None
    return load_json(reports[-1])


def load_session_multipliers():
    """Load session-reward-multipliers.json."""
    return load_json(SESSION_MULTIPLIERS_PATH)


def _format_value(val):
    """Format a numeric value for the table."""
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        # Show up to 4 decimal places, strip trailing zeros
        return f"{val:.4f}".rstrip("0").rstrip(".")
    return str(val)


def build_weights_table(params, groups):
    """Build the markdown table of current weights by group."""
    lines = []
    lines.append("| Group | Param | Value | Range |")
    lines.append("|-------|-------|-------|-------|")

    # Group params by group name, preserving order
    grouped = {}
    for p in params:
        g = p.get("group", "ungrouped")
        grouped.setdefault(g, []).append(p)

    for group_name, members in grouped.items():
        # Pretty group label
        label = groups.get(group_name, {}).get("description", group_name)
        # Use the group key as the display name (shorter)
        display = group_name.replace("_", " ").title()
        for p in members:
            pid = p["id"]
            val = _format_value(p["value"])
            rng = f"[{_format_value(p['min'])}, {_format_value(p['max'])}]"
            lines.append(f"| {display} | {pid} | {val} | {rng} |")

    return "\n".join(lines)


def build_lrf_section(lrf_data):
    """Build the LRF cluster state section."""
    if not lrf_data:
        return (
            "#### LRF Cluster State\n"
            "- No LRF cluster data available yet."
        )
    lines = ["#### LRF Cluster State"]
    k = lrf_data.get("k", lrf_data.get("n_clusters", "?"))
    sil = lrf_data.get("silhouette_score", lrf_data.get("silhouette", "?"))
    decisions = lrf_data.get("per_cluster_decisions", lrf_data.get("decision_counts", []))
    lines.append(f"- **k:** {k} clusters")
    if sil != "?":
        lines.append(f"- **Silhouette score:** {_format_value(sil)}")
    else:
        lines.append(f"- **Silhouette score:** {sil}")
    if decisions:
        lines.append(f"- **Per-cluster decisions:** {decisions}")
    return "\n".join(lines)


def build_exploration_section(params):
    """Build the exploration schedule section from params."""
    lines = ["#### Exploration Schedule"]
    floor_param = None
    for p in params:
        if p["id"] == "explorationFloorGlobal":
            floor_param = p
            break
    if floor_param:
        lines.append(f"- **Global floor:** {_format_value(floor_param['value'])}")
    else:
        lines.append("- **Global floor:** not configured")
    # Per-cluster overrides would come from LRF clusters if available
    lines.append("- **Per-cluster overrides:** read from LRF cluster config at runtime")
    return "\n".join(lines)


def build_session_multipliers_section(multipliers_data):
    """Build session-type multipliers section."""
    lines = ["#### Session-Type Multipliers"]
    if not multipliers_data:
        lines.append("- No session-reward-multipliers.json found.")
        return "\n".join(lines)
    mults = multipliers_data.get("multipliers", {})
    default = multipliers_data.get("default", "?")
    lines.append(f"Active config from `config/session-reward-multipliers.json` (default: `{default}`)")
    lines.append("")
    lines.append("| Session Type | DQ | Cost | Behavioral | Boosts |")
    lines.append("|---|---|---|---|---|")
    for stype, vals in mults.items():
        dq = _format_value(vals.get("dq", "-"))
        cost = _format_value(vals.get("cost", "-"))
        beh = _format_value(vals.get("behavioral", "-"))
        boosts = []
        for k, v in vals.items():
            if k not in ("dq", "cost", "behavioral"):
                boosts.append(f"{k}={_format_value(v)}")
        boost_str = ", ".join(boosts) if boosts else "-"
        lines.append(f"| {stype} | {dq} | {cost} | {beh} | {boost_str} |")
    return "\n".join(lines)


def build_bo_section(bo_report):
    """Build the last BO result section."""
    lines = ["#### Last BO Result"]
    if not bo_report:
        lines.append("- No BO cycles completed yet.")
        return "\n".join(lines)

    date = bo_report.get("generated_at", bo_report.get("month", "?"))
    candidates = bo_report.get("candidates", [])
    validation = bo_report.get("validation", {})
    promoted = validation.get("promoted")
    improvement = validation.get("improvement", 0)
    reason = validation.get("reason", "")

    lines.append(f"- **Date:** {date}")
    lines.append(f"- **Candidates tested:** {len(candidates)}")
    if promoted:
        lines.append(f"- **Winner:** promoted config (improvement {improvement:+.1%})")
    else:
        lines.append(f"- **Winner:** baseline retained ({reason})")
    lines.append(f"- **Reward improvement:** {improvement:+.1%}")

    # Early stopping is not tracked yet; note it
    early = bo_report.get("early_stopped", None)
    if early is not None:
        lines.append(f"- **Early stopped:** {'Yes' if early else 'No'}")
    else:
        lines.append("- **Early stopped:** N/A")

    return "\n".join(lines)


def build_coevo_block(params, groups, lrf_data, bo_report, multipliers_data):
    """Assemble the full coevo content block (between markers)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [
        MARKER_START,
        "### Live Weight State (auto-updated by coevo-update.py)",
        "",
        f"**Last updated:** {now}",
        "",
        "#### Current Weights by Group",
        build_weights_table(params, groups),
        "",
        build_lrf_section(lrf_data),
        "",
        build_exploration_section(params),
        "",
        build_session_multipliers_section(multipliers_data),
        "",
        build_bo_section(bo_report),
        MARKER_END,
    ]
    return "\n".join(parts)


def patch_claude_md(content, new_block):
    """
    Replace content between COEVO markers, or insert after the
    Learnable Weight System section if markers are not found.

    Returns (new_content, changed: bool).
    """
    start_idx = content.find(MARKER_START)
    end_idx = content.find(MARKER_END)

    if start_idx != -1 and end_idx != -1:
        # Replace between markers (inclusive)
        end_idx += len(MARKER_END)
        new_content = content[:start_idx] + new_block + content[end_idx:]
        return new_content, True

    # First run: find the Learnable Weight System section and insert after it
    anchor_idx = content.find(SECTION_ANCHOR)
    if anchor_idx == -1:
        # Can't find anchor, append at end
        new_content = content.rstrip("\n") + "\n\n" + new_block + "\n"
        return new_content, True

    # Find the end of the paragraph/section after the anchor line
    # Look for the next blank line followed by ## (next section) or end of file
    search_from = anchor_idx
    lines = content[search_from:].split("\n")

    # Walk past the anchor line, then find the next ## heading or end
    insert_after = search_from
    found_anchor_line = False
    offset = 0
    for line in lines:
        offset += len(line) + 1  # +1 for newline
        if not found_anchor_line:
            if SECTION_ANCHOR in line:
                found_anchor_line = True
            continue
        # After anchor line, look for next ## heading
        stripped = line.strip()
        if stripped.startswith("## "):
            # Insert before this heading
            insert_pos = search_from + offset - len(line) - 1
            new_content = (
                content[:insert_pos].rstrip("\n")
                + "\n\n"
                + new_block
                + "\n\n"
                + content[insert_pos:].lstrip("\n")
            )
            return new_content, True

    # No next section found, insert before end of file
    new_content = content.rstrip("\n") + "\n\n" + new_block + "\n"
    return new_content, True


def log_update(params, bo_report):
    """Append an entry to data/coevo-updates.jsonl."""
    now = datetime.now(timezone.utc).isoformat() + "Z"
    values = {p["id"]: p["value"] for p in params}
    bo_date = None
    if bo_report:
        bo_date = bo_report.get("generated_at", bo_report.get("month"))
    entry = {
        "timestamp": now,
        "param_snapshot": values,
        "bo_result_date": bo_date,
    }
    try:
        COEVO_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(COEVO_LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"[coevo-update] Warning: could not write log: {e}", file=sys.stderr)


def main():
    dry_run = "--dry-run" in sys.argv

    # Load all data sources
    params, groups = load_params()
    if not params:
        print("[coevo-update] Warning: no params loaded from learnable-params.json", file=sys.stderr)

    lrf_data = load_lrf_clusters()
    bo_report = load_latest_bo_report()
    multipliers_data = load_session_multipliers()

    # Build the new block
    new_block = build_coevo_block(params, groups, lrf_data, bo_report, multipliers_data)

    if dry_run:
        print("=== DRY RUN: would insert the following block ===")
        print(new_block)
        print("=== END DRY RUN ===")
        return

    # Read CLAUDE.md
    if not CLAUDE_MD.exists():
        print(f"[coevo-update] Warning: {CLAUDE_MD} not found. Exiting.", file=sys.stderr)
        sys.exit(0)

    try:
        content = CLAUDE_MD.read_text()
    except OSError as e:
        print(f"[coevo-update] Warning: could not read {CLAUDE_MD}: {e}", file=sys.stderr)
        sys.exit(0)

    new_content, changed = patch_claude_md(content, new_block)

    if changed:
        try:
            CLAUDE_MD.write_text(new_content)
            print(f"[coevo-update] CLAUDE.md patched with {len(params)} params.")
        except OSError as e:
            print(f"[coevo-update] Warning: could not write {CLAUDE_MD}: {e}", file=sys.stderr)
            sys.exit(0)

        # Log the update
        log_update(params, bo_report)
    else:
        print("[coevo-update] No changes needed.")


if __name__ == "__main__":
    main()
