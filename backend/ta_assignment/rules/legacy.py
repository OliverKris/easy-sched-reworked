"""Bridge from the original hardcoded settings to a department profile.

The API and UI currently send GPA floors and scoring weights
(EligibilityConfig + DefaultScoringStrategy). profile_from_legacy() turns
those into the equivalent DepartmentProfile, so the app can move onto the
config-driven path without changing what users see, and the parity tests can
check old and new agree across many settings.
"""

from typing import Optional

from ..scoring import DefaultScoringStrategy, EligibilityConfig
from .schema import DepartmentProfile


def profile_from_legacy(eligibility: Optional[EligibilityConfig] = None,
                        scorer: Optional[DefaultScoringStrategy] = None,
                        department: str = "Legacy settings") -> DepartmentProfile:
    eligibility = eligibility or EligibilityConfig()
    scorer = scorer or DefaultScoringStrategy()

    hard_rules = [
        {"id": "applied", "rule": "applied_for_position"},
        {"id": "passed-course", "rule": "passed_course"},
        {"id": "lecture", "rule": "no_lecture_conflict", "when": "if_required"},
        {"id": "lab", "rule": "conflict_free_lab"},
    ]
    # Mirrors EligibilityConfig.threshold_for: UTAs use min_gpa_uta when set,
    # otherwise min_gpa; LAs always use min_gpa.
    if eligibility.min_gpa is not None:
        positions = ["LA"] if eligibility.min_gpa_uta is not None else ["LA", "UTA"]
        hard_rules.append({"id": "min-gpa", "rule": "cmp", "field": "applicant.gpa",
                           "op": ">=", "value": eligibility.min_gpa, "positions": positions})
    if eligibility.min_gpa_uta is not None:
        hard_rules.append({"id": "min-gpa-uta", "rule": "cmp", "field": "applicant.gpa",
                           "op": ">=", "value": eligibility.min_gpa_uta, "positions": ["UTA"]})

    # Same order and arithmetic as DefaultScoringStrategy.score.
    scoring = [
        {"id": "grade", "term": "course_grade", "weight": scorer.grade_weight},
        {"id": "experience", "term": "teaching_experience", "weight": scorer.experience_weight,
         "cap": 4, "general_share": 0.6, "course_share": 0.4},
        {"id": "recommendations", "term": "recommendation_strength", "weight": scorer.recommendation_weight},
        {"id": "preference", "term": "preference_rank", "weight": scorer.preference_weight},
        {"id": "skills", "term": "skill_overlap", "weight": scorer.skill_match_weight},
        {"id": "uta-readiness", "term": "bonus", "weight": scorer.uta_readiness_bonus,
         "positions": ["UTA"],
         "when": {"rule": "cmp", "field": "applicant.prior_la_terms", "op": ">=", "value": 2}},
    ]

    return DepartmentProfile.model_validate({
        "version": 1,
        "department": department,
        "hard_rules": hard_rules,
        "scoring": scoring,
    })
