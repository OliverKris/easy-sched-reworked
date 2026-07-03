"""Tests for lock/block constraints in CSPSolver (ta_assignment.locks +
the _resolve_locks logic in csp_solver.py).

Run with:
    python -m pytest backend/tests/ -v
"""

import pytest

from ta_assignment.csp_solver import CSPSolver, SolverConfig
from ta_assignment.enums import PositionType
from ta_assignment.locks import Lock, LockType
from ta_assignment.test_data_extended import load_extended_data


@pytest.fixture(scope="module")
def data():
    courses, sections, applicants, applications = load_extended_data()
    return {
        "applicants": applicants,
        "applications": applications,
        "sections": sections,
        "sections_by_id": {s.section_id: s for s in sections},
    }


SECTION_1010 = "CSCI 1010-10 (Fall 2026)"   # 1 LA slot, several eligible applicants
SECTION_3212 = "CSCI 3212-10 (Fall 2026)"   # 2 UTA slots

class TestLocking:
    def test_locked_applicant_is_placed_even_if_not_top_scorer(self, data):
        # A014 is eligible for CSCI 1010 LA but scores low (no recs, no
        # skill overlap, unranked). Without a lock the solver would never
        # pick them over A001/A009/A010/A012.
        lock = Lock("A014", SECTION_1010, PositionType.LA, LockType.LOCKED)
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=[lock]),
        )
        result = solver.solve()
        winners = {a.applicant_id for a in result.assignments if a.section_id == SECTION_1010}
        assert winners == {"A014"}
        assert result.lock_conflicts == []

    def test_locked_applicant_excluded_from_search_pool_elsewhere(self, data):
        # Locking A001 into 1010 should remove them from consideration for
        # every other free slot (they can only hold one position).
        lock = Lock("A001", SECTION_1010, PositionType.LA, LockType.LOCKED)
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=[lock]),
        )
        result = solver.solve()
        assert sum(1 for a in result.assignments if a.applicant_id == "A001") == 1

    def test_two_locks_fill_both_uta_slots_on_a_two_slot_section(self, data):
        locks = [
            Lock("A005", SECTION_3212, PositionType.UTA, LockType.LOCKED),
            Lock("A011", SECTION_3212, PositionType.UTA, LockType.LOCKED),
        ]
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=locks),
        )
        result = solver.solve()
        winners = {a.applicant_id for a in result.assignments if a.section_id == SECTION_3212}
        assert winners == {"A005", "A011"}
        assert result.lock_conflicts == []

    def test_third_lock_on_a_two_slot_section_is_a_conflict(self, data):
        locks = [
            Lock("A005", SECTION_3212, PositionType.UTA, LockType.LOCKED),
            Lock("A011", SECTION_3212, PositionType.UTA, LockType.LOCKED),
            Lock("A001", SECTION_3212, PositionType.UTA, LockType.LOCKED),  # no slot left
        ]
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=locks),
        )
        result = solver.solve()
        assert any("no open slot remaining" in c for c in result.lock_conflicts)
        assert not any(a.applicant_id == "A001" and a.section_id == SECTION_3212 for a in result.assignments)

    def test_double_locked_applicant_keeps_first_lock_flags_second(self, data):
        locks = [
            Lock("A001", SECTION_1010, PositionType.LA, LockType.LOCKED),
            Lock("A001", SECTION_3212, PositionType.UTA, LockType.LOCKED),
        ]
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=locks),
        )
        result = solver.solve()
        a001_assignments = [a for a in result.assignments if a.applicant_id == "A001"]
        assert len(a001_assignments) == 1
        assert a001_assignments[0].section_id == SECTION_1010
        assert any("already locked into another slot" in c for c in result.lock_conflicts)

    def test_unknown_applicant_lock_is_a_conflict_not_a_crash(self, data):
        lock = Lock("NOPE", SECTION_1010, PositionType.LA, LockType.LOCKED)
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=[lock]),
        )
        result = solver.solve()
        assert any("unknown applicant" in c for c in result.lock_conflicts)


class TestBlocking:
    def test_blocked_applicant_never_assigned_to_that_section_position(self, data):
        block = Lock("A001", SECTION_1010, PositionType.LA, LockType.BLOCKED)
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=[block]),
        )
        result = solver.solve()
        assert not any(a.applicant_id == "A001" and a.section_id == SECTION_1010 for a in result.assignments)

    def test_blocked_applicant_still_eligible_elsewhere(self, data):
        # Blocking A001 from 1010/LA shouldn't touch their eligibility for
        # other sections they qualify for.
        block = Lock("A001", SECTION_1010, PositionType.LA, LockType.BLOCKED)
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=[block]),
        )
        result = solver.solve()
        assert any(a.applicant_id == "A001" for a in result.assignments)  # placed somewhere else

    def test_lock_contradicting_a_block_is_a_conflict(self, data):
        locks = [
            Lock("A001", SECTION_1010, PositionType.LA, LockType.BLOCKED),
            Lock("A001", SECTION_1010, PositionType.LA, LockType.LOCKED),
        ]
        solver = CSPSolver(
            data["applicants"], data["applications"], data["sections"],
            config=SolverConfig(locks=locks),
        )
        result = solver.solve()
        assert any("contradicts an existing block" in c for c in result.lock_conflicts)
        assert not any(a.applicant_id == "A001" and a.section_id == SECTION_1010 for a in result.assignments)


class TestNoLocks:
    def test_empty_locks_behaves_exactly_like_before(self, data):
        solver = CSPSolver(data["applicants"], data["applications"], data["sections"])
        result = solver.solve()
        assert result.lock_conflicts == []
        assert result.total_score > 0