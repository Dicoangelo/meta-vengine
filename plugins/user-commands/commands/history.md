---
description: Export Chrome browsing history for NotebookLM
allowed-tools: [Bash, Write]
---

# Chrome History Export

Export recent Chrome browsing history to a format suitable for NotebookLM.

## Steps

1. Query Chrome's History SQLite database:
```bash
sqlite3 ~/Library/Application\ Support/Google/Chrome/Default/History \
  "SELECT datetime(last_visit_time/1000000-11644473600,'unixepoch','localtime') as visit_time, url, title FROM urls ORDER BY last_visit_time DESC LIMIT 500;"
```

2. Format output as markdown with sections by date

3. Save to ~/Desktop/chrome-history-export.md

4. Confirm to user with file location
