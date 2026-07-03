"""Eligibility (hard constraints) and score (soft preferences) for
matching an Applicant/Application to a Section + PositionType.

Eligibility answers "CAN this applicant fill this slot at all?" (used to 
prune the CSP's domains). Scoring answers "HOW GOOD a fit they are?" (used
as the objective the solver maximizes). Scoring is intentionally pluggable
via `ScoreingStrategy` so you can swap in different weighting schemes later.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from .applicants import Applicant
from .applications import Application
from .courses import Section
from .enums import PositionType
from .scheduling import has_conflict


@dataclass
class EligibilityConfig:
    """Admin-tunable hard-constraint settings, applied across the whole
    hiring cycle. Kept seperate from PostionRequirement since these are
    deparment/admin-level policy knobs rather than per-section facts.
    """
    # Minimum overall GPA required to be eligible at all. None = no floor
    min_gpa: Optional[float] = None
    # Optionally set a stricter floor specifically for UTAs (who carry more
    # responsibility) while leaving LA at `min_gpa`. None = use min_gpa for both.
    min_gpa_uta: Optional[float] = None

    def threshold_for(self, positon: PositionType) -> Optional[float]:
        if positon == PositionType.UTA and self.min_gpa_uta is not None:
            return self.min_gpa_uta
        return self.min_gpa


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: List[str]  # human-readable reasons, populated when ineligible


def check_eligibility(applicant: Applicant, application: Application,
                        section: Section, position: PositionType,
                        config: Optional[EligibilityConfig] = None) -> EligibilityResult:
    """Hard constraints only:
        1. Applicant applied for this position type.
        2. Applicant has taken (and passed) the course.
        3. No schedule conflict with lecture, IF this position must attend lecture.
        4. At least one lab section the applicant can attend without conflict.
        5. Applicant's overall GPA meets the admin-configured threshold, if set.
    """
    reasons = []

    if not application.wants_position(position):
        reasons.append(f"Did not apply for {position.value}")

    if applicant.has_taken(section.course.course_id) is None:
        reasons.append(f"Has not taken/passed {section.course.course_id}")

    reqs = section.position_requirements
    if reqs.must_attend_lecture(position):
        if has_conflict(applicant.upcoming_schedule, section.lecture_meetings):
            reasons.append("Schedule conflicts with required lecture time")

    if section.labs:
        conflict_free_lab = any(
            not has_conflict(applicant.upcoming_schedule, lab.meetings)
            for lab in section.labs
        )
        if not conflict_free_lab:
            reasons.append("No conflict-free lab section available")
    else:
        reasons.append("Section has no lab sections defined")

    if config is not None:
        threshold = config.threshold_for(position)
        if threshold is not None:
            gpa = applicant.overall_gpa
            if gpa is None:
                reasons.append(f"No GPA on record (requires >= {threshold:.2f})")
            elif gpa < threshold:
                reasons.append(f"GPA {gpa:.2f} below required {threshold:.2f}")

    return EligibilityResult(eligible=(len(reasons) == 0), reasons=reasons)


class ScoringStrategy(ABC):
    """Pluggable objective function. Implement `score` to change how
    candidates are ranked; the CSP solver just maximizes whatever this
    returns."""

    @abstractmethod
    def score(self, applicant: Applicant, application: Application,
                section: Section, position: PositionType) -> float:
        ...


@dataclass
class DefaultScoringStrategy(ScoringStrategy):
    """Weighted sum of: grade in the course, prior teaching experience,
    recommendation strenght, honoring the applicant's ranked preference,
    and skill/topic overlap with the course. All weights are tunable so
    an admin can customize the algorithm's priorities per your requirement.
    """
    grade_weight: float = 3.0
    experience_weight: float = 2.5
    recommendation_weight: float = 2.0
    preference_weight: float = 2.5
    skill_match_weight: float = 1.0

    # Soft norm: applicants are expectedc to LA for ~2 semesters before
    # becoming a UTA. This bonus rewards UTA applicants who've met that
    # norm (it's a preference signal, not a hard eligibility rule).
    uta_readiness_bonus: float = 1.5

    def score(self, applicant: Applicant, application: Application,
                section: Section, position: PositionType) -> float:
        course_id = section.course.course_id
        total = 0.0

        # 1. Grade earned in the course (0-4 scale -> normalize to 0-1)
        grade = applicant.grade_in(course_id)
        if grade is not None:
            total += self.grade_weight * (grade.gpa_points / 4.0)

        # 2. Prior teaching experience (general, plus bonus for this exact course)
        general_exp = min(applicant.prior_positions_count(), 4) / 4.0
        course_exp_bonus = 1.0 if applicant.has_taught(course_id) else 0.0
        total += self.experience_weight * (0.6 * general_exp + 0.4 * course_exp_bonus)

        # 3. Recommendations (average strength, normalized off a 1-5 scale)
        if applicant.recommendations:
            avg_strength = sum(r.strength for r in applicant.recommendations) / len(applicant.recommendations)
            total += self.recommendation_weight * (avg_strength / 5.0)

        # 4. Honor the applicant's ranked course preference (rank 1 = best)
        rank = application.preference_rank(course_id)
        preference_score = 1.0 / rank # rank 1 -> 1.0, rank 2 -> 0.5, ...
        total += self.preference_weight * preference_score

        # 5. Skill/topic overlap between applicant and course
        if section.course.skills:
            overlap = len(applicant.skills & section.course.skills) / len(section.course.skills)
            total += self.skill_match_weight * overlap

        # 6. Soft norm bonus: 2+ semesters as LA before applying as UTA
        if position == PositionType.UTA and applicant.prior_positions_count(PositionType.LA) >= 2:
            total += self.uta_readiness_bonus

        return total