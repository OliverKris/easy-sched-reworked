"""Applicant-side models: who they are, what they've taken, taught, and
who has recommended them, plus their upcoming sechdule (used for conflict
checking against sections they'd TA/LA for)."""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .enums import Grade, PositionType, Semester
from .scheduling import TimeSlot


@dataclass
class PastCourseRecord:
    """A course the applicant has already completed."""
    course_id: str
    grade: Grade
    term: Semester
    year: int

    def __str__(self):
        return f"{self.course_id}: {self.grade.name} ({self.term.value} {self.year})"


@dataclass
class TeachingExperienceRecord:
    """A prior LA/UTA position the applicant has held."""
    course_id: str
    position: PositionType
    term: Semester
    year: int
    supervisor_rating: Optional[float] = None

    def __str__(self):
        rating = f", rating={self.supervisor_rating}" if self.supervisor_rating else ""
        return f"{self.position.value} for {self.course_id} ({self.term.value} {self.year}){rating}"


@dataclass
class Recommendation:
    """A faculty reference backing the applicant."""
    faculty_name: str
    course_id: Optional[str] = None     # Course the recommendation is tied to, if any
    strength: float = 3.0               # e.g. 1 (weak) - 5 (stronest)
    note: str = ""

    def __str__(self):
        tie = f" (re: {self.course_id})" if self.course_id else ""
        return f"{self.faculty_name}{tie}, strength={self.strength}"


@dataclass
class Applicant:
    """An undergraduate CS student applying for LA/UTA positions."""
    applicant_id: str
    name: str
    email: str

    past_courses: List[PastCourseRecord] = field(default_factory=list)
    teaching_experience: List[TeachingExperienceRecord] = field(default_factory=list)
    recommendations: List[Recommendation] = field(default_factory=list)

    # the applicant's own upcoming-term commitments (their classes, etc.),
    # used to detect conflicts with a section's lecture/lab meeting times.
    upcoming_schedule: List[TimeSlot] = field(default_factory=list)

    # Free-form skill tags (languages/topics they're strong in), used for
    # skill-matching against a Course's `skills` set in scoring.
    skills: Set[str] = field(default_factory=set)

    # --- Helpers ---
    def has_taken(self, course_id: str) -> Optional[PastCourseRecord]:
        """Returns the PastCourseRecord for course_id if the applicant took
        it and passed (grade > F), else None."""
        for rec in self.past_courses:
            if rec.course_id == course_id and rec.grade > Grade.F:
                return rec
        return None

    def grade_in(self, course_id: str) -> Optional[Grade]:
        rec = self.has_taken(course_id)
        return rec.grade if rec else None

    def prior_positions_count(self, position: Optional[PositionType] = None) -> int:
        if position is None:
            return len(self.teaching_experience)
        return sum(1 for t in self.teaching_experience if t.position == position)

    def has_taught(self, course_id: str) -> bool:
        return any(t.course_id == course_id for t in self.teaching_experience)

    @property
    def overall_gpa(self) -> Optional[float]:
        """Simple (unweighted, since we don't track credit hours) average
        GPA across completed courses. Returns None if the applicant has no
        completed (graded) courses on record."""
        completed = [r for r in self.past_courses if r.grade != Grade.IN_PROGRESS]
        if not completed:
            return None
        return sum(r.grade.gpa_points for r in completed) / len(completed)

    def __str__(self):
        return f"{self.name} ({self.applicant_id})"