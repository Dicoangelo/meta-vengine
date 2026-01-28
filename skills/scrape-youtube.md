---
name: scrape-youtube
description: Scrape YouTube channel videos with metadata for research tracking
---

# YouTube Channel Scraper

When the user runs `/scrape-youtube`, help them scrape a YouTube channel's videos and metadata into the ResearchGravity system.

## Interactive Flow

1. **Get the channel** (if not provided as argument):
   - Ask: "Which YouTube channel? (provide @handle or full URL)"
   - Parse input to extract handle

2. **Ask for research classification** (optional, show defaults):
   - Tier: 1 (primary sources), 2 (amplifiers - default), or 3 (context)?
   - Category: labs, research, industry, video (default), education?
   - Limit: Max videos to fetch? (default: all)

3. **Check for active research session**:
   ```bash
   cd ~/researchgravity && python3 status.py
   ```
   - If session active, ask: "Add to current research session?"

4. **Run the scraper**:
   ```bash
   cd ~/researchgravity && python3 youtube_channel.py @HANDLE \
     --tier TIER \
     --category CATEGORY \
     [--limit LIMIT] \
     [--log-to-session]
   ```

5. **Show results summary**:
   - Read the generated `full.json` file
   - Display:
     - Channel name
     - Total videos scraped
     - Top 3 videos by views (title, views, duration, URL)
     - File locations

6. **Confirm completion**:
   ```
   ✅ Scraped N videos from @ChannelName

   Files saved:
   - ~/.agent-core/research/youtube/HANDLE/urls.txt
   - ~/.agent-core/research/youtube/HANDLE/videos.txt
   - ~/.agent-core/research/youtube/HANDLE/full.json

   Top videos:
   1. [Title] - [views] views - [duration]
   2. [Title] - [views] views - [duration]
   3. [Title] - [views] views - [duration]
   ```

## Usage Examples

```bash
/scrape-youtube @NateBJones
/scrape-youtube https://youtube.com/@anthropic --tier 1
/scrape-youtube @3blue1brown --limit 100
```

## Arguments

- `@handle` or URL: Channel to scrape (can be provided inline)
- `--tier N`: Research tier (1-3, default: 2)
- `--category X`: Category (labs/research/industry/video/education, default: video)
- `--limit N`: Max videos (default: all)
- `--session`: Force add to research session

## Smart Defaults

- Tier 2 (amplifiers) for most channels
- Category "video" unless specified
- Auto-detect research session and offer to log
- Fetch all videos unless limited

## Error Handling

If the scraper fails:
- Check API key exists: `~/.agent-core/config.json`
- Verify channel handle is correct
- Check API quota (free tier: limited requests/day)
- Show helpful error message with troubleshooting steps

## Output Files Location

All files go to: `~/.agent-core/research/youtube/CHANNEL_HANDLE/`

- **urls.txt** - One URL per line (batch processing)
- **videos.txt** - Human-readable list with dates and titles
- **full.json** - Complete metadata (views, likes, comments, duration)
