"""
tests/unit/test_habit_nudge.py
------------------------------
Unit test suite for HabitNudgeEngine (Habit-Breaking Voice Nudge).
"""

import pytest
from unittest.mock import MagicMock
from fluid_voice.habit_nudge import HabitNudgeEngine


def test_habit_nudge_initialization():
    """Verifies HabitNudgeEngine instantiation and defaults."""
    nudge = HabitNudgeEngine(key_threshold=5)
    assert nudge.key_threshold == 5
    assert nudge._key_count == 0
    assert nudge._nudge_shown is False


def test_habit_nudge_trigger_threshold():
    """Verifies that nudge trigger fires once key count exceeds threshold."""
    callback = MagicMock()
    nudge = HabitNudgeEngine(key_threshold=5, on_nudge_trigger=callback)

    # Simulate 5 keypresses
    for _ in range(5):
        nudge._on_key_press("a")

    assert callback.call_count == 1
    assert nudge._nudge_shown is True

    # Simulate 5 more keypresses (should NOT trigger again - no spam)
    for _ in range(5):
        nudge._on_key_press("b")

    assert callback.call_count == 1


def test_habit_nudge_reset_on_voice_dictation():
    """Verifies that reset_nudge_state allows nudge to trigger again on subsequent manual typing."""
    callback = MagicMock()
    nudge = HabitNudgeEngine(key_threshold=5, on_nudge_trigger=callback)

    # First typing run
    for _ in range(5):
        nudge._on_key_press("a")
    assert callback.call_count == 1

    # User uses Alt+S Voice Dictation -> resets nudge state
    nudge.reset_nudge_state()
    assert nudge._nudge_shown is False

    # Second typing run -> triggers once more
    for _ in range(5):
        nudge._on_key_press("b")
    assert callback.call_count == 2
