"""Course catalog and section (lecture + lab) models.

A `Course` is a catalog entry (e.g. "CSCI 1202 - Program Design and Data
Structures I"). A `Section` is one offering of that course in a given term
(e.g. Fall 2026, Section 10), and bundles together the lecture meeting
time(s) and the individual lab sub-sections students/TAs attach to.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .enums import PositionType, Semester
from .scheduling import TimeSlot



@dataclass
class Course:
    """A catalog course, independent of term (e.g. CSCI 1012)."""
    course_id: str          # e.g. "CSCI 1012"
    title: str              # e.g. "Program Design and Data Structures I"
    description: str = ""
    # Rough topical tags used for skill-matching in scoring (e.g. "java",
    # 'recursion', 'data-structures' 'systems', 'python').
    skills: Set[str] = field(default_factory=set)

    def __hash__(self):
        return hash(self.course_id)

    def __str__(self):
        return f"{self.course_id}: {self.title}" 



@dataclass
class LabSection:
    """One lab meeting option attached to a course Section.

    Students/prospective TAs are typically enrolled in exactly one of there 
    per course section; an applicant only needs to be conflict-free with
    ONE LabSection to satisfy the "must attend a lab" eligibility rule.
    """
    lab_id: str         # e.g. "Lab 10"
    meetings: List[TimeSlot] = field(default_factory=list)
    capacity: Optional[int] = None

    def __str__(self):
        times = ", ".join(str(m) for m in self.meetings)
        return f"{self.lab_id} ({times})"
    


@dataclass
class PositionRequirement:
    """How many LA/UTA slots a section needs, and the rules for each.

    Defaults are 2 LAs + 1 UTA,
    LAs work ~5 hrs/wk helping, UTAs work ~10 hrs/wk leading labs, and
    UTA lecture attendance is professor-dependent.
    """
    la_count: int = 2
    uta_count: int = 1
    la_hours_per_week: float = 5.0
    uta_hours_per_week: float = 10.0
    # Some professors require UTAs (not LAs) to also attend lecture
    uta_must_attend_lecture: bool = False
    la_must_attend_lecture: bool = False

    def count_for(self, position: PositionType) -> int:
        return self.la_count if position == PositionType.LA else self.uta_count
    
    def hours_for(self, position: PositionType) -> float:
        return self.la_hours_per_week if position == PositionType.LA else self.uta_hours_per_week

    def must_attend_lecture(self, position: PositionType) -> bool:
        return self.la_must_attend_lecture if position == PositionType.LA else self.uta_must_attend_lecture



@dataclass
class Section:
    """One term offering of a Course: a lecture plus its lab sub-sections"""
    course: Course
    section_number: str
    term: Semester
    year: int
    instructor: str = ""
    lecture_meetings: List[TimeSlot] = field(default_factory=list)
    labs: List[LabSection] = field(default_factory=list)
    position_requirements: PositionRequirement = field(default_factory=PositionRequirement)

    @property
    def section_id(self) -> str:
        return f"{self.course.course_id}-{self.section_number} ({self.term.value} {self.year})"

    def total_positions_needed(self) -> int:
        return self.position_requirements.la_count + self.position_requirements.uta_count

    def __str__(self):
        return self.section_id