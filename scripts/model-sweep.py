#!/usr/bin/env python3
"""
Model Sweep — Multi-provider ecosystem-wide model ID health check and auto-heal.

Scans all repos under ~/projects/ for hardcoded model IDs across ALL providers
(Anthropic, OpenAI, Google, xAI), validates against the canonical registry
(config/pricing.json), and optionally auto-fixes stale references.

Live validation: fetches current models from provider APIs to detect registry drift.

Part of the Frontier Operations framework: Model Drift is a seam failure.

Usage:
    model-sweep                    # Scan and report
    model-sweep --fix              # Auto-fix stale model IDs (with confirmation)
    model-sweep --fix --yes        # Auto-fix without confirmation
    model-sweep --validate <id>    # Check if a specific model ID is current
    model-sweep --registry         # Show canonical registry
    model-sweep --live             # Validate registry against live provider APIs
    model-sweep --provider claude  # Filter by provider
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
CONFIG_DIR = SCRIPT_DIR.parent / "config"
PRICING_FILE = CONFIG_DIR / "pricing.json"
PROJECTS_DIR = Path.home() / "projects"
CLAUDE_DIR = Path.home() / ".claude"

# Directories to skip
SKIP_DIRS = {
    "node_modules", ".venv", "venv", ".git", "__pycache__", "dist",
    ".next", ".turbo", "build", "coverage", ".pytest_cache",
    "shell-snapshots", "session-summaries", "cache"
}

# File extensions to scan
SCAN_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".json", ".sh", ".yaml", ".yml",
    ".env", ".md", ".toml"
}

# Multi-provider patterns
MODEL_PATTERNS = [
    # Claude — all generations
    re.compile(r'claude-(opus|sonnet|haiku)-[\d][\w.-]*'),
    re.compile(r'claude-3\.?5?-?(opus|sonnet|haiku)-\d{8}'),
    re.compile(r'claude-3-(opus|sonnet|haiku)-\d{8}'),
    # OpenAI
    re.compile(r'gpt-4o(?:-mini)?(?:-\d{4}-\d{2}-\d{2})?'),
    re.compile(r'gpt-4-turbo(?:-preview)?(?:-\d{4}-\d{2}-\d{2})?'),
    re.compile(r'gpt-3\.5-turbo(?:-\d{4})?'),
    re.compile(r'o[13](?:-mini|-preview)?(?:-\d{4}-\d{2}-\d{2})?'),
    # Google Gemini
    re.compile(r'gemini-[\d]+\.[\d]+(?:-flash|-pro|-ultra)(?:-lite)?(?:-\d{3,})?'),
    re.compile(r'gemini-pro(?:-vision)?'),
    # xAI Grok
    re.compile(r'grok-[\d]+(?:-mini)?(?:-beta)?'),
]

# Files that ARE the registry (don't flag these)
REGISTRY_FILES = {"pricing.json", "model-sweep.py"}


def load_registry():
    """Load the canonical model registry with multi-provider support."""
    if not PRICING_FILE.exists():
        print(f"ERROR: Registry not found at {PRICING_FILE}")
        sys.exit(1)

    with open(PRICING_FILE) as f:
        config = json.load(f)

    # Build current IDs from all providers
    current_ids = set()
    providers = config.get("providers", {})
    for provider_data in providers.values():
        for model_data in provider_data.get("models", {}).values():
            current_ids.add(model_data["id"])

    # Also support legacy flat "models" key for backwards compat
    for model_data in config.get("models", {}).values():
        if isinstance(model_data, dict) and "id" in model_data:
            current_ids.add(model_data["id"])

    deprecated = config.get("deprecated", {})
    aliases = config.get("aliases", {})

    return {
        "current": current_ids,
        "deprecated": deprecated,
        "aliases": aliases,
        "providers": providers,
        "models": config.get("models", {}),
        "meta": config["_meta"],
        "raw": config,
    }


def detect_provider(model_id):
    """Detect which provider a model ID belongs to."""
    mid = model_id.lower()
    if mid.startswith("claude"):
        return "anthropic"
    elif mid.startswith(("gpt-", "o1", "o3")):
        return "openai"
    elif mid.startswith("gemini"):
        return "google"
    elif mid.startswith("grok"):
        return "xai"
    return "unknown"


def extract_model_ids(content):
    """Extract all model IDs from file content across all providers."""
    found = []
    for pattern in MODEL_PATTERNS:
        for match in pattern.finditer(content):
            found.append(match.group())
    return list(set(found))


def classify_model_id(model_id, registry):
    """Classify a model ID as current, deprecated, or unknown."""
    if model_id in registry["current"]:
        return "current", None

    if model_id in registry["deprecated"]:
        return "deprecated", registry["deprecated"][model_id]

    # Check if it's a short alias (e.g., "claude-opus-4" resolves to "claude-opus-4-6")
    for current_id in registry["current"]:
        if current_id.startswith(model_id):
            return "alias", f"Resolves to {current_id}"

    provider = detect_provider(model_id)
    return "unknown", f"Not in registry ({provider}) — verify manually"


def scan_file(filepath, registry, provider_filter=None):
    """Scan a single file for model IDs."""
    try:
        content = filepath.read_text(errors="ignore")
    except (PermissionError, OSError):
        return []

    model_ids = extract_model_ids(content)
    if not model_ids:
        return []

    results = []
    for line_num, line in enumerate(content.splitlines(), 1):
        for model_id in model_ids:
            if model_id in line:
                provider = detect_provider(model_id)
                if provider_filter and provider != provider_filter:
                    continue
                status, note = classify_model_id(model_id, registry)
                results.append({
                    "file": str(filepath),
                    "line": line_num,
                    "model_id": model_id,
                    "provider": provider,
                    "status": status,
                    "note": note,
                    "context": line.strip()[:120],
                })

    # Deduplicate by (file, model_id)
    seen = set()
    deduped = []
    for r in results:
        key = (r["file"], r["model_id"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped


def scan_directory(root, registry, provider_filter=None):
    """Recursively scan a directory for model IDs."""
    all_results = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for filename in filenames:
            if filename in REGISTRY_FILES:
                continue

            ext = Path(filename).suffix
            if ext not in SCAN_EXTENSIONS:
                continue

            filepath = Path(dirpath) / filename
            results = scan_file(filepath, registry, provider_filter)
            all_results.extend(results)

    return all_results


def get_fix_mapping(registry):
    """Build a mapping from deprecated IDs to their replacements."""
    mapping = {}
    for dep_id, note in registry["deprecated"].items():
        # Extract the replacement from the note (e.g., "Use claude-opus-4-6" or "Use gpt-4o")
        match = re.search(r'Use ([\w.-]+)', note)
        if match:
            mapping[dep_id] = match.group(1)
    return mapping


def apply_fixes(results, registry, auto_yes=False):
    """Auto-fix deprecated model IDs in files."""
    fix_mapping = get_fix_mapping(registry)
    fixable = [r for r in results if r["status"] == "deprecated" and r["model_id"] in fix_mapping]

    if not fixable:
        print("No auto-fixable issues found.")
        return 0

    by_file = {}
    for r in fixable:
        by_file.setdefault(r["file"], []).append(r)

    print(f"\n  Found {len(fixable)} fixable references across {len(by_file)} files:\n")
    for filepath, refs in by_file.items():
        rel = os.path.relpath(filepath, Path.home())
        print(f"  ~/{rel}:")
        for r in refs:
            replacement = fix_mapping[r["model_id"]]
            print(f"    L{r['line']}: {r['model_id']} → {replacement} [{r['provider']}]")

    if not auto_yes:
        answer = input("\n  Apply fixes? [y/N] ").strip().lower()
        if answer != "y":
            print("  Aborted.")
            return 0

    fixed_count = 0
    for filepath, refs in by_file.items():
        try:
            content = Path(filepath).read_text()
            for r in refs:
                old_id = r["model_id"]
                new_id = fix_mapping[old_id]
                content = content.replace(old_id, new_id)
                fixed_count += 1
            Path(filepath).write_text(content)
        except (PermissionError, OSError) as e:
            print(f"  ERROR: Could not fix {filepath}: {e}")

    print(f"\n  Fixed {fixed_count} references across {len(by_file)} files.")
    return fixed_count


def live_validate(registry):
    """Validate registry models against live provider APIs."""
    providers = registry.get("providers", {})
    results = {"valid": [], "invalid": [], "unreachable": []}

    print("\n  LIVE VALIDATION — checking provider APIs...\n")

    for provider_name, provider_config in providers.items():
        endpoint = provider_config.get("models_endpoint")
        api_base = provider_config.get("api_base", "")
        env_key = provider_config.get("env_key", "")
        api_key = os.environ.get(env_key, "")

        if provider_name == "anthropic":
            # Anthropic has no /models endpoint — test with a minimal dry-run
            _validate_anthropic(provider_config, api_key, results)
        elif endpoint and api_key:
            _validate_openapi_style(provider_name, provider_config, api_base, endpoint, api_key, results)
        elif endpoint and provider_name == "google":
            # Google uses API key as query param
            google_key = os.environ.get("GOOGLE_API_KEY", "")
            if google_key:
                _validate_google(provider_config, api_base, endpoint, google_key, results)
            else:
                for model_data in provider_config.get("models", {}).values():
                    results["unreachable"].append({
                        "model_id": model_data["id"],
                        "provider": provider_name,
                        "reason": f"No {env_key} set"
                    })
        else:
            for model_data in provider_config.get("models", {}).values():
                results["unreachable"].append({
                    "model_id": model_data["id"],
                    "provider": provider_name,
                    "reason": f"No {env_key} set"
                })

    # Print results
    if results["valid"]:
        print(f"  VALID ({len(results['valid'])}):")
        for r in results["valid"]:
            print(f"    ✓ {r['model_id']:40} [{r['provider']}]")

    if results["invalid"]:
        print(f"\n  INVALID ({len(results['invalid'])}):")
        for r in results["invalid"]:
            print(f"    ✗ {r['model_id']:40} [{r['provider']}] — {r['reason']}")

    if results["unreachable"]:
        print(f"\n  UNREACHABLE ({len(results['unreachable'])}):")
        for r in results["unreachable"]:
            print(f"    ? {r['model_id']:40} [{r['provider']}] — {r['reason']}")

    # Check for NEW models from providers not in our registry
    if results.get("new_models"):
        print(f"\n  NEW MODELS AVAILABLE ({len(results['new_models'])}):")
        for r in results["new_models"]:
            print(f"    + {r['model_id']:40} [{r['provider']}]")

    return len(results["invalid"])


def _validate_anthropic(provider_config, api_key, results):
    """Validate Anthropic models by attempting a minimal API call."""
    if not api_key:
        for model_data in provider_config.get("models", {}).values():
            results["unreachable"].append({
                "model_id": model_data["id"],
                "provider": "anthropic",
                "reason": "No ANTHROPIC_API_KEY set"
            })
        return

    for model_data in provider_config.get("models", {}).values():
        model_id = model_data["id"]
        try:
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({
                    "model": model_id,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "hi"}]
                }).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                method="POST"
            )
            resp = urllib.request.urlopen(req, timeout=10)
            # If we get a 200, model exists (we just used 1 token)
            results["valid"].append({"model_id": model_id, "provider": "anthropic"})
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="ignore")
            if e.code == 404 or "not_found" in body:
                results["invalid"].append({
                    "model_id": model_id,
                    "provider": "anthropic",
                    "reason": f"404 — model does not exist"
                })
            elif e.code == 401:
                results["unreachable"].append({
                    "model_id": model_id,
                    "provider": "anthropic",
                    "reason": "Invalid API key"
                })
            elif e.code == 429:
                # Rate limited but model exists
                results["valid"].append({"model_id": model_id, "provider": "anthropic"})
            elif e.code == 400:
                # Bad request but model was found (could be billing issue)
                if "not_found" in body:
                    results["invalid"].append({
                        "model_id": model_id,
                        "provider": "anthropic",
                        "reason": "Model not found"
                    })
                else:
                    results["valid"].append({"model_id": model_id, "provider": "anthropic"})
            else:
                results["unreachable"].append({
                    "model_id": model_id,
                    "provider": "anthropic",
                    "reason": f"HTTP {e.code}"
                })
        except Exception as e:
            results["unreachable"].append({
                "model_id": model_id,
                "provider": "anthropic",
                "reason": str(e)[:60]
            })


def _validate_openapi_style(provider_name, provider_config, api_base, endpoint, api_key, results):
    """Validate models against OpenAI-compatible /models endpoint."""
    try:
        url = f"{api_base}{endpoint}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        # Extract available model IDs from the API response
        available = set()
        for model in data.get("data", []):
            available.add(model.get("id", ""))

        # Store for new model detection
        registry_ids = set()
        for model_data in provider_config.get("models", {}).values():
            registry_ids.add(model_data["id"])

        for model_data in provider_config.get("models", {}).values():
            model_id = model_data["id"]
            if model_id in available:
                results["valid"].append({"model_id": model_id, "provider": provider_name})
            else:
                # Check prefix matches (API often returns versioned IDs)
                found = any(a.startswith(model_id) or model_id.startswith(a) for a in available)
                if found:
                    results["valid"].append({"model_id": model_id, "provider": provider_name})
                else:
                    results["invalid"].append({
                        "model_id": model_id,
                        "provider": provider_name,
                        "reason": "Not found in /models response"
                    })

        # Detect new models from the provider not in our registry
        new_models = []
        for avail_id in sorted(available):
            if avail_id not in registry_ids:
                # Only flag notable models (skip fine-tuned, deprecated, etc.)
                if any(avail_id.startswith(p) for p in ["gpt-4", "gpt-5", "o1", "o3", "grok-"]):
                    new_models.append({"model_id": avail_id, "provider": provider_name})
        if new_models:
            results.setdefault("new_models", []).extend(new_models)

    except Exception as e:
        for model_data in provider_config.get("models", {}).values():
            results["unreachable"].append({
                "model_id": model_data["id"],
                "provider": provider_name,
                "reason": str(e)[:60]
            })


def _validate_google(provider_config, api_base, endpoint, api_key, results):
    """Validate Google models via their models endpoint."""
    try:
        url = f"{api_base}{endpoint}?key={api_key}"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())

        available = set()
        for model in data.get("models", []):
            # Google returns "models/gemini-2.0-flash" format
            name = model.get("name", "")
            model_id = name.replace("models/", "")
            available.add(model_id)

        for model_data in provider_config.get("models", {}).values():
            model_id = model_data["id"]
            if model_id in available:
                results["valid"].append({"model_id": model_id, "provider": "google"})
            else:
                found = any(a.startswith(model_id) or model_id.startswith(a) for a in available)
                if found:
                    results["valid"].append({"model_id": model_id, "provider": "google"})
                else:
                    results["invalid"].append({
                        "model_id": model_id,
                        "provider": "google",
                        "reason": "Not found in /models response"
                    })

    except Exception as e:
        for model_data in provider_config.get("models", {}).values():
            results["unreachable"].append({
                "model_id": model_data["id"],
                "provider": "google",
                "reason": str(e)[:60]
            })


def print_report(results, registry):
    """Print a formatted report of scan results."""
    deprecated = [r for r in results if r["status"] == "deprecated"]
    unknown = [r for r in results if r["status"] == "unknown"]
    current = [r for r in results if r["status"] in ("current", "alias")]

    # Group by provider
    by_provider = {}
    for r in results:
        p = r.get("provider", "unknown")
        by_provider.setdefault(p, {"current": 0, "deprecated": 0, "unknown": 0})
        by_provider[p][r["status"] if r["status"] in ("current", "deprecated", "unknown") else "current"] += 1

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  MODEL SWEEP — Multi-Provider Ecosystem Health Check         ║
║  Registry: v{registry['meta']['version']}  Updated: {registry['meta']['updated']}              ║
╠══════════════════════════════════════════════════════════════╣
║  Current models:                                             ║""")

    providers = registry.get("providers", {})
    for prov_name, prov_data in providers.items():
        print(f"║  {prov_name:10}                                              ║")
        for model_data in prov_data.get("models", {}).values():
            print(f"║    {model_data['display']:12} → {model_data['id']:34} ║")

    print(f"""╠══════════════════════════════════════════════════════════════╣
║  Scan Results:                                               ║
║    Current:    {len(current):4} references ✓                           ║
║    Deprecated: {len(deprecated):4} references ✗                           ║
║    Unknown:    {len(unknown):4} references ?                           ║
║                                                              ║""")

    for prov, counts in sorted(by_provider.items()):
        total = sum(counts.values())
        dep = counts.get("deprecated", 0)
        unk = counts.get("unknown", 0)
        status = "✓" if dep == 0 and unk == 0 else "✗"
        print(f"║    {prov:10} {total:3} refs ({dep} deprecated, {unk} unknown) {status}   ║")

    print(f"╚══════════════════════════════════════════════════════════════╝")

    if deprecated:
        print("\n  DEPRECATED (auto-fixable):")
        for r in deprecated:
            rel = os.path.relpath(r["file"], Path.home())
            print(f"    ~/{rel}:{r['line']}")
            print(f"      [{r['provider']}] {r['model_id']} → {r['note']}")

    if unknown:
        print("\n  UNKNOWN (verify manually):")
        for r in unknown:
            rel = os.path.relpath(r["file"], Path.home())
            print(f"    ~/{rel}:{r['line']}")
            print(f"      [{r['provider']}] {r['model_id']}")

    if not deprecated and not unknown:
        print("\n  All model IDs are current across all providers. No action needed.")

    return len(deprecated) + len(unknown)


def validate_single(model_id, registry):
    """Validate a single model ID."""
    status, note = classify_model_id(model_id, registry)
    provider = detect_provider(model_id)
    if status == "current":
        print(f"  ✓ {model_id} [{provider}] — current")
    elif status == "deprecated":
        print(f"  ✗ {model_id} [{provider}] — DEPRECATED: {note}")
    elif status == "alias":
        print(f"  ~ {model_id} [{provider}] — {note}")
    else:
        print(f"  ? {model_id} [{provider}] — {note}")
    return 0 if status == "current" else 1


def show_registry(registry):
    """Show the canonical multi-provider registry."""
    print(f"\n  Canonical Model Registry (v{registry['meta']['version']})")
    print(f"  Updated: {registry['meta']['updated']}\n")

    providers = registry.get("providers", {})
    for prov_name, prov_data in providers.items():
        print(f"  {prov_name.upper()}")
        for model_data in prov_data.get("models", {}).values():
            print(f"    {model_data['id']:40} {model_data['display']}")
        print()

    print("  DEPRECATED:")
    for dep_id, note in sorted(registry.get("deprecated", {}).items()):
        print(f"    {dep_id:40} → {note}")


# Provider filter name normalization
PROVIDER_ALIASES = {
    "claude": "anthropic", "anthropic": "anthropic",
    "openai": "openai", "gpt": "openai", "chatgpt": "openai",
    "google": "google", "gemini": "google",
    "xai": "xai", "grok": "xai",
}


def main():
    parser = argparse.ArgumentParser(description="Model Sweep — multi-provider model ID health check")
    parser.add_argument("--fix", action="store_true", help="Auto-fix deprecated model IDs")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation for --fix")
    parser.add_argument("--validate", metavar="MODEL_ID", help="Validate a single model ID")
    parser.add_argument("--registry", action="store_true", help="Show canonical registry")
    parser.add_argument("--live", action="store_true", help="Validate registry against live provider APIs")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--path", metavar="DIR", help="Scan a specific directory instead of ~/projects/")
    parser.add_argument("--provider", metavar="NAME", help="Filter by provider (claude/openai/gemini/grok)")
    args = parser.parse_args()

    registry = load_registry()

    provider_filter = None
    if args.provider:
        provider_filter = PROVIDER_ALIASES.get(args.provider.lower())
        if not provider_filter:
            print(f"Unknown provider: {args.provider}. Use: claude, openai, gemini, grok")
            return 1

    if args.registry:
        show_registry(registry)
        return 0

    if args.validate:
        return validate_single(args.validate, registry)

    if args.live:
        return live_validate(registry)

    # Scan
    scan_roots = []
    if args.path:
        scan_roots.append(Path(args.path))
    else:
        scan_roots.append(PROJECTS_DIR)
        for subdir in ["config", "kernel", "scripts", "agents", "commands", "hooks"]:
            p = CLAUDE_DIR / subdir
            if p.exists():
                scan_roots.append(p)

    all_results = []
    for root in scan_roots:
        if root.exists():
            all_results.extend(scan_directory(root, registry, provider_filter))

    if args.json:
        print(json.dumps(all_results, indent=2))
        return 0

    issues = print_report(all_results, registry)

    if args.fix and issues > 0:
        apply_fixes(all_results, registry, auto_yes=args.yes)

    return 1 if issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
