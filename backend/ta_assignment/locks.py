"""Amdmin-placed constraints layered on top of the CSP solver's automated
eligibility/scoring:

    - LOCKED pins an applicant into a (section, position) regardless of
      score -- and regardless of eligibility, too. An admin lock is a 
      deliberate override of the algorithm's judgement, not another vote
      that has to win a scoring contest.
    - BLOCKED forbids an applicant from ever being placed into a
    (section, position), no matter how well they'd otherwise score there.
    
Locks/blocks apply at the (section, position) level, not to a specific
slot_index: slots for the same section+position are interchangeable (see
csp_solver.py's SlotSpec docstring), so "lock this person into UTA#1
specifically" isn't a distinction admins need to make -- "lock them into
a UTA slot for this section" is.
"""

from dataclasses import dataclass
from enum import Enum

from .enums import PositionType


class LockType(Enum):
    LOCKED = "locked"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Lock:
    applicant_id: str
    section_id: str     # matches Section.section_id, e.g. "CSCI 1012-10 (Fall 2026)"
    position: PositionType
    lock_type: LockType

    def __str__(self):
        verb = "LOCKED into" if self.lock_type == LockType.LOCKED else "BLOCKED from"
        return f"{self.applicant_id} {verb} {self.section_id} ({self.position.name})"