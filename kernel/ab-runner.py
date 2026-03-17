"""
US-209: A/B Test Automation Pipeline

Statistically rigorous A/B test runner for weight config comparison.
Reads historical behavioral outcomes, applies two weight configs in
interleaved ABAB order, computes composite rewards, and produces a
full statistical report (Welch's t-test, Cohen's d, power analysis,
adaptive early stopping).

Pure Python stdlib — no scipy/numpy.

Usage:
    python3 kernel/ab-runner.py --baseline config_a.json --candidate config_b.json --n 100
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTCOMES_PATH = DATA_DIR / "behavioral-outcomes.jsonl"
REPORT_DIR = DATA_DIR / "ab-reports"

# ---------------------------------------------------------------------------
# Incomplete Beta / t-distribution (pure Python, Lentz's continued fraction)
# ---------------------------------------------------------------------------


def _log_gamma(x):
    """
    Log-gamma via Lanczos approximation (g=7, n=9).
    Accurate to ~15 digits for x > 0.5.
    """
    if x <= 0:
        return math.inf
    coefs = [
        0.99999999999980993,
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    ]
    if x < 0.5:
        # Reflection formula
        return (
            math.log(math.pi / math.sin(math.pi * x))
            - _log_gamma(1 - x)
        )
    x -= 1
    g = 7
    a = coefs[0]
    t = x + g + 0.5
    for i in range(1, len(coefs)):
        a += coefs[i] / (x + i)
    return 0.5 * math.log(2 * math.pi) + (x + 0.5) * math.log(t) - t + math.log(a)


def _beta_cf(a, b, x, max_iter=200, tol=1e-12):
    """
    Continued fraction expansion for the regularised incomplete beta
    function using the modified Lentz algorithm.
    """
    # Lentz's method
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0

    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c

        # Odd step
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < tol:
            break

    return h


def regularised_incomplete_beta(a, b, x):
    """
    I_x(a, b) — regularised incomplete beta function.
    Uses continued fraction with symmetry transform for numerical stability.
    """
    if x < 0.0 or x > 1.0:
        raise ValueError(f"x must be in [0,1], got {x}")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    # Log of the front factor
    log_front = (
        _log_gamma(a + b)
        - _log_gamma(a)
        - _log_gamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    front = math.exp(log_front)

    # Use symmetry when x > (a+1)/(a+b+2) for convergence
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_cf(a, b, x) / a
    else:
        return 1.0 - (
            math.exp(
                _log_gamma(a + b)
                - _log_gamma(a)
                - _log_gamma(b)
                + b * math.log(1.0 - x)
                + a * math.log(x)
            )
            * _beta_cf(b, a, 1.0 - x)
            / b
        )


def t_cdf(t_val, df):
    """
    CDF of the Student's t-distribution with `df` degrees of freedom.
    P(T <= t_val) using the regularised incomplete beta function.
    """
    if df <= 0:
        return 0.5
    x = df / (df + t_val * t_val)
    ibeta = regularised_incomplete_beta(df / 2.0, 0.5, x)
    cdf = 0.5 * ibeta
    if t_val >= 0:
        return 1.0 - cdf
    return cdf


def welch_t_test(mean_a, var_a, n_a, mean_b, var_b, n_b):
    """
    Welch's t-test (two-tailed).
    Returns (t_statistic, degrees_of_freedom, p_value).
    """
    se_a = var_a / n_a if n_a > 0 else 0
    se_b = var_b / n_b if n_b > 0 else 0
    se_sum = se_a + se_b

    if se_sum < 1e-15:
        # Identical distributions or zero variance
        return 0.0, max(n_a + n_b - 2, 1), 1.0

    t_stat = (mean_a - mean_b) / math.sqrt(se_sum)

    # Welch-Satterthwaite degrees of freedom
    num = se_sum ** 2
    denom = 0.0
    if n_a > 1 and se_a > 0:
        denom += (se_a ** 2) / (n_a - 1)
    if n_b > 1 and se_b > 0:
        denom += (se_b ** 2) / (n_b - 1)
    df = num / denom if denom > 0 else max(n_a + n_b - 2, 1)

    # Two-tailed p-value
    p_left = t_cdf(t_stat, df)
    p_value = 2.0 * min(p_left, 1.0 - p_left)
    p_value = max(0.0, min(1.0, p_value))

    return t_stat, df, p_value


def cohens_d(mean_a, var_a, n_a, mean_b, var_b, n_b):
    """
    Cohen's d effect size using pooled standard deviation.
    Positive d means B > A.
    """
    pooled_var = 0.0
    denom = n_a + n_b - 2
    if denom > 0:
        pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / denom
    pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1e-10
    return (mean_b - mean_a) / pooled_std


def compute_power(effect_size, n_a, n_b, alpha=0.05):
    """
    Approximate achieved power using non-central t approximation.
    Power = P(reject H0 | H1 true).

    Uses the approximation: under H1 the test statistic follows a
    non-central t-distribution with noncentrality parameter
    delta = d * sqrt(n_a * n_b / (n_a + n_b)).

    We approximate using a shifted central t-distribution.
    """
    if n_a <= 1 or n_b <= 1:
        return 0.0

    df = n_a + n_b - 2
    ncp = abs(effect_size) * math.sqrt(n_a * n_b / (n_a + n_b))

    # Critical t-value for two-tailed test at alpha
    # Binary search for t_crit such that 2*(1-t_cdf(t_crit, df)) = alpha
    t_crit = _t_critical(df, alpha)

    # Power = P(|T'| > t_crit) where T' ~ noncentral t(df, ncp)
    # Approximate: P(T' > t_crit) + P(T' < -t_crit)
    # Under non-central t, shift by ncp:
    # P(T' > t_crit) ≈ 1 - Φ(t_crit - ncp)  (normal approx for large df)
    # For moderate df, use t_cdf with shift
    power_right = 1.0 - t_cdf(t_crit - ncp, df)
    power_left = t_cdf(-t_crit - ncp, df)
    power = power_right + power_left

    return max(0.0, min(1.0, power))


def _t_critical(df, alpha=0.05):
    """
    Find critical t-value for two-tailed test via bisection.
    We want t_crit such that P(|T| > t_crit) = alpha.
    """
    lo, hi = 0.0, 20.0
    target = 1.0 - alpha / 2.0

    for _ in range(100):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def confidence_interval_95(mean_a, var_a, n_a, mean_b, var_b, n_b):
    """95% CI for the difference (candidate - baseline)."""
    se = math.sqrt(var_a / max(n_a, 1) + var_b / max(n_b, 1))
    diff = mean_b - mean_a
    df_approx = max(n_a + n_b - 2, 1)
    t_crit = _t_critical(df_approx, 0.05)
    return [round(diff - t_crit * se, 6), round(diff + t_crit * se, 6)]


# ---------------------------------------------------------------------------
# Reward computation (mirrors bandit-engine.js computeReward)
# ---------------------------------------------------------------------------


def compute_reward(outcome, weight_config):
    """
    Compute composite reward from a behavioral outcome record and a weight config.

    weight_config should contain keys like:
        rewardWeightDQ, rewardWeightCost, rewardWeightBehavioral
    (with defaults 0.40, 0.30, 0.30 if missing).

    The outcome record contains component scores and a behavioral_score.
    We derive DQ, cost, and behavioral components from the outcome.
    """
    dq_w = weight_config.get("rewardWeightDQ", 0.40)
    cost_w = weight_config.get("rewardWeightCost", 0.30)
    behav_w = weight_config.get("rewardWeightBehavioral", 0.30)

    components = outcome.get("components", {})

    # DQ component: tool_success serves as quality proxy
    dq_component = max(0.0, min(1.0, components.get("tool_success", 0.5)))

    # Cost component: efficiency (higher = cheaper)
    cost_component = max(0.0, min(1.0, components.get("efficiency", 0.5)))

    # Behavioral component: the pre-computed behavioral_score
    behav_component = max(
        0.0, min(1.0, outcome.get("behavioral_score", 0.5))
    )

    reward = dq_w * dq_component + cost_w * cost_component + behav_w * behav_component
    return max(0.0, min(1.0, reward))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_outcomes(path=None, limit=None):
    """
    Load behavioral outcome records from JSONL.
    Returns a list of dicts.
    """
    p = Path(path) if path else OUTCOMES_PATH
    if not p.exists():
        print(f"[ab-runner] WARNING: outcomes file not found: {p}", file=sys.stderr)
        return []

    records = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if limit and len(records) >= limit:
                break
    return records


# ---------------------------------------------------------------------------
# A/B test runner
# ---------------------------------------------------------------------------


def run_ab_test(baseline_config, candidate_config, n_per_group=100, outcomes=None):
    """
    Run an interleaved ABAB test.

    For each of 2*N decisions, alternating baseline/candidate:
      - Apply the weight config to the outcome to compute reward
      - Collect into two arrays

    Returns the full report dict.
    """
    if outcomes is None:
        # Need 2*N outcomes total (N baseline + N candidate, interleaved)
        outcomes = load_outcomes(limit=2 * n_per_group)

    total_needed = 2 * n_per_group
    if len(outcomes) < total_needed:
        print(
            f"[ab-runner] WARNING: only {len(outcomes)} outcomes available, "
            f"need {total_needed}. Reducing n to {len(outcomes) // 2}.",
            file=sys.stderr,
        )
        n_per_group = max(1, len(outcomes) // 2)
        total_needed = 2 * n_per_group

    baseline_rewards = []
    candidate_rewards = []
    early_stopped = False

    for i in range(total_needed):
        outcome = outcomes[i]
        if i % 2 == 0:
            # Even index -> baseline
            r = compute_reward(outcome, baseline_config)
            baseline_rewards.append(r)
        else:
            # Odd index -> candidate
            r = compute_reward(outcome, candidate_config)
            candidate_rewards.append(r)

        # Adaptive early stopping at halfway
        n_so_far_per_group = min(len(baseline_rewards), len(candidate_rewards))
        if n_so_far_per_group == 50 and n_per_group >= 100:
            interim = _compute_stats(baseline_rewards, candidate_rewards)
            if interim["p_value"] < 0.01:
                early_stopped = True
                print(
                    f"[ab-runner] Early stop at N=50: p={interim['p_value']:.6f}",
                    file=sys.stderr,
                )
                break

    return _build_report(
        baseline_config,
        candidate_config,
        baseline_rewards,
        candidate_rewards,
        early_stopped,
    )


def _compute_stats(baseline_rewards, candidate_rewards):
    """Compute t-test stats from two reward arrays."""
    n_a = len(baseline_rewards)
    n_b = len(candidate_rewards)

    mean_a = sum(baseline_rewards) / n_a if n_a > 0 else 0.0
    mean_b = sum(candidate_rewards) / n_b if n_b > 0 else 0.0

    var_a = (
        sum((x - mean_a) ** 2 for x in baseline_rewards) / (n_a - 1)
        if n_a > 1
        else 0.0
    )
    var_b = (
        sum((x - mean_b) ** 2 for x in candidate_rewards) / (n_b - 1)
        if n_b > 1
        else 0.0
    )

    t_stat, df, p_val = welch_t_test(mean_a, var_a, n_a, mean_b, var_b, n_b)

    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "var_a": var_a,
        "var_b": var_b,
        "n_a": n_a,
        "n_b": n_b,
        "t_statistic": t_stat,
        "degrees_of_freedom": df,
        "p_value": p_val,
    }


def _build_report(
    baseline_config,
    candidate_config,
    baseline_rewards,
    candidate_rewards,
    early_stopped,
):
    """Build the full JSON report."""
    stats = _compute_stats(baseline_rewards, candidate_rewards)

    d = cohens_d(
        stats["mean_a"],
        stats["var_a"],
        stats["n_a"],
        stats["mean_b"],
        stats["var_b"],
        stats["n_b"],
    )
    power = compute_power(
        d, stats["n_a"], stats["n_b"], alpha=0.05
    )
    ci = confidence_interval_95(
        stats["mean_a"],
        stats["var_a"],
        stats["n_a"],
        stats["mean_b"],
        stats["var_b"],
        stats["n_b"],
    )

    # Verdict
    p = stats["p_value"]
    if p < 0.05 and stats["mean_b"] > stats["mean_a"]:
        verdict = "candidate_wins"
    elif p < 0.05 and stats["mean_a"] > stats["mean_b"]:
        verdict = "baseline_wins"
    else:
        verdict = "inconclusive"

    std_a = math.sqrt(stats["var_a"]) if stats["var_a"] > 0 else 0.0
    std_b = math.sqrt(stats["var_b"]) if stats["var_b"] > 0 else 0.0

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "baseline_config": baseline_config,
        "candidate_config": candidate_config,
        "n_per_group": stats["n_a"],
        "baseline_mean": round(stats["mean_a"], 6),
        "baseline_std": round(std_a, 6),
        "candidate_mean": round(stats["mean_b"], 6),
        "candidate_std": round(std_b, 6),
        "t_statistic": round(stats["t_statistic"], 4),
        "degrees_of_freedom": round(stats["degrees_of_freedom"], 1),
        "p_value": round(p, 6),
        "cohens_d": round(d, 4),
        "power": round(power, 4),
        "verdict": verdict,
        "early_stopped": early_stopped,
        "confidence_interval_95": ci,
    }

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_config(value):
    """
    Load a weight config from a file path or inline JSON string.
    """
    # Try as file path first
    p = Path(value)
    if p.exists():
        return json.loads(p.read_text())

    # Try relative to BASE_DIR
    p2 = BASE_DIR / value
    if p2.exists():
        return json.loads(p2.read_text())

    # Try as inline JSON
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        raise ValueError(
            f"Cannot parse config: '{value}' is neither a file path nor valid JSON"
        )


def main():
    parser = argparse.ArgumentParser(
        description="US-209: A/B Test Runner for weight config comparison"
    )
    parser.add_argument(
        "--baseline",
        required=True,
        help="Baseline weight config (JSON file or inline JSON string)",
    )
    parser.add_argument(
        "--candidate",
        required=True,
        help="Candidate weight config (JSON file or inline JSON string)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=100,
        help="Sample size per group (default: 100)",
    )
    parser.add_argument(
        "--outcomes",
        default=None,
        help="Path to behavioral-outcomes.jsonl (default: data/behavioral-outcomes.jsonl)",
    )

    args = parser.parse_args()

    baseline_config = _load_config(args.baseline)
    candidate_config = _load_config(args.candidate)

    outcomes = None
    if args.outcomes:
        outcomes = load_outcomes(args.outcomes, limit=2 * args.n)

    report = run_ab_test(baseline_config, candidate_config, args.n, outcomes)

    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    report_path = REPORT_DIR / f"{ts}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    # Print JSON to stdout
    print(json.dumps(report, indent=2))

    # Human-readable summary to stderr
    print("\n" + "=" * 60, file=sys.stderr)
    print("A/B TEST REPORT", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  N per group:   {report['n_per_group']}", file=sys.stderr)
    print(f"  Baseline mean: {report['baseline_mean']:.4f} (std {report['baseline_std']:.4f})", file=sys.stderr)
    print(f"  Candidate mean:{report['candidate_mean']:.4f} (std {report['candidate_std']:.4f})", file=sys.stderr)
    print(f"  t-statistic:   {report['t_statistic']:.4f}", file=sys.stderr)
    print(f"  df:            {report['degrees_of_freedom']:.1f}", file=sys.stderr)
    print(f"  p-value:       {report['p_value']:.6f}", file=sys.stderr)
    print(f"  Cohen's d:     {report['cohens_d']:.4f}", file=sys.stderr)
    print(f"  Power:         {report['power']:.4f}", file=sys.stderr)
    print(f"  95% CI:        {report['confidence_interval_95']}", file=sys.stderr)
    print(f"  Early stopped: {report['early_stopped']}", file=sys.stderr)
    print(f"  VERDICT:       {report['verdict'].upper()}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Report saved:  {report_path}", file=sys.stderr)

    return report


if __name__ == "__main__":
    main()
