#!/usr/bin/env python3
"""
Centralized pricing configuration loader.
Import this module to get current Claude API pricing.

Usage:
    from pricing import PRICING, get_cost_per_message, get_model_cost
"""

import json
from pathlib import Path

PRICING_FILE = Path(__file__).parent / "pricing.json"

def load_pricing():
    """Load pricing from centralized config."""
    with open(PRICING_FILE) as f:
        return json.load(f)

# Load once at import time
_config = load_pricing()

# Expose commonly used values
PRICING = _config["models"]
# Filter out metadata keys from estimates
ESTIMATES = {k: v for k, v in _config["estimates"].items() if not k.startswith("_")}
SUBSCRIPTION = _config["subscription"]
VERSION = _config["_meta"]["version"]

def get_model_cost(model: str, input_tokens: int, output_tokens: int, cache_reads: int = 0) -> float:
    """Calculate cost for a model usage in dollars."""
    model_key = model.lower()
    if "opus" in model_key:
        model_key = "opus"
    elif "sonnet" in model_key:
        model_key = "sonnet"
    elif "haiku" in model_key:
        model_key = "haiku"

    if model_key not in PRICING:
        return 0.0

    p = PRICING[model_key]
    cost = (input_tokens / 1_000_000) * p["input"]
    cost += (output_tokens / 1_000_000) * p["output"]
    cost += (cache_reads / 1_000_000) * p["cache_read"]
    return cost

def get_cost_per_message(model: str) -> float:
    """Get estimated cost per message for a model."""
    model_key = model.lower()
    if "opus" in model_key:
        return ESTIMATES["opus"]
    elif "sonnet" in model_key:
        return ESTIMATES["sonnet"]
    elif "haiku" in model_key:
        return ESTIMATES["haiku"]
    return ESTIMATES["sonnet"]  # Default

def get_input_rate(model: str) -> float:
    """Get input token rate ($ per million) for a model."""
    model_key = "opus" if "opus" in model.lower() else "sonnet" if "sonnet" in model.lower() else "haiku"
    return PRICING.get(model_key, PRICING["sonnet"])["input"]

def get_output_rate(model: str) -> float:
    """Get output token rate ($ per million) for a model."""
    model_key = "opus" if "opus" in model.lower() else "sonnet" if "sonnet" in model.lower() else "haiku"
    return PRICING.get(model_key, PRICING["sonnet"])["output"]

# For scripts that just need the raw values
INPUT_RATES = {k: v["input"] for k, v in PRICING.items()}
OUTPUT_RATES = {k: v["output"] for k, v in PRICING.items()}
CACHE_READ_RATES = {k: v["cache_read"] for k, v in PRICING.items()}

if __name__ == "__main__":
    print(f"Pricing Version: {VERSION}")
    print(f"\nModels:")
    for model, prices in PRICING.items():
        print(f"  {model}: ${prices['input']}/M input, ${prices['output']}/M output")
    print(f"\nPer-message estimates:")
    for model, cost in ESTIMATES.items():
        print(f"  {model}: ${cost}")
