---
name: history
description: Export Chrome browsing history to NotebookLM-ready format
---

# Chrome History Export Skill

Export today's Chrome browsing history with detailed analytics for NotebookLM.

## What This Does

When the user runs `/history`, execute these steps:

1. **Close Chrome** (required to access the database):
```bash
pkill -f "Google Chrome" 2>/dev/null || true
sleep 2
```

2. **Run the enhanced export script**:
```bash
python3 ~/chrome-history-export-guide/scripts/export_for_notebooklm_ENHANCED.py
```

3. **Report the results** to the user:
   - File location: `~/Desktop/chrome_notebooklm/chrome_activity_[DATE]_ENHANCED.md`
   - Number of visits exported
   - Remind them to upload to https://notebooklm.google.com

## Optional Arguments

- `/history open` - Also open the output folder after export:
```bash
open ~/Desktop/chrome_notebooklm
```

- `/history today` - Export only today's history (default behavior)

## Output Includes

- Total page visits (individual, not aggregated)
- Total browsing time
- Navigation analysis (typed, clicked, back/forward)
- Time spent by category
- Top domains
- Complete chronological activity flow

## Example Questions for NotebookLM

After uploading, users can ask:
- "What was my research flow this morning?"
- "How much time did I spend on AI tools vs entertainment?"
- "Show me my complete browsing path between 5-9 AM"
- "Which pages did I spend the most time on?"
