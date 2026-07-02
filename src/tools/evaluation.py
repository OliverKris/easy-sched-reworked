"""
evaluation.py — TA Applicant Scoring Pipeline

Stages:
    1. Hard filters  — disqualify ineligible applicants before scoring
    2. Dimension scores — five weighted sub-scores (each 0–100)
    3. Override layer — post-score adjustments (workload, continuity)

Public API:
    evaluate(student, group, context) -> EvaluationResult | None
    evaluate_all(student, groups, context) -> List[EvaluationResult]
    evaluate_matrix(students, groups, context) -> Dict[str, Dict[str, EvaluationResult]]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models.application import StudentApplication, has_time_conflict
from models.assignment import PositionType
from models.course import SectionGroup


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Dimension weights — must sum to 1.0
WEIGHTS = {
    "preference":    0.25,
    "academic_fit":  0.25,
    "ta_experience": 0.20,
    "skill_match":   0.20,
    "recommendation": 0.10,
}

# Hard filter thresholds
MIN_GPA_UG   = 2.75   # undergraduate floor
MIN_GPA_GRAD = 3.00   # graduate floor

# Override layer constants
WORKLOAD_PENALTY_PER_SLOT = 5.0   # deducted per existing TA slot held this term
REPEAT_TA_BONUS            = 8.0   # added if applicant TAed this exact course before
SAME_COURSE_RECENT_BONUS   = 5.0   # additional bonus if that was within 2 semesters


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DimensionScores:
    """Raw 0–100 score for each dimension, before weighting."""
    preference:    float = 0.0
    academic_fit:  float = 0.0
    ta_experience: float = 0.0
    skill_match:   float = 0.0
    recommendation: float = 0.0


@dataclass
class EvaluationResult:
    student_id:  str
    group_id:    str
    final_score: float                   # weighted sum + overrides, clamped [0, 100]
    dimensions:  DimensionScores = field(default_factory=DimensionScores)
    override_delta: float = 0.0          # net points added/subtracted by override layer
    filter_reason: Optional[str] = None  # set when the applicant was disqualified
    eligible: bool = True


@dataclass
class EvaluationContext:
    """
    Runtime context the scorer cannot derive from the application alone.
    Pass this in from the scheduler so scoring stays stateless.
    """
    # student_id -> number of TA slots already assigned this term
    current_slot_counts: Dict[str, int] = field(default_factory=dict)

    # student_id -> list of (course_number, semesters_ago) from their history
    # If you already have this in the applicant JSON, the parser can build it.
    # This field is optional — the scorer falls back to the applicant's
    # ta_history attribute when the context dict is empty.
    ta_history_override: Dict[str, list] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Hard Filters
# ─────────────────────────────────────────────────────────────────────────────

def _passes_hard_filters(
        student: StudentApplication,
        group: SectionGroup,
        context: EvaluationContext,
) -> Optional[str]:
    """
    Return a disqualification reason string if the applicant should be filtered
    out, or None if they pass all gates.
    """
    from models.application import StudentLevel

    # 1a. GPA floor
    if student.gpa is not None:
        floor = (MIN_GPA_GRAD
                 if student.student_level == StudentLevel.GRADUATE
                 else MIN_GPA_UG)
        if student.gpa < floor:
            return f"GPA {student.gpa:.2f} below department minimum {floor:.2f}"

    # 1b. Schedule conflict with any section in the group
    for section in group.all_sections:
        for meeting in section.meetings:
            if meeting.days and meeting.start_time and meeting.end_time:
                if has_time_conflict(student, meeting.days,
                                     meeting.start_time, meeting.end_time):
                    return (f"Schedule conflict with section {section.crn} "
                            f"({meeting.days} {meeting.start_time}–{meeting.end_time})")

    # 1c. Already at max TA slots
    max_slots = getattr(student, "max_ta_slots", 1)
    current   = context.current_slot_counts.get(student.student_id, 0)
    if current >= max_slots:
        return f"Already holds {current}/{max_slots} TA slot(s) this term"

    return None  # passed all filters


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Dimension Scorers (each returns 0–100)
# ─────────────────────────────────────────────────────────────────────────────

def _score_preference(student: StudentApplication, group: SectionGroup) -> float:
    """
    Rank-based preference score.
    1st choice → 100, 2nd → 75, 3rd → 50, 4th → 30, 5th+ → 15, unlisted → 0.
    """
    rank_scores = {1: 100, 2: 75, 3: 50, 4: 30, 5: 15}
    group_number = group.course_number  # e.g. "1012"

    for pref in student.preferred_courses:
        # preferences store "CSCI 1012"; strip the subject prefix
        pref_number = pref.course_number.split()[-1]
        if pref_number == group_number:
            return float(rank_scores.get(pref.preference_rank, 10))

    return 0.0  # not in the applicant's preference list


def _score_academic_fit(student: StudentApplication, group: SectionGroup) -> float:
    """
    Blended score: 40% raw GPA contribution + 60% grade-in-this-course.

    Grade points map:
        A/A+ → 100   A- → 92   B+ → 83   B → 75   B- → 67
        C+ → 58      C  → 50   below C → 20   not taken → 0

    The GPA sub-score scales linearly: 4.0 → 100, department floor → 0.
    """
    from models.application import StudentLevel

    # GPA sub-score
    if student.gpa is None:
        gpa_score = 50.0  # unknown — give benefit of the doubt
    else:
        floor = MIN_GPA_GRAD if student.student_level == StudentLevel.GRADUATE else MIN_GPA_UG
        gpa_score = min(100.0, max(0.0, (student.gpa - floor) / (4.0 - floor) * 100))

    # Grade-in-course sub-score
    grade_map = {
        "A+": 100, "A": 100, "A-": 92,
        "B+": 83,  "B": 75,  "B-": 67,
        "C+": 58,  "C": 50,  "C-": 35,
        "D":  20,  "F": 0,
    }

    grade_score = 0.0
    group_number = group.course_number

    course_grades = getattr(student, "course_grades", [])
    for entry in course_grades:
        cnum = str(entry.get("course_number", "")).split()[-1]
        if cnum == group_number:
            raw_grade = entry.get("grade", "").strip()
            grade_score = float(grade_map.get(raw_grade, 0))
            break
    # If we have no grade record, fall back to GPA-only
    # (weight fully toward GPA if course grade is missing)
    if grade_score == 0.0:
        return gpa_score

    return 0.40 * gpa_score + 0.60 * grade_score


def _score_ta_experience(student: StudentApplication, group: SectionGroup) -> float:
    """
    Score based on prior TA history, split into three tiers:

    Tier A — Same-course stints (scored first, highest weight)
        Most recent same-course stint:
            ≤1 semester ago → 100
            2 semesters ago → 85
            3–4 semesters ago → 70
            5+ semesters ago → 55

    Tier B — General TA experience (any course), only if no same-course match
        Base 35 pts for having any history, plus recency bonus for best stint:
            ≤1 semester ago → +30   (total 65)
            2 semesters ago → +20   (total 55)
            3–4 semesters ago → +12 (total 47)
            5+ semesters ago → +5   (total 40)

    Tier C — No TA history → 0

    Rationale: someone who TAed THIS course recently should clearly outscore
    someone with unrelated TA experience, regardless of recency.
    """
    ta_history = getattr(student, "ta_history", [])
    if not ta_history:
        return 0.0

    group_number = group.course_number

    same_course_scores = {1: 100, 2: 85, 3: 70, 4: 70, 5: 55}
    general_recency    = {1: 30,  2: 20, 3: 12, 4: 12, 5: 5}

    # Tier A: find the most recent same-course stint
    best_same = None
    for stint in ta_history:
        history_number = str(stint.get("course_number", "")).split()[-1]
        if history_number == group_number:
            ago = int(stint.get("semesters_ago", 99))
            if best_same is None or ago < best_same:
                best_same = ago

    if best_same is not None:
        return float(same_course_scores.get(best_same, 55))

    # Tier B: general TA experience — use the most recent stint
    best_ago = min(int(s.get("semesters_ago", 99)) for s in ta_history)
    return float(35 + general_recency.get(best_ago, 5))


def _score_skill_match(student: StudentApplication, group: SectionGroup) -> float:
    """
    Overlap score: matched_skills / total_required_skills * 100.

    Falls back to 50 if the course has no declared skill requirements
    (avoids punishing applicants for incomplete course metadata).
    """
    required: list = getattr(group, "skills_required", [])
    if not required:
        return 50.0  # no metadata — neutral score

    student_skills_lower = {s.lower() for s in student.skills}
    required_lower       = [r.lower() for r in required]

    matched = sum(1 for r in required_lower if r in student_skills_lower)
    return round(matched / len(required_lower) * 100, 1)


def _score_recommendation(student: StudentApplication, group: SectionGroup) -> float:
    """
    Composite rec score based on:
        - Recommender seniority: faculty → 40 pts, lecturer → 28 pts, industry → 18 pts
        - Tone:                  strong  → 40 pts, neutral  → 20 pts, weak     → 5 pts
        - Relevance:             rec is for a course related to this group → +10 pts
        - No recommendations     → 30 pts (neutral default — absence ≠ poor candidate)
        - Lukewarm rec           → worse than no rec (5 pts tone = below 30)

    If the applicant has multiple recommendations, average the per-rec scores.
    """
    recs = student.recommendations
    if not recs:
        return 30.0  # neutral default

    seniority_scores = {"faculty": 40, "lecturer": 28, "industry": 18}
    tone_scores      = {"strong": 40, "neutral": 20, "weak": 5}
    group_number     = group.course_number

    per_rec = []
    for rec in recs:
        seniority = getattr(rec, "recommender_seniority",
                            rec.__dict__.get("recommender_seniority", "faculty")
                            if hasattr(rec, "__dict__") else "faculty")
        tone      = getattr(rec, "tone",
                            rec.__dict__.get("tone", "neutral")
                            if hasattr(rec, "__dict__") else "neutral")

        s = float(seniority_scores.get(seniority, 28))
        t = float(tone_scores.get(tone, 20))

        # Relevance bonus: did the professor teach the same or related course?
        course_taught_num = str(getattr(rec, "course_taught", "")).split()[-1]
        relevance = 10.0 if course_taught_num == group_number else 0.0

        per_rec.append(min(100.0, s + t + relevance))

    return round(sum(per_rec) / len(per_rec), 1)


# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 — Weighted Sum
# ─────────────────────────────────────────────────────────────────────────────

def _weighted_score(dims: DimensionScores) -> float:
    return (
        dims.preference    * WEIGHTS["preference"]    +
        dims.academic_fit  * WEIGHTS["academic_fit"]  +
        dims.ta_experience * WEIGHTS["ta_experience"] +
        dims.skill_match   * WEIGHTS["skill_match"]   +
        dims.recommendation * WEIGHTS["recommendation"]
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 — Override Layer
# ─────────────────────────────────────────────────────────────────────────────

def _apply_overrides(
        raw_score: float,
        student: StudentApplication,
        group: SectionGroup,
        context: EvaluationContext,
) -> tuple[float, float]:
    """
    Return (adjusted_score, delta) after applying override adjustments.

    Overrides (applied in order, all additive/subtractive):
        - Workload penalty: -WORKLOAD_PENALTY_PER_SLOT per existing TA slot
        - Repeat TA bonus: +REPEAT_TA_BONUS if same course TAed before
          + SAME_COURSE_RECENT_BONUS if that was within 2 semesters
    """
    delta = 0.0

    # Workload balance penalty
    slots_held = context.current_slot_counts.get(student.student_id, 0)
    if slots_held > 0:
        delta -= slots_held * WORKLOAD_PENALTY_PER_SLOT

    # Continuity bonus: small nudge for repeating the same course,
    # on top of what the dimension score already captured.
    # Kept modest (REPEAT_TA_BONUS = 8) since the tier-A dimension
    # score already gives same-course experience its primary reward.
    for stint in getattr(student, "ta_history", []):
        history_number = str(stint.get("course_number", "")).split()[-1]
        if history_number == group.course_number:
            delta += REPEAT_TA_BONUS
            break  # one application only; recency already in dimension score

    adjusted = min(100.0, max(0.0, raw_score + delta))
    return adjusted, delta


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(
        student: StudentApplication,
        group: SectionGroup,
        context: Optional[EvaluationContext] = None,
) -> EvaluationResult:
    """
    Score one applicant against one section group.
    Returns an EvaluationResult with eligible=False and a filter_reason
    if the applicant is disqualified at the hard-filter stage.
    """
    if context is None:
        context = EvaluationContext()

    # Stage 1 — Hard filters
    reason = _passes_hard_filters(student, group, context)
    if reason:
        return EvaluationResult(
            student_id=student.student_id,
            group_id=group.group_id,
            final_score=0.0,
            eligible=False,
            filter_reason=reason,
        )

    # Stage 2 — Dimension scores
    dims = DimensionScores(
        preference    = _score_preference(student, group),
        academic_fit  = _score_academic_fit(student, group),
        ta_experience = _score_ta_experience(student, group),
        skill_match   = _score_skill_match(student, group),
        recommendation = _score_recommendation(student, group),
    )

    # Stage 3 — Weighted sum
    raw = _weighted_score(dims)

    # Stage 4 — Override layer
    final, delta = _apply_overrides(raw, student, group, context)

    return EvaluationResult(
        student_id=student.student_id,
        group_id=group.group_id,
        final_score=round(final, 2),
        dimensions=dims,
        override_delta=round(delta, 2),
        eligible=True,
    )


def evaluate_all(
        student: StudentApplication,
        groups: List[SectionGroup],
        context: Optional[EvaluationContext] = None,
) -> List[EvaluationResult]:
    """Score one applicant against every section group."""
    if context is None:
        context = EvaluationContext()
    return [evaluate(student, g, context) for g in groups]


def evaluate_matrix(
        students: List[StudentApplication],
        groups: List[SectionGroup],
        context: Optional[EvaluationContext] = None,
) -> Dict[str, Dict[str, EvaluationResult]]:
    """
    Score every applicant against every group.
    Returns matrix[student_id][group_id] = EvaluationResult.
    Useful for the Stage 4 assignment optimizer.
    """
    if context is None:
        context = EvaluationContext()
    return {
        s.student_id: {g.group_id: evaluate(s, g, context) for g in groups}
        for s in students
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick smoke test — run directly: python evaluation.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from tools.processed_parser import load_section_groups
    from tools.applicant_parser import load_applications

    DATA     = os.path.join(os.path.dirname(__file__), "..", "data")
    groups   = load_section_groups(os.path.join(DATA, "processed_courses.json"))
    students = load_applications(os.path.join(DATA, "applicants.json"))

    print(f"Loaded {len(groups)} section groups, {len(students)} applicants\n")

    # Show top-5 candidates for each group
    for group in groups:
        results = [evaluate(s, group) for s in students]
        eligible = sorted(
            [r for r in results if r.eligible],
            key=lambda r: r.final_score, reverse=True
        )
        print(f"── {group.course_subject} {group.course_number} [{group.instructor}]")
        for r in eligible[:5]:
            student = next(s for s in students if s.student_id == r.student_id)
            dims = r.dimensions
            print(
                f"  {student.name:<22} {r.final_score:5.1f}  "
                f"[pref={dims.preference:.0f} "
                f"acad={dims.academic_fit:.0f} "
                f"ta={dims.ta_experience:.0f} "
                f"skill={dims.skill_match:.0f} "
                f"rec={dims.recommendation:.0f}]"
                + (f"  override={r.override_delta:+.1f}" if r.override_delta else "")
            )
        if not eligible:
            print("  (no eligible applicants)")
        print()
