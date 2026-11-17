"""Tests for config-driven rules (ta_assignment.rules).

1. Parity: a profile built from the legacy settings must produce the exact same
   candidate table (same applicants, same scores, same order) as the original
   hardcoded check_eligibility + DefaultScoringStrategy, across many settings.
2. Golden: both solvers driven by profiles/gwu_cs.json reach every golden optimum.
3. Validation: bad configs fail on load with a clear message.
4. A second department (profiles/example_math.json) runs through the same code
   and its rules really are enforced.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmarks.generator import generate_instance, generate_sized
from benchmarks.golden import CASES, golden_path
from ta_assignment.csp_solver import CSPSolver, SolverConfig
from ta_assignment.enums import Grade, PositionType
from ta_assignment.matching_solver import MatchingSolver
from ta_assignment.rules import compile_profile, load_profile
from ta_assignment.rules.legacy import profile_from_legacy
from ta_assignment.scoring import DefaultScoringStrategy, EligibilityConfig
from ta_assignment.test_data import load_demo_data
from ta_assignment.test_data_extended import load_extended_data

PROFILES = Path(__file__).resolve().parent.parent / "profiles"


def _datasets():
    for name, loader in [("demo", load_demo_data), ("extended", load_extended_data)]:
        _c, sections, applicants, applications = loader()
        yield name, applicants, applications, sections
    for size, seed in [("small", 1), ("small", 2), ("medium", 1), ("large", 3)]:
        inst = generate_sized(size, seed)
        yield inst.name, inst.applicants, inst.applications, inst.sections


LEGACY_SETTINGS = {
    "no-gpa-floor": (EligibilityConfig(), DefaultScoringStrategy()),
    "gwu-3.0-3.3": (EligibilityConfig(min_gpa=3.0, min_gpa_uta=3.3), DefaultScoringStrategy()),
    "la-only-floor": (EligibilityConfig(min_gpa=3.5), DefaultScoringStrategy()),
    "uta-only-floor": (EligibilityConfig(min_gpa_uta=3.2), DefaultScoringStrategy()),
    "custom-weights": (EligibilityConfig(min_gpa=2.8),
                       DefaultScoringStrategy(grade_weight=1.0, experience_weight=4.0,
                                              recommendation_weight=0.5, preference_weight=5.0,
                                              skill_match_weight=2.0, uta_readiness_bonus=0.0)),
}


@pytest.mark.parametrize("setting", list(LEGACY_SETTINGS))
def test_profile_matches_legacy_candidate_table_exactly(setting):
    eligibility, scorer = LEGACY_SETTINGS[setting]
    compiled = compile_profile(profile_from_legacy(eligibility, scorer))
    for name, applicants, applications, sections in _datasets():
        legacy = CSPSolver(applicants, applications, sections,
                           config=SolverConfig(eligibility=eligibility, scorer=scorer))
        via_profile = CSPSolver(applicants, applications, sections,
                                config=SolverConfig(profile=compiled))
        assert via_profile.candidates == legacy.candidates, f"{setting} differs on {name}"


def test_gwu_profile_file_matches_benchmark_defaults():
    compiled = load_profile(PROFILES / "gwu_cs.json")
    legacy_cfg = SolverConfig(eligibility=EligibilityConfig(min_gpa=3.0, min_gpa_uta=3.3),
                              scorer=DefaultScoringStrategy())
    for name, applicants, applications, sections in _datasets():
        a = CSPSolver(applicants, applications, sections, config=legacy_cfg)
        b = CSPSolver(applicants, applications, sections, config=SolverConfig(profile=compiled))
        assert a.candidates == b.candidates, name


@pytest.mark.parametrize("Solver", [CSPSolver, MatchingSolver], ids=["csp", "matching"])
@pytest.mark.parametrize("name", list(CASES))
def test_profile_driven_solvers_reach_golden_scores(name, Solver):
    expected = json.loads(golden_path(name).read_text())
    applicants, applications, sections = CASES[name]()
    config = SolverConfig(profile=load_profile(PROFILES / "gwu_cs.json"))
    result = Solver(applicants, applications, sections, config=config).solve()
    assert result.optimal
    assert result.total_score == pytest.approx(expected["total_score"], abs=1e-6)


# --- validation ---------------------------------------------------------------

def _minimal(**overrides):
    base = {"version": 1, "department": "Test",
            "hard_rules": [{"rule": "applied_for_position"}],
            "scoring": [{"term": "preference_rank", "weight": 1.0}]}
    base.update(overrides)
    return base


@pytest.mark.parametrize("bad, message", [
    (_minimal(hard_rules=[{"rule": "cmp", "field": "applicant.gpaa", "op": ">=", "value": 3}]), "unknown field"),
    (_minimal(hard_rules=[{"rule": "must_be_nice"}]), "rule"),
    (_minimal(hard_rules=[{"rule": "passed_course", "min_grade": "B+"}]), "unknown grade"),
    (_minimal(hard_rules=[{"rule": "applied_for_position", "colour": "blue"}]), "colour"),
    (_minimal(scoring=[{"term": "course_grade", "weight": "lots"}]), "weight"),
    (_minimal(version=2), "version"),
])
def test_bad_profiles_are_rejected_on_load(bad, message):
    with pytest.raises(ValidationError) as err:
        compile_profile(bad)
    assert message in str(err.value)


# --- behaviour ----------------------------------------------------------------

def test_failing_rules_report_every_reason():
    _c, sections, applicants, applications = load_extended_data()
    compiled = compile_profile(_minimal(hard_rules=[
        {"rule": "passed_course", "min_grade": "A"},
        {"rule": "cmp", "field": "applicant.gpa", "op": ">=", "value": 4.1},
    ]))
    session = compiled.new_session()
    apps = {a.applicant_id: a for a in applications}
    applicant = next(iter(applicants.values()))
    result = session.check(applicant, apps[applicant.applicant_id], sections[0], PositionType.LA)
    assert not result.eligible
    assert any("applicant.gpa" in r for r in result.reasons)


def test_course_scoped_rule_only_applies_to_that_course():
    inst = generate_instance(40, 12, seed=5)
    target = inst.sections[0].course.course_id
    # Nobody can have a GPA above 5, so this rule rejects everyone -- but only for `target`.
    compiled = compile_profile(_minimal(hard_rules=[
        {"rule": "applied_for_position"},
        {"rule": "cmp", "field": "applicant.gpa", "op": ">", "value": 5.0, "courses": [target]},
    ]))
    solver = CSPSolver(inst.applicants, inst.applications, inst.sections, config=SolverConfig(profile=compiled))
    for slot in solver.slots:
        if slot.section.course.course_id == target:
            assert solver.candidates[slot.slot_id] == []
    assert any(solver.candidates[s.slot_id] for s in solver.slots if s.section.course.course_id != target)


def test_example_math_department_rules_are_enforced():
    inst = generate_sized("large", 2)
    math = load_profile(PROFILES / "example_math.json")
    gwu = load_profile(PROFILES / "gwu_cs.json")

    math_result = MatchingSolver(inst.applicants, inst.applications, inst.sections,
                                 config=SolverConfig(profile=math)).solve()
    gwu_result = MatchingSolver(inst.applicants, inst.applications, inst.sections,
                                config=SolverConfig(profile=gwu)).solve()

    sections = {s.section_id: s for s in inst.sections}
    assert math_result.assignments, "math profile should still fill some slots"
    for a in math_result.assignments:
        applicant = inst.applicants[a.applicant_id]
        section = sections[a.section_id]
        grade = applicant.grade_in(section.course.course_id)
        assert grade is not None and not grade < Grade.B_PLUS
        assert (applicant.overall_gpa or 0) >= 3.4 or grade.gpa_points >= 4.0
        if a.position == PositionType.UTA:
            assert applicant.prior_positions_count() >= 1

    # Different policy -> a different assignment from the same applicant pool.
    as_set = lambda r: {(a.applicant_id, a.section_id, a.position) for a in r.assignments}
    assert as_set(math_result) != as_set(gwu_result)


def test_new_session_does_not_reuse_stale_applicant_values():
    inst = generate_instance(10, 4, seed=1)
    compiled = compile_profile(_minimal(hard_rules=[
        {"rule": "cmp", "field": "applicant.prior_positions", "op": ">=", "value": 99},
    ]))
    applicant = next(a for a in inst.applicants.values() if a.teaching_experience)
    app = next(a for a in inst.applications if a.applicant_id == applicant.applicant_id)
    section = inst.sections[0]

    assert not compiled.new_session().check(applicant, app, section, PositionType.LA).eligible
    applicant.teaching_experience = [applicant.teaching_experience[0]] * 99   # data changed between solves
    assert compiled.new_session().check(applicant, app, section, PositionType.LA).eligible
