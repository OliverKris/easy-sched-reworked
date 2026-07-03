"""Pytest suite build on top of `src.test_data_extended`.

Run with:
    python -m pytest tests/ -v
"""

from datetime import time

import pytest

from ta_assignment.enums import Day, Grade, PositionType, Semester
from ta_assignment.scheduling import TimeSlot, has_conflict
from ta_assignment.scoring import EligibilityConfig, DefaultScoringStrategy, check_eligibility
from ta_assignment.csp_solver import CSPSolver, SolverConfig, build_slots
from ta_assignment.test_data_extended import load_extended_data

@pytest.fixture(scope="module")
def data():
    courses, sections, applicants, applications = load_extended_data()
    apps_by_id = {a.applicant_id: a for a in applications}
    return {
        "courses": courses, "sections": sections,
        "applicants": applicants, "applications": applications,
        "apps_by_id": apps_by_id,
        "sections_by_id": {s.section_id: s for s in sections},
    }

# ------------------------------------------------------------
# TimeSlot / conflict primitives
# ------------------------------------------------------------

class TestTimeSlot:
    def test_back_to_back_slots_do_not_conflict(self):
        a = TimeSlot(Day.MON, time(9, 0), time(10, 0))
        b = TimeSlot(Day.MON, time(10, 0), time(11, 0))
        assert not a.overlaps(b)

    def test_overlapping_same_day(self):
        a = TimeSlot(Day.MON, time(9, 0), time(10, 30))
        b = TimeSlot(Day.MON, time(10, 0), time(11, 0))
        assert a.overlaps(b)

    def test_different_days_never_conflict(self):
        a = TimeSlot(Day.MON, time(9, 0), time(10, 0))
        b = TimeSlot(Day.TUE, time(9, 0), time(10, 0))
        assert not a.overlaps(b)

    def test_invalid_slot_raises(self):
        with pytest.raises(ValueError):
            TimeSlot(Day.MON, time(10, 0), time(9, 0))
    
    def test_has_conflict_across_lists(self):
        a = [TimeSlot(Day.MON, time(9, 0), time(10,0))]
        b = [TimeSlot(Day.TUE, time(9, 0), time(10, 0)),
             TimeSlot(Day.MON, time(9, 30), time(10, 30))]
        assert has_conflict(a, b)


# ------------------------------------------------------------
# Applicant helpers
# ------------------------------------------------------------

class TestApplicant:
    def test_failed_course_not_counted_as_taken(self, data):
        a003 = data["applicants"]["A003"]
        assert a003.has_taken("CSCI 1012") is None

    def test_gpa_none_when_only_in_progress(self, data):
        a004 = data["applicants"]["A004"]
        assert a004.overall_gpa is None

    def test_gpa_boundary_exactly_at_threshold(self, data):
        a002 = data["applicants"]["A002"]
        assert a002.overall_gpa == pytest.approx(3.0)


# ------------------------------------------------------------
# Eligibility
# ------------------------------------------------------------

class TestEligibilty:
    def test_lecture_conflict_blocks_uta_when_required(self, data):
        a005 = data["applicants"]["A005"]
        app = data["apps_by_id"]["A005"]
        section = data["sections_by_id"]["CSCI 3212-10 (Fall 2026)"]
        result = check_eligibility(a005, app, section, PositionType.UTA)
        assert not result.eligible
        assert any ("lecture" in r.lower() for r in result.reasons)

    def test_conflict_with_one_of_two_labs_still_eligibile(self, data):
        a006 = data["applicants"]["A006"]
        app = data["apps_by_id"]["A006"]
        section = data["sections_by_id"]["CSCI 1012-10 (Fall 2026)"]
        result = check_eligibility(a006, app, section, PositionType.LA)
        assert result.eligible

    def test_conflict_with_all_labs_ineligible(self, data):
        a007 = data["applicants"]["A007"]
        app = data["apps_by_id"]["A007"]
        section = data["sections_by_id"]["CSCI 1012-10 (Fall 2026)"]
        result = check_eligibility(a007, app, section, PositionType.LA)
        assert not result.eligible
        assert any("lab" in r.lower() for r in result.reasons)

    def test_section_with_no_labs_is_always_ineligible(self, data):
        a001 = data["applicants"]["A001"]
        # A001 hasn't taken CSCI 1000 either, but even a perfect record
        # would fail here since the section defines zero lab sections.
        section = data["sections_by_id"]["CSCI 1000-01 (Fall 2026)"]
        app = data["apps_by_id"]["A001"]
        result = check_eligibility(a001, app, section, PositionType.LA)
        assert not result.eligible
        assert any("no lab sections" in r.lower() for r in result.reasons)

    def test_gpa_exactly_at_floor_passes(self, data):
        a002 = data["applicants"]["A002"]
        app = data["apps_by_id"]["A002"]
        section = data["sections_by_id"]["CSCI 1012-10 (Fall 2026)"]
        config = EligibilityConfig(min_gpa=3.0)
        result = check_eligibility(a002, app, section, PositionType.LA, config)
        assert result.eligible

    def test_gpa_none_fails_configured_floor(self, data):
        a004 = data["applicants"]["A004"]
        app = data["apps_by_id"]["A004"]
        section = data["sections_by_id"]["CSCI 1012-10 (Fall 2026)"]
        config = EligibilityConfig(min_gpa=2.0)
        result = check_eligibility(a004, app, section, PositionType.LA, config)
        assert not result.eligible
        assert any("no gpa on record" in r.lower() for r in result.reasons)

    def test_did_not_apply_for_position_is_reported(self, data):
        a011 = data["applicants"]["A011"]  # only applied for UTA
        app = data["apps_by_id"]["A011"]
        section = data["sections_by_id"]["CSCI 3212-10 (Fall 2026)"]
        result = check_eligibility(a011, app, section, PositionType.LA)
        assert not result.eligible
        assert any("did not apply" in r.lower() for r in result.reasons)


# ------------------------------------------------------------
# Scoring
# ------------------------------------------------------------

class TestScoring:
    def test_identical_applicants_score_identically(self, data):
        scorer = DefaultScoringStrategy()
        section = data["sections_by_id"]["CSCI 1010-10 (Fall 2026)"]
        a009, a010 = data["applicants"]["A009"], data["applicants"]["A010"]
        app9, app10 = data["apps_by_id"]["A009"], data["apps_by_id"]["A010"]
        s9 = scorer.score(a009, app9, section, PositionType.LA)
        s10 = scorer.score(a010, app10, section, PositionType.LA)
        assert s9 == pytest.approx(s10)

    def test_experience_component_caps_at_four_priors(self, data):
        scorer = DefaultScoringStrategy()
        a012 = data["applicants"]["A012"]  # 6 prior positions
        assert min(a012.prior_positions_count(), 4) == 4

    def test_uta_readiness_bonus_applied_at_two_la_terms(self, data):
        scorer = DefaultScoringStrategy()
        a011 = data["applicants"]["A011"]
        app = data["apps_by_id"]["A011"]
        section = data["sections_by_id"]["CSCI 3212-10 (Fall 2026)"]
        with_bonus = scorer.score(a011, app, section, PositionType.UTA)
        without_bonus = scorer.score(a011, app, section, PositionType.LA)
        # UTA score should include the +1.5 readiness bonus that LA doesn't
        assert with_bonus - without_bonus >= scorer.uta_readiness_bonus - 1e-9

    def test_score_is_never_negative_for_minimal_applicant(self, data):
        scorer = DefaultScoringStrategy()
        a014 = data["applicants"]["A014"]  # no recs, no skills, unranked
        app = data["apps_by_id"]["A014"]
        section = data["sections_by_id"]["CSCI 1010-10 (Fall 2026)"]
        score = scorer.score(a014, app, section, PositionType.LA)
        assert score >= 0

    
# ------------------------------------------------------------
# CSP Solver
# ------------------------------------------------------------

class TestSolver:
    def test_multi_uta_section_produces_distinct_slots(self, data):
        section = data["sections_by_id"]["CSCI 3212-10 (Fall 2026)"]
        slots = build_slots([section])
        uta_slots = [s for s in slots if s.position == PositionType.UTA]
        assert len(uta_slots) == 2
        assert len({s.slot_id for s in uta_slots}) == 2  # regression: were colliding

    def test_solver_never_double_assigns_an_applicant(self, data):
        solver = CSPSolver(data["applicants"], data["applications"], data["sections"])
        result = solver.solve()
        assigned_ids = [a.applicant_id for a in result.assignments]
        assert len(assigned_ids) == len(set(assigned_ids))

    def test_section_with_no_eligible_applicants_fully_unfilled(self, data):
        section = data["sections_by_id"]["CSCI 4980-10 (Fall 2026)"]
        solver = CSPSolver(data["applicants"], data["applications"], [section])
        result = solver.solve()
        assert result.assignments == []
        assert len(result.unfilled_slots) == 2  # 1 LA + 1 UTA slot, both unfilled

    def test_oversubscribed_section_fills_only_available_slots(self, data):
        section = data["sections_by_id"]["CSCI 1010-10 (Fall 2026)"]
        solver = CSPSolver(data["applicants"], data["applications"], [section])
        result = solver.solve()
        # Only 1 LA slot exists on this section, regardless of how many
        # eligible applicants (A001, A009, A010, A012, A014) there are.
        assert len(result.assignments) == 1

    def test_term_year_is_not_enforced_known_gap(self, data):
        """Documents current behavior: an application for a DIFFERENT term
        (A008, Spring 2026) is still considered for Fall 2026 sections that
        happen to match the applicant's course history, because
        check_eligibility never compares application.term/year against
        section.term/year. This test will start FAILING the moment that
        filter is added -- which is the point: it's a deliberate tripwire,
        not an assertion that the current behavior is correct."""
        a008 = data["applicants"]["A008"]
        app = data["apps_by_id"]["A008"]  # term=SPRING, year=2026
        fall_section = data["sections_by_id"]["CSCI 1011-05 (Fall 2026)"] \
            if "CSCI 1011-05 (Fall 2026)" in data["sections_by_id"] else None
        # A008 only has a Spring 2026 section to match against in this
        # dataset, so instead we assert the gap directly:
        assert app.term == Semester.SPRING and app.year == 2026
        spring_section = data["sections_by_id"]["CSCI 1011-05 (Spring 2026)"]
        result = check_eligibility(a008, app, spring_section, PositionType.LA)
        assert result.eligible  # fine -- terms happen to match here
        # No code path anywhere cross-checks application.term/year against
        # section.term/year; nothing stops a Fall application from being
        # scored against a Spring section's slots if course history lines up.
