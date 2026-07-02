from dataclasses import dataclass, field
from enum import Enum
from typing import List


class PositionType(Enum):
    LA  = "Learning Assistant"
    UTA = "Undergraduate Teaching Assistant"
    GTA = "Graduate Teaching Assistant"


# PositionRequirements must be defined before CourseRequirements references it
@dataclass
class PositionRequirements:
    position_type: PositionType
    count: int


@dataclass
class CourseRequirements:
    """TA staffing requirements for one SectionGroup (instructor + their labs)."""
    course_title: str
    instructor: str
    lecture_crn: str
    position_requirements: List[PositionRequirements] = field(default_factory=list)


@dataclass
class Assignment:
    student_id: str
    course_requirements: CourseRequirements
    position_type: PositionType
    term: str


# Default staffing counts: 2 LAs, 1 UTA, 1 GTA per section group
DEFAULT_POS_COUNTS = {
    PositionType.LA:  2,
    PositionType.UTA: 1,
    PositionType.GTA: 1,
}


def default_requirements(course_title: str, instructor: str, lecture_crn: str) -> CourseRequirements:
    return CourseRequirements(
        course_title=course_title,
        instructor=instructor,
        lecture_crn=lecture_crn,
        position_requirements=[
            PositionRequirements(position_type=pt, count=count)
            for pt, count in DEFAULT_POS_COUNTS.items()
        ],
    )
