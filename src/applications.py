"""An `Applicantion` is what an Applicant submits for a hiring cycle: which
position type(s) they're applyuing for (LA, UTA, or both) -- the CSP solver
will ultimately pick at most one based on their ranked course preferences."""

from dataclasses import dataclass, field
from typing import List, Set

from .enums import PositionType, Semester


@dataclass
class CoursePreference:
    """One entry in an applicant's ranked preference list.

    `rank` is 1-indexed, 1 = most preferred.
    """
    course_id: str
    rank: int


@dataclass
class Application:
    """A single applicant's application for a given hiring term."""
    applicant_id: str 
    term: Semester
    year: int

    # The position type(s) the applicant is open to. A person can list both
    # LA and UTA if they're willing to do either; the assignment algorithm
    # will settle on at most one.
    position_types: Set[PositionType] = field(default_factory=lambda: {PositionType.LA})

    ranked_preferences: List[CoursePreference] = field(default_factory=list)

    def preference_rank(self, course_id: str) -> int:
        """Returns the applicant's rank for course_id, or a large number
        (i.e. "unranked / least preferred") if they didn't list it."""
        for pref in self.ranked_preferences:
            if pref.course_id == course_id:
                return pref.rank
        return len(self.ranked_preferences) + 1

    def wants_position(self, position: PositionType) -> bool:
        return position in self.position_types

    def __str__(self):
        positions = "/".join(p.name for p in self.position_types)
        courses = ", ".join(f"{p.course_id}(#{p.rank})" for p in 
                                sorted(self.ranked_preferences, key=lambda p: p.rank))
        return f"Application[{self.applicant_id}, {positions}]: {courses}"


@dataclass
class Assignment:
    """One resolved (applicant -> section, position) assignment, i.e. a
    single filled slot in the final CSP solution."""
    applicant_id: str
    section_id: str
    position: PositionType
    score: float = 0.0

    def __str__(self):
        return f"{self.applicant_id} -> {self.section_id} as {self.position.value} (score={self.score:.2f})"