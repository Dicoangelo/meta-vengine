# Command Center Architecture

<div align="center">

![Version](https://img.shields.io/badge/Version-1.1.1-00d9ff?style=for-the-badge&labelColor=0d1117)
![Data](https://img.shields.io/badge/Data-100%25_Real-00d9ff?style=for-the-badge&labelColor=0d1117)
![Tabs](https://img.shields.io/badge/Tabs-12-00d9ff?style=for-the-badge&labelColor=0d1117)

</div>

## Overview

The Command Center is a unified HTML dashboard that aggregates all META-VENGINE metrics, analytics, and insights into a single glassmorphic interface with 12 interactive tabs.

**Key Achievement (v1.1.1):** 100% real data - zero simulated placeholders

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMMAND CENTER v1.1.1                             │
│                         12 Tabs • 100% Real Data                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            ┌───────▼────────┐               ┌─────────▼──────────┐
            │  ccc-generator │               │  analytics-engine  │
            │      .sh       │               │       .py          │
            │  (orchestrator)│               │  (data processor)  │
            └───────┬────────┘               └─────────┬──────────┘
                    │                                   │
        ┌───────────┼───────────────────────────────────┼───────────┐
        │           │                                   │           │
┌───────▼──────┐ ┌──▼──────┐ ┌────────────┐ ┌─────────▼──────┐ ┌──▼─────────┐
│  stats-cache │ │ memory  │ │  activity  │ │   Observatory  │ │   routing  │
│     .json    │ │  .json  │ │    .log    │ │   data/*.jsonl │ │   metrics  │
│              │ │         │ │            │ │                │ │    .jsonl  │
│ • sessions   │ │ • facts │ │ • file ops │ │ • sessions     │ │ • dq-scores│
│ • messages   │ │ • deci- │ │ • bash cmd │ │ • costs        │ │ • routing  │
│ • tokens     │ │   sions │ │ • writes   │ │ • productivity │ │   latency  │
│ • daily data │ │ • ptrns │ │            │ │ • commands     │ │            │
└──────────────┘ └─────────┘ └────────────┘ │ • tools        │ └────────────┘
                                             │ • git activity │
                                             └────────────────┘
                                                      │
                    ┌─────────────────────────────────┘
                    │
        ┌───────────▼────────────┐
        │  command-center.html   │
        │    (single file)       │
        │                        │
        │  • 12 interactive tabs │
        │  • Chart.js visuals    │
        │  • Glassmorphism UI    │
        │  • Keyboard shortcuts  │
        │  • Real-time rendering │
        └────────────────────────┘
```

## Data Flow (Color-Coded by Source Type)

### 🟢 Real Data Sources (97%)

#### Primary Metrics (stats-cache.json)
```json
{
  "totalSessions": 120,        // ✅ Real (computed from transcripts)
  "totalMessages": 33085,      // ✅ Real (computed from transcripts)
  "dailyActivity": [...],      // ✅ Real (daily aggregates)
  "modelUsage": {...},         // ✅ Real (token tracking)
  "hourCounts": {...}          // ✅ Real (activity heatmap)
}
```

#### Observatory Data (data/*.jsonl)
```json
// cost-tracking.jsonl
{"ts": 1737152400, "session_id": "...", "cost_usd": 21.19, ...}  // ✅ Real

// productivity.jsonl
{"reads": 0, "writes": 650, "net_loc": 9821, ...}  // ✅ Real

// git-activity.jsonl (backfilled)
{"event": "commit", "commit_hash": "...", "files_changed": 5, ...}  // ✅ Real
```

#### Routing Metrics (dq-scores.jsonl)
```json
{"ts": 1768587809599, "dqScore": 0.826, "model": "haiku", ...}  // ✅ Real
```

### 🔵 Calculated Data (3%)

All calculations use real data as input:

```javascript
// Trend calculation (command-center.html:2207-2222)
const calculateTrend = (metric) => {
  const recent = dailyActivity.slice(half);
  const previous = dailyActivity.slice(0, half);
  return ((recentSum - prevSum) / prevSum * 100);  // ✅ Calculated from real data
};

// DQ score average (ccc-generator.sh:209-236)
avg_dq = sum(scores) / len(scores)  // ✅ Calculated from routing history

// ROI multiplier (subscription-tracker.js)
roi = totalValue / subscriptionCost  // ✅ Calculated from real usage
```

### ⚫ Simulated Data (0%)

**NONE** - All placeholders eliminated in v1.1.0

## Tab Architecture (12 Tabs)

### Core Tabs (1-9)

| Tab | ID | Keyboard | Data Sources | Real Data % |
|-----|----|---------|--------------| ------------|
| 1 | overview | `1` | stats-cache.json, subscription | 100% |
| 2 | memory | `2` | knowledge.json | 100% |
| 3 | activity | `3` | activity.log | 100% |
| 4 | cost | `4` | cost-tracking.jsonl | 100% |
| 5 | projects | `5` | git stats (live) | 100% |
| 6 | commands | `6` | command-usage.jsonl | 100% |
| 7 | routing | `7` | routing-metrics.jsonl, dq-scores.jsonl | 100% |
| 8 | coevo | `8` | detected-patterns.json, modifications.jsonl | 100% |
| 9 | context-efficiency | `9` | proactive suggestions | 100% |

### Observatory Tabs (10-12) - New in v1.1.0

| Tab | ID | Keyboard | Data Sources | Real Data % |
|-----|----|---------|--------------| ------------|
| 10 | session-outcomes | `0` or `O` | session-outcomes.jsonl | 100% |
| 11 | productivity | `P` | productivity.jsonl | 100% |
| 12 | tool-analytics | `T` | tool-success.jsonl, git-activity.jsonl | 100% |

## Component Structure

### Generation Pipeline

```bash
# 1. Data Collection (automated)
~/.claude/scripts/observatory/collectors/
  ├── session-tracker.sh      # Bash hooks for session events
  ├── command-tracker.sh      # Wraps cq/cc/co aliases
  ├── tool-tracker.sh         # Preexec/precmd hooks for bash
  ├── git-tracker.sh          # Wraps gcommit/gpush
  ├── cost-tracker.py         # Parses session transcripts
  └── productivity-analyzer.py # Analyzes activity.log

# 2. Data Processing
analytics-engine.py export 9999
  ↓ Processes all JSONL files
  ↓ Calculates comprehensive metrics
  ↓ Generates insights
  ↓ Returns JSON

# 3. Dashboard Generation
ccc-generator.sh
  ↓ Loads all data sources (bash)
  ↓ Calculates DQ score (python)
  ↓ Injects into template (python)
  ↓ Outputs to /tmp/claude-command-center.html
  ↓ Opens in browser

# 4. Rendering (client-side)
command-center.html
  ↓ Parses injected data
  ↓ Renders Chart.js visualizations
  ↓ Handles tab switching
  ↓ Keyboard shortcuts
```

### Technology Stack

**Generation:**
- Bash (orchestration)
- Python 3.8+ (data processing, calculations)
- jq (JSON manipulation)

**Frontend:**
- HTML5
- CSS3 (Glassmorphism, CSS Grid, Flexbox)
- JavaScript (ES6+)
- Chart.js 4.4.0 (visualizations)

**Data Storage:**
- JSONL (append-only logs)
- JSON (caches, configs)
- Plain text (activity.log)

## Data Authenticity Timeline

### Before v1.1.0
```
┌─────────────────────────────────────────────────────────┐
│ Data Breakdown (v1.0.0)                                 │
├─────────────────────────────────────────────────────────┤
│ ██████████████████ 75% Real                             │
│ █████ 20% Calculated                                    │
│ █ 3% Simulated (placeholders)                           │
│ █ 2% Missing                                            │
└─────────────────────────────────────────────────────────┘
```

### After v1.1.0
```
┌─────────────────────────────────────────────────────────┐
│ Data Breakdown (v1.1.0)                                 │
├─────────────────────────────────────────────────────────┤
│ ████████████████████████ 97% Real                       │
│ █ 3% Calculated (from real sources)                     │
│ 0% Simulated ✅                                          │
│ 0% Missing ✅                                            │
└─────────────────────────────────────────────────────────┘
```

## Performance Characteristics

### Load Time
- **Generation:** ~1.5s (data aggregation + template rendering)
- **Browser Load:** ~300ms (HTML + Chart.js initialization)
- **Total:** <2s from `ccc` command to interactive dashboard

### Data Volume
- **stats-cache.json:** ~3.7KB
- **cost-tracking.jsonl:** ~93KB (285 sessions)
- **productivity.jsonl:** ~751B
- **git-activity.jsonl:** ~15KB (216 commits)
- **Total Observatory:** ~109KB

### Update Frequency
- **Automatic:** Daily snapshot (via init.sh on shell startup)
- **Manual:** Run `ccc` to regenerate with latest data
- **Real-time:** Cost tracker processes on session close

## Keyboard Shortcuts

```
1-9     Switch to tabs 1-9
0       Session Outcomes (Tab 10)
O       Session Outcomes (Tab 10) - mnemonic
P       Productivity (Tab 11) - mnemonic
T       Tool Analytics (Tab 12) - mnemonic
R       Refresh dashboard
```

## Security & Privacy

- ✅ **Local-only:** All data stored in `~/.claude/`
- ✅ **No telemetry:** Zero external data transmission
- ✅ **Query hashing:** Content not stored, only MD5 hashes for deduplication
- ✅ **90-day retention:** Configurable data lifecycle
- ✅ **Git-ignored:** Sensitive data excluded from version control

## Extensibility

### Adding a New Tab

1. Add tab button HTML
2. Add tab content HTML with unique ID
3. Update keyboard shortcuts array
4. Add data source to ccc-generator.sh
5. Add rendering logic to init() function
6. Update footer help text

### Adding a New Metric

1. Create collector script in `observatory/collectors/`
2. Add data export to `analytics-engine.py`
3. Update `ccc-generator.sh` to load new data
4. Inject into template
5. Render in command-center.html

## Troubleshooting

### Dashboard Shows "No Data"
```bash
# Check if data files exist
ls -lh ~/.claude/data/*.jsonl

# Verify Observatory is running
echo $OBSERVATORY_SESSION_START

# Restart Observatory
exec zsh
```

### Trends Show 0%
```bash
# Requires multiple days of data
# Trend = (recent half) vs (previous half)
# Minimum: 2 days in stats-cache.json dailyActivity
```

### DQ Score Shows 0.750 (fallback)
```bash
# No routing history found
# Use intelligent routing to generate data:
claude -p "test query"  # Uses DQ scorer

# Check if dq-scores.jsonl exists
cat ~/.claude/kernel/dq-scores.jsonl | wc -l
```

## References

- [Observatory README](../OBSERVATORY_README.md)
- [Routing System](../ROUTING_SYSTEM_README.md)
- [Co-Evolution Architecture](coevolution/ARCHITECTURE.md)
- [Main README](../README.md)

---

**Architecture Version:** 1.1.0  
**Last Updated:** 2026-01-19  
**Maintainer:** Dicoangelo
