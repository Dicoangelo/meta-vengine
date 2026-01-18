#!/bin/bash
# Auto-log session summary to project SESSION_LOG.md

PROJECT_DIR="$1"
SUMMARY="$2"
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H:%M)

# Default to OS-App if no project specified
if [ -z "$PROJECT_DIR" ]; then
    PROJECT_DIR="$HOME/Desktop/OS-App"
fi

LOG_FILE="$PROJECT_DIR/SESSION_LOG.md"

# Only log if SESSION_LOG.md exists in project
if [ -f "$LOG_FILE" ]; then
    echo "" >> "$LOG_FILE"
    echo "---" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
    echo "## $DATE @ $TIME" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    if [ -n "$SUMMARY" ]; then
        echo "$SUMMARY" >> "$LOG_FILE"
    else
        echo "**Session ended** (no summary provided)" >> "$LOG_FILE"
    fi

    echo "" >> "$LOG_FILE"
    echo "Session logged to $LOG_FILE"
else
    echo "No SESSION_LOG.md found in $PROJECT_DIR"
fi
