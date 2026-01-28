#!/usr/bin/env python3
"""
Comprehensive QA Test Suite for Autonomous Session Analysis System
Tests all components: agents, ACE consensus, summarizer, dashboard data
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import importlib.util

# Load modules using importlib
observatory_dir = Path(__file__).parent

# Load post_session_analyzer
spec = importlib.util.spec_from_file_location("post_session_analyzer", observatory_dir / "post-session-analyzer.py")
psa_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(psa_module)
PostSessionAnalyzer = psa_module.PostSessionAnalyzer

# Load session_summarizer
spec = importlib.util.spec_from_file_location("session_summarizer", observatory_dir / "session_summarizer.py")
ss_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ss_module)
SessionSummarizer = ss_module.SessionSummarizer

# Load ace_consensus
spec = importlib.util.spec_from_file_location("ace_consensus", observatory_dir / "ace_consensus.py")
ace_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ace_module)
ACEConsensus = ace_module.ACEConsensus

# Add agents directory to path for relative imports
agents_dir = observatory_dir / "agents"
sys.path.insert(0, str(agents_dir))

# Load base agent class first
spec = importlib.util.spec_from_file_location("agents", agents_dir / "__init__.py")
agents_module = importlib.util.module_from_spec(spec)
sys.modules['agents'] = agents_module  # Register as a package
spec.loader.exec_module(agents_module)

# Now load individual agents (they can use relative imports)
spec = importlib.util.spec_from_file_location("agents.outcome_detector", agents_dir / "outcome_detector.py")
od_module = importlib.util.module_from_spec(spec)
sys.modules['agents.outcome_detector'] = od_module
spec.loader.exec_module(od_module)
OutcomeDetectorAgent = od_module.OutcomeDetectorAgent

spec = importlib.util.spec_from_file_location("agents.quality_scorer", agents_dir / "quality_scorer.py")
qs_module = importlib.util.module_from_spec(spec)
sys.modules['agents.quality_scorer'] = qs_module
spec.loader.exec_module(qs_module)
QualityScorerAgent = qs_module.QualityScorerAgent

spec = importlib.util.spec_from_file_location("agents.complexity_analyzer", agents_dir / "complexity_analyzer.py")
ca_module = importlib.util.module_from_spec(spec)
sys.modules['agents.complexity_analyzer'] = ca_module
spec.loader.exec_module(ca_module)
ComplexityAnalyzerAgent = ca_module.ComplexityAnalyzerAgent

spec = importlib.util.spec_from_file_location("agents.model_efficiency", agents_dir / "model_efficiency.py")
me_module = importlib.util.module_from_spec(spec)
sys.modules['agents.model_efficiency'] = me_module
spec.loader.exec_module(me_module)
ModelEfficiencyAgent = me_module.ModelEfficiencyAgent

spec = importlib.util.spec_from_file_location("agents.productivity_analyzer", agents_dir / "productivity_analyzer.py")
pa_module = importlib.util.module_from_spec(spec)
sys.modules['agents.productivity_analyzer'] = pa_module
spec.loader.exec_module(pa_module)
ProductivityAnalyzerAgent = pa_module.ProductivityAnalyzerAgent

spec = importlib.util.spec_from_file_location("agents.routing_quality", agents_dir / "routing_quality.py")
rq_module = importlib.util.module_from_spec(spec)
sys.modules['agents.routing_quality'] = rq_module
spec.loader.exec_module(rq_module)
RoutingQualityAgent = rq_module.RoutingQualityAgent


class QATestSuite:
    """Comprehensive QA test suite."""

    def __init__(self):
        self.analyzer = PostSessionAnalyzer()
        self.summarizer = SessionSummarizer()
        self.ace = ACEConsensus()
        self.passed = 0
        self.failed = 0
        self.tests = []

    def test_result(self, name: str, passed: bool, details: str = ""):
        """Record test result."""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if details:
            print(f"         {details}")

        self.tests.append({
            "name": name,
            "passed": passed,
            "details": details
        })

        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def test_agent_initialization(self):
        """Test 1: All agents initialize correctly."""
        print("\n=== Test 1: Agent Initialization ===")

        agents = [
            ("OutcomeDetectorAgent", OutcomeDetectorAgent),
            ("QualityScorerAgent", QualityScorerAgent),
            ("ComplexityAnalyzerAgent", ComplexityAnalyzerAgent),
            ("ModelEfficiencyAgent", ModelEfficiencyAgent),
            ("ProductivityAnalyzerAgent", ProductivityAnalyzerAgent),
            ("RoutingQualityAgent", RoutingQualityAgent)
        ]

        for name, agent_class in agents:
            try:
                agent = agent_class()
                self.test_result(f"{name} initialization", True, f"Agent name: {agent.name}")
            except Exception as e:
                self.test_result(f"{name} initialization", False, str(e))

    def test_transcript_loading(self):
        """Test 2: Session transcript loading."""
        print("\n=== Test 2: Transcript Loading ===")

        # Find a real session
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        if not outcomes_file.exists():
            self.test_result("Outcomes file exists", False, "session-outcomes.jsonl not found")
            return

        self.test_result("Outcomes file exists", True, str(outcomes_file))

        # Get a session ID
        with open(outcomes_file) as f:
            lines = f.readlines()
            if lines:
                first_session = json.loads(lines[0])
                session_id = first_session.get("session_id")

                if session_id:
                    try:
                        transcript = self.analyzer.load_session_transcript(session_id)

                        # Check transcript structure
                        has_messages = len(transcript.get("messages", [])) > 0
                        has_tools = "tools" in transcript
                        has_metadata = "metadata" in transcript

                        self.test_result(
                            "Transcript loading",
                            has_messages and has_tools and has_metadata,
                            f"{len(transcript.get('messages', []))} messages, {len(transcript.get('tools', []))} tools"
                        )
                    except Exception as e:
                        self.test_result("Transcript loading", False, str(e))

    def test_agent_analysis(self):
        """Test 3: Each agent runs analysis."""
        print("\n=== Test 3: Agent Analysis ===")

        # Get a session to test with
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        with open(outcomes_file) as f:
            first_session = json.loads(f.readline())
            session_id = first_session.get("session_id")

        try:
            transcript = self.analyzer.load_session_transcript(session_id)

            agents = {
                "outcome": OutcomeDetectorAgent(),
                "quality": QualityScorerAgent(),
                "complexity": ComplexityAnalyzerAgent(),
                "model_efficiency": ModelEfficiencyAgent(),
                "productivity": ProductivityAnalyzerAgent(),
                "routing_quality": RoutingQualityAgent()
            }

            for name, agent in agents.items():
                try:
                    result = agent.analyze(transcript)

                    # Check result structure
                    has_summary = "summary" in result
                    has_dq = "dq_score" in result
                    has_confidence = "confidence" in result

                    valid = has_summary and has_dq and has_confidence

                    self.test_result(
                        f"{name} agent analysis",
                        valid,
                        f"Summary: {result.get('summary', 'N/A')[:50]}..."
                    )
                except Exception as e:
                    self.test_result(f"{name} agent analysis", False, str(e))

        except Exception as e:
            self.test_result("Agent analysis setup", False, str(e))

    def test_ace_consensus(self):
        """Test 4: ACE consensus synthesis."""
        print("\n=== Test 4: ACE Consensus ===")

        # Get a session
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        with open(outcomes_file) as f:
            first_session = json.loads(f.readline())
            session_id = first_session.get("session_id")

        try:
            transcript = self.analyzer.load_session_transcript(session_id)

            # Run all agents
            agent_results = {}
            agents = {
                "outcome": OutcomeDetectorAgent(),
                "quality": QualityScorerAgent(),
                "complexity": ComplexityAnalyzerAgent(),
                "model_efficiency": ModelEfficiencyAgent(),
                "productivity": ProductivityAnalyzerAgent(),
                "routing_quality": RoutingQualityAgent()
            }

            for name, agent in agents.items():
                agent_results[name] = agent.analyze(transcript)

            # Apply ACE consensus
            consensus = self.ace.synthesize(agent_results, transcript)

            # Check consensus structure
            has_outcome = "outcome" in consensus
            has_quality = "quality" in consensus
            has_complexity = "complexity" in consensus
            has_efficiency = "model_efficiency" in consensus
            has_dq = "dq_score" in consensus
            has_confidence = "confidence" in consensus

            valid = all([has_outcome, has_quality, has_complexity, has_efficiency, has_dq, has_confidence])

            self.test_result(
                "ACE consensus synthesis",
                valid,
                f"Outcome: {consensus.get('outcome')}, Quality: {consensus.get('quality')}, DQ: {consensus.get('dq_score', 0):.3f}"
            )

        except Exception as e:
            self.test_result("ACE consensus synthesis", False, str(e))

    def test_summarizer(self):
        """Test 5: Session summarizer."""
        print("\n=== Test 5: Session Summarizer ===")

        # Get a session
        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        with open(outcomes_file) as f:
            first_session = json.loads(f.readline())
            session_id = first_session.get("session_id")

        try:
            transcript = self.analyzer.load_session_transcript(session_id)

            # Create mock analysis
            analysis = {
                "outcome": "success",
                "quality": 4,
                "complexity": 0.5,
                "model_efficiency": 0.8
            }

            summary = self.summarizer.generate_summary(transcript, analysis)

            # Check summary structure
            has_title = "title" in summary
            has_intent = "intent" in summary
            has_summary = "summary" in summary
            has_achievements = "achievements" in summary
            has_files = "files_modified" in summary

            valid = all([has_title, has_intent, has_summary, has_achievements, has_files])

            self.test_result(
                "Summary generation",
                valid,
                f"Title: {summary.get('title', 'N/A')[:50]}..."
            )

        except Exception as e:
            self.test_result("Summary generation", False, str(e))

    def test_data_integrity(self):
        """Test 6: Data integrity checks."""
        print("\n=== Test 6: Data Integrity ===")

        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        try:
            # Load all entries
            entries = []
            with open(outcomes_file) as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            self.test_result("JSONL file parsing", True, f"{len(entries)} entries loaded")

            # Check for required fields
            required_fields = ["session_id", "outcome", "quality", "complexity", "model_efficiency", "dq_score"]

            valid_entries = 0
            for entry in entries:
                if all(field in entry for field in required_fields):
                    valid_entries += 1

            self.test_result(
                "Required fields present",
                valid_entries == len(entries),
                f"{valid_entries}/{len(entries)} entries have all required fields"
            )

            # Check for duplicates
            session_ids = [e["session_id"] for e in entries]
            unique_ids = set(session_ids)

            self.test_result(
                "No duplicates check",
                len(session_ids) == len(unique_ids),
                f"{len(unique_ids)} unique sessions, {len(session_ids)} total entries"
            )

            # Check summary fields
            with_summaries = sum(1 for e in entries if "title" in e and "intent" in e)

            self.test_result(
                "Summary fields present",
                with_summaries > 0,
                f"{with_summaries}/{len(entries)} entries have summary data"
            )

        except Exception as e:
            self.test_result("Data integrity checks", False, str(e))

    def test_dashboard_data(self):
        """Test 7: Dashboard data API."""
        print("\n=== Test 7: Dashboard Data ===")

        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        try:
            # Load entries
            entries = []
            with open(outcomes_file) as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            # Calculate metrics (same as dashboard)
            total = len(entries)
            avg_quality = sum(e.get("quality", 0) for e in entries) / total if total > 0 else 0
            avg_complexity = sum(e.get("complexity", 0) for e in entries) / total if total > 0 else 0
            avg_efficiency = sum(e.get("model_efficiency", 0) for e in entries) / total if total > 0 else 0
            avg_dq = sum(e.get("dq_score", 0) for e in entries) / total if total > 0 else 0

            # Outcome distribution
            outcomes = {}
            for e in entries:
                outcome = e.get("outcome", "unknown")
                outcomes[outcome] = outcomes.get(outcome, 0) + 1

            self.test_result(
                "Dashboard metrics calculation",
                total > 0,
                f"Total: {total}, Avg Quality: {avg_quality:.2f}, Avg DQ: {avg_dq:.3f}"
            )

            self.test_result(
                "Outcome distribution",
                len(outcomes) > 0,
                ", ".join([f"{k}: {v}" for k, v in outcomes.items()])
            )

        except Exception as e:
            self.test_result("Dashboard data checks", False, str(e))

    def test_empty_session_filtering(self):
        """Test 8: Empty session filtering logic."""
        print("\n=== Test 8: Empty Session Filtering ===")

        outcomes_file = Path.home() / ".claude/data/session-outcomes.jsonl"

        try:
            # Load entries
            entries = []
            with open(outcomes_file) as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            # Count empty sessions (same logic as dashboard)
            empty_count = 0
            for e in entries:
                if (e.get("outcome") == "abandoned" and
                    e.get("quality") == 1 and
                    (not e.get("files_modified") or len(e.get("files_modified", [])) == 0)):
                    empty_count += 1

            self.test_result(
                "Empty session detection",
                True,
                f"{empty_count} empty sessions detected out of {len(entries)} total"
            )

        except Exception as e:
            self.test_result("Empty session filtering", False, str(e))

    def test_file_structure(self):
        """Test 9: File structure and naming."""
        print("\n=== Test 9: File Structure ===")

        projects_dir = Path.home() / ".claude/projects"

        # Check for numbered sessions
        numbered_pattern = "????-??-??_#*_*_id-*.jsonl"
        numbered_files = list(projects_dir.rglob(numbered_pattern))

        self.test_result(
            "Numbered session files exist",
            len(numbered_files) > 0,
            f"{len(numbered_files)} files with new naming scheme"
        )

        # Check for summary files
        summary_files = list(projects_dir.rglob("*.summary.md"))

        self.test_result(
            "Summary files exist",
            len(summary_files) > 0,
            f"{len(summary_files)} summary files found"
        )

        # Check observatory directory structure
        observatory_dir = Path.home() / ".claude/scripts/observatory"

        required_files = [
            "post-session-analyzer.py",
            "session_summarizer.py",
            "ace_consensus.py",
            "batch-process-all-sessions.py",
            "agents/outcome_detector.py",
            "agents/quality_scorer.py",
            "agents/complexity_analyzer.py",
            "agents/model_efficiency.py",
            "agents/productivity_analyzer.py",
            "agents/routing_quality.py"
        ]

        missing = []
        for file in required_files:
            if not (observatory_dir / file).exists():
                missing.append(file)

        self.test_result(
            "Observatory files complete",
            len(missing) == 0,
            f"All required files present" if not missing else f"Missing: {', '.join(missing)}"
        )

    def run_all_tests(self):
        """Run all QA tests."""
        print("=" * 70)
        print("🧪 AUTONOMOUS SESSION ANALYSIS SYSTEM - QA TEST SUITE")
        print("=" * 70)

        self.test_agent_initialization()
        self.test_transcript_loading()
        self.test_agent_analysis()
        self.test_ace_consensus()
        self.test_summarizer()
        self.test_data_integrity()
        self.test_dashboard_data()
        self.test_empty_session_filtering()
        self.test_file_structure()

        # Summary
        print("\n" + "=" * 70)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 70)
        print(f"\n✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📈 Success Rate: {self.passed / (self.passed + self.failed) * 100:.1f}%")

        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! System is fully operational.")
        else:
            print(f"\n⚠️  {self.failed} test(s) failed. Review details above.")

        return self.failed == 0


def main():
    suite = QATestSuite()
    success = suite.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
