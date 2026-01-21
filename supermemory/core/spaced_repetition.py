#!/usr/bin/env python3
"""
Supermemory Spaced Repetition - SM-2 Algorithm Implementation

Implements the SuperMemo 2 (SM-2) algorithm for optimal learning retention.
Auto-populates from extracted learnings.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from storage.index_db import MemoryDB


class SpacedRepetition:
    """Spaced repetition system using SM-2 algorithm."""

    def __init__(self):
        self.db = MemoryDB()

    def get_due_items(self, limit: int = 10) -> list[dict]:
        """Get items due for review today or earlier."""
        return self.db.get_due_reviews(limit)

    def record_review(self, item_id: str, quality: int):
        """
        Record a review response and update scheduling.

        Args:
            item_id: ID of the review item
            quality: Response quality 0-5
                0 - Complete blackout
                1 - Incorrect, but recognized answer
                2 - Incorrect, answer easy to recall
                3 - Correct with serious difficulty
                4 - Correct with hesitation
                5 - Perfect response
        """
        # Map 1-4 scale to 0-5 for SM-2
        if quality == 1:
            q = 1  # Forgot -> map to 1
        elif quality == 2:
            q = 3  # Hard -> map to 3
        elif quality == 3:
            q = 4  # Good -> map to 4
        elif quality == 4:
            q = 5  # Easy -> map to 5
        else:
            q = quality

        # Get current item state
        items = self.db.get_due_reviews(1000)  # Get all to find this one
        item = None
        for i in items:
            if i['id'] == item_id:
                item = i
                break

        if not item:
            # Item not found in due list, try to find it anyway
            # For now, use defaults
            ease_factor = 2.5
            interval = 1
            repetitions = 0
        else:
            ease_factor = item.get('ease_factor', 2.5)
            interval = item.get('interval_days', 1)
            repetitions = item.get('repetitions', 0)

        # Apply SM-2 algorithm
        new_ef, new_interval, new_reps = self._sm2_algorithm(
            q, ease_factor, interval, repetitions
        )

        # Calculate next review date
        next_review = (datetime.now() + timedelta(days=new_interval)).strftime("%Y-%m-%d")

        # Update database
        self.db.update_review(item_id, new_ef, new_interval, new_reps, next_review)

    def _sm2_algorithm(self, quality: int, ease_factor: float,
                       interval: int, repetitions: int) -> tuple[float, int, int]:
        """
        SM-2 Algorithm implementation.

        Args:
            quality: Response quality (0-5)
            ease_factor: Current ease factor (≥1.3)
            interval: Current interval in days
            repetitions: Number of successful repetitions

        Returns:
            (new_ease_factor, new_interval, new_repetitions)
        """
        # If response was correct (quality >= 3)
        if quality >= 3:
            if repetitions == 0:
                new_interval = 1
            elif repetitions == 1:
                new_interval = 6
            else:
                new_interval = round(interval * ease_factor)

            new_repetitions = repetitions + 1
        else:
            # Incorrect response - reset
            new_interval = 1
            new_repetitions = 0

        # Update ease factor
        new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

        # Ease factor minimum
        if new_ef < 1.3:
            new_ef = 1.3

        return new_ef, new_interval, new_repetitions

    def add_item(self, content: str, category: Optional[str] = None,
                 source_id: Optional[str] = None) -> str:
        """Add a new item to the review queue."""
        return self.db.add_review_item(content, category, source_id)

    def populate_from_learnings(self, limit: int = 50):
        """Auto-populate review items from high-quality learnings."""
        learnings = self.db.get_learnings(limit=limit)

        added = 0
        for learning in learnings:
            # Only add high-quality learnings
            quality = learning.get('quality', 0)
            if quality and quality >= 4:
                self.add_item(
                    content=learning['content'],
                    category=learning.get('category'),
                    source_id=learning['id']
                )
                added += 1

        return added

    def get_stats(self) -> dict:
        """Get spaced repetition statistics."""
        items = self.db.get_due_reviews(10000)  # Get all

        today = datetime.now().strftime("%Y-%m-%d")
        due_today = sum(1 for i in items if i.get('next_review', '') <= today)
        total = len(items)

        # Calculate average ease factor
        ease_factors = [i.get('ease_factor', 2.5) for i in items]
        avg_ease = sum(ease_factors) / len(ease_factors) if ease_factors else 2.5

        # Calculate average interval
        intervals = [i.get('interval_days', 1) for i in items]
        avg_interval = sum(intervals) / len(intervals) if intervals else 1

        return {
            'total_items': total,
            'due_today': due_today,
            'avg_ease_factor': avg_ease,
            'avg_interval_days': avg_interval,
        }

    def get_upcoming_reviews(self, days: int = 7) -> dict:
        """Get review schedule for upcoming days."""
        items = self.db.get_due_reviews(10000)
        today = datetime.now()

        schedule = {}
        for i in range(days):
            date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
            schedule[date] = sum(
                1 for item in items
                if item.get('next_review', '') == date
            )

        return schedule
