"""Turns a solver run into the payload the Assign screen renders.

For every slot it reports who is there, whether they're locked, how their
score breaks down term by term, who else could have taken the slot (and where
those people ended up), and, for an empty slot, why nobody could fill it.
Everything comes from the same compiled profile the solver used, so the
explanations always match the decision.
"""

from collections import Counter
from typing import Dict, List

from ta_assignment.csp_solver import BaseSolver, SolverResult
from ta_assignment.locks import Lock, LockType
from ta_assignment.rules import CompiledProfile

MAX_ALTERNATIVES = 3
MAX_INELIGIBLE_EXAMPLES = 2


def _slot_label(section_id: str, position: str) -> str:
    return f"{section_id} · {position}"


def build_solve_view(
    solver: BaseSolver,
    result: SolverResult,
    profile: CompiledProfile,
    applicants: Dict,
    apps_by_id: Dict,
    locks: List[Lock],
) -> dict:
    session = profile.new_session()
    names = {aid: a.name for aid, a in applicants.items()}

    locked_pairs = {
        (l.applicant_id, l.section_id, l.position.name)
        for l in locks if l.lock_type == LockType.LOCKED
    }

    # Who sits in which slot.
    by_slot: Dict[str, str] = {}
    placement: Dict[str, str] = {}  # applicant_id -> "section · position"
    scores: Dict[str, float] = {}
    remaining = {}
    for a in result.assignments:
        remaining.setdefault((a.section_id, a.position.name), []).append(a)
    for slot in solver.slots:
        bucket = remaining.get((slot.section.section_id, slot.position.name))
        if bucket:
            a = bucket.pop(0)
            by_slot[slot.slot_id] = a.applicant_id
            placement[a.applicant_id] = _slot_label(a.section_id, a.position.name)
            scores[slot.slot_id] = a.score

    slots_out = []
    for slot in solver.slots:
        section, position = slot.section, slot.position
        aid = by_slot.get(slot.slot_id)
        candidates = solver.candidates.get(slot.slot_id, [])

        entry = {
            "slot_id": slot.slot_id,
            "section_id": section.section_id,
            "course_id": section.course.course_id,
            "position": position.name,
            "slot_index": slot.slot_index,
            "applicant_id": aid,
            "applicant_name": names.get(aid) if aid else None,
            "score": round(scores[slot.slot_id], 2) if aid else None,
            "locked": bool(aid) and (aid, section.section_id, position.name) in locked_pairs,
            "preference_rank": None,
            "breakdown": [],
            "alternatives": [],
            "ineligible_examples": [],
            "unfilled_reason": None,
        }

        if aid:
            app = apps_by_id[aid]
            entry["preference_rank"] = app.preference_rank(section.course.course_id)
            entry["breakdown"] = [
                {"id": key, "label": label, "points": round(points, 2)}
                for key, label, points in session.explain(applicants[aid], app, section, position)
                if points != 0
            ]

        # Other eligible people for this slot, best first, and where they went.
        for other_id, other_score in candidates:
            if other_id == aid:
                continue
            entry["alternatives"].append({
                "applicant_id": other_id,
                "applicant_name": names.get(other_id, other_id),
                "score": round(other_score, 2),
                "placed_in": placement.get(other_id),
            })
            if len(entry["alternatives"]) >= MAX_ALTERNATIVES:
                break

        # People who wanted this course but were ruled out, and the first rule that did it.
        failure_counts: Counter = Counter()
        for app_id, app in apps_by_id.items():
            if not app.wants_position(position):
                continue
            failing = session.failing_rules(applicants[app_id], app, section, position)
            if not failing:
                continue
            _key, label, reason = failing[0]
            failure_counts[label] += 1
            ranked_here = section.course.course_id in {p.course_id for p in app.ranked_preferences}
            if ranked_here and len(entry["ineligible_examples"]) < MAX_INELIGIBLE_EXAMPLES:
                entry["ineligible_examples"].append({
                    "applicant_id": app_id,
                    "applicant_name": names.get(app_id, app_id),
                    "reason": reason,
                })

        if not aid:
            if candidates:
                n = len(candidates)
                entry["unfilled_reason"] = (
                    f"{n} eligible {'person is' if n == 1 else 'people are'} placed elsewhere, "
                    "where the overall result is better."
                )
            else:
                top = ", ".join(f"{label} ({count})" for label, count in failure_counts.most_common(3))
                entry["unfilled_reason"] = f"No one eligible. Rules not met: {top}." if top else "No one applied."
            entry["failure_counts"] = [
                {"label": label, "count": count} for label, count in failure_counts.most_common()
            ]

        slots_out.append(entry)

    return {
        "filled": sum(1 for s in slots_out if s["applicant_id"]),
        "total_slots": len(slots_out),
        "slots": slots_out,
    }
