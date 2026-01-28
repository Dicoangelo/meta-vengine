# Autonomous Session Analysis System - Quick Start Guide

## 🚀 Quick Access

**Dashboard**: http://127.0.0.1:8888/autonomous-analysis-dashboard.html

```bash
# Start dashboard server
cd ~/.claude/scripts/observatory && python3 api-server.py

# Run QA tests
python3 ~/.claude/scripts/observatory/qa-test-suite.py

# Analyze a single session
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --session-id "SESSION_ID"

# Batch process all UUID sessions
python3 ~/.claude/scripts/observatory/batch-process-all-sessions.py

# Dry run (see what would happen)
python3 ~/.claude/scripts/observatory/batch-process-all-sessions.py --dry-run
```

---

## 📊 Dashboard Features

### Key Metrics
- **Total Sessions**: Number of analyzed sessions (deduplicated)
- **Average Quality**: Quality score 1-5 (productivity-based)
- **Average Complexity**: Session complexity 0-1
- **Model Efficiency**: Optimal model usage percentage
- **Empty Sessions**: Count and percentage of empty sessions

### Filtering
- **Show/Hide Empty Sessions**: Checkbox to toggle empty session visibility
- **Filter Stats**: Shows how many sessions are hidden

### Session Table
- **Hover for Summary**: Tooltip shows full session summary
- **Columns**: Session ID, Title, Intent, Outcome, Quality, Complexity, Efficiency
- **Last 10 Sessions**: Most recent analyses displayed first

### Refresh
- **Manual**: Click "🔄 Refresh Data" button
- **Auto**: Refreshes every 30 seconds automatically

---

## 🤖 How It Works

### 1. Session Analysis Pipeline

```
Session Transcript (JSONL)
        ↓
6-Agent Analysis (parallel)
        ↓
ACE Consensus (DQ-weighted voting)
        ↓
Session Summary Generation
        ↓
Structured JSONL Entry
        ↓
Dashboard Visualization
```

### 2. Agent Roles

| Agent | Purpose | Output |
|-------|---------|--------|
| **OutcomeDetector** | Git commits, errors, completion signals | success/abandoned/error/research |
| **QualityScorer** | LOC, files, productivity | Quality 1-5 |
| **ComplexityAnalyzer** | Query complexity analysis | Complexity 0-1 |
| **ModelEfficiency** | Optimal model matching | Efficiency 0-100% |
| **ProductivityAnalyzer** | LOC velocity, metrics | Productivity stats |
| **RoutingQuality** | DQ score tracking | DQ average & accuracy |

### 3. ACE Consensus

**Formula**:
```
DQ_overall = (validity × 0.4) + (specificity × 0.3) + (correctness × 0.3)
Vote_weight = agent_confidence × DQ_overall

Special weights:
- Outcome detector: 2× for outcome voting
- Quality scorer: 2× for quality calculation
```

### 4. Outcome Classification

- **Success**: Git commits + high quality + completion signals
- **Abandoned**: No git commits OR session ended prematurely
- **Error**: High error rate (>50% tool failures)
- **Research**: Exploratory work, no commits, low file changes

---

## 📝 Session Naming Convention

```
YYYY-MM-DD_#NUMBER_context-keywords_id-SHORTID.jsonl

Example:
2026-01-09_#0002_replicate-readme_id-d3f00861.jsonl

Components:
- Date: Session creation date
- Number: Sequential #0001, #0002, etc.
- Context: First 4-6 keywords from first user query
- ShortID: First 8 chars of UUID for traceability
```

---

## 🔍 Understanding the Metrics

### Quality Score (1-5)

- **5**: Excellent - High LOC (100+), low errors, smooth flow, high productivity
- **4**: Good - Solid progress (20-100 LOC), minor issues
- **3**: Fair - Moderate progress, some friction
- **2**: Poor - Limited progress, significant issues
- **1**: Very Poor - No meaningful progress, high errors

**Factors**:
- File changes (0-2 points)
- LOC changed (0-1 point)
- Tool success rate (0-1 point)
- Error count (-1 to 0 points)
- Productivity/LOC per hour (0-0.5 point)

### Complexity Score (0-1)

- **0.0-0.3**: Simple - Quick questions, lookups, simple edits
- **0.3-0.5**: Moderate - Standard coding, debugging
- **0.5-0.7**: Complex - Architecture, refactoring, multi-file
- **0.7-1.0**: Very Complex - System design, research, innovation

### Model Efficiency (0-100%)

- **90-100%**: Optimal - Right model for complexity
- **70-90%**: Good - Slight over/under-provisioning
- **50-70%**: Moderate - Noticeable inefficiency
- **0-50%**: Poor - Significant over/under-provisioning

---

## 🎯 Common Tasks

### Analyze a Recent Session

```bash
# Get session ID from recent work
SESSION_ID="your-session-uuid"

# Run analysis
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --session-id "$SESSION_ID"

# Check results
tail -1 ~/.claude/data/session-outcomes.jsonl | jq '.'
```

### Batch Process Remaining Sessions

```bash
# See what would happen (dry run)
python3 ~/.claude/scripts/observatory/batch-process-all-sessions.py --dry-run

# Process first 10
python3 ~/.claude/scripts/observatory/batch-process-all-sessions.py --limit 10

# Process all
python3 ~/.claude/scripts/observatory/batch-process-all-sessions.py
```

### View QA Report

```bash
# View full QA report
cat ~/.claude/data/qa-test-report.md

# Run QA tests again
python3 ~/.claude/scripts/observatory/qa-test-suite.py
```

### Start Dashboard Server

```bash
# Start server in background
cd ~/.claude/scripts/observatory
python3 api-server.py > /tmp/dashboard-api.log 2>&1 &

# Open dashboard
open "http://127.0.0.1:8888/autonomous-analysis-dashboard.html"

# Check server logs
tail -f /tmp/dashboard-api.log
```

---

## 🗂️ File Locations

### Data Files
- `~/.claude/data/session-outcomes.jsonl` - All analysis results
- `~/.claude/data/empty-sessions-archive/` - Archived empty sessions
- `~/.claude/data/qa-test-report.md` - Latest QA report

### Session Files
- `~/.claude/projects/*/YYYY-MM-DD_#NNNN_*.jsonl` - Session transcripts
- `~/.claude/projects/*/YYYY-MM-DD_#NNNN_*.summary.md` - Session summaries

### System Files
- `~/.claude/scripts/observatory/post-session-analyzer.py` - Main orchestrator
- `~/.claude/scripts/observatory/agents/` - 6 analysis agents
- `~/.claude/scripts/observatory/ace_consensus.py` - ACE engine
- `~/.claude/scripts/observatory/session_summarizer.py` - Summary generator
- `~/.claude/scripts/observatory/api-server.py` - Dashboard API server
- `~/.claude/scripts/autonomous-analysis-dashboard.html` - Dashboard UI

---

## 🐛 Troubleshooting

### Dashboard Not Loading Data

```bash
# Check if API server is running
ps aux | grep api-server

# Check API endpoint
curl http://127.0.0.1:8888/api/sessions | head -c 100

# Restart server
pkill -f api-server
cd ~/.claude/scripts/observatory && python3 api-server.py &
```

### "Address already in use" Error

```bash
# Find process using port 8888
lsof -i :8888

# Kill the process
kill -9 <PID>

# Restart server
python3 ~/.claude/scripts/observatory/api-server.py
```

### Session Analysis Fails

```bash
# Check if session file exists
ls ~/.claude/projects/*/*-id-SHORTID.jsonl

# Try analyzing with verbose output
python3 ~/.claude/scripts/observatory/post-session-analyzer.py \
  --session-id "SESSION_ID" 2>&1 | tee /tmp/analysis-debug.log
```

### Dashboard Shows Old Data

```bash
# Force refresh in browser (Cmd+Shift+R on Mac)
# Or clear browser cache

# Check JSONL has latest data
tail -5 ~/.claude/data/session-outcomes.jsonl
```

---

## 📚 Additional Documentation

- **Full System Documentation**: See plan file at `~/.claude/plans/atomic-squishing-curry.md`
- **QA Test Report**: `~/.claude/data/qa-test-report.md`
- **Agent Documentation**: See docstrings in `~/.claude/scripts/observatory/agents/*.py`

---

## ✅ System Status

**Current Status**: ✅ FULLY OPERATIONAL

**Last QA Test**: 2026-01-19
**Pass Rate**: 92.3% (24/26 tests)
**Sessions Analyzed**: 146
**Dashboard**: http://127.0.0.1:8888/autonomous-analysis-dashboard.html

---

**Questions?** Check the QA report or examine agent code for implementation details.
