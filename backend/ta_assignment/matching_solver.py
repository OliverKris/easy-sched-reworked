"""Exact solver: TA assignment as maximum-weight bipartite matching.

Why this works: every hard rule except "one slot per applicant" is already
applied per (applicant, slot) pair when the candidate table is built. What's
left is choosing at most one applicant per slot and at most one slot per
applicant to maximise total score, which is the assignment problem. scipy's
linear_sum_assignment solves it exactly in polynomial time, so the result is
always optimal and needs no node budget.

Stops being valid if a rule ever spans several assignments (weekly hour caps
across positions, one person holding two roles). Keep CSPSolver for those.
"""

from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from .csp_solver import BaseSolver, SlotSpec, SolverResult


class MatchingSolver(BaseSolver):

    def solve(self) -> SolverResult:
        # 1. Locks are decided before anything else, exactly as in CSPSolver.
        locked_assignments, lock_conflicts = self._resolve_locks()
        locked_applicants = {aid for aid, _ in locked_assignments.values()}

        # 2. What's still open: slots not locked, applicants not locked.
        open_slots: List[SlotSpec] = [s for s in self.slots if s not in locked_assignments]
        applicant_ids: List[str] = sorted({
            aid
            for slot in open_slots
            for aid, _ in self.candidates[slot.slot_id]
            if aid not in locked_applicants
        })
        if not open_slots or not applicant_ids:
            return self._build_result({}, 0.0, locked_assignments, lock_conflicts,
                                      nodes_explored=0, optimal=True)

        # 3. Score matrix (rows = open slots, cols = applicants) plus a mask of
        #    which cells are real candidates. Ineligible cells hold 0, which the
        #    algorithm may still "pick" when a row has no real option, so the
        #    mask is what decides whether a pick counts.
        col_of: Dict[str, int] = {aid: j for j, aid in enumerate(applicant_ids)}
        weights = np.zeros((len(open_slots), len(applicant_ids)))
        eligible = np.zeros_like(weights, dtype=bool)
        for i, slot in enumerate(open_slots):
            for aid, score in self.candidates[slot.slot_id]:
                j = col_of.get(aid)
                if j is None:          # applicant is already locked elsewhere
                    continue
                weights[i, j] = max(score, 0.0)
                eligible[i, j] = True

        # 4. Solve. Non-square matrices are fine: extra rows or columns go unmatched.
        rows, cols = linear_sum_assignment(weights, maximize=True)

        # 5. Keep only real candidates; everything else stays unfilled.
        chosen: Dict[SlotSpec, Tuple[str, float]] = {}
        for i, j in zip(rows, cols):
            if eligible[i, j]:
                chosen[open_slots[i]] = (applicant_ids[j], float(weights[i, j]))
        chosen_score = sum(score for _, score in chosen.values())

        return self._build_result(chosen, chosen_score, locked_assignments, lock_conflicts,
                                  nodes_explored=0, optimal=True)
