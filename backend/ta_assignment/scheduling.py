"""Time/schedule primirtives used to detect conflicts between an applicant's
existing commitments and a course section's lecture/lab meeting times."""

from dataclasses import dataclass
from datetime import time
from typing import Iterable, List

from .enums import Day

@dataclass(frozen=True)
class TimeSlot:
    """A single recurring block of time, e.g. Mon/Wed/Fri 10:00-11:15."""
    day: Day
    start: time
    end: time
    label: str = "" # Optional, e.g. "CSCI 1012 Lecture"

    def __post_init__(self):
        if self.start >= self.end:
            raise ValueError(
                f"TimeSlot start ({self.start}) must be before end ({self.end})"
            )
    
    def overlaps(self, other: "TimeSlot") -> bool:
        """True if this slot and `other` share any time on the same day."""
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end

    def __str__(self):
        return f"{self.day.value[:3]} {self.start.strftime('%H:%M')}-{self.end.strftime('%H:%M')}"

def has_conflict(slots_a: Iterable[TimeSlot], slots_b: Iterable[TimeSlot]) -> bool:
    """True if any slot in slots_a overlap any slot in slots_b."""
    slots_a = list(slots_a)
    slots_b = list(slots_b)
    return any(a.overlaps(b) for a in slots_a for b in slots_b)

def conflicting_pairs(slots_a: Iterable[TimeSlot], slots_b: Iterable[TimeSlot]):
    """Returns the actual (a, b) slot pairs that conflict"""
    slots_a = list(slots_a)
    slots_b = list(slots_b)
    return [(a, b) for a in slots_a for b in slots_b if a.overlaps(b)]