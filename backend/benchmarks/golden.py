"""Golden-result snapshots for regression-testing the solver.

A golden file records what the solver returns for a fixed input. tests/test_golden.py
re-runs every case and compares. Only cases the current solver proves OPTIMAL
are used, so the expected total score is the true optimum and must survive any
correct refactor (rule compiler, tighter bounds, a matching-based solver...).

Regenerate after an intentional behaviour change, from backend/:

    python -m benchmarks.golden --update

then review the diff in tests/golden/ before committing it.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Tuple

from ta_assignment.csp_solver import CSPSolver
from ta_assignment.test_data import load_demo_data
from ta_assignment.test_data_extended import load_extended_data

from .generator import generate_instance
from .run import default_config

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "tests" / "golden"


def _from_loader(loader) -> Callable[[], Tuple]:
    def build():
        _courses, sections, applicants, applications = loader()
        return applicants, applications, sections
    return build


def _from_generator(n_applicants: int, n_sections: int, seed: int) -> Callable[[], Tuple]:
    def build():
        inst = generate_instance(n_applicants, n_sections, seed)
        return inst.applicants, inst.applications, inst.sections
    return build


# Small enough that backtracking finishes and proves optimality.
CASES: Dict[str, Callable[[], Tuple]] = {
    "demo": _from_loader(load_demo_data),
    "extended": _from_loader(load_extended_data),
    "gen-8a-3s-seed1": _from_generator(8, 3, 1),
    "gen-10a-4s-seed1": _from_generator(10, 4, 1),
    "gen-10a-4s-seed2": _from_generator(10, 4, 2),
    "gen-12a-5s-seed3": _from_generator(12, 5, 3),
}


def solve_case(name: str) -> dict:
    """Runs one case and returns a JSON-friendly snapshot of the result."""
    applicants, applications, sections = CASES[name]()
    result = CSPSolver(applicants, applications, sections, config=default_config()).solve()

    # Slots within the same section/position are interchangeable, so record
    # assignments and unfilled counts by (section, position), not slot index.
    assignments = sorted(
        [a.applicant_id, a.section_id, a.position.name, round(a.score, 6)]
        for a in result.assignments
    )
    unfilled: Dict[str, int] = {}
    for slot in result.unfilled_slots:
        key = f"{slot.section.section_id}::{slot.position.name}"
        unfilled[key] = unfilled.get(key, 0) + 1

    return {
        "case": name,
        "optimal": result.optimal,
        "total_score": round(result.total_score, 6),
        "filled": len(result.assignments),
        "assignments": assignments,
        "unfilled": dict(sorted(unfilled.items())),
    }


def golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.json"


def update_all() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in CASES:
        snapshot = solve_case(name)
        if not snapshot["optimal"]:
            raise SystemExit(f"{name}: solver did not prove optimality; pick a smaller case")
        golden_path(name).write_text(json.dumps(snapshot, indent=2) + "\n")
        print(f"wrote {golden_path(name).relative_to(GOLDEN_DIR.parent.parent)} "
              f"(score {snapshot['total_score']}, filled {snapshot['filled']})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Manage golden solver snapshots.")
    parser.add_argument("--update", action="store_true", help="rewrite every golden file")
    args = parser.parse_args(argv)
    if not args.update:
        parser.print_help()
        return 1
    update_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())