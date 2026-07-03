"""CSP solver.

Formulation:
    - Variables: one per open position slot. A Section needing 2 LAs + 1 UTA
      contributes 3 slot variables (LA#1, LA#2, UTA#1). Slots for the same
      section/position are interchangable, so we don't distinguish "LA#1"
      from "LA#2" beyond bookkeeping
    - Domains: for each slot, the set of applicants who pass `check_eligibility`
      for that section+position (hard constraint), paired with their score from 
      a `ScoringStrategy`.
    - Global constraints (all-different): each applicant may be assigned to at
      most one slot in the whole solution (a person holds one position).
    - Objective: maximize the sum of scores across all filled slots. Slots may
      be left unfilled i no eligible candidates remain

Search strategy: backtracking with
    - MRV (minimum remaining values) variable ordering: slots with the fewest
      eligible candidates are assigned first, since they're most likely to
      fail/constrain the search and should be reasolved early.
    - Best-first value ordering: try each slot's highest-scoring available
      candidate first, so good solutions are found quickly.
    - Branch-and-bound pruning: track the best total score found so far, and
      prune any partial assignment whose optimistic upper bound (current score
      + sum of each remaining slot's best candidate score) can't beat it.
    - A `max_nodes` budget guards against worst-case blowup on large inputs;
      if hit, the best solution found so far is returned and flagged as
      possibly non-optimal.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .applicants import Applicant
from .applications import Application, Assignment
from .courses import Section
from .enums import PositionType
from .scoring import EligibilityConfig, ScoringStrategy, DefaultScoringStrategy, check_eligibility


@dataclass(frozen=True, eq=False)
class SlotSpec:
    """One open position to fill: e.g. 'CSCI 1012-10 LA slot #1'.
    
    `eq`/`hash` are defined manuallyt off `slot_id` rather than dataclass
    defaults, since `Section` (a plain mutable dataclass) isn't hashable.
    """
    section: Section
    position: PositionType
    slot_index: int     # 1-indexed, purely for display/debugging

    @property
    def slot_id(self) -> str:
        return f"{self.section.section_id}::{self.position.name}#{self.slot_index}"
    
    def __eq__(self, other):
        return isinstance(other, SlotSpec) and self.slot_id == other.slot_id
    
    def __hash__(self):
        return hash(self.slot_id)
    
    def __str__(self):
        return self.slot_id
    
def build_slots(sections: List[Section]) -> List[SlotSpec]:
    """Expands each section's PositionalRequirement counts into individual slots"""
    slots: List[SlotSpec] = []
    for section in sections:
        reqs = section.position_requirements
        for i in range(1, reqs.la_count + 1):
            slots.append(SlotSpec(section, PositionType.LA, i))
        for i in range(1, reqs.uta_count + 1):
            slots.append(SlotSpec(section, PositionType.UTA, i))
    return slots


@dataclass
class SolverConfig:
    eligibility: EligibilityConfig = field(default_factory=EligibilityConfig)
    scorer: ScoringStrategy = field(default_factory=DefaultScoringStrategy)
    max_nodes: int = 300_000 # safety value on the backtracking search


@dataclass
class SolverResult:
    assignments: List[Assignment]
    unfilled_slots: List[SlotSpec]
    total_score: float
    nodes_explored: int
    optimal: bool # False if max_nodes was hit before search was completed

    def __str__(self):
        lines = [f"Total score: {self.total_score:.2f} "
                 f"(nodes={self.nodes_explored}, optimal={self.optimal})"]
        
        for a in self.assignments:
            lines.append(f"  {a}")
        if self.unfilled_slots:
            lines.append("  Unfilled:")
            for s in self.unfilled_slots:
                lines.append(f"    {s}")
        return "\n".join(lines)
    

class CSPSolver:
    def __init__(self,
                 applicants: Dict[str, Applicant],
                 applications: List[Application],
                 sections: List[Section],
                 config: Optional[SolverConfig] = None):
        self.applicants = applicants
        self.apps_by_id = {a.applicant_id: a for a in applications}
        self.sections = sections
        self.config = config or SolverConfig()

        self.slots: List[SlotSpec] = build_slots(sections)
        # slot_id -> list[(applicant_id, score)], sorted best-score-first
        self.candidates: Dict[str, List[Tuple[str, float]]] = self._build_candidate_table()

        # search state, populated by solve()
        self._best_assignment: Dict[SlotSpec, Tuple[str, float]] = {}
        self._best_score: float = -1.0
        self._nodes_explored: int = 0
        self._hit_node_limit: bool = False

    def _build_candidate_table(self) -> Dict[str, List[Tuple[str, float]]]:
        table: Dict[str, List[Tuple[str, float]]] = {}
        for slot in self.slots:
            candidates = []
            for applicant in self.applicants.values():
                application = self.apps_by_id.get(applicant.applicant_id)
                if application is None:
                    continue
                result = check_eligibility(
                    applicant, application, slot.section, slot.position,
                    self.config.eligibility
                )
                if result.eligible:
                    score = self.config.scorer.score(applicant, application, slot.section, slot.position)
                    candidates.append((applicant.applicant_id, score))
            candidates.sort(key=lambda pair: -pair[1])
            table[slot.slot_id] = candidates
        return table
    
    def solve(self) -> SolverResult:
        # MRV ordering: fewest eligible candidates first.
        order = sorted(self.slots, key=lambda s: len(self.candidates[s.slot_id]))

        # Suffix upper bounds for branch-and-bound: suffix_upper[i] is the
        # most additional score achievable from slots order [i:], ignoring the
        # all-dfferent constraint (an admissible, if loose, upper bound
        # since it can only overestimate what's truly reachable).
        suffix_upper = [0.0] * (len(order) + 1)
        for i in range(len(order) - 1, -1, -1):
            cands = self.candidates[order[i].slot_id]
            best_here = cands[0][1] if cands else 0.0
            suffix_upper[i] = suffix_upper[i + 1] + max(best_here, 0.0)

        used_applicants: set = set()
        current: Dict[SlotSpec, Tuple[str, float]] = {}
        self._backtrack(order, 0, used_applicants, current, 0.0, suffix_upper)

        assignments = [
            Assignment(applicant_id=aid, section_id=slot.section.section_id,
                       position=slot.position, score=score)
            for slot, (aid, score) in self._best_assignment.items()
        ]
        unfilled = [s for s in self.slots if s not in self._best_assignment]

        return SolverResult(
            assignments=assignments,
            unfilled_slots=unfilled,
            total_score=max(self._best_score, 0.0),
            nodes_explored=self._nodes_explored,
            optimal=not self._hit_node_limit,
        )

    def _backtrack(self, order, idx, used, current, current_score, suffix_upper):
        self._nodes_explored += 1
        if self._nodes_explored > self.config.max_nodes:
            self._hit_node_limit = True
            return
        
        if idx == len(order):
            if current_score > self._best_score:
                self._best_score = current_score
                self._best_assignment = dict(current)
            return
        
        # Prune: even filling every remaining slot with its best candidate
        # (ignoring reuse) can't beat the best solution found so far
        if current_score + suffix_upper[idx] <= self._best_score:
            return
        
        slot = order[idx]
        for applicant_id, score in self.candidates[slot.slot_id]:
            if applicant_id in used:
                continue
            used.add(applicant_id)
            current[slot] = (applicant_id, score)
            self._backtrack(order, idx + 1, used, current, current_score + score, suffix_upper)
            del current[slot]
            used.discard(applicant_id)
            if self._hit_node_limit:
                return
            
        # Also try leaving this slot unfilled (valid when no/no-more eligible
        # candidates remain, or when skipping it enables a better overall solution).
        self._backtrack(order, idx + 1, used, current, current_score, suffix_upper)