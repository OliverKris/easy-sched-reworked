"""
scheduler.py — TA Scheduling Entry Point (MVP)

Loads:
  - processed_courses.json  → List[SectionGroup]   (via processed_parser)
  - applicants.json         → List[StudentApplication] (via applicant_parser)

Builds:
  - requirements: one CourseRequirements per SectionGroup
  - eligibility:  per applicant, which groups they can cover without a time conflict

Prints a ready-to-assign summary so the next step (matching) has clean inputs.
"""

from models.assignment import CourseRequirements, default_requirements
from models.application import has_time_conflict
from tools.processed_parser import load_section_groups
from tools.applicant_parser import load_applications
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Data structures produced by this stage
# ---------------------------------------------------------------------------

@dataclass
class GroupRequirements:
    """Pairs a SectionGroup with its TA staffing requirements."""
    group_id: str
    course_subject: str
    course_number: str
    course_title: str
    instructor: str
    lecture_crn: str
    lab_crns: List[str]
    requirements: CourseRequirements


@dataclass
class ApplicantEligibility:
    """
    For one applicant, the set of group_ids they are eligible for —
    meaning their position type is allowed AND they have no time conflict
    with any section in that group.
    """
    student_id: str
    name: str
    positions_applied: list
    eligible_group_ids: List[str]
    conflicted_group_ids: List[str]     # preferred but blocked by schedule
    unpreferred_group_ids: List[str]    # eligible groups not in their preferences


# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------

def build_requirements(groups) -> List[GroupRequirements]:
    reqs = []
    for g in groups:
        reqs.append(GroupRequirements(
            group_id=g.group_id,
            course_subject=g.course_subject,
            course_number=g.course_number,
            course_title=g.course_title,
            instructor=g.instructor,
            lecture_crn=g.lecture.crn,
            lab_crns=[s.crn for s in g.labs],
            requirements=default_requirements(g.course_title, g.instructor, g.lecture.crn),
        ))
    return reqs


def _group_conflicts_with_applicant(app, group) -> bool:
    """Return True if the applicant has a schedule conflict with ANY section in the group."""
    for section in group.all_sections:
        for meeting in section.meetings:
            if meeting.days and meeting.start_time and meeting.end_time:
                if has_time_conflict(app, meeting.days, meeting.start_time, meeting.end_time):
                    return True
    return False


def build_eligibility(applications, groups) -> List[ApplicantEligibility]:
    # Index groups by id and by course_number for preference matching
    groups_by_id = {g.group_id: g for g in groups}
    groups_by_course_number = {}
    for g in groups:
        groups_by_course_number.setdefault(g.course_number, []).append(g)

    results = []
    for app in applications:
        # Normalise: applicants store "CSCI 1012", groups store "1012"
        preferred_numbers = {
            cp.course_number.split()[-1] for cp in app.preferred_courses
        }

        eligible     = []
        conflicted   = []
        unpreferred  = []

        for g in groups:
            has_conflict = _group_conflicts_with_applicant(app, g)
            is_preferred = g.course_number in preferred_numbers

            if has_conflict:
                if is_preferred:
                    conflicted.append(g.group_id)
                # conflicted + not preferred → silently skip
            else:
                if is_preferred:
                    eligible.append(g.group_id)
                else:
                    unpreferred.append(g.group_id)

        results.append(ApplicantEligibility(
            student_id=app.student_id,
            name=app.name,
            positions_applied=app.positions_applied,
            eligible_group_ids=eligible,
            conflicted_group_ids=conflicted,
            unpreferred_group_ids=unpreferred,
        ))

    return results


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def print_requirements(reqs: List[GroupRequirements]):
    print("=" * 60)
    print("SECTION GROUP REQUIREMENTS")
    print("=" * 60)
    for r in reqs:
        labs = r.lab_crns if r.lab_crns else ["(none)"]
        print(f"\n[{r.group_id}]")
        print(f"  {r.course_subject} {r.course_number} — {r.course_title}")
        print(f"  Instructor  : {r.instructor}")
        print(f"  Lecture CRN : {r.lecture_crn}   Labs: {labs}")
        for pr in r.requirements.position_requirements:
            print(f"  {pr.position_type.value:<38} need {pr.count}")


def print_eligibility(eligibility: List[ApplicantEligibility], reqs: List[GroupRequirements]):
    req_index = {r.group_id: r for r in reqs}

    print("\n" + "=" * 60)
    print("APPLICANT ELIGIBILITY")
    print("=" * 60)
    for e in eligibility:
        pos_names = [p.value for p in e.positions_applied]
        print(f"\n{e.name} ({e.student_id})  —  {', '.join(pos_names)}")

        if e.eligible_group_ids:
            print("  Eligible (preferred, no conflict):")
            for gid in e.eligible_group_ids:
                r = req_index[gid]
                print(f"    ✓  {r.course_subject} {r.course_number} [{r.instructor}]")

        if e.conflicted_group_ids:
            print("  Blocked by schedule conflict:")
            for gid in e.conflicted_group_ids:
                r = req_index[gid]
                print(f"    ✗  {r.course_subject} {r.course_number} [{r.instructor}]")

        if not e.eligible_group_ids and not e.conflicted_group_ids:
            print("  (no preferred courses matched any section group)")
