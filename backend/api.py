"""FastAPI backend for the Easy Sched admin console.

This is a thin HTTP layer over `ta_assignment`: it does not reimplement
eligibility, scoring, or solving -- it calls check_eligibility() /
DefaultScoringStrategy / CSPSolver and serializes the results to JSON.

Run with (from backend/):
    pip install -r requirements.txt
    uvicorn api:app --reload --port 8000
    
Docs at http://127.0.0.1:8000/docs (FastAPI's auto-generated Swagger UI).
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ta_assignment.enums import PositionType
from ta_assignment.scoring import EligibilityConfig, DefaultScoringStrategy, check_eligibility
from ta_assignment.csp_solver import CSPSolver, SolverConfig
from ta_assignment.test_data import load_demo_data
from ta_assignment.test_data_extended import load_extended_data

app = FastAPI(title="Easy Sched API")

# allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATASETS = {
    "demo": load_demo_data,
    "extended": load_extended_data,
}

def get_dataset(name: str):
    loader = DATASETS.get(name)
    if loader is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{name}'")
    courses, sections, applicants, applications = loader()
    apps_by_id = {a.applicant_id: a for a in applications}
    return courses, sections, applicants, applications, apps_by_id


def section_summary(section) -> dict:
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


def applicant_summary(applicant, application=None) -> dict:
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


class ScoringWeights(BaseModel):
    grade_weight: float = 3.0
    experience_weight: float = 2.5
    recommendation_weight: float = 2.0
    preference_weight: float = 2.5
    skill_match_weight: float = 1.0
    uta_readiness_bonus: float = 1.5

class SolveRequest(BaseModel):
    dataset: str = "demo"
    min_gpa: Optional[float] = None
    min_gpa_uta: Optional[float] = None
    weights: ScoringWeights = ScoringWeights()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/datasets")
def api_datasets():
    """Which dataset keys the frontend can pass to other endpoints."""
    return {"datasets": list(DATASETS.keys())}


@app.get("/api/dataset")
def api_dataset(dataset: str = Query("demo")):
    """Everything the frontend needs for the browse views in one call."""
    courses, sections, applicants, applications, apps_by_id = get_dataset(dataset)
    return {
        "dataset": dataset,
        "sections": [section_summary(s) for s in sections],
        "applicants": [
            applicant_summary(a, apps_by_id.get(a.applicant_id)) 
            for a in applicants.values()
        ],
    }


@app.get("/api/eligibility")
def api_eligibility(
    dataset: str = Query("demo"),
    min_gpa: Optional[float] = Query(None),
    min_gpa_uta: Optional[float] = Query(None),
):
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
                result = check_eligibility(
                    applicant, application, section, position, config
                )
                cell = {
                    "applicant_id": applicant.applicant_id,
                    "applicant_name": applicant.name,
                    "position": position.name,
                    "eligible": result.eligible,
                    "reasons": result.reasons,
                    "score": (
                        round(scorer.score(applicant, application, section, position), 2)
                        if result.eligible else None
                    ),
                }
                cells.append(cell)
        rows.append({"section_id": section.section_id, "cells": cells})
        
    return {"dataset": dataset, "rows": rows}

@app.post("/api/solve")
def api_solve(req: SolveRequest):
    courses, sections, applicants, applications, apps_by_id = get_dataset(req.dataset)

    eli_config = EligibilityConfig(min_gpa=req.min_gpa, min_gpa_uta=req.min_gpa_uta)
    scorer = DefaultScoringStrategy(**req.weights.model_dump())

    solver = CSPSolver(
        applicants, applications, sections,
        config=SolverConfig(eligibility=eli_config, scorer=scorer),
    )
    result = solver.solve()

    return {
        "dataset": req.dataset,
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
    }