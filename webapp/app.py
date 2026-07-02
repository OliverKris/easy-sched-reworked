"""Local admin web app for Easy Sched

Run with (from project root):
    pip install -r requirements.txt
    python webapp/app.py

Then open http://127.0.0.1:5000 in a browser
"""

import os
import sys
from dataclasses import asdict

from flask import Flask, jsonify, request, render_template

# Make the sibling `src` package importable when running this file directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.enums import PositionType
from src.scoring import EligibilityConfig, DefaultScoringStrategy, check_eligibility
from src.csp_solver import CSPSolver, SolverConfig
from src.test_data import load_demo_data
from src.test_data_extended import load_extended_data

app = Flask(__name__)

DATASETS = {
    "demo": load_demo_data,
    "extended": load_extended_data,
}


def get_dataset(name: str):
    loader = DATASETS.get(name, DATASETS["demo"])
    courses, sections, applicants, applications = loader()
    apps_by_id = {a.applicant_id: a for a in applications}
    return courses, sections, applicants, applications, apps_by_id


def section_summary(section):
    reqs = section.position_requirements
    return {
        "section_id": section.section_id,
        "course_id": section.course.course_id,
        "title": section.course.title,
        "instructor": section.instructor,
        "term": section.term.value,
        "year": section.year,
        "la_count": reqs.la_count,
        "uta_count": reqs.uta_count,
        "uta_must_attend_lecture": reqs.uta_must_attend_lecture,
        "la_must_attend_lecture": reqs.la_must_attend_lecture,
        "lecture_meetings": [str(m) for m in section.lecture_meetings],
        "labs": [
            {"lab_id": lab.lab_id, "meetings": [str(m) for m in lab.meetings]}
            for lab in section.labs
        ],
    }


def applicant_summary(applicant, application=None):
    gpa = applicant.overall_gpa
    return {
        "applicant_id": applicant.applicant_id,
        "name": applicant.name,
        "email": applicant.email,
        "gpa": round(gpa, 2) if gpa is not None else None,
        "skills": sorted(applicant.skills),
        "past_courses": [str(c) for c in applicant.past_courses],
        "teaching_experience": [str(t) for t in applicant.teaching_experience],
        "recommendations": [str(r) for r in applicant.recommendations],
        "position_types": sorted(p.name for p in application.position_types) if application else [],
        "ranked_preferences": (
            [{"course_id": p.course_id, "rank": p.rank}
             for p in sorted(application.ranked_preferences, key=lambda p: p.rank)]
            if application else []
        ),
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/dataset")
def api_dataset():
    """Everything the frontend needs for the browse veiws in one call."""
    dataset = request.args.get("dataset", "demo")
    courses, sections, applicants, applications, apps_by_id = get_dataset(dataset)
    return jsonify({
        "dataset": dataset,
        "sections": [section_summary(s) for s in sections],
        "applicants": [
            applicant_summary(a, apps_by_id.get(a.applicant_id))
            for a in applicants.values()
        ],
    })


@app.route("/api/eligibility")
def api_eligibilityh():
    dataset = request.args.get("dataset", "demo")
    min_gpa = request.args.get("min_pga", type=float)
    min_gpa_uta = request.args.get("min_gpa_uta", type=float)

    courses, sections, applicants, applications, apps_by_id = get_dataset(dataset)
    config = EligibilityConfig(min_gpa=min_gpa, min_gpa_uta=min_gpa_uta)
    scorer = DefaultScoringStrategy()

    rows = []
    for section in sections:
        cells = []
        for applicant in applicants.values():
            application = apps_by_id.get(applicant.applicant_id)
            if application is None:
                continue
            for position in (PositionType.LA, PositionType.UTA):
                result = check_eligibility(applicant, application, section, position, config)
                cell = {
                    "applicant_id": applicant.applicant_id,
                    "applicant_name": applicant.name,
                    "position": position.name,
                    "eligible": result.eligible,
                    "reasons": result.reasons,
                }
                if result.eligible:
                    cell["score"] = round(scorer.score(applicant, application, section, position), 2)
                cells.append(cell)
            rows.append({"sections_id": section.section_id, "cells": cells})
        
        return jsonify({"dataset": dataset, "rows":rows})

@app.route("/api/solve", methods=["POST"])
def api_solve():
    body = request.get_json(force=True) or {}
    dataset = body.get("dataset", "demo")
    min_gpa = body.get("min_gpa")
    min_gpa_uta = body.get("min_gpa_uta")
    weights = body.get("weights", {})

    courses, sections, applicants, applications, apps_by_id = get_dataset(dataset)

    elig_config = EligibilityConfig(
        min_gpa=float(min_gpa) if min_gpa not in (None, "") else None,
        min_gpa_uta=float(min_gpa_uta) if min_gpa_uta not in (None, "") else None,
    )

    scorer = DefaultScoringStrategy(
        grade_weight=float(weights.get("grade_weight", 3.0)),
        experience_weight=float(weights.get("experience_weight", 2.5)),
        recommendation_weight=float(weights.get("recommendation_weight", 2.0)),
        preference_weight=float(weights.get("preference_weight", 2.5)),
        skill_match_weight=float(weights.get("skill_match_weight", 1.0)),
        uta_readiness_bonus=float(weights.get("uta_readiness_bonus", 1.5)),
    )

    solver = CSPSolver(
        applicants, applications, sections,
        config=SolverConfig(eligibility=elig_config, scorer=scorer),
    )
    result = solver.solve()

    return jsonify({
        "dataset": dataset,
        "total_score": round(result.total_score, 2),
        "nodes_explored": result.nodes_explored,
        "optimal": result.optimal,
        "assignments": [
            {
                "applicant_id": a.applicant_id,
                "applicant_name": applicants[a.applicant_id].name,
                "section_id": a.section_id,
                "position": a.position.name,
                "score": round(a.score, 2),
            }
            for a in result.assignments
        ],
        "unfilled_slots": [s.slot_id for s in result.unfilled_slots],
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)