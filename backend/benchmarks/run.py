"""Benchmark runner for the CSP solver.

Run from the backend/ directory:

    python -m benchmarks.run                         # small, medium, large x seeds 1-3
    python -m benchmarks.run --sizes small xlarge --seeds 1 2 3 4 5
    python -m benchmarks.run --max-nodes 1000000 --csv results.csv

For each instance it reports:
    build_ms   time to build the candidate table (eligibility + scoring)
    search_ms  time spent in the backtracking search
    nodes      search nodes explored
    score      total score of the returned assignment
    filled     slots filled / total slots
    optimal    False if the max_nodes budget cut the search short
    ref        exact optimum from bipartite matching (needs scipy; see reference.py)
    gap        how far `score` is below `ref`, in percent

Keep build and search timings separate: the planned rule-compiler work changes
the build step, and search improvements (tighter bounds) change the search
step, so you want to see each move independently.
"""

import argparse
import csv
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

from ta_assignment.csp_solver import CSPSolver, SolverConfig
from ta_assignment.scoring import DefaultScoringStrategy, EligibilityConfig

from . import reference
from .generator import SIZES, generate_sized


def default_config(max_nodes: int = 300_000) -> SolverConfig:
    """Matches the policy used in demo.py: 3.0 GPA floor, 3.3 for UTAs."""
    return SolverConfig(
        eligibility=EligibilityConfig(min_gpa=3.0, min_gpa_uta=3.3),
        scorer=DefaultScoringStrategy(),
        max_nodes=max_nodes,
    )


@dataclass
class RunResult:
    instance: str
    size: str
    seed: int
    applicants: int
    slots: int
    build_ms: float
    search_ms: float
    nodes: int
    score: float
    filled: int
    optimal: bool
    ref_score: Optional[float] = None

    @property
    def gap_pct(self) -> Optional[float]:
        if self.ref_score is None or self.ref_score == 0:
            return None
        return 100 * (self.ref_score - self.score) / self.ref_score


def run_one(size: str, seed: int, max_nodes: int) -> RunResult:
    inst = generate_sized(size, seed)

    t0 = time.perf_counter()
    solver = CSPSolver(inst.applicants, inst.applications, inst.sections, config=default_config(max_nodes))
    t1 = time.perf_counter()
    result = solver.solve()
    t2 = time.perf_counter()

    return RunResult(
        instance=inst.name,
        size=size,
        seed=seed,
        applicants=len(inst.applicants),
        slots=len(solver.slots),
        build_ms=(t1 - t0) * 1000,
        search_ms=(t2 - t1) * 1000,
        nodes=result.nodes_explored,
        score=result.total_score,
        filled=len(result.assignments),
        optimal=result.optimal,
        ref_score=reference.matching_optimum(solver),
    )


def print_table(results: List[RunResult]) -> None:
    header = (f"{'instance':<18} {'apps':>5} {'slots':>5} {'build_ms':>9} {'search_ms':>10} {'nodes':>9} "
              f"{'score':>8} {'ref':>8} {'gap':>6} {'filled':>9}  optimal")
    print(header)
    print("-" * len(header))
    for r in results:
        ref = f"{r.ref_score:8.2f}" if r.ref_score is not None else f"{'-':>8}"
        gap = f"{r.gap_pct:5.1f}%" if r.gap_pct is not None else f"{'-':>6}"
        print(f"{r.instance:<18} {r.applicants:>5} {r.slots:>5} {r.build_ms:>9.1f} {r.search_ms:>10.1f} "
              f"{r.nodes:>9} {r.score:>8.2f} {ref} {gap} {f'{r.filled}/{r.slots}':>9}  "
              f"{'yes' if r.optimal else 'NO (budget hit)'}")
    if not reference.available():
        print("\n(install scipy to see the exact reference optimum and gap columns)")

    print("\nMedian per size:")
    for size in dict.fromkeys(r.size for r in results):
        rows = [r for r in results if r.size == size]
        print(f"  {size:<8} build {statistics.median(r.build_ms for r in rows):8.1f} ms | "
              f"search {statistics.median(r.search_ms for r in rows):9.1f} ms | "
              f"nodes {statistics.median(r.nodes for r in rows):>9.0f} | "
              f"optimal {sum(r.optimal for r in rows)}/{len(rows)}"
              + (f" | gap {statistics.median(r.gap_pct for r in rows):4.1f}%"
                 if all(r.gap_pct is not None for r in rows) else ""))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the Easy-Sched CSP solver.")
    parser.add_argument("--sizes", nargs="+", default=["small", "medium", "large"], choices=list(SIZES))
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--max-nodes", type=int, default=300_000)
    parser.add_argument("--csv", help="optional path to write raw results as CSV")
    args = parser.parse_args(argv)

    results = [run_one(size, seed, args.max_nodes) for size in args.sizes for seed in args.seeds]
    print_table(results)

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            fields = list(asdict(results[0]).keys()) + ["gap_pct"]
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow({**asdict(r), "gap_pct": r.gap_pct})
        print(f"\nWrote {len(results)} rows to {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
