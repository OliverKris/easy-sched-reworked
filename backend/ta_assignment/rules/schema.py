"""The department profile format: what a department's JSON config looks like.

A profile has two lists:
    hard_rules  -- every one must pass for an applicant to be eligible for a slot
    scoring     -- weighted terms summed into the score the solver maximises

Each rule/term is a small JSON object whose "rule" (or "term") key picks its
type. Pydantic validates the whole file on load, so a typo like
"applicant.gpaa" or a weight given as text fails immediately with a clear
message instead of halfway through a solve.

Example (abridged):
    {
      "version": 1,
      "department": "GWU Computer Science",
      "hard_rules": [
        {"id": "applied", "rule": "applied_for_position"},
        {"id": "gpa-uta", "rule": "cmp", "field": "applicant.gpa", "op": ">=",
         "value": 3.3, "positions": ["UTA"]}
      ],
      "scoring": [
        {"id": "grade", "term": "course_grade", "weight": 3.0}
      ]
    }
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from ..enums import Grade, PositionType
from .fields import FIELDS

PROFILE_VERSION = 1


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")  # unknown keys are errors, not silently ignored


class _Scoped(_Base):
    """Optional scope shared by every rule and term. Out of scope = rule is skipped
    (a hard rule passes, a scoring term adds nothing)."""
    id: Optional[str] = None
    label: Optional[str] = None                      # human-readable name shown in the UI
    positions: Optional[List[PositionType]] = None   # e.g. ["UTA"]
    courses: Optional[List[str]] = None              # e.g. ["CSCI 1111"]

    @field_validator("positions", mode="before")
    @classmethod
    def _positions_by_name(cls, v):
        # Accept "LA"/"UTA" (enum names) as well as the enum values.
        if v is None:
            return v
        return [PositionType[p] if isinstance(p, str) and p in PositionType.__members__ else p for p in v]

    @field_serializer("positions")
    def _positions_as_names(self, v):
        return None if v is None else [p.name for p in v]


# --- hard rules --------------------------------------------------------------

class AppliedForPosition(_Scoped):
    """Applicant ticked this position type on their application."""
    rule: Literal["applied_for_position"]


class PassedCourse(_Scoped):
    """Applicant took this slot's course and passed it (grade above F),
    optionally with at least `min_grade`."""
    rule: Literal["passed_course"]
    min_grade: Optional[str] = None   # Grade enum name, e.g. "B_PLUS"

    @field_validator("min_grade")
    @classmethod
    def _known_grade(cls, v):
        if v is not None and v not in Grade.__members__:
            raise ValueError(f"unknown grade {v!r}; use one of {list(Grade.__members__)}")
        return v


class NoLectureConflict(_Scoped):
    """Applicant's own classes don't overlap the section's lecture.
    when='if_required' (default) only checks positions the section marks as
    must-attend; when='always' checks every position."""
    rule: Literal["no_lecture_conflict"]
    when: Literal["if_required", "always"] = "if_required"


class ConflictFreeLab(_Scoped):
    """At least one of the section's labs fits the applicant's schedule.
    A section with no labs fails unless allow_no_labs is true (useful for
    grader-only or lecture-only offerings)."""
    rule: Literal["conflict_free_lab"]
    allow_no_labs: bool = False


class Compare(_Scoped):
    """Compares a named field to a value, e.g. applicant.gpa >= 3.0.
    `missing` decides what happens when the field has no value (no GPA on file)."""
    rule: Literal["cmp"]
    field: str
    op: Literal[">=", ">", "<=", "<", "==", "!="]
    value: float
    missing: Literal["fail", "pass"] = "fail"

    @field_validator("field")
    @classmethod
    def _known_field(cls, v):
        if v not in FIELDS:
            raise ValueError(f"unknown field {v!r}; available: {sorted(FIELDS)}")
        return v


class AllOf(_Scoped):
    rule: Literal["all"]
    rules: List["HardRule"]


class AnyOf(_Scoped):
    rule: Literal["any"]
    rules: List["HardRule"]


class Not(_Scoped):
    rule: Literal["not"]
    inner: "HardRule"


HardRule = Annotated[
    Union[AppliedForPosition, PassedCourse, NoLectureConflict, ConflictFreeLab,
          Compare, AllOf, AnyOf, Not],
    Field(discriminator="rule"),
]


# --- scoring terms -----------------------------------------------------------

class _Term(_Scoped):
    weight: float


class CourseGrade(_Term):
    """weight x (grade points in this course / 4)."""
    term: Literal["course_grade"]


class TeachingExperience(_Term):
    """weight x (general_share x min(prior positions, cap)/cap
                 + course_share x [has taught this exact course])."""
    term: Literal["teaching_experience"]
    cap: int = 4
    general_share: float = 0.6
    course_share: float = 0.4


class RecommendationStrength(_Term):
    """weight x (average recommendation strength / 5). Adds nothing with no recommendations."""
    term: Literal["recommendation_strength"]


class PreferenceRank(_Term):
    """weight x (1 / rank). Unranked courses count as rank = (number ranked + 1)."""
    term: Literal["preference_rank"]


class SkillOverlap(_Term):
    """weight x (share of the course's skill tags the applicant has). Nothing if the course has no tags."""
    term: Literal["skill_overlap"]


class Bonus(_Term):
    """Adds `weight` when the `when` rule passes, e.g. a readiness bonus for UTAs
    with 2+ semesters as an LA."""
    term: Literal["bonus"]
    when: HardRule


ScoreTerm = Annotated[
    Union[CourseGrade, TeachingExperience, RecommendationStrength, PreferenceRank,
          SkillOverlap, Bonus],
    Field(discriminator="term"),
]


# --- the profile -------------------------------------------------------------

class DepartmentProfile(_Base):
    version: Literal[1] = PROFILE_VERSION
    department: str
    description: Optional[str] = None
    hard_rules: List[HardRule]
    scoring: List[ScoreTerm]


AllOf.model_rebuild()
AnyOf.model_rebuild()
Not.model_rebuild()
Bonus.model_rebuild()
DepartmentProfile.model_rebuild()
