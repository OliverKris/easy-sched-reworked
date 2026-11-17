"""Compiles a DepartmentProfile into fast Python functions the solvers call.

compile_profile() walks the validated profile once and turns every rule and
term into a closure. The solver then asks, for each (applicant, slot) pair:

    session.check(...)  -> EligibilityResult (eligible + every failing reason)
    session.score(...)  -> float

A Session caches applicant-only field values (GPA, prior positions, average
recommendation) so they're computed once per applicant instead of once per
applicant x slot. Make a new session per solve: applicant data can change
between solves.

Scoring adds the terms in the order the profile lists them, using the same
arithmetic as the original DefaultScoringStrategy, so a profile that mirrors
the old defaults reproduces its scores exactly (see tests/test_rules.py).
"""

import json
import operator
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from ..applicants import Applicant
from ..applications import Application
from ..courses import Section
from ..enums import Grade, PositionType
from ..scheduling import has_conflict
from ..scoring import EligibilityResult
from . import schema as s
from .fields import FIELDS

_OPS = {">=": operator.ge, ">": operator.gt, "<=": operator.le,
        "<": operator.lt, "==": operator.eq, "!=": operator.ne}


class _Ctx:
    """One (applicant, slot) evaluation, with access to the session's field cache."""
    __slots__ = ("applicant", "application", "section", "position", "cache")

    def __init__(self, applicant, application, section, position, cache):
        self.applicant = applicant
        self.application = application
        self.section = section
        self.position = position
        self.cache = cache

    def field(self, name: str) -> Optional[float]:
        fdef = FIELDS[name]
        if not fdef.per_applicant:
            return fdef.getter(self.applicant, self.application, self.section, self.position)
        key = (self.applicant.applicant_id, name)
        if key not in self.cache:
            self.cache[key] = fdef.getter(self.applicant, self.application, self.section, self.position)
        return self.cache[key]


# A compiled hard rule returns None when it passes, or a human-readable reason when it fails.
RuleFn = Callable[[_Ctx], Optional[str]]
TermFn = Callable[[_Ctx], float]


def _in_scope(node, ctx: _Ctx) -> bool:
    if node.positions is not None and ctx.position not in node.positions:
        return False
    if node.courses is not None and ctx.section.course.course_id not in node.courses:
        return False
    return True


# --- hard rules --------------------------------------------------------------

def _compile_rule(rule) -> RuleFn:
    inner = _compile_rule_body(rule)
    if rule.positions is None and rule.courses is None:
        return inner

    def scoped(ctx: _Ctx) -> Optional[str]:
        return inner(ctx) if _in_scope(rule, ctx) else None
    return scoped


def _compile_rule_body(rule) -> RuleFn:
    if isinstance(rule, s.AppliedForPosition):
        return lambda c: None if c.application.wants_position(c.position) \
            else f"Did not apply for {c.position.value}"

    if isinstance(rule, s.PassedCourse):
        floor = Grade[rule.min_grade] if rule.min_grade else None

        def passed_course(c: _Ctx) -> Optional[str]:
            cid = c.section.course.course_id
            rec = c.applicant.has_taken(cid)
            if rec is None:
                return f"Has not taken/passed {cid}"
            if floor is not None and rec.grade < floor:
                return f"Grade {rec.grade.name} in {cid} below required {floor.name}"
            return None
        return passed_course

    if isinstance(rule, s.NoLectureConflict):
        always = rule.when == "always"

        def no_lecture_conflict(c: _Ctx) -> Optional[str]:
            required = always or c.section.position_requirements.must_attend_lecture(c.position)
            if required and has_conflict(c.applicant.upcoming_schedule, c.section.lecture_meetings):
                return "Schedule conflicts with required lecture time"
            return None
        return no_lecture_conflict

    if isinstance(rule, s.ConflictFreeLab):
        allow_none = rule.allow_no_labs

        def conflict_free_lab(c: _Ctx) -> Optional[str]:
            labs = c.section.labs
            if not labs:
                return None if allow_none else "Section has no lab sections defined"
            if any(not has_conflict(c.applicant.upcoming_schedule, lab.meetings) for lab in labs):
                return None
            return "No conflict-free lab section available"
        return conflict_free_lab

    if isinstance(rule, s.Compare):
        name, op, value, missing_passes = rule.field, _OPS[rule.op], rule.value, rule.missing == "pass"
        label = f"{rule.field} {rule.op} {rule.value:g}"

        def compare(c: _Ctx) -> Optional[str]:
            v = c.field(name)
            if v is None:
                return None if missing_passes else f"No value for {name} (requires {label})"
            return None if op(v, value) else f"{name} = {v:.2f}, requires {label}"
        return compare

    if isinstance(rule, s.AllOf):
        parts = [_compile_rule(r) for r in rule.rules]

        def all_of(c: _Ctx) -> Optional[str]:
            for p in parts:
                reason = p(c)
                if reason:
                    return reason
            return None
        return all_of

    if isinstance(rule, s.AnyOf):
        parts = [_compile_rule(r) for r in rule.rules]

        def any_of(c: _Ctx) -> Optional[str]:
            reasons = []
            for p in parts:
                reason = p(c)
                if reason is None:
                    return None
                reasons.append(reason)
            return "None of: " + "; ".join(reasons)
        return any_of

    if isinstance(rule, s.Not):
        part = _compile_rule(rule.inner)
        label = rule.id or "inner rule"
        return lambda c: f"Must not satisfy {label}" if part(c) is None else None

    raise TypeError(f"unhandled rule type {type(rule).__name__}")


# --- scoring terms -----------------------------------------------------------

def _compile_term(term) -> TermFn:
    body = _compile_term_body(term)
    if term.positions is None and term.courses is None:
        return body
    return lambda c: body(c) if _in_scope(term, c) else 0.0


def _compile_term_body(term) -> TermFn:
    w = term.weight

    if isinstance(term, s.CourseGrade):
        def course_grade(c: _Ctx) -> float:
            grade = c.applicant.grade_in(c.section.course.course_id)
            return w * (grade.gpa_points / 4.0) if grade is not None else 0.0
        return course_grade

    if isinstance(term, s.TeachingExperience):
        cap, gen_share, course_share = term.cap, term.general_share, term.course_share

        def teaching_experience(c: _Ctx) -> float:
            general = min(c.field("applicant.prior_positions"), cap) / cap
            course_bonus = 1.0 if c.applicant.has_taught(c.section.course.course_id) else 0.0
            return w * (gen_share * general + course_share * course_bonus)
        return teaching_experience

    if isinstance(term, s.RecommendationStrength):
        def recommendation_strength(c: _Ctx) -> float:
            avg = c.field("applicant.avg_recommendation")
            return w * (avg / 5.0) if avg is not None else 0.0
        return recommendation_strength

    if isinstance(term, s.PreferenceRank):
        return lambda c: w * (1.0 / c.application.preference_rank(c.section.course.course_id))

    if isinstance(term, s.SkillOverlap):
        def skill_overlap(c: _Ctx) -> float:
            skills = c.section.course.skills
            if not skills:
                return 0.0
            return w * (len(c.applicant.skills & skills) / len(skills))
        return skill_overlap

    if isinstance(term, s.Bonus):
        cond = _compile_rule(term.when)
        return lambda c: w if cond(c) is None else 0.0

    raise TypeError(f"unhandled term type {type(term).__name__}")


# --- public API --------------------------------------------------------------

_TERM_LABELS = {
    "course_grade": "Grade in course",
    "teaching_experience": "Teaching experience",
    "recommendation_strength": "Recommendations",
    "preference_rank": "Preference",
    "skill_overlap": "Skill match",
    "bonus": "Bonus",
}


def _rule_key(node, index: int) -> Tuple[str, str]:
    """A stable (id, label) for a rule or term, for explanations and the UI."""
    kind = getattr(node, "rule", None) or getattr(node, "term", None)
    key = node.id or f"{kind}-{index}"
    label = node.label or _TERM_LABELS.get(kind) or key.replace("-", " ").replace("_", " ").capitalize()
    return key, label


class Session:
    """Evaluates a compiled profile, caching applicant-only fields. One per solve."""

    def __init__(self, rules, terms):
        self._rules = rules      # list of (id, label, RuleFn)
        self._terms = terms      # list of (id, label, TermFn)
        self._cache: Dict[Tuple[str, str], Optional[float]] = {}

    def _ctx(self, applicant, application, section, position) -> _Ctx:
        return _Ctx(applicant, application, section, position, self._cache)

    def check(self, applicant: Applicant, application: Application,
              section: Section, position: PositionType) -> EligibilityResult:
        ctx = self._ctx(applicant, application, section, position)
        reasons = [r for r in (fn(ctx) for _, _, fn in self._rules) if r]
        return EligibilityResult(eligible=not reasons, reasons=reasons)

    def failing_rules(self, applicant: Applicant, application: Application,
                      section: Section, position: PositionType) -> List[Tuple[str, str, str]]:
        """Every failing hard rule as (rule id, rule label, reason). Empty = eligible."""
        ctx = self._ctx(applicant, application, section, position)
        out = []
        for key, label, fn in self._rules:
            reason = fn(ctx)
            if reason:
                out.append((key, label, reason))
        return out

    def score(self, applicant: Applicant, application: Application,
              section: Section, position: PositionType) -> float:
        ctx = self._ctx(applicant, application, section, position)
        total = 0.0
        for _, _, fn in self._terms:
            total += fn(ctx)
        return total

    def explain(self, applicant: Applicant, application: Application,
                section: Section, position: PositionType) -> List[Tuple[str, str, float]]:
        """Each scoring term's contribution as (term id, label, points), in profile
        order. The contributions add up to score() exactly."""
        ctx = self._ctx(applicant, application, section, position)
        return [(key, label, fn(ctx)) for key, label, fn in self._terms]


class CompiledProfile:
    """A department profile turned into functions. Safe to reuse across solves."""

    def __init__(self, profile: s.DepartmentProfile):
        self.profile = profile
        self._rules = [(*_rule_key(r, i), _compile_rule(r)) for i, r in enumerate(profile.hard_rules)]
        self._terms = [(*_rule_key(t, i), _compile_term(t)) for i, t in enumerate(profile.scoring)]

    def new_session(self) -> Session:
        return Session(self._rules, self._terms)


def compile_profile(profile: Union[s.DepartmentProfile, dict]) -> CompiledProfile:
    if isinstance(profile, dict):
        profile = s.DepartmentProfile.model_validate(profile)
    return CompiledProfile(profile)


def load_profile(path: Union[str, Path]) -> CompiledProfile:
    """Reads, validates and compiles a profile JSON file."""
    data = json.loads(Path(path).read_text())
    return compile_profile(data)
