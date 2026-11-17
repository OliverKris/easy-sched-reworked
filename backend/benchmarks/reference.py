"""Exact reference optimum for benchmark instances.

With the current rule set, the only constraint that spans several slots is
"each applicant holds at most one slot" (all-different). Eligibility and
scores are computed per (applicant, slot) pair up front. That makes the
problem a maximum-weight bipartite matching between slots and applicants,
which `scipy.optimize.linear_sum_assignment` solves exactly in polynomial
time.

The benchmark uses this as a yardstick: `gap` = how far the CSP solver's
answer is below the true optimum when its node budget runs out.

Caveats:
    - Ignores locks/blocks (benchmark instances don't use them).
    - Only valid while every cross-slot rule is the one-slot-per-applicant
      rule. Adding hour caps across multiple positions, or letting one
      person hold two roles, breaks the pure-matching shape.
"""

from typing import Optional

try:
    import numpy as np
    from scipy.optimize import linear_sum_assignment
except ImportError:  # optional dependency
    np = None
    linear_sum_assignment = None


def available() -> bool:
    return linear_sum_assignment is not None


def matching_optimum(solver) -> Optional[float]:
    """Exact best total score for a constructed (not necessarily solved) CSPSolver.

    Returns None if scipy isn't installed.
    """
    if not available():
        return None
    applicant_ids = sorted({aid for cands in solver.candidates.values() for aid, _ in cands})
    if not applicant_ids or not solver.slots:
        return 0.0
    col = {aid: i for i, aid in enumerate(applicant_ids)}
    weights = np.zeros((len(solver.slots), len(applicant_ids)))
    for row, slot in enumerate(solver.slots):
        for aid, score in solver.candidates[slot.slot_id]:
            # Scores are non-negative, so a zero cell is equivalent to
            # "leave this slot unfilled" and never beats a real candidate.
            weights[row, col[aid]] = max(score, 0.0)
    rows, cols = linear_sum_assignment(weights, maximize=True)
    return float(weights[rows, cols].sum())
