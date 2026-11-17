"""Seeded synthetic data generator for benchmarking the CSP solver.

Every instance is fully determined by (n_applicants, n_sections, seed), so the
same call always produces byte-for-byte identical data. That makes it usable
both for timing runs (benchmarks.run) and for golden regression tests
(benchmarks.golden / tests/test_golden.py).

The data is shaped to look like a real CS department's hiring cycle:
    - a course catalog with skill tags
    - sections with MW or TR lectures, 1-3 labs each, and 1-3 LA / 0-2 UTA slots
    - applicants with transcripts skewed toward A/B grades (plus the odd F),
      prior LA/UTA experience, recommendations, class schedules that can
      conflict with lectures/labs, and ranked course preferences
"""

from dataclasses import dataclass
from datetime import time
import random
from typing import Dict, List

from ta_assignment.applicants import (
    Applicant, PastCourseRecord, Recommendation, TeachingExperienceRecord,
)
from ta_assignment.applications import Application, CoursePreference
from ta_assignment.courses import Course, LabSection, PositionRequirement, Section
from ta_assignment.enums import Day, Grade, PositionType, Semester
from ta_assignment.scheduling import TimeSlot

TERM = Semester.FALL
YEAR = 2026

SKILL_POOL = [
    "python", "java", "c", "javascript", "sql", "recursion", "data-structures",
    "algorithms", "systems", "networking", "security", "ml", "web", "databases",
    "discrete-math", "theory",
]

# Weighted toward the grades TA applicants actually have; F is included so
# the "took it but failed" eligibility path gets exercised.
GRADE_WEIGHTS = [
    (Grade.A, 30), (Grade.A_MINUS, 22), (Grade.B_PLUS, 15), (Grade.B, 12),
    (Grade.B_MINUS, 8), (Grade.C_PLUS, 5), (Grade.C, 4), (Grade.F, 4),
]

START_HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17]


@dataclass
class Instance:
    """One generated benchmark problem, in the shape CSPSolver expects."""
    name: str
    courses: List[Course]
    sections: List[Section]
    applicants: Dict[str, Applicant]
    applications: List[Application]


# --- small helpers ---------------------------------------------------------

def _block(rng: random.Random, minutes: int = 75) -> tuple:
    start_h = rng.choice(START_HOURS)
    start_m = rng.choice([0, 30])
    total = start_h * 60 + start_m + minutes
    return time(start_h, start_m), time(total // 60, total % 60)


def _paired_days(rng: random.Random, label: str) -> List[TimeSlot]:
    """A recurring MW or TR meeting, the way most lectures are scheduled."""
    days = rng.choice([(Day.MON, Day.WED), (Day.TUE, Day.THU)])
    start, end = _block(rng)
    return [TimeSlot(d, start, end, label) for d in days]


def _weighted_grade(rng: random.Random) -> Grade:
    grades, weights = zip(*GRADE_WEIGHTS)
    return rng.choices(grades, weights=weights, k=1)[0]


# --- generators ------------------------------------------------------------

def _make_courses(rng: random.Random, n_courses: int) -> List[Course]:
    courses = []
    for i in range(n_courses):
        level = 1000 + (i // 4) * 1000            # spread across 1000-4000 levels
        course_id = f"CSCI {level + 11 + i * 10}"
        skills = set(rng.sample(SKILL_POOL, k=rng.randint(0, 4)))  # 0 = untagged course
        courses.append(Course(course_id=course_id, title=f"Synthetic Course {i + 1}", skills=skills))
    return courses


def _make_sections(rng: random.Random, courses: List[Course], n_sections: int) -> List[Section]:
    sections = []
    per_course_count: Dict[str, int] = {}
    for i in range(n_sections):
        course = courses[i % len(courses)]        # every course gets at least one section
        n = per_course_count.get(course.course_id, 0)
        per_course_count[course.course_id] = n + 1
        labs = []
        for j in range(rng.randint(1, 3)):
            start, end = _block(rng, minutes=105)
            labs.append(LabSection(
                lab_id=f"Lab {30 + j}",
                meetings=[TimeSlot(rng.choice(list(Day)), start, end, "Lab")],
            ))
        reqs = PositionRequirement(
            la_count=rng.randint(1, 3),
            uta_count=rng.randint(0, 2),
            uta_must_attend_lecture=rng.random() < 0.3,
            la_must_attend_lecture=rng.random() < 0.1,
        )
        sections.append(Section(
            course=course,
            section_number=str(10 + n),
            term=TERM,
            year=YEAR,
            instructor=f"Prof {chr(65 + i % 26)}",
            lecture_meetings=_paired_days(rng, f"{course.course_id} Lecture"),
            labs=labs,
            position_requirements=reqs,
        ))
    return sections


def _make_applicant(rng: random.Random, idx: int, courses: List[Course]) -> tuple:
    applicant_id = f"S{idx:04d}"
    taken = rng.sample(courses, k=rng.randint(2, min(6, len(courses))))
    past = [
        PastCourseRecord(c.course_id, _weighted_grade(rng), rng.choice(list(Semester)), rng.randint(2022, 2025))
        for c in taken
    ]
    passed = [r.course_id for r in past if r.grade > Grade.F]

    experience = [
        TeachingExperienceRecord(
            course_id=rng.choice(passed) if passed else taken[0].course_id,
            position=PositionType.LA if rng.random() < 0.75 else PositionType.UTA,
            term=rng.choice(list(Semester)),
            year=rng.randint(2023, 2025),
            supervisor_rating=round(rng.uniform(3.0, 5.0), 1) if rng.random() < 0.6 else None,
        )
        for _ in range(rng.choices([0, 1, 2, 3, 4], weights=[40, 25, 18, 10, 7], k=1)[0])
    ]

    recommendations = [
        Recommendation(faculty_name=f"Prof {chr(65 + rng.randint(0, 25))}",
                       course_id=rng.choice(passed) if passed and rng.random() < 0.5 else None,
                       strength=float(rng.randint(1, 5)))
        for _ in range(rng.randint(0, 3))
    ]

    schedule: List[TimeSlot] = []
    for k in range(rng.randint(2, 4)):
        schedule.extend(_paired_days(rng, f"Own class {k + 1}"))

    applicant = Applicant(
        applicant_id=applicant_id,
        name=f"Student {idx}",
        email=f"s{idx:04d}@example.edu",
        past_courses=past,
        teaching_experience=experience,
        recommendations=recommendations,
        upcoming_schedule=schedule,
        skills=set(rng.sample(SKILL_POOL, k=rng.randint(1, 5))),
    )

    roll = rng.random()
    if roll < 0.55:
        positions = {PositionType.LA}
    elif roll < 0.75:
        positions = {PositionType.UTA}
    else:
        positions = {PositionType.LA, PositionType.UTA}

    # Mostly rank courses they've passed; occasionally one they haven't
    # (realistic, and exercises the "has not taken" ineligibility path).
    pref_pool = passed[:] if passed else [c.course_id for c in taken]
    if rng.random() < 0.2:
        pref_pool.append(rng.choice(courses).course_id)
    rng.shuffle(pref_pool)
    prefs = [CoursePreference(cid, rank) for rank, cid in enumerate(dict.fromkeys(pref_pool[:3]), start=1)]

    application = Application(
        applicant_id=applicant_id, term=TERM, year=YEAR,
        position_types=positions, ranked_preferences=prefs,
    )
    return applicant, application


def generate_instance(n_applicants: int, n_sections: int, seed: int, name: str = "") -> Instance:
    """Builds one deterministic problem instance."""
    rng = random.Random(seed)
    n_courses = max(4, n_sections // 2)
    courses = _make_courses(rng, n_courses)
    sections = _make_sections(rng, courses, n_sections)

    applicants: Dict[str, Applicant] = {}
    applications: List[Application] = []
    for i in range(1, n_applicants + 1):
        applicant, application = _make_applicant(rng, i, courses)
        applicants[applicant.applicant_id] = applicant
        applications.append(application)

    return Instance(
        name=name or f"{n_applicants}a-{n_sections}s-seed{seed}",
        courses=courses, sections=sections,
        applicants=applicants, applications=applications,
    )


# Named sizes used by the benchmark runner and the golden tests.
SIZES = {
    "small": (20, 8),
    "medium": (50, 20),
    "large": (100, 40),
    "xlarge": (200, 80),
}


def generate_sized(size: str, seed: int) -> Instance:
    n_applicants, n_sections = SIZES[size]
    return generate_instance(n_applicants, n_sections, seed, name=f"{size}-seed{seed}")