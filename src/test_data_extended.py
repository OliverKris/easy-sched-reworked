"""A larger, edge-case-oriented dataset for exercising the eligibility,
scoring, and CSP-solver logic beyond the small happy-path demo in
`test_data.py`.

Every applicant and section below is annotated with WHY it exists — what
specific rule or code path it's meant to exercise. Use `load_extended_data()`
the same way you'd use `load_demo_data()`. Import `SCENARIOS` if you want
the human-readable map of "applicant/section -> what it's testing" (handy
for building assertions in tests, or for a QA checklist in the web app).

Coverage summary:
  Eligibility (check_eligibility):
    - did-not-apply-for-position
    - never took the course / took it but failed (F)
    - GPA below floor / at floor / above floor / no completed courses (None)
    - lecture-conflict-required vs not-required
    - conflict with ALL labs vs conflict with SOME (still eligible) vs no labs at all
  Scoring (DefaultScoringStrategy):
    - grade contribution incl. no grade on record
    - teaching-experience cap at 4 priors, course-specific bonus
    - recommendation averaging, incl. zero recommendations
    - preference rank 1 vs unranked
    - skill overlap incl. course with no skills tagged
    - UTA-readiness bonus (>=2 prior LA terms)
    - two applicants who should score EXACTLY equal, to test tie-break
      determinism (solver must not crash or double-assign)
  CSP solver (CSPSolver):
    - a section with uta_count=2 (regression test for the slot_index bug
      where both UTA slots collapsed into one SlotSpec)
    - a section nobody is eligible for (must show up entirely in unfilled)
    - an applicant eligible for many sections (over-subscription / the
      all-different constraint must still give them only one slot)
    - more open slots than eligible applicants, and vice versa
    - a KNOWN GAP: `Application.term`/`year` is never cross-checked against
      `Section.term`/`year`. A004b below applied for a *past* term but is
      still a live candidate for the *current* Fall 2026 sections. This
      isn't a crash bug, just an untested assumption worth deciding on
      deliberately (filter applications by term before building the
      candidate table, or accept that one application covers all terms).
"""

from datetime import time

from .applicants import Applicant, PastCourseRecord, TeachingExperienceRecord, Recommendation
from .applications import Application, CoursePreference
from .courses import Course, LabSection, Section, PositionRequirement
from .enums import Day, Grade, PositionType, Semester
from .scheduling import TimeSlot
from .test_data import COURSES as BASE_COURSES


def _mw(start_h, start_m, end_h, end_m, label=""):
    return [
        TimeSlot(Day.MON, time(start_h, start_m), time(end_h, end_m), label),
        TimeSlot(Day.WED, time(start_h, start_m), time(end_h, end_m), label),
    ]


# ---------------------------------------------------------------------------
# 1. Courses — reuse the base catalog and add a couple more
# ---------------------------------------------------------------------------

COURSES = dict(BASE_COURSES)
COURSES.update({
    "CSCI 4980": Course("CSCI 4980", "Special Topics: Distributed Systems",
                         skills={"systems", "networking", "distributed-systems"}),
    "CSCI 1000": Course("CSCI 1000", "First-Year Seminar",
                         skills=set()),   # deliberately no skills tagged
})


# ---------------------------------------------------------------------------
# 2. Sections — Fall 2026 (current cycle) + one Spring 2026 (past-term trap)
# ---------------------------------------------------------------------------

SECTIONS = [
    # -- Normal, well-subscribed section (baseline / control case) ----------
    Section(
        course=COURSES["CSCI 1012"], section_number="10",
        term=Semester.FALL, year=2026, instructor="Prof. Alvarado",
        lecture_meetings=_mw(9, 35, 10, 50, "1012 Lecture"),
        labs=[
            LabSection("Lab A", [TimeSlot(Day.FRI, time(11, 10), time(13, 0))]),
            LabSection("Lab B", [TimeSlot(Day.FRI, time(13, 10), time(15, 0))]),
        ],
        position_requirements=PositionRequirement(la_count=2, uta_count=1),
    ),

    # -- Needs 2 UTAs: regression test for the SlotSpec slot_index bug ------
    Section(
        course=COURSES["CSCI 3212"], section_number="10",
        term=Semester.FALL, year=2026, instructor="Prof. Kim",
        lecture_meetings=_mw(14, 10, 15, 25, "3212 Lecture"),
        labs=[LabSection("Lab A", [TimeSlot(Day.FRI, time(9, 35), time(11, 25))])],
        position_requirements=PositionRequirement(
            la_count=0, uta_count=2, uta_must_attend_lecture=True,
        ),
    ),

    # -- No lab sections defined at all: everyone should be ineligible ------
    Section(
        course=COURSES["CSCI 1000"], section_number="01",
        term=Semester.FALL, year=2026, instructor="Prof. Reyes",
        lecture_meetings=_mw(10, 0, 10, 50, "1000 Lecture"),
        labs=[],  # <-- triggers "Section has no lab sections defined"
        position_requirements=PositionRequirement(la_count=1, uta_count=0),
    ),

    # -- Nobody should be eligible: brand-new course, nobody's taken it -----
    Section(
        course=COURSES["CSCI 4980"], section_number="10",
        term=Semester.FALL, year=2026, instructor="Prof. Nakamura",
        lecture_meetings=_mw(15, 35, 16, 50, "4980 Lecture"),
        labs=[LabSection("Lab A", [TimeSlot(Day.TUE, time(9, 35), time(11, 25))])],
        position_requirements=PositionRequirement(la_count=1, uta_count=1),
    ),

    # -- Oversubscribed: everyone eligible, only 1 LA slot to fight over ----
    Section(
        course=COURSES["CSCI 1010"], section_number="10",
        term=Semester.FALL, year=2026, instructor="Prof. Osei",
        lecture_meetings=_mw(8, 0, 8, 50, "1010 Lecture"),
        labs=[LabSection("Lab A", [TimeSlot(Day.THU, time(8, 0), time(9, 50))])],
        position_requirements=PositionRequirement(la_count=1, uta_count=0),
    ),

    # -- Past-term section: only A008 (Spring 2026 applicant) "matches" it,
    #    to make the term/year gap observable rather than theoretical -------
    Section(
        course=COURSES["CSCI 1011"], section_number="05",
        term=Semester.SPRING, year=2026, instructor="Prof. Alvarado",
        lecture_meetings=_mw(9, 0, 9, 50, "1011 Lecture (Spring)"),
        labs=[LabSection("Lab A", [TimeSlot(Day.TUE, time(9, 0), time(10, 50))])],
        position_requirements=PositionRequirement(la_count=1, uta_count=0),
    ),
]


# ---------------------------------------------------------------------------
# 3. Applicants — each tagged with the edge case it exercises
# ---------------------------------------------------------------------------

APPLICANTS = {

    # A001 — the "obviously eligible, high scorer" control case
    "A001": Applicant(
        applicant_id="A001", name="Priya Sharma", email="psharma@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1010", Grade.A, Semester.FALL, 2024),
            PastCourseRecord("CSCI 1012", Grade.A, Semester.FALL, 2025),
            PastCourseRecord("CSCI 3212", Grade.A_MINUS, Semester.SPRING, 2026),
        ],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 1010", PositionType.LA, Semester.SPRING, 2025, 4.5),
            TeachingExperienceRecord("CSCI 1012", PositionType.LA, Semester.FALL, 2025, 4.8),
        ],
        recommendations=[Recommendation("Prof. Alvarado", "CSCI 1012", strength=4.5)],
        upcoming_schedule=[],
        skills={"java", "python", "algorithms"},
    ),

    # A002 — GPA exactly AT the floor (boundary test: `gpa < threshold`
    # should NOT reject an exact match, only a value strictly below it)
    "A002": Applicant(
        applicant_id="A002", name="Marcus Lee", email="mlee@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.B, Semester.FALL, 2025),  # gpa exactly 3.0
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills={"java"},
    ),

    # A003 — took the course but FAILED it (has_taken must return None)
    "A003": Applicant(
        applicant_id="A003", name="Devon Walker", email="dwalker@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.F, Semester.FALL, 2025),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills={"java"},
    ),

    # A004 — only an IN_PROGRESS course on record -> overall_gpa is None,
    # and a GPA floor must reject a None GPA rather than crashing on it
    "A004": Applicant(
        applicant_id="A004", name="Sofia Ibrahim", email="sibrahim@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.IN_PROGRESS, Semester.FALL, 2026),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills=set(),
    ),

    # A005 — schedule conflicts with the REQUIRED lecture (3212 UTA must
    # attend lecture) but has no lab conflict; should fail only on lecture
    "A005": Applicant(
        applicant_id="A005", name="Wei Zhang", email="wzhang@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 3212", Grade.A, Semester.SPRING, 2026),
        ],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 3212", PositionType.LA, Semester.SPRING, 2026, 4.2),
        ],
        recommendations=[Recommendation("Prof. Kim", strength=4.0)],  # no course tie
        upcoming_schedule=[
            TimeSlot(Day.MON, time(14, 10), time(15, 25), "conflicts with 3212 lecture"),
        ],
        skills={"algorithms"},
    ),

    # A006 — conflicts with ONE of two lab options for 1012, but the other
    # lab is free: must still be eligible ("at least one conflict-free lab")
    "A006": Applicant(
        applicant_id="A006", name="Elena Petrova", email="epetrova@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.A_MINUS, Semester.FALL, 2025),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[
            TimeSlot(Day.FRI, time(11, 10), time(13, 0), "conflicts with Lab A only"),
        ],
        skills={"java", "data-structures"},
    ),

    # A007 — conflicts with BOTH labs for 1012: must be ineligible for it
    "A007": Applicant(
        applicant_id="A007", name="Omar Farouk", email="ofarouk@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1012", Grade.B_PLUS, Semester.FALL, 2025),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[
            TimeSlot(Day.FRI, time(11, 10), time(13, 0), "conflicts with Lab A"),
            TimeSlot(Day.FRI, time(13, 10), time(15, 0), "conflicts with Lab B"),
        ],
        skills={"java"},
    ),

    # A008 — only applied against a SPRING 2026 course; surfaces the
    # term/year gap described in the module docstring
    "A008": Applicant(
        applicant_id="A008", name="Grace Kim", email="gkim@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 1011", Grade.A, Semester.FALL, 2025),
        ],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills={"python"},
    ),

    # A009 & A010 — deliberately identical on every scored dimension, to
    # confirm the solver/tie-break doesn't crash or double-count when two
    # candidates for the same slot have equal scores
    "A009": Applicant(
        applicant_id="A009", name="Ravi Patel", email="rpatel@gwu.edu",
        past_courses=[PastCourseRecord("CSCI 1010", Grade.A_MINUS, Semester.FALL, 2025)],
        teaching_experience=[],
        recommendations=[Recommendation("Prof. Osei", strength=3.0)],
        upcoming_schedule=[],
        skills={"python"},
    ),
    "A010": Applicant(
        applicant_id="A010", name="Naomi Clarke", email="nclarke@gwu.edu",
        past_courses=[PastCourseRecord("CSCI 1010", Grade.A_MINUS, Semester.FALL, 2025)],
        teaching_experience=[],
        recommendations=[Recommendation("Prof. Osei", strength=3.0)],
        upcoming_schedule=[],
        skills={"python"},
    ),

    # A011 — UTA-readiness bonus: exactly 2 prior LA terms (>=2 threshold)
    "A011": Applicant(
        applicant_id="A011", name="Lucas Moreau", email="lmoreau@gwu.edu",
        past_courses=[
            PastCourseRecord("CSCI 3212", Grade.A, Semester.SPRING, 2026),
        ],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 1010", PositionType.LA, Semester.FALL, 2024, 4.0),
            TeachingExperienceRecord("CSCI 1012", PositionType.LA, Semester.SPRING, 2025, 4.3),
        ],
        recommendations=[Recommendation("Prof. Kim", "CSCI 3212", strength=5.0)],
        upcoming_schedule=[],
        skills={"algorithms", "proofs"},
    ),

    # A012 — huge teaching history (6 prior positions) to test the
    # `min(prior_positions_count(), 4)` cap doesn't overshoot 1.0
    "A012": Applicant(
        applicant_id="A012", name="Isabella Rossi", email="irossi@gwu.edu",
        past_courses=[PastCourseRecord("CSCI 1010", Grade.A, Semester.FALL, 2023)],
        teaching_experience=[
            TeachingExperienceRecord("CSCI 1010", PositionType.LA, Semester.FALL, 2023, 4.0),
            TeachingExperienceRecord("CSCI 1010", PositionType.LA, Semester.SPRING, 2024, 4.0),
            TeachingExperienceRecord("CSCI 1011", PositionType.LA, Semester.FALL, 2024, 4.0),
            TeachingExperienceRecord("CSCI 1011", PositionType.LA, Semester.SPRING, 2025, 4.0),
            TeachingExperienceRecord("CSCI 1012", PositionType.UTA, Semester.FALL, 2025, 4.5),
            TeachingExperienceRecord("CSCI 1012", PositionType.UTA, Semester.SPRING, 2026, 4.5),
        ],
        recommendations=[Recommendation("Prof. Osei", strength=5.0)],
        upcoming_schedule=[],
        skills={"python"},
    ),

    # A013 — applies for a course they've never taken; should show up in
    # the CSCI 4980 section as ineligible along with everyone else
    "A013": Applicant(
        applicant_id="A013", name="Jonah Brooks", email="jbrooks@gwu.edu",
        past_courses=[PastCourseRecord("CSCI 1010", Grade.C, Semester.FALL, 2025)],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills={"networking"},
    ),

    # A014 — no GPA floor issue, but zero recommendations AND zero skill
    # overlap AND unranked preference: tests the "all soft signals near
    # zero" floor of the scoring function without going negative
    "A014": Applicant(
        applicant_id="A014", name="Ana Costa", email="acosta@gwu.edu",
        past_courses=[PastCourseRecord("CSCI 1010", Grade.C_MINUS, Semester.FALL, 2025)],
        teaching_experience=[],
        recommendations=[],
        upcoming_schedule=[],
        skills=set(),
    ),
}


# ---------------------------------------------------------------------------
# 4. Applications
# ---------------------------------------------------------------------------

APPLICATIONS = [
    Application("A001", Semester.FALL, 2026, {PositionType.LA, PositionType.UTA},
                [CoursePreference("CSCI 1012", 1), CoursePreference("CSCI 3212", 2)]),
    Application("A002", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1012", 1)]),
    Application("A003", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1012", 1)]),
    Application("A004", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1012", 1)]),
    Application("A005", Semester.FALL, 2026, {PositionType.UTA},
                [CoursePreference("CSCI 3212", 1)]),
    Application("A006", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1012", 1)]),
    Application("A007", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1012", 1)]),
    # A008 only ever applies against a Spring 2026 course:
    Application("A008", Semester.SPRING, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1011", 1)]),
    Application("A009", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1010", 1)]),
    Application("A010", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1010", 1)]),
    Application("A011", Semester.FALL, 2026, {PositionType.UTA},
                [CoursePreference("CSCI 3212", 1)]),
    Application("A012", Semester.FALL, 2026, {PositionType.LA},
                [CoursePreference("CSCI 1010", 1)]),
    Application("A013", Semester.FALL, 2026, {PositionType.LA, PositionType.UTA},
                [CoursePreference("CSCI 4980", 1)]),
    Application("A014", Semester.FALL, 2026, {PositionType.LA},
                []),  # unranked on purpose
]


# ---------------------------------------------------------------------------
# 5. Human-readable scenario map (useful for building assertions / a QA
#    checklist in the web UI without re-deriving "why does this exist?")
# ---------------------------------------------------------------------------

SCENARIOS = {
    "A001": "Control case: clearly eligible, high scorer across the board.",
    "A002": "GPA exactly at the configured floor (boundary, should PASS).",
    "A003": "Failed the course (F): has_taken/grade_in must return None.",
    "A004": "Only an IN_PROGRESS course -> overall_gpa is None; must fail a GPA floor cleanly.",
    "A005": "Conflicts with a lecture that's required for the position; labs are fine.",
    "A006": "Conflicts with one of two labs; still eligible via the other lab.",
    "A007": "Conflicts with ALL labs for the section; must be ineligible.",
    "A008": "Only applied against a different term/year section (term/year gap probe).",
    "A009/A010": "Identical scores on every dimension (tie-break stability).",
    "A011": "Exactly 2 prior LA terms: should receive the UTA-readiness bonus.",
    "A012": "6 prior teaching positions: experience component must cap at 1.0, not overshoot.",
    "A013": "Applies for a course nobody (including them) has ever taken.",
    "A014": "No recommendations, no skill overlap, unranked preference (score floor, not negative).",
    "CSCI 3212-10": "uta_count=2: regression test for the SlotSpec slot_index collision bug.",
    "CSCI 1000-01": "No labs defined at all: everyone must be ineligible for this section.",
    "CSCI 4980-10": "Brand-new course: nobody eligible, section is fully unfilled.",
    "CSCI 1010-10": "Oversubscribed: many eligible applicants, only 1 LA slot.",
    "CSCI 1011-05": "Spring 2026 section, only matched by A008's Spring application.",
}


def load_extended_data():
    """Convenience loader returning (courses, sections, applicants, applications)."""
    return COURSES, SECTIONS, APPLICANTS, APPLICATIONS
