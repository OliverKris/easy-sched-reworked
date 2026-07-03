"""Core enumerations shared across the TA/LA assignment models."""

from enum import Enum, auto

class PositionType(Enum):
    """The two undergraduate teaching positions"""
    LA = 'Learning Assistant'   # Helps run labs, holds office hours, ~5 hrs/wk               
    UTA = 'Undergraduate TA'    # Leads labs, holds office hours, ~10 hrs/wk


class MeetingType(Enum):
    LECTURE = "Lecture"
    LAB = "Lab"


class Day(Enum):
    MON = "Monday"
    TUE = "Tuesday"
    WED = "Wednesday"
    THU = "Thursday"
    FRI = "Friday"


class Semester(Enum):
    FALL = "Fall"
    SPRING = "Spring"


class Grade(Enum):
    """Letter grades, orders so they can be compared (A > A- > B+ ...)."""
    A = 12
    A_MINUS = 11
    B_PLUS = 10
    B = 9
    B_MINUS = 8
    C_PLUS = 7
    C = 6
    C_MINUS = 5
    D_PLUS = 4
    D = 3
    D_MINUS = 2
    F = 1
    IN_PROGRESS = 0 # Currently enrolled, no grade

    def __lt__(self, other):
        if not isinstance(other, Grade):
            return NotImplemented
        return self.value < other.value

    def __le__(self, other):
        if not isinstance(other, Grade):
            return NotImplemented
        return self.value <= other.value

    def __gt__(self, other):
        if not isinstance(other, Grade):
            return NotImplemented
        return self.value > other.value

    def __ge__(self, other):
        if not isinstance(other, Grade):
            return NotImplemented
        return self.value >= other.value

    @property
    def gpa_points(self) -> float:
        """Standard 4.0-scale GPA points for scoring"""
        mapping = {
            Grade.A: 4.0, Grade.A_MINUS: 3.7,
            Grade.B_PLUS: 3.3, Grade.B: 3.0, Grade.B_MINUS: 2.7,
            Grade.C_PLUS: 2.3, Grade.C: 2.0, Grade.C_MINUS: 1.7,
            Grade.D_PLUS: 1.3, Grade.D: 1.0, Grade.D_MINUS: 0.7,
            Grade.F: 0.0, Grade.IN_PROGRESS: 0.0,
        }
        return mapping[self]