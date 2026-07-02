from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from models.assignment import PositionType


class StudentLevel(Enum):
    UNDERGRADUATE = "Undergraduate"
    GRADUATE      = "Graduate"


# Enforce which positions each student level may apply for.
ELIGIBLE_POSITIONS = {
    StudentLevel.UNDERGRADUATE: [PositionType.LA, PositionType.UTA],
    StudentLevel.GRADUATE:      [PositionType.GTA],
}


@dataclass
class ScheduledCourse:
    """
    A course the applicant is currently enrolled in or teaching.
    Used to detect time conflicts with lecture/lab sections.
    """
    course_name: str        # e.g. "CSCI 2501"
    days: str               # e.g. "MWF", "TR"
    start_time: str         # e.g. "10:00AM"
    end_time: str           # e.g. "11:15AM"


@dataclass
class ProfessorRecommendation:
    professor_name: str
    course_taught: str      # course the professor knows the student from
    comments: Optional[str] = None


@dataclass
class CoursePreference:
    course_title: str           # e.g. "Introduction to Programming with Python"
    course_number: str          # e.g. "CSCI 1012"
    preference_rank: int        # 1 = most preferred
    prior_experience: bool = False  # has the student previously TA'd this course?


@dataclass
class StudentApplication:
    # --- Identity ---
    student_id: str
    name: str
    email: str
    student_level: StudentLevel

    # --- Term ---
    term: str               # e.g. "Fall 2024"  (matches schedule_of_classes.term)

    # --- Eligibility ---
    gpa: Optional[float]
    positions_applied: List[PositionType]   # validated against student_level on creation

    # --- Preferences ---
    preferred_courses: List[CoursePreference] = field(default_factory=list)
    skills: List[str]        = field(default_factory=list)  # e.g. ["Python", "Linux"]

    # --- Conflict detection ---
    current_schedule: List[ScheduledCourse] = field(default_factory=list)

    # --- Supporting material ---
    recommendations: List[ProfessorRecommendation] = field(default_factory=list)
    statement: Optional[str] = None

    def __post_init__(self):
        allowed = ELIGIBLE_POSITIONS[self.student_level]
        invalid = [p for p in self.positions_applied if p not in allowed]
        if invalid:
            raise ValueError(
                f"{self.student_level.value} may not apply for: "
                f"{[p.value for p in invalid]}. "
                f"Allowed: {[p.value for p in allowed]}"
            )


def has_time_conflict(app: StudentApplication, days: str, start: str, end: str) -> bool:
    """
    Return True if any course in the applicant's current_schedule overlaps
    with the given days / start / end window.

    Times are compared as naive strings in "HH:MMam/pm" format (e.g. "09:35AM").
    Days overlap when the two day strings share at least one character
    (M, T, W, R, F, S, U).
    """
    from datetime import datetime

    fmt = "%I:%M%p"

    def parse_t(t: str):
        return datetime.strptime(t.strip().upper(), fmt)

    def days_overlap(d1: str, d2: str) -> bool:
        return bool(set(d1) & set(d2))

    try:
        new_start = parse_t(start)
        new_end   = parse_t(end)
    except ValueError:
        return False    # unparseable time — assume no conflict

    for sc in app.current_schedule:
        if not days_overlap(sc.days, days):
            continue
        try:
            sc_start = parse_t(sc.start_time)
            sc_end   = parse_t(sc.end_time)
        except ValueError:
            continue
        # Overlap: not (new ends before sc starts OR new starts after sc ends)
        if not (new_end <= sc_start or new_start >= sc_end):
            return True

    return False
