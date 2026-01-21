#!/usr/bin/env python3
"""
Supermemory CLI - Unified intelligent memory layer

Usage:
    supermemory search "query"     # Hybrid search across all memory
    supermemory rollup             # Generate weekly rollup
    supermemory project os-app     # Show project memory
    supermemory inject             # Inject relevant context
    supermemory errors "text"      # Find past error solutions
    supermemory review             # Spaced repetition review
    supermemory sync               # Rebuild indexes
    supermemory stats              # System statistics
"""

import argparse
import sys
from pathlib import Path

# Add supermemory to path
SUPERMEMORY_DIR = Path(__file__).parent
sys.path.insert(0, str(SUPERMEMORY_DIR))

from storage.index_db import MemoryDB
from core.search_engine import SearchEngine
from core.rollup_generator import RollupGenerator
from core.spaced_repetition import SpacedRepetition
from core.unified_index import UnifiedIndex
from extractors.learning_extractor import LearningExtractor
from extractors.error_extractor import ErrorExtractor
from injectors.session_injector import SessionInjector
from aggregators.project_aggregator import ProjectAggregator


def cmd_search(args):
    """Search across all memory sources."""
    engine = SearchEngine()
    results = engine.search(args.query, limit=args.limit)

    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, 1):
        score = result.get('score', 0)
        source = result.get('source', 'unknown')
        content = result.get('content', '')[:200]
        date = result.get('date', '')

        print(f"\n{i}. [{source}] {date} (score: {score:.2f})")
        print(f"   {content}...")


def cmd_rollup(args):
    """Generate weekly/monthly rollups."""
    generator = RollupGenerator()

    if args.week:
        result = generator.generate_weekly(args.week)
    elif args.month:
        result = generator.generate_monthly(args.month)
    else:
        result = generator.generate_current_week()

    if result:
        print(f"Generated rollup: {result}")
    else:
        print("No data available for rollup.")


def cmd_project(args):
    """Show project-specific memory."""
    aggregator = ProjectAggregator()
    memory = aggregator.get_project_memory(args.name)

    if not memory:
        print(f"No memory found for project: {args.name}")
        return

    print(f"\n# Project Memory: {args.name}\n")
    print(memory)


def cmd_inject(args):
    """Inject relevant context for current session."""
    injector = SessionInjector()
    context = injector.get_injection_context(args.project)

    if context:
        print(context)
    else:
        print("No relevant context to inject.")


def cmd_errors(args):
    """Find past error solutions."""
    extractor = ErrorExtractor()
    solutions = extractor.find_solutions(args.text)

    if not solutions:
        print("No matching error patterns found.")
        return

    print("\n## Similar Errors & Solutions\n")
    for sol in solutions:
        print(f"### {sol['category']} ({sol['count']} occurrences)")
        print(f"Pattern: {sol['pattern']}")
        if sol.get('solution'):
            print(f"Solution: {sol['solution']}")
        print()


def cmd_review(args):
    """Spaced repetition review session."""
    sr = SpacedRepetition()
    items = sr.get_due_items(limit=args.limit)

    if not items:
        print("No items due for review. Great job!")
        return

    print(f"\n## Review Session ({len(items)} items)\n")

    for i, item in enumerate(items, 1):
        print(f"\n--- Item {i}/{len(items)} ---")
        print(f"\n{item['content']}\n")

        while True:
            response = input("Rate (1=forgot, 2=hard, 3=good, 4=easy, s=skip, q=quit): ").strip().lower()
            if response == 'q':
                print("Review session ended.")
                return
            if response == 's':
                break
            if response in ['1', '2', '3', '4']:
                sr.record_review(item['id'], int(response))
                print("✓ Recorded")
                break


def cmd_sync(args):
    """Rebuild all indexes from source data."""
    print("Syncing supermemory indexes...")

    index = UnifiedIndex()
    stats = index.rebuild_all()

    print(f"\n✓ Sync complete:")
    print(f"  - Memory items: {stats.get('memory_items', 0)}")
    print(f"  - Learnings: {stats.get('learnings', 0)}")
    print(f"  - Error patterns: {stats.get('error_patterns', 0)}")
    print(f"  - Review items: {stats.get('review_items', 0)}")


def cmd_stats(args):
    """Show system statistics."""
    db = MemoryDB()
    stats = db.get_stats()

    print("\n## Supermemory Statistics\n")
    print(f"Memory Items:    {stats.get('memory_items', 0):,}")
    print(f"Learnings:       {stats.get('learnings', 0):,}")
    print(f"Error Patterns:  {stats.get('error_patterns', 0):,}")
    print(f"Review Items:    {stats.get('review_items', 0):,}")
    print(f"Memory Links:    {stats.get('memory_links', 0):,}")
    print(f"\nDatabase Size:   {stats.get('db_size_mb', 0):.2f} MB")

    # Show project breakdown
    projects = stats.get('projects', {})
    if projects:
        print("\n### By Project")
        for proj, count in sorted(projects.items(), key=lambda x: -x[1]):
            print(f"  {proj}: {count:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Supermemory - Unified intelligent memory layer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # search
    p_search = subparsers.add_parser('search', help='Hybrid search across all memory')
    p_search.add_argument('query', help='Search query')
    p_search.add_argument('-n', '--limit', type=int, default=10, help='Max results')
    p_search.set_defaults(func=cmd_search)

    # rollup
    p_rollup = subparsers.add_parser('rollup', help='Generate weekly/monthly rollups')
    p_rollup.add_argument('--week', help='Week in ISO format (e.g., 2026-W03)')
    p_rollup.add_argument('--month', help='Month (e.g., 2026-01)')
    p_rollup.set_defaults(func=cmd_rollup)

    # project
    p_project = subparsers.add_parser('project', help='Show project memory')
    p_project.add_argument('name', help='Project name (e.g., os-app)')
    p_project.set_defaults(func=cmd_project)

    # inject
    p_inject = subparsers.add_parser('inject', help='Inject relevant context')
    p_inject.add_argument('--project', help='Override project detection')
    p_inject.set_defaults(func=cmd_inject)

    # errors
    p_errors = subparsers.add_parser('errors', help='Find past error solutions')
    p_errors.add_argument('text', help='Error text to search')
    p_errors.set_defaults(func=cmd_errors)

    # review
    p_review = subparsers.add_parser('review', help='Spaced repetition review')
    p_review.add_argument('-n', '--limit', type=int, default=5, help='Items per session')
    p_review.set_defaults(func=cmd_review)

    # sync
    p_sync = subparsers.add_parser('sync', help='Rebuild indexes')
    p_sync.set_defaults(func=cmd_sync)

    # stats
    p_stats = subparsers.add_parser('stats', help='System statistics')
    p_stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == '__main__':
    main()
