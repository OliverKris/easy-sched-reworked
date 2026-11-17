"""Golden regression tests: the solver must keep producing the recorded results.

Two levels of strictness:
    - test_optimal_score_unchanged: the total score must match. Every case is
      one the solver proved optimal, so ANY correct solver must reach this
      score. A failure here means a real bug.
    - test_assignments_unchanged: the exact assignment must match. When two
      solutions tie on score, a refactor that changes tie-breaking can fail
      this without being wrong. If so, check the new result is still valid,
      then regenerate with `python -m benchmarks.golden --update`.
"""

import json

import pytest

from benchmarks.golden import CASES, golden_path, solve_case


def _load(name: str) -> dict:
    path = golden_path(name)
    if not path.exists():
        pytest.fail(f"missing golden file {path}; run `python -m benchmarks.golden --update`")
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def results():
    return {name: solve_case(name) for name in CASES}


@pytest.mark.parametrize("name", list(CASES))
def test_optimal_score_unchanged(name, results):
    expected = _load(name)
    actual = results[name]
    assert actual["optimal"], f"{name}: solver no longer proves optimality"
    assert actual["total_score"] == pytest.approx(expected["total_score"], abs=1e-6)


@pytest.mark.parametrize("name", list(CASES))
def test_assignments_unchanged(name, results):
    expected = _load(name)
    actual = results[name]
    assert actual["filled"] == expected["filled"]
    assert actual["assignments"] == expected["assignments"]
    assert actual["unfilled"] == expected["unfilled"]


def test_generator_is_deterministic():
    from benchmarks.generator import generate_instance
    a = generate_instance(30, 10, seed=7)
    b = generate_instance(30, 10, seed=7)
    assert [str(x) for x in a.sections] == [str(x) for x in b.sections]
    assert [vars(x) for x in a.applications] == [vars(x) for x in b.applications]
    assert [x.past_courses for x in a.applicants.values()] == [x.past_courses for x in b.applicants.values()]


def test_reference_matches_optimal_csp():
    """Where backtracking proves optimality, the matching yardstick must agree.
    Guards the claim the benchmark's `gap` column relies on."""
    from benchmarks import reference
    from benchmarks.generator import generate_instance
    from benchmarks.run import default_config
    from ta_assignment.csp_solver import CSPSolver

    if not reference.available():
        pytest.skip("scipy not installed")
    for n_applicants, n_sections, seed in [(8, 3, 1), (10, 4, 1), (10, 4, 2), (12, 5, 3)]:
        inst = generate_instance(n_applicants, n_sections, seed)
        solver = CSPSolver(inst.applicants, inst.applications, inst.sections, config=default_config())
        result = solver.solve()
        assert result.optimal
        assert reference.matching_optimum(solver) == pytest.approx(result.total_score, abs=1e-6)