#!/bin/bash
# File watcher automation
# Triggers actions when files change

# Requires: fswatch (brew install fswatch)

# Watch and auto-test on changes
watch-test() {
  local dir="${1:-.}"
  echo "👀 Watching $dir for changes (auto-test)..."
  fswatch -o "$dir" --include '\.tsx?$' --include '\.jsx?$' --exclude '.*' | while read; do
    echo "🔄 Change detected, running tests..."
    npm test 2>&1 | tail -5
  done
}

# Watch and auto-build
watch-build() {
  local dir="${1:-.}"
  echo "👀 Watching $dir for changes (auto-build)..."
  fswatch -o "$dir" --include '\.tsx?$' --include '\.jsx?$' --exclude '.*' | while read; do
    echo "🔄 Change detected, building..."
    npm run build 2>&1 | tail -5
  done
}

# Watch and notify Claude of changes (for use inside claude session)
watch-notify() {
  local dir="${1:-.}"
  echo "👀 Watching $dir - will log changes..."
  fswatch -o "$dir" | while read; do
    echo "$(date '+%H:%M:%S') FILE_CHANGE in $dir" >> ~/.claude/activity.log
  done
}
