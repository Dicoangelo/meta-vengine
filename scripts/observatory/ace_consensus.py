"""
ACE Consensus Engine for Session Analysis

Adaptive Consensus Engine that synthesizes results from 7 analysis agents
using DQ-weighted voting. Ported from OS-App/services/adaptiveConsensus.ts.

Includes ContrarianAgent (7th agent) for adversarial analysis that:
- Challenges consensus when all agents agree
- Identifies hidden assumptions
- Provides minority opinions
- Flags overconfident conclusions
"""

from typing import Dict, List, Optional


class ACEConsensus:
    """
    Adaptive Consensus Engine for Session Analysis.

    Uses DQ scoring (validity 40% + specificity 30% + correctness 30%)
    to weight agent contributions and reach consensus.
    """

    def __init__(self):
        # DQ weights (same as OS-App)
        self.dq_weights = {
            "validity": 0.4,
            "specificity": 0.3,
            "correctness": 0.3
        }

    def synthesize(self, agent_results: Dict, transcript: Dict) -> Dict:
        """
        Apply ACE consensus to combine agent results.

        Args:
            agent_results: Dict of {agent_name: agent_result}
            transcript: Original session transcript

        Returns:
            Consensus analysis with confidence score
        """

        # Calculate overall DQ score for each agent
        agent_dqs = self._calculate_agent_weights(agent_results)

        # Weighted voting for outcome
        outcome = self._consensus_outcome(agent_results, agent_dqs)

        # Weighted average for quality
        quality = self._consensus_quality(agent_results, agent_dqs)

        # Extract complexity from complexity agent
        complexity = self._extract_complexity(agent_results)

        # Extract model efficiency from model_efficiency agent
        model_efficiency = self._extract_model_efficiency(agent_results)

        # Calculate overall DQ score (weighted average of agent DQs)
        overall_dq = self._calculate_overall_dq(agent_dqs)

        # Calculate consensus confidence
        confidence = self._calculate_confidence(agent_dqs, agent_results)

        # Extract optimal model recommendation
        optimal_model = self._extract_optimal_model(agent_results)

        # Extract contrarian insights (if ContrarianAgent participated)
        minority_opinion = None
        assumption_risks = []
        if "contrarian" in agent_results:
            contrarian_data = agent_results["contrarian"].get("data", {})
            minority_opinion = contrarian_data.get("minority_opinion")
            assumption_risks = contrarian_data.get("assumption_risks", [])

        return {
            "outcome": outcome,
            "quality": quality,
            "complexity": complexity,
            "model_efficiency": model_efficiency,
            "dq_score": overall_dq,
            "confidence": confidence,
            "optimal_model": optimal_model,
            "agent_contributions": agent_dqs,
            "minority_opinion": minority_opinion,
            "assumption_risks": assumption_risks
        }

    def _calculate_agent_weights(self, agent_results: Dict) -> Dict:
        """Calculate DQ-based weights for each agent."""

        agent_dqs = {}

        for name, result in agent_results.items():
            dq = result.get("dq_score", {})

            # Calculate overall DQ using standard weights
            overall_dq = (
                dq.get("validity", 0.5) * self.dq_weights["validity"] +
                dq.get("specificity", 0.5) * self.dq_weights["specificity"] +
                dq.get("correctness", 0.5) * self.dq_weights["correctness"]
            )

            # Agent confidence multiplier
            agent_confidence = result.get("confidence", 0.5)

            # Combined weight
            weight = agent_confidence * overall_dq

            agent_dqs[name] = {
                "dq": overall_dq,
                "confidence": agent_confidence,
                "weight": weight
            }

        return agent_dqs

    def _consensus_outcome(self, agent_results: Dict, agent_dqs: Dict) -> str:
        """Weighted voting for outcome."""

        outcome_votes = {}

        # Outcome detector has primary say on outcome
        if "outcome" in agent_results:
            outcome = agent_results["outcome"].get("outcome", "unknown")
            weight = agent_dqs.get("outcome", {}).get("weight", 0.5)
            outcome_votes[outcome] = outcome_votes.get(outcome, 0) + weight * 2  # Double weight

        # Quality scorer can influence (low quality might indicate partial/error)
        if "quality" in agent_results:
            quality_data = agent_results["quality"].get("data", {})
            quality_score = quality_data.get("quality", 3)

            if quality_score <= 2:
                # Low quality suggests partial or error outcome
                outcome_votes["partial"] = outcome_votes.get("partial", 0) + 0.3
            elif quality_score >= 4:
                # High quality suggests success
                outcome_votes["success"] = outcome_votes.get("success", 0) + 0.2

        # Productivity analyzer can influence
        if "productivity" in agent_results:
            prod_data = agent_results["productivity"].get("data", {})
            prod_level = prod_data.get("level", "Moderate")

            if prod_level in ["Very High", "High"]:
                outcome_votes["success"] = outcome_votes.get("success", 0) + 0.1

        # Return outcome with highest vote
        if outcome_votes:
            winning_outcome = max(outcome_votes.items(), key=lambda x: x[1])[0]
            return winning_outcome
        else:
            return "unknown"

    def _consensus_quality(self, agent_results: Dict, agent_dqs: Dict) -> int:
        """Weighted average for quality score."""

        quality_scores = []
        total_weight = 0

        # Quality scorer has primary say
        if "quality" in agent_results:
            quality_data = agent_results["quality"].get("data", {})
            quality = quality_data.get("quality", 3)
            weight = agent_dqs.get("quality", {}).get("weight", 0.5) * 2  # Double weight
            quality_scores.append(quality * weight)
            total_weight += weight

        # Model efficiency can influence
        if "model_efficiency" in agent_results:
            eff_data = agent_results["model_efficiency"].get("data", {})
            efficiency = eff_data.get("efficiency", 0.5)
            # Map efficiency to quality (0.5 -> 3, 1.0 -> 5, 0.0 -> 1)
            quality_from_eff = 1 + efficiency * 4
            weight = agent_dqs.get("model_efficiency", {}).get("weight", 0.5) * 0.5
            quality_scores.append(quality_from_eff * weight)
            total_weight += weight

        # Productivity can influence
        if "productivity" in agent_results:
            prod_data = agent_results["productivity"].get("data", {})
            prod_score = prod_data.get("productivity_score", 0.5)
            # Map productivity to quality
            quality_from_prod = 1 + prod_score * 4
            weight = agent_dqs.get("productivity", {}).get("weight", 0.5) * 0.5
            quality_scores.append(quality_from_prod * weight)
            total_weight += weight

        if total_weight > 0:
            avg_quality = sum(quality_scores) / total_weight
            return max(1, min(5, int(round(avg_quality))))
        else:
            return 3

    def _extract_complexity(self, agent_results: Dict) -> float:
        """Extract complexity from complexity analyzer agent."""

        if "complexity" in agent_results:
            return agent_results["complexity"].get("complexity", 0.5)
        return 0.5

    def _extract_model_efficiency(self, agent_results: Dict) -> float:
        """Extract model efficiency from model_efficiency agent."""

        if "model_efficiency" in agent_results:
            eff_data = agent_results["model_efficiency"].get("data", {})
            return eff_data.get("efficiency", 0.5)
        return 0.5

    def _extract_optimal_model(self, agent_results: Dict) -> str:
        """Extract optimal model recommendation."""

        if "model_efficiency" in agent_results:
            eff_data = agent_results["model_efficiency"].get("data", {})
            return eff_data.get("optimal_model", "unknown")
        return "unknown"

    def _calculate_overall_dq(self, agent_dqs: Dict) -> float:
        """Calculate overall DQ score (weighted average of agent DQs)."""

        if not agent_dqs:
            return 0.5

        total_dq = 0
        total_weight = 0

        for name, metrics in agent_dqs.items():
            dq = metrics["dq"]
            weight = metrics["weight"]

            total_dq += dq * weight
            total_weight += weight

        if total_weight > 0:
            return total_dq / total_weight
        else:
            return 0.5

    def _calculate_confidence(self, agent_dqs: Dict, agent_results: Dict) -> float:
        """
        Calculate confidence in consensus.

        High confidence when:
        1. Agent DQ scores are high
        2. Agent confidences are high
        3. Results are consistent (agents agree)
        """

        if not agent_dqs:
            return 0.3

        # Average agent DQ
        avg_agent_dq = sum(a["dq"] for a in agent_dqs.values()) / len(agent_dqs)

        # Average agent confidence
        avg_agent_conf = sum(a["confidence"] for a in agent_dqs.values()) / len(agent_dqs)

        # Check result consistency (outcome agreement)
        outcome_consistency = self._calculate_outcome_consistency(agent_results)

        # Weighted confidence
        confidence = (
            0.4 * avg_agent_dq +
            0.3 * avg_agent_conf +
            0.3 * outcome_consistency
        )

        return min(1.0, max(0.0, confidence))

    def _calculate_outcome_consistency(self, agent_results: Dict) -> float:
        """Calculate how consistent agents are about outcome."""

        # Check if quality and productivity align with outcome
        if "outcome" not in agent_results:
            return 0.5

        outcome = agent_results["outcome"].get("outcome", "unknown")

        consistency_score = 0.5  # Base

        # Check quality alignment
        if "quality" in agent_results:
            quality = agent_results["quality"].get("data", {}).get("quality", 3)

            if outcome == "success" and quality >= 4:
                consistency_score += 0.15
            elif outcome == "error" and quality <= 2:
                consistency_score += 0.15
            elif outcome == "partial" and 2 < quality < 4:
                consistency_score += 0.15

        # Check productivity alignment
        if "productivity" in agent_results:
            prod_score = agent_results["productivity"].get("data", {}).get("productivity_score", 0.5)

            if outcome == "success" and prod_score >= 0.6:
                consistency_score += 0.15
            elif outcome == "error" and prod_score < 0.4:
                consistency_score += 0.15

        # Check model efficiency alignment
        if "model_efficiency" in agent_results:
            efficiency = agent_results["model_efficiency"].get("data", {}).get("efficiency", 0.5)

            if outcome == "success" and efficiency >= 0.7:
                consistency_score += 0.1
            elif outcome == "error" and efficiency < 0.5:
                consistency_score += 0.1

        return min(1.0, consistency_score)
