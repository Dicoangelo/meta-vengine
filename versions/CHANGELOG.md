# CLAUDE.md Version Changelog

## [2.1.0] - 2026-01-19 - Meta-Vengine v2.0 Release

### Added - Phase 1: Adversarial ACE Agent
- New `ContrarianAgent` as 7th agent in ACE consensus pipeline
- Challenges consensus when all agents agree (groupthink detection)
- Identifies hidden assumptions in other agents' analyses
- Provides minority opinions and alternative interpretations
- Flags overconfident conclusions (>0.9 confidence threshold)

### Added - Phase 2: Prompt/Agent Versioning
- Semantic versioning for CLAUDE.md (major.minor.patch)
- `~/.claude/versions/` directory for archived versions
- `version-manager.sh` CLI for version management
- Automatic version header injection in CLAUDE.md
- Agent definition archival support
- Aliases: prompt-version, prompt-bump, prompt-rollback, prompt-diff

### Added - Phase 3: Persistent Vector Memory
- `memory-api.py` with sentence-transformers embeddings
- Semantic similarity search across knowledge.json
- Auto-embedding on persist, rebuild capability
- Fallback to keyword search when embeddings unavailable
- Memory graph linking support
- Aliases: mem-query, mem-persist, mem-rebuild, mem-stats

### Added - Phase 4: Background Agent Daemon
- `agent-runner.py` daemon with 3 autonomous agents:
  - Daily Brief Agent: Morning summaries at 8am
  - Research Crawler Agent: arXiv monitoring every 6 hours
  - Pattern Predictor Agent: Tomorrow's predictions at 11pm
- `agent-daemon.sh` management script
- Desktop notifications (macOS)
- Daily briefs saved to `~/.claude/briefs/`
- Aliases: daemon-start, daemon-stop, daemon-status, brief

### Added - Phase 5: Smart Context Compression
- `context-compressor.py` for intelligent context management
- Priority-based content selection
- Extractive summarization for long content
- Recency and relevance weighting
- Token budget enforcement (~50K default)
- Aliases: context-compress, context-estimate

### Changed
- Updated ACE consensus to include minority_opinion and assumption_risks
- Added Meta-Vengine section to init.sh with all new aliases
- Added mvhelp command for quick reference

## [2.0.0] - 2026-01-19 - Initial Versioning
- Established semantic versioning for CLAUDE.md
- Added version tracking header
- Created version-manager.sh for management

