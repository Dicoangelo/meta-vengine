#!/usr/bin/env python3
"""
Expertise-Aware Routing - Route based on user expertise confidence.

When you're an expert in a domain (confidence > 0.7), you need less AI help,
so we can use a cheaper model. When you're unfamiliar (confidence < 0.3),
we should use a more capable model to compensate.

Integrates with:
- identity-manager.js (expertise tracking)
- dq-scorer.js (routing decisions)
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Paths
KERNEL_DIR = Path.home() / ".claude" / "kernel"
IDENTITY_FILE = KERNEL_DIR / "identity.json"
EXPERTISE_ROUTING_LOG = KERNEL_DIR / "expertise-routing.jsonl"
EXPERTISE_ROUTING_STATE = KERNEL_DIR / "expertise-routing-state.json"

# Expertise signal keywords (same as identity-manager.js)
EXPERTISE_SIGNALS = {
    'react': ['react', 'jsx', 'component', 'hook', 'usestate', 'useeffect', 'props', 'nextjs', 'vite'],
    'typescript': ['typescript', 'type', 'interface', 'generic', 'ts', 'tsx', 'typing'],
    'node': ['node', 'npm', 'express', 'server', 'backend', 'api', 'middleware'],
    'python': ['python', 'pip', 'django', 'flask', 'pandas', 'numpy', 'async'],
    'ai-agents': ['agent', 'llm', 'prompt', 'claude', 'gpt', 'model', 'ai', 'embedding'],
    'research': ['arxiv', 'paper', 'study', 'research', 'methodology', 'analysis'],
    'devops': ['docker', 'kubernetes', 'ci', 'cd', 'deploy', 'pipeline', 'github actions'],
    'database': ['sql', 'postgres', 'mongodb', 'supabase', 'query', 'schema', 'migration'],
    'testing': ['test', 'spec', 'vitest', 'jest', 'coverage', 'mock', 'e2e'],
    'architecture': ['architecture', 'design', 'pattern', 'system', 'structure', 'refactor']
}

# Model tiers
MODEL_TIERS = {
    'haiku': {'cost': 1, 'capability': 0.3},
    'sonnet': {'cost': 2, 'capability': 0.7},
    'opus': {'cost': 3, 'capability': 1.0}
}


def load_identity() -> Dict:
    """Load identity.json for expertise data."""
    if IDENTITY_FILE.exists():
        return json.loads(IDENTITY_FILE.read_text())
    return {}


def detect_domain(query: str) -> Tuple[str, float]:
    """
    Detect the primary domain of a query.
    Returns (domain, match_strength).
    """
    query_lower = query.lower()
    domain_scores = {}

    for domain, signals in EXPERTISE_SIGNALS.items():
        matches = sum(1 for signal in signals if signal in query_lower)
        if matches > 0:
            # Score = matches / total signals (normalized)
            domain_scores[domain] = matches / len(signals)

    if not domain_scores:
        return ('general', 0.0)

    # Return domain with highest score
    best_domain = max(domain_scores.items(), key=lambda x: x[1])
    return best_domain


def get_expertise_confidence(identity: Dict, domain: str) -> float:
    """Get user's confidence level in a domain."""
    confidence = identity.get('expertise', {}).get('confidence', {})
    return confidence.get(domain, 0.5)  # Default to neutral


def route_by_expertise(query: str, base_complexity: float) -> Dict:
    """
    Route query based on user expertise in the detected domain.

    Logic:
    - High expertise (>0.7): User needs less help, DOWNGRADE model
    - Low expertise (<0.3): User needs more help, UPGRADE model
    - Medium expertise: Use complexity-based routing normally

    Returns routing recommendation with reasoning.
    """
    identity = load_identity()
    domain, domain_match = detect_domain(query)
    expertise = get_expertise_confidence(identity, domain)

    # Determine base model from complexity
    if base_complexity < 0.30:
        base_model = 'haiku'
    elif base_complexity < 0.70:
        base_model = 'sonnet'
    else:
        base_model = 'opus'

    # Apply expertise-based adjustment
    final_model = base_model
    adjustment = None
    reasoning = []

    if expertise > 0.7 and domain_match > 0.2:
        # High expertise - can use cheaper model
        if base_model == 'opus':
            final_model = 'sonnet'
            adjustment = 'downgrade'
            reasoning.append(f"High expertise in {domain} ({expertise:.0%}) - using sonnet instead of opus")
        elif base_model == 'sonnet' and base_complexity < 0.5:
            final_model = 'haiku'
            adjustment = 'downgrade'
            reasoning.append(f"High expertise in {domain} ({expertise:.0%}) - using haiku for simple task")
    elif expertise < 0.3 and domain_match > 0.2:
        # Low expertise - need more capable model
        if base_model == 'haiku':
            final_model = 'sonnet'
            adjustment = 'upgrade'
            reasoning.append(f"Low expertise in {domain} ({expertise:.0%}) - using sonnet for better guidance")
        elif base_model == 'sonnet' and base_complexity > 0.5:
            final_model = 'opus'
            adjustment = 'upgrade'
            reasoning.append(f"Low expertise in {domain} ({expertise:.0%}) - using opus for complex task")

    if not reasoning:
        reasoning.append(f"Standard routing for {domain} (expertise: {expertise:.0%})")

    result = {
        "query_preview": query[:50],
        "detected_domain": domain,
        "domain_match_strength": round(domain_match, 3),
        "expertise_confidence": round(expertise, 3),
        "base_complexity": round(base_complexity, 3),
        "base_model": base_model,
        "final_model": final_model,
        "adjustment": adjustment,
        "reasoning": reasoning,
        "timestamp": datetime.now().isoformat()
    }

    # Log the routing decision
    log_routing(result)

    return result


def log_routing(decision: Dict):
    """Log routing decision for analysis."""
    with open(EXPERTISE_ROUTING_LOG, 'a') as f:
        f.write(json.dumps(decision) + '\n')


def get_stats(days: int = 7) -> Dict:
    """Get expertise routing statistics."""
    if not EXPERTISE_ROUTING_LOG.exists():
        return {"total": 0, "adjustments": {"upgrade": 0, "downgrade": 0}}

    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=days)

    decisions = []
    for line in EXPERTISE_ROUTING_LOG.read_text().strip().split('\n'):
        if line:
            try:
                d = json.loads(line)
                if datetime.fromisoformat(d['timestamp']) > cutoff:
                    decisions.append(d)
            except:
                pass

    if not decisions:
        return {"total": 0, "adjustments": {"upgrade": 0, "downgrade": 0}}

    adjustments = {"upgrade": 0, "downgrade": 0, "none": 0}
    domains = {}
    cost_savings = 0

    for d in decisions:
        adj = d.get('adjustment')
        if adj == 'upgrade':
            adjustments['upgrade'] += 1
        elif adj == 'downgrade':
            adjustments['downgrade'] += 1
            # Estimate cost savings from downgrade
            base = MODEL_TIERS.get(d.get('base_model'), {}).get('cost', 2)
            final = MODEL_TIERS.get(d.get('final_model'), {}).get('cost', 2)
            cost_savings += (base - final)
        else:
            adjustments['none'] += 1

        domain = d.get('detected_domain', 'unknown')
        domains[domain] = domains.get(domain, 0) + 1

    return {
        "total": len(decisions),
        "adjustments": adjustments,
        "top_domains": sorted(domains.items(), key=lambda x: x[1], reverse=True)[:5],
        "estimated_cost_savings": cost_savings,
        "adjustment_rate": round((adjustments['upgrade'] + adjustments['downgrade']) / len(decisions), 2) if decisions else 0
    }


def export_state() -> Dict:
    """Export current expertise routing state for dq-scorer.js integration."""
    identity = load_identity()
    expertise = identity.get('expertise', {}).get('confidence', {})

    state = {
        "timestamp": datetime.now().isoformat(),
        "expertise_levels": expertise,
        "high_expertise_domains": [d for d, c in expertise.items() if c > 0.7],
        "low_expertise_domains": [d for d, c in expertise.items() if c < 0.3]
    }

    EXPERTISE_ROUTING_STATE.write_text(json.dumps(state, indent=2))
    return state


# CLI Interface
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Expertise-Aware Routing")
        print("")
        print("Commands:")
        print("  route \"query\" [complexity]  - Route query by expertise")
        print("  stats [days]                - Get routing statistics")
        print("  export                      - Export expertise state")
        print("  detect \"query\"              - Detect domain of query")
        sys.exit(0)

    command = args[0]

    if command == 'route':
        query = args[1] if len(args) > 1 else ""
        complexity = float(args[2]) if len(args) > 2 else 0.5
        result = route_by_expertise(query, complexity)
        print(json.dumps(result, indent=2))

    elif command == 'stats':
        days = int(args[1]) if len(args) > 1 else 7
        print(json.dumps(get_stats(days), indent=2))

    elif command == 'export':
        state = export_state()
        print(json.dumps(state, indent=2))

    elif command == 'detect':
        query = args[1] if len(args) > 1 else ""
        domain, strength = detect_domain(query)
        identity = load_identity()
        expertise = get_expertise_confidence(identity, domain)
        print(json.dumps({
            "domain": domain,
            "match_strength": round(strength, 3),
            "expertise_confidence": round(expertise, 3)
        }, indent=2))

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
