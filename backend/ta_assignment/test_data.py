"""Preset demo data modeled loosely on GW's CS course sequence, so you can
load a working scenario without hand-building objects.

NOTE: Course numbers/titles below are illustrative placeholders based on the
general shape of GW's CS curriculum (intro programming -> data structures ->
systems/theory -> upper-level electives). Double check exact course numbers,
titles, and prerequisite chains against the current GW Bulletin before using
this for anything beyond development/testing.
"""

from datetime import time

from .applicants import Applicant, PastCourseRecord, TeachingExperienceRecord, Recommendation
from .applications import Application, CoursePreference
from .courses import Course, LabSection, Section, PositionRequirement
from .enums import Day, Grade, PositionType, Semester
from .scheduling import TimeSlot


# ---------------------------------------------------------------------------
# 1. Course catalog
# ---------------------------------------------------------------------------

COURSES = {
    "CSCI 1010": Course("CSCI 1010", "Introduction to Computer Science I",
                         skills={"python", "intro-programming"}),
    "CSCI 1011": Course("CSCI 1011", "Introduction to Computer Science II",
                         skills={"python", "recursion", "oop"}),
    "CSCI 1012": Course("CSCI 1012", "Program Design and Data Structures I",
                         skills={"java", "data-structures", "oop"}),
    "CSCI 1013": Course("CSCI 1013", "Program Design and Data Structures II",
                         skills={"java", "data-structures", "algorithms"}),
    "CSCI 2113": Course("CSCI 2113", "Program Design and Development",
                         skills={"c", "systems", "memory-management"}),
    "CSCI 2461": Course("CSCI 2461", "Software Paradigms",
                         skills={"functional-programming", "prolog", "haskell"}),
    "CSCI 3212": Course("CSCI 3212", "Algorithms",
                         skills={"algorithms", "proofs", "complexity-analysis"}),
    "CSCI 3411": Course("CSCI 3411", "Systems Programming",
                         skills={"c", "unix", "systems"}),
}


# ---------------------------------------------------------------------------
# 2. Sections (one term: Fall 2026)
# ---------------------------------------------------------------------------

def _mw(start_h, start_m, end_h, end_m, label=""):
    return [
        TimeSlot(Day.MON, time(start_h, start_m), time(end_h, end_m), label),
        TimeSlot(Day.WED, time(start_h, start_m), time(end_h, end_m), label),
    ]


SECTIONS = [
    Section(
        course=COURSES["CSCI 1012"],
        section_number="10",
        term=Semester.FALL,
        year=2026,
        instructor="Prof. Alvarado",
        lecture_meetings=_mw(9, 35, 10, 50, "CSCI 1012-10 Lecture"),
        labs=[
            LabSection("Lab A", [TimeSlot(Day.FRI, time(11, 10), time(13, 0), "1012 Lab A")]),
            LabSection("Lab B", [TimeSlot(Day.FRI, time(13, 10), time(15, 0), "1012 Lab B")]),
        ],
        position_requirements=PositionRequirement(
            la_count=2, uta_count=1, uta_must_attend_lecture=False,
        ),
    ),
    Section(
        course=COURSES["CSCI 1013"],
        section_number="10",
        term=Semester.FALL,
        year=2026,
        instructor="Prof. Chen",
        lecture_meetings=_mw(11, 10, 12, 25, "CSCI 1013-10 Lecture"),
        labs=[
            LabSection("Lab A", [TimeSlot(Day.THU, time(9, 35), time(11, 25), "1013 Lab A")]),
        ],
        position_requirements=PositionRequirement(
            la_count=2, uta_count=1, uta_must_attend_lecture=True,  # this prof requires it
        ),
    ),
    Section(
        course=COURSES["CSCI 2113"],
        section_number="11",
        term=Semester.FALL,
        year=2026,
        instructor="Prof. Okafor",
        lecture_meetings=_mw(12, 45, 14, 0, "CSCI 2113-11 Lecture"),
        labs=[
            LabSection("Lab A", [TimeSlot(Day.TUE, time(15, 10), time(17, 0), "2113 Lab A")]),
            LabSection("Lab B", [TimeSlot(Day.WED, time(15, 10), time(17, 0), "2113 Lab B")]),
        ],
        position_requirements=PositionRequirement(la_count=1, uta_count=1),
    ),
    Section(
        course=COURSES["CSCI 3212"],
        section_number="10",
        term=Semester.FALL,
        year=2026,
        instructor="Prof. Kim",
        lecture_meetings=_mw(14, 10, 15, 25, "CSCI 3212-10 Lecture"),
        labs=[
            LabSection("Lab A", [TimeSlot(Day.FRI, time(9, 35), time(11, 25), "3212 Lab A")]),
        ],
        position_requirements=PositionRequirement(la_count=0, uta_count=2, uta_must_attend_lecture=True),
    ),
]


# ---------------------------------------------------------------------------
# 3. Applicants
# ---------------------------------------------------------------------------

APPLICANTS = {
    "A001": Applicant(
        applicant_id="A001", name="Priya Sharma", email="psharma@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1010", Grade.A, Semester.FALL, 2024),
            PastCourseRecord("CSCI 1011", Grade.A_MINUS, Semester.SPRING, 2025),
            PastCourseRecord("CSCI 1012", Grade.A, Semester.FALL, 2025),
        ],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 1010", PositionType.LA, Semester.SPRING, 2025, supervisor_rating=4.5),
            TeachingExperienceRecord("CSCI 1011", PositionType.LA, Semester.FALL, 2025, supervisor_rating=4.8),
        ],
        recommendations=[Recommendation("Prof. Alvarado", "CSCI 1012", strength=4.5)],
        upcoming_schedule=[
            TimeSlot(Day.TUE, time(9, 35), time(10, 50), "Priya's own class"),
        ],
        skills={"java", "data-structures", "python"},
    ),
    "A002": Applicant(
        applicant_id="A002", name="Marcus Lee", email="mlee@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1010", Grade.B_PLUS, Semester.FALL, 2024),
            PastCourseRecord("CSCI 1011", Grade.B, Semester.SPRING, 2025),
            PastCourseRecord("CSCI 1012", Grade.A_MINUS, Semester.FALL, 2025),
            PastCourseRecord("CSCI 1013", Grade.B_PLUS, Semester.SPRING, 2026),
        ],
        teaching_experience=[],  # first-time applicant
        recommendations=[Recommendation("Prof. Chen", "CSCI 1013", strength=4.0)],
        upcoming_schedule=[
            TimeSlot(Day.MON, time(9, 35), time(10, 50), "conflicts with 1012 lecture"),
        ],
        skills={"java", "algorithms"},
    ),
    "A003": Applicant(
        applicant_id="A003", name="Sofia Ibrahim", email="sibrahim@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.A, Semester.SPRING, 2024),
            PastCourseRecord("CSCI 1013", Grade.A, Semester.FALL, 2024),
            PastCourseRecord("CSCI 2113", Grade.A_MINUS, Semester.SPRING, 2025),
        ],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 1012", PositionType.LA, Semester.FALL, 2024, supervisor_rating=4.9),
            TeachingExperienceRecord("CSCI 1012", PositionType.LA, Semester.SPRING, 2025, supervisor_rating=5.0),
        ],
        recommendations=[
            Recommendation("Prof. Alvarado", "CSCI 1012", strength=5.0),
            Recommendation("Prof. Okafor", "CSCI 2113", strength=4.7),
        ],
        upcoming_schedule=[],  # conveniently free
        skills={"java", "c", "systems", "data-structures"},
    ),
    "A004": Applicant(
        applicant_id="A004", name="Devon Walker", email="dwalker@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.C_PLUS, Semester.FALL, 2025),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[
            TimeSlot(Day.FRI, time(11, 10), time(13, 0), "conflicts with Lab A"),
            TimeSlot(Day.FRI, time(13, 10), time(15, 0), "conflicts with Lab B too"),
        ],
        skills={"java"},
    ),
}


# ---------------------------------------------------------------------------
# 4. Applications
# ---------------------------------------------------------------------------

APPLICATIONS = [
    Application(
        applicant_id="A001", term=Semester.FALL, year=2026,
        position_types={PositionType.LA, PositionType.UTA},
        ranked_preferences=[
            CoursePreference("CSCI 1012", 1),
            CoursePreference("CSCI 1013", 2),
        ],
    ),
    Application(
        applicant_id="A002", term=Semester.FALL, year=2026,
        position_types={PositionType.LA},
        ranked_preferences=[
            CoursePreference("CSCI 1013", 1),
        ],
    ),
    Application(
        applicant_id="A003", term=Semester.FALL, year=2026,
        position_types={PositionType.UTA},
        ranked_preferences=[
            CoursePreference("CSCI 1012", 1),
            CoursePreference("CSCI 2113", 2),
        ],
    ),
    Application(
        applicant_id="A004", term=Semester.FALL, year=2026,
        position_types={PositionType.LA},
        ranked_preferences=[
            CoursePreference("CSCI 1012", 1),
        ],
    ),
]


def load_demo_data():
    """Convenience loader returning (courses, sections, applicants, applications)."""
    return COURSES, SECTIONS, APPLICANTS, APPLICATIONS