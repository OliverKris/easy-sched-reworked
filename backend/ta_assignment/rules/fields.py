"""Named fields that `cmp` rules can compare against.

Each field maps a name used in profile JSON to a function of
(applicant, application, section, position) that returns a number, or None
when the value is missing. Adding a field here makes it available to every
department's config immediately.

Applicant-only fields (marked `per_applicant=True`) don't depend on the slot,
so the compiler computes them once per applicant and reuses the value across
every slot, which matters when there are hundreds of slots.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional

from ..enums import PositionType


@dataclass(frozen=True)
class FieldDef:
    getter: Callable[..., Optional[float]]
    per_applicant: bool
    description: str


def _avg_recommendation(applicant, *_):
    recs = applicant.recommendations
    return sum(r.strength for r in recs) / len(recs) if recs else None


def _grade_points_in_course(applicant, _application, section, _position):
    grade = applicant.grade_in(section.course.course_id)
    return grade.gpa_points if grade is not None else None


FIELDS: Dict[str, FieldDef] = {
    "applicant.gpa": FieldDef(
        lambda a, *_: a.overall_gpa, True,
        "Overall GPA across completed courses (None if no completed courses)"),
    "applicant.prior_positions": FieldDef(
        lambda a, *_: float(a.prior_positions_count()), True,
        "Number of past LA/UTA positions of any kind"),
    "applicant.prior_la_terms": FieldDef(
        lambda a, *_: float(a.prior_positions_count(PositionType.LA)), True,
        "Number of past LA positions"),
    "applicant.prior_uta_terms": FieldDef(
        lambda a, *_: float(a.prior_positions_count(PositionType.UTA)), True,
        "Number of past UTA positions"),
    "applicant.recommendation_count": FieldDef(
        lambda a, *_: float(len(a.recommendations)), True,
        "Number of faculty recommendations"),
    "applicant.avg_recommendation": FieldDef(
        _avg_recommendation, True,
        "Average recommendation strength on a 1-5 scale (None if none)"),
    "course.grade_points": FieldDef(
        _grade_points_in_course, False,
        "Grade points (0-4) earned in this slot's course (None if not passed)"),
    "application.preference_rank": FieldDef(
        lambda _a, app, sec, _p: float(app.preference_rank(sec.course.course_id)), False,
        "Applicant's rank for this slot's course (unranked = number ranked + 1)"),
}
