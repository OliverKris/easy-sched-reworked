"""FastAPI backend for the Easy Sched admin console.

Read endpoints (dataset/eligibility/solve) are a thin layer over
`ta_assignment`: they call check_eligibility() / DefaultScoringStrategy /
CSPSolver on domain dataclasses and serialize the results to JSON. Those
dataclasses are now hydrated from SQLite (via ta_assignment.db.repository)
instead of the hardcoded sample loaders -- each `dataset` query param is a
separate workspace, seeded from the sample data on first access and then
mutated in place by the CRUD endpoints below.

Run with (from backend/):
    pip install -r requirements.txt
    uvicorn api:app --reload --port 8000

In production the same app also serves the built frontend (see the bottom
of this file), so the whole product runs as one service.
    
Docs at http://127.0.0.1:8000/docs (FastAPI's auto-generated Swagger UI).
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Literal, List, Optional

from fastapi import Header, Response, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ta_assignment.db import repository as repo
from ta_assignment.db.seed import SEED_LOADERS, ensure_seeded, reset_dataset
from ta_assignment.db import workspaces as ws_repo
from ta_assignment.db import bundle as bundle_io
from ta_assignment.db.bundle import SettingsJ
from ta_assignment.db import editing
from ta_assignment.db import csv_import as csv_io
from collections import Counter
from ta_assignment.db.session import get_db, init_db
from ta_assignment.enums import PositionType
from ta_assignment.locks import LockType
from ta_assignment.scoring import EligibilityConfig, DefaultScoringStrategy, check_eligibility
from ta_assignment.csp_solver import CSPSolver, SolverConfig
from ta_assignment.matching_solver import MatchingSolver
from ta_assignment.rules import compile_profile
from ta_assignment.rules.legacy import profile_from_legacy
from solve_view import build_solve_view
import os
import time
import csv
import io
import re


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db() # create tables if they don't exist
    yield


app = FastAPI(title="Easy Sched API", lifespan=lifespan)

# Deployment settings, all from the environment so the same code runs locally and on a host.
#   EASY_SCHED_CORS_ORIGINS   comma-separated origins allowed to call the API from another site
#                             (only needed when the frontend is served from a different domain)
#   EASY_SCHED_DEMO_MODE      "1" on a public demo whose storage can be wiped; the app warns users
#   EASY_SCHED_FRONTEND_DIST  folder with the built frontend (default ../frontend/dist)
CORS_ORIGINS = [o.strip() for o in os.environ.get("EASY_SCHED_CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
DEMO_MODE = os.environ.get("EASY_SCHED_DEMO_MODE", "").lower() in ("1", "true", "yes")
MAX_BODY_BYTES = 5 * 1024 * 1024

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_body_size(request, call_next):
    """Reject oversized uploads before reading them (a public demo shouldn't accept 1 GB CSVs)."""
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse({"detail": "That file is too large (limit 5 MB)."}, status_code=413)
    return await call_next(request)


def client_id(x_client_id: Optional[str] = Header(None, alias="X-Client-Id")) -> Optional[str]:
    """The anonymous id the browser generates and sends on every request."""
    return x_client_id


def open_workspace(db: Session, dataset: str, client: Optional[str]) -> None:
    """Gate for every endpoint that reads or writes workspace data.

    The built-in sample datasets ("demo", "extended") stay shared and are
    seeded on first touch. Anything else must be a workspace owned by the
    calling browser; otherwise it's reported as not found, so one browser
    can't even learn that another's workspace exists.
    """
    if dataset in SEED_LOADERS:
        ensure_seeded(db, dataset)
        return
    if not client or ws_repo.get_owned(db, dataset, client) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")


def dataset_dep(db: Session = Depends(get_db), dataset: str = Query("demo"),
                client: Optional[str] = Depends(client_id)):
    """Checks access to the requested workspace and hands back (db, dataset)."""
    open_workspace(db, dataset, client)
    return db, dataset


# -------------------------------------------------------------------------
# Read-model serializers (unchanged shape from the previous version, so the
# existing frontend views don't need to change )
# -------------------------------------------------------------------------

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


# --------------
# Read endpoints
# --------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    """Facts about this server the frontend adapts to."""
    return {"demo_mode": DEMO_MODE}


@app.get("/api/datasets")
def api_datasets():
    """Which dataset keys the frontend can pass to other endpoints."""
    return {"datasets": list(SEED_LOADERS.keys())}


@app.post("/api/dataset/{dataset}/reset")
def api_reset_dataset(dataset: str, db: Session = Depends(get_db)):
    """Discards all edits in this workspace and reseeds it from sample data."""
    if dataset not in SEED_LOADERS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset '{dataset}'")
    reset_dataset(db, dataset)
    return {"dataset": dataset, "status": "reset"}


@app.get("/api/dataset")
def api_dataset(ctx=Depends(dataset_dep)):
    """Everything the frontend needs for the browse views in one call."""
    db, dataset = ctx
    sections = repo.get_sections(db, dataset)
    applicants = repo.get_applicants(db, dataset)
    apps_by_id = {a.applicant_id: repo.get_application(db, dataset, a.applicant_id) for a in applicants.values()}
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
    min_gpa: Optional[float] = Query(None),
    min_gpa_uta: Optional[float] = Query(None),
    ctx=Depends(dataset_dep)
):
    db, dataset = ctx
    sections = repo.get_sections(db, dataset)
    applicants = repo.get_applicants(db, dataset)
    apps_by_id = {a.applicant_id: repo.get_application(db, dataset, a.applicant_id) for a in applicants.values()}
    
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
    ignore_locks: bool = False  # preview an unconstrained solve for comparison
    solver: Literal["matching", "csp"] = "matching"  # exact matching by default


@app.post("/api/solve")
def api_solve(req: SolveRequest, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, req.dataset, client)
    sections = repo.get_sections(db, req.dataset)
    applicants = repo.get_applicants(db, req.dataset)
    applications = repo.get_applications(db, req.dataset)
    locks = [] if req.ignore_locks else repo.get_locks(db, req.dataset)

    eli_config = EligibilityConfig(min_gpa=req.min_gpa, min_gpa_uta=req.min_gpa_uta)
    scorer = DefaultScoringStrategy(**req.weights.model_dump())
    # The UI's GPA fields and weight sliders become a department profile, so
    # eligibility, scoring and the explanations all come from one rule set.
    profile = compile_profile(profile_from_legacy(eli_config, scorer))
    SolverClass = MatchingSolver if req.solver == "matching" else CSPSolver

    started = time.perf_counter()
    solver = SolverClass(
        applicants, applications, sections,
        config=SolverConfig(profile=profile, locks=locks),
    )
    result = solver.solve()
    elapsed_ms = (time.perf_counter() - started) * 1000

    apps_by_id = {a.applicant_id: a for a in applications}
    view = build_solve_view(solver, result, profile, applicants, apps_by_id, locks)

    return {
        "dataset": req.dataset,
        "solver": req.solver,
        "elapsed_ms": round(elapsed_ms, 1),
        "total_score": round(result.total_score, 2),
        "nodes_explored": result.nodes_explored,
        "optimal": result.optimal,
        "filled": view["filled"],
        "total_slots": view["total_slots"],
        "slots": view["slots"],
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
        "lock_conflicts": result.lock_conflicts,
    }


# -------------
# Write schemas
# -------------

class TimeSlotIn(BaseModel):
    day: str         # "MON" | "TUE" | "WED" | "THU" | "FRI"
    start: str       # "HH:MM"
    end: str         # "HH:MM"
    label: str = ''


class LabIn(BaseModel):
    lab_id: str
    meetings: list[TimeSlotIn] = Field(default_factory=list)
    capacity: Optional[int] = None


class CourseCreate(BaseModel):
    course_id: str
    title: str
    description: str = ""
    skills: List[str] = Field(default_factory=list)


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    skills: Optional[List[str]] = None


class SectionCreate(BaseModel):
    course_id: str
    section_number: str
    term: str            # "FALL" | "SPRING"
    year: int
    instructor: str = ""
    lecture_meetings: List[TimeSlotIn] = Field(default_factory=list)
    labs: List[LabIn] = Field(default_factory=list)
    la_count: int = 2
    uta_count: int = 1
    la_hours_per_week: float = 5.0
    uta_hours_per_week: float = 10.0
    uta_must_attend_lecture: bool = False
    la_must_attend_lecture: bool = False


class SectionUpdate(BaseModel):
    section_number: Optional[str] = None
    term: Optional[str] = None
    year: Optional[int] = None
    instructor: Optional[str] = None
    lecture_meetings: Optional[List[TimeSlotIn]] = None
    labs: Optional[List[LabIn]] = None
    la_count: Optional[int] = None
    uta_count: Optional[int] = None
    la_hours_per_week: Optional[float] = None
    uta_hours_per_week: Optional[float] = None
    uta_must_attend_lecture: Optional[bool] = None
    la_must_attend_lecture: Optional[bool] = None


class PastCourseIn(BaseModel):
    course_id: str
    grade: str            # Grade name, e.g. "A_MINUS"
    term: str
    year: int


class TeachingExperienceIn(BaseModel):
    course_id: str
    position: str          # "LA" | "UTA"
    term: str
    year: int
    supervisor_rating: Optional[float] = None


class RecommendationIn(BaseModel):
    faculty_name: str
    course_id: Optional[str] = None
    strength: float = 3.0
    note: str = ""


class ApplicationFields(BaseModel):
    term: str
    year: int
    position_types: List[str] = Field(default_factory=lambda: ["LA"])
    ranked_preferences: List[dict] = Field(default_factory=list)  # [{"course_id","rank"}]


class ApplicantCreate(BaseModel):
    applicant_id: str
    name: str
    email: str
    skills: List[str] = Field(default_factory=list)
    past_courses: List[PastCourseIn] = Field(default_factory=list)
    teaching_experience: List[TeachingExperienceIn] = Field(default_factory=list)
    recommendations: List[RecommendationIn] = Field(default_factory=list)
    upcoming_schedule: List[TimeSlotIn] = Field(default_factory=list)
    application: ApplicationFields


class ApplicantUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[List[str]] = None
    past_courses: Optional[List[PastCourseIn]] = None
    teaching_experience: Optional[List[TeachingExperienceIn]] = None
    recommendations: Optional[List[RecommendationIn]] = None
    upcoming_schedule: Optional[List[TimeSlotIn]] = None
    application: Optional[ApplicationFields] = None


def _dump_timeslots(slots: List[TimeSlotIn]) -> List[dict]:
    return [slot.model_dump() for slot in slots]


def _dump_labs(labs: List[LabIn]) -> List[dict]:
    return [{"lab_id": l.lab_id, "capacity": l.capacity, "meetings": _dump_timeslots(l.meetings)} for l in labs]


# -----------
# Course CRUD
# -----------

@app.post("/api/courses", status_code=201)
def create_course(payload: CourseCreate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    try:
        row = repo.create_course(db, dataset, payload.course_id, payload.title, payload.description, payload.skills)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Course '{payload.course_id}' already exists in dataset '{dataset}'")
    return {"course_id": row.course_id, "title": row.title, "description": row.description, "skills": row.skills}


@app.put("/api/courses/{course_id}")
def update_course(course_id: str, payload: CourseUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    row = repo.update_course(db, dataset, course_id, **payload.model_dump())
    if row is None:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found in '{dataset}'")
    return {"course_id": row.course_id, "title": row.title, "description": row.description, "skills": row.skills}


@app.delete("/api/courses/{course_id}", status_code=204)
def delete_course(course_id: str, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    if not repo.delete_course(db, dataset, course_id):
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found in '{dataset}'")


# ------------
# Section CRUD
# ------------

@app.post("/api/sections", status_code=201)
def create_section(payload: SectionCreate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    if payload.course_id not in repo.get_courses(db, dataset):
        raise HTTPException(status_code=400, detail=f"Course '{payload.course_id}' does not exist in '{dataset}'")
    fields = payload.model_dump(exclude={"lecture_meetings", "labs"})
    fields["lecture_meetings"] = _dump_timeslots(payload.lecture_meetings)
    fields["labs"] = _dump_labs(payload.labs)
    try:
        row = repo.create_section(db, dataset, **fields)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A section with that course/number/term/year already exists")
    return {"id": row.id}


@app.put("/api/sections/{section_id}")
def update_section(section_id: int, payload: SectionUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    fields = payload.model_dump(exclude={"lecture_meetings", "labs"})
    if payload.lecture_meetings is not None:
        fields["lecture_meetings"] = _dump_timeslots(payload.lecture_meetings)
    if payload.labs is not None:
        fields["labs"] = _dump_labs(payload.labs)
    row = repo.update_section(db, dataset, section_id, **fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found in '{dataset}'")
    return {"id": row.id}


@app.delete("/api/sections/{section_id}", status_code=204)
def delete_section(section_id: int, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    if not repo.delete_section(db, dataset, section_id):
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found in '{dataset}'")


# ---------------------------------------------------
# Applicant CRUD (bundles the linked Application row)
# ---------------------------------------------------


@app.post("/api/applicants", status_code=201)
def create_applicant(payload: ApplicantCreate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    applicant_fields = {
        "applicant_id": payload.applicant_id,
        "name": payload.name,
        "email": payload.email,
        "skills": payload.skills,
        "past_courses": [p.model_dump() for p in payload.past_courses],
        "teaching_experience": [p.model_dump() for p in payload.teaching_experience],
        "recommendations": [p.model_dump() for p in payload.recommendations],
        "upcoming_schedule": _dump_timeslots(payload.upcoming_schedule),
    }
    application_fields = payload.application.model_dump()
    try:
        row = repo.create_applicant(db, dataset, applicant_fields, application_fields)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Applicant '{payload.applicant_id}' already exists in '{dataset}'")
    return {"applicant_id": row.applicant_id}


@app.put("/api/applicants/{applicant_id}")
def update_applicant(applicant_id: str, payload: ApplicantUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    applicant_fields = payload.model_dump(exclude={"past_courses", "teaching_experience", "recommendations", "upcoming_schedule", "application"})
    if payload.past_courses is not None:
        applicant_fields["past_courses"] = [p.model_dump() for p in payload.past_courses]
    if payload.teaching_experience is not None:
        applicant_fields["teaching_experience"] = [p.model_dump() for p in payload.teaching_experience]
    if payload.recommendations is not None:
        applicant_fields["recommendations"] = [p.model_dump() for p in payload.recommendations]
    if payload.upcoming_schedule is not None:
        applicant_fields["upcoming_schedule"] = _dump_timeslots(payload.upcoming_schedule)

    application_fields = payload.application.model_dump() if payload.application is not None else {}

    row = repo.update_applicant(db, dataset, applicant_id, applicant_fields, application_fields)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Applicant '{applicant_id}' not found in '{dataset}'")
    return {"applicant_id": row.applicant_id}


@app.delete("/api/applicants/{applicant_id}", status_code=204)
def delete_applicant(applicant_id: str, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    if not repo.delete_applicant(db, dataset, applicant_id):
        raise HTTPException(status_code=404, detail=f"Applicant '{applicant_id}' not found in '{dataset}'")


# ---------------------------------------------------------------------------
# Lock / block CRUD
#
# A lock pins an applicant into a (section, position); a block forbids one.
# Both apply at the section+position level (not a specific slot_index --
# see ta_assignment/locks.py). Persisted per-dataset, and automatically
# applied every time /api/solve runs for that dataset (pass
# `ignore_locks: true` in the solve request to preview without them).
# ---------------------------------------------------------------------------

class LockCreate(BaseModel):
    applicant_id: str
    section_id: str
    position: str       # "LA" | "UTA"
    lock_type: str     # "locked" | "blocked"


def _serialize_lock(row) -> dict:
    return {
        "id": row.id,
        "applicant_id": row.applicant_id,
        "section_id": row.section_id,
        "position": row.position,
        "lock_type": row.lock_type,
    }


@app.get("/api/locks")
def list_locks(dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    return {"locks": [_serialize_lock(r) for r in repo.list_lock_rows(db, dataset)]}


@app.post("/api/locks", status_code=201)
def create_lock(payload: LockCreate, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)

    if payload.position not in {p.name for p in PositionType}:
        raise HTTPException(status_code=400, detail="position must be 'LA' or 'UTA'" )
    if payload.lock_type not in {lt.value for lt in LockType}:
        raise HTTPException(status_code=400, detail="lock_type must be 'locked' or 'blocked'")
    if payload.applicant_id not in repo.get_applicants(db, dataset):
        raise HTTPException(status_code=400, detail=f"Applicant '{payload.applicant_id}' not found in '{dataset}'")
    if payload.section_id not in {s.section_id for s in repo.get_sections(db, dataset)}:
        raise HTTPException(status_code=400, detail=f"Section '{payload.section_id}' not found in '{dataset}'")
    
    existing = [
        r for r in repo.list_lock_rows(db, dataset)
        if r.applicant_id == payload.applicant_id and r.section_id == payload.section_id and r.position == payload.position
    ]
    if existing:
        raise HTTPException(
            status_code=409,
            detail="A lock/block already exists for this applicant + section + position. Delete it first.",
        )
    
    row = repo.create_lock(db, dataset, payload.applicant_id, payload.section_id, payload.position, payload.lock_type)
    return _serialize_lock(row)


@app.delete("/api/locks/{lock_id}", status_code=204)
def delete_lock(lock_id: int, dataset: str = Query("demo"), db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    open_workspace(db, dataset, client)
    if not repo.delete_lock(db, dataset, lock_id):
        raise HTTPException(status_code=404, detail=f"Lock {lock_id} not found in '{dataset}'")


# ---------------------------------------------------------------------------
# Recommendations: top-N eligible candidates for one open (section, position)
# slot, for the admin's "quick lock" workflow. Lock-aware -- excludes anyone
# already LOCKED into any slot (they're spokem for, can only hold one
# position) and anyone BLOCKED from this exact slot, so every name returned
# here is genuinely available to lock in right now.
# ---------------------------------------------------------------------------

@app.get("/api/recommendations")
def api_recommendations(
    section_id: str = Query(..., description="Section.section_id, e.g. 'CSCI 1012-10 (Fall 2026)'"),
    position: str = Query(..., description="'LA' or 'UTA'"),
    limit: int = Query(5, ge=1, le=50),
    min_gpa: Optional[float] = Query(None),
    min_gpa_uta: Optional[float] = Query(None),
    dataset: str = Query("demo"),
    db: Session = Depends(get_db),
    client: Optional[str] = Depends(client_id),
):
    open_workspace(db, dataset, client)
    if position not in {p.name for p in PositionType}:
        raise HTTPException(status_code=400, detail="position must be 'LA' or 'UTA'")
    
    sections = repo.get_sections(db, dataset)
    section = next((s for s in sections if s.section_id == section_id), None)
    if section is None:
        raise HTTPException(status_code=404, detail=f"Section `{section_id}` not found in `{dataset}`")
    
    applicants = repo.get_applicants(db, dataset)
    applications = repo.get_applications(db, dataset)
    apps_by_id = {a.applicant_id: a for a in applications}
    locks = repo.get_locks(db, dataset)
    pos = PositionType[position]

    # Anyone LOCKED into any slot is unavailable everywhere else (one
    # position per person). Anyone BLOCKED specifically from this
    # section+position is unavailable here only.
    locked_elsewhere = {l.applicant_id for l in locks if l.lock_type == LockType.LOCKED}
    blocked_here = {
        l.applicant_id for l in locks
        if l.lock_type == LockType.BLOCKED and l.section_id == section_id and l.position == pos
    }

    config = EligibilityConfig(min_gpa=min_gpa, min_gpa_uta=min_gpa_uta)
    scorer = DefaultScoringStrategy()

    candidates = []
    for applicant in applicants.values():
        if applicant.applicant_id in locked_elsewhere or applicant.applicant_id in blocked_here:
            continue
        application = apps_by_id.get(applicant.applicant_id)
        if application is None:
            continue
        result = check_eligibility(applicant, application, section, pos, config)
        if not result.eligible:
            continue
        score = scorer.score(applicant, application, section, pos)
        gpa = applicant.overall_gpa
        candidates.append({
            "applicant_id": applicant.applicant_id,
            "applicant_name": applicant.name,
            "gpa": round(gpa, 2) if gpa is not None else None,
            "score": round(score, 2),
        })

    candidates.sort(key=lambda c:  -c["score"])
    return {
        "section_id": section_id,
        "position": position,
        "recommendations": candidates[:limit],
    }

# ---------------------------------------------------------------------------
# Workspaces: per-browser projects, their saved settings, finalized schedules,
# and workspace files (export / import).
# ---------------------------------------------------------------------------

MAX_WORKSPACES_PER_BROWSER = 25


def _require_client(client: Optional[str]) -> str:
    if not client:
        raise HTTPException(status_code=400, detail="Missing X-Client-Id header")
    return client


def _owned(db: Session, workspace_id: str, client: Optional[str]):
    ws = ws_repo.get_owned(db, workspace_id, _require_client(client))
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


def _validation_message(err: ValidationError) -> str:
    parts = []
    for e in err.errors()[:8]:
        where = ".".join(str(x) for x in e["loc"])
        parts.append(f"{where}: {e['msg'].removeprefix('Value error, ')}")
    more = len(err.errors()) - 8
    return "; ".join(parts) + (f"; and {more} more" if more > 0 else "")


class WorkspaceCreate(BaseModel):
    name: str = "Untitled term"
    sample: Optional[str] = None   # "extended" or "demo" to start from sample data


class WorkspaceUpdate(BaseModel):
    name: str


class BundleImport(BaseModel):
    bundle: dict
    parts: Optional[List[str]] = None   # default: every part the file contains
    name: Optional[str] = None          # for importing as a new workspace


@app.get("/api/workspaces")
def list_workspaces(db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    return {"workspaces": [ws_repo.summarize(db, ws) for ws in ws_repo.list_workspaces(db, _require_client(client))]}


@app.post("/api/workspaces", status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    owner = _require_client(client)
    if len(ws_repo.list_workspaces(db, owner)) >= MAX_WORKSPACES_PER_BROWSER:
        raise HTTPException(status_code=400, detail=f"A browser can hold up to {MAX_WORKSPACES_PER_BROWSER} workspaces")
    try:
        ws = ws_repo.create_workspace(db, owner, payload.name, payload.sample)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ws_repo.summarize(db, ws)


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    return ws_repo.summarize(db, _owned(db, workspace_id, client))


@app.patch("/api/workspaces/{workspace_id}")
def rename_workspace(workspace_id: str, payload: WorkspaceUpdate, db: Session = Depends(get_db),
                     client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    ws.name = payload.name.strip() or ws.name
    db.commit()
    return ws_repo.summarize(db, ws)


@app.delete("/api/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws_repo.delete_workspace(db, _owned(db, workspace_id, client))


@app.post("/api/workspaces/{workspace_id}/reset")
def reset_workspace(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    try:
        ws_repo.reset_sample(db, ws)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ws_repo.summarize(db, ws)


@app.put("/api/workspaces/{workspace_id}/settings")
def save_settings(workspace_id: str, payload: SettingsJ, db: Session = Depends(get_db),
                  client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    ws.settings = payload.model_dump()
    db.commit()
    return ws_repo.summarize(db, ws)


def _solve_with_settings(db: Session, dataset: str, settings: dict):
    """Runs the exact solver with a workspace's saved settings and locks."""
    eli = EligibilityConfig(min_gpa=settings.get("min_gpa"), min_gpa_uta=settings.get("min_gpa_uta"))
    scorer = DefaultScoringStrategy(**settings.get("weights", {}))
    profile = compile_profile(profile_from_legacy(eli, scorer))
    applicants = repo.get_applicants(db, dataset)
    solver = MatchingSolver(
        applicants, repo.get_applications(db, dataset), repo.get_sections(db, dataset),
        config=SolverConfig(profile=profile, locks=repo.get_locks(db, dataset)),
    )
    return solver.solve(), applicants


@app.post("/api/workspaces/{workspace_id}/schedule")
def finalize_schedule(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    """Marks the current best assignment (saved settings + locks) as final."""
    ws = _owned(db, workspace_id, client)
    result, applicants = _solve_with_settings(db, ws.id, ws.settings or ws_repo.DEFAULT_SETTINGS)
    if not result.assignments:
        raise HTTPException(status_code=400, detail="Nothing to finalize: no one could be assigned yet")
    ws.schedule = {
        "finalized_at": ws_repo._now(),
        "total_score": round(result.total_score, 2),
        "assignments": [
            {"applicant_id": a.applicant_id, "applicant_name": applicants[a.applicant_id].name,
             "section_id": a.section_id, "position": a.position.name, "score": round(a.score, 2)}
            for a in sorted(result.assignments, key=lambda a: (a.section_id, a.position.name, a.applicant_id))
        ],
        "unfilled": [s.slot_id for s in result.unfilled_slots],
    }
    db.commit()
    return ws_repo.summarize(db, ws)


@app.delete("/api/workspaces/{workspace_id}/schedule", status_code=204)
def unfinalize_schedule(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    ws.schedule = None
    db.commit()


@app.get("/api/workspaces/{workspace_id}/schedule.csv")
def schedule_csv(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    if not ws.schedule:
        raise HTTPException(status_code=404, detail="No finalized schedule yet")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "position", "applicant_id", "name", "score"])
    for a in ws.schedule["assignments"]:
        writer.writerow([a["section_id"], a["position"], a["applicant_id"], a["applicant_name"], a["score"]])
    for slot_id in ws.schedule.get("unfilled", []):
        writer.writerow([slot_id, "", "", "UNFILLED", ""])
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", ws.name).strip("-") or "schedule"
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}-schedule.csv"'},
    )


@app.get("/api/workspaces/{workspace_id}/export")
def export_workspace(workspace_id: str, parts: Optional[str] = Query(None, description="comma-separated parts"),
                     db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    chosen = [p.strip() for p in parts.split(",")] if parts else None
    if chosen and any(p not in bundle_io.PARTS for p in chosen):
        raise HTTPException(status_code=400, detail=f"parts must be from {', '.join(bundle_io.PARTS)}")
    return bundle_io.export_workspace(db, ws, chosen)


def _parse_upload(payload: BundleImport):
    try:
        bundle = bundle_io.parse_bundle(payload.bundle)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"This file isn't a valid workspace file. {_validation_message(e)}")
    if payload.parts and any(p not in bundle_io.PARTS for p in payload.parts):
        raise HTTPException(status_code=400, detail=f"parts must be from {', '.join(bundle_io.PARTS)}")
    return bundle


@app.post("/api/workspaces/import", status_code=201)
def import_as_new(payload: BundleImport, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    owner = _require_client(client)
    bundle = _parse_upload(payload)
    if len(ws_repo.list_workspaces(db, owner)) >= MAX_WORKSPACES_PER_BROWSER:
        raise HTTPException(status_code=400, detail=f"A browser can hold up to {MAX_WORKSPACES_PER_BROWSER} workspaces")
    ws = ws_repo.create_workspace(db, owner, payload.name or bundle.name)
    try:
        report = bundle_io.import_into(db, ws, bundle, payload.parts)
    except bundle_io.BundleError as e:
        ws_repo.delete_workspace(db, ws)
        raise HTTPException(status_code=400, detail=str(e))
    return {"workspace": ws_repo.summarize(db, ws), "report": report}


@app.post("/api/workspaces/{workspace_id}/import")
def import_into_workspace(workspace_id: str, payload: BundleImport, db: Session = Depends(get_db),
                          client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    bundle = _parse_upload(payload)
    try:
        report = bundle_io.import_into(db, ws, bundle, payload.parts)
    except bundle_io.BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"workspace": ws_repo.summarize(db, ws), "report": report}


# ---------------------------------------------------------------------------
# Editing courses, sections and applicants, and CSV upload. Workspace-scoped
# and validated with the workspace-file models (see db/editing.py,
# db/csv_import.py).
# ---------------------------------------------------------------------------

def _parse_body(model, body: dict):
    try:
        return model.model_validate(body)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=_validation_message(e))


def _edit(fn, *args):
    try:
        return fn(*args)
    except editing.EditError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@app.get("/api/workspaces/{workspace_id}/courses")
def ws_list_courses(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return {"courses": editing.list_courses(db, ws.id)}


@app.put("/api/workspaces/{workspace_id}/courses/{course_id}")
def ws_save_course(workspace_id: str, course_id: str, body: dict, db: Session = Depends(get_db),
                   client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return _edit(editing.save_course, db, ws.id, course_id, _parse_body(bundle_io.CourseJ, body))


@app.delete("/api/workspaces/{workspace_id}/courses/{course_id}", status_code=204)
def ws_delete_course(workspace_id: str, course_id: str, db: Session = Depends(get_db),
                     client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    _edit(editing.delete_course, db, ws.id, course_id)


@app.post("/api/workspaces/{workspace_id}/sections", status_code=201)
def ws_create_section(workspace_id: str, body: dict, db: Session = Depends(get_db),
                      client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return _edit(editing.create_section, db, ws.id, _parse_body(bundle_io.SectionJ, body))


@app.put("/api/workspaces/{workspace_id}/sections/{section_db_id}")
def ws_update_section(workspace_id: str, section_db_id: int, body: dict, db: Session = Depends(get_db),
                      client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return _edit(editing.update_section, db, ws.id, section_db_id, _parse_body(bundle_io.SectionJ, body))


@app.delete("/api/workspaces/{workspace_id}/sections/{section_db_id}", status_code=204)
def ws_delete_section(workspace_id: str, section_db_id: int, db: Session = Depends(get_db),
                      client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    _edit(editing.delete_section, db, ws.id, section_db_id)


@app.get("/api/workspaces/{workspace_id}/applicants")
def ws_list_applicants(workspace_id: str, db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return {"applicants": editing.list_applicants(db, ws.id)}


@app.put("/api/workspaces/{workspace_id}/applicants/{applicant_id}")
def ws_save_applicant(workspace_id: str, applicant_id: str, body: dict, db: Session = Depends(get_db),
                      client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    return _edit(editing.save_applicant, db, ws.id, applicant_id, _parse_body(bundle_io.ApplicantJ, body))


@app.delete("/api/workspaces/{workspace_id}/applicants/{applicant_id}", status_code=204)
def ws_delete_applicant(workspace_id: str, applicant_id: str, db: Session = Depends(get_db),
                        client: Optional[str] = Depends(client_id)):
    ws = _owned(db, workspace_id, client)
    _edit(editing.delete_applicant, db, ws.id, applicant_id)


MAX_CSV_ROWS = 5000


@app.get("/api/csv/columns/{kind}")
def csv_columns(kind: Literal["sections", "applicants"]):
    """Column names, labels, aliases and examples, for matching headers and building templates."""
    return {"kind": kind, "columns": csv_io.column_spec(kind)}


class CsvImport(BaseModel):
    rows: List[Dict[str, Optional[str]]]
    mode: Literal["merge", "replace"] = "merge"
    dry_run: bool = True
    term: Optional[str] = None   # applications' term/year; defaults to the workspace's sections
    year: Optional[int] = None


def _default_term(db: Session, dataset: str) -> tuple:
    sections = repo.get_sections(db, dataset)
    if sections:
        pairs = Counter((s.term.name, s.year) for s in sections)
        return pairs.most_common(1)[0][0]
    from datetime import date
    return ("FALL", date.today().year)


@app.post("/api/workspaces/{workspace_id}/csv/{kind}")
def csv_upload(workspace_id: str, kind: Literal["sections", "applicants"], payload: CsvImport,
               db: Session = Depends(get_db), client: Optional[str] = Depends(client_id)):
    """Converts and validates spreadsheet rows; with dry_run=false and no errors, imports them.

    mode="merge" adds new rows and updates ones with the same id; "replace"
    swaps out everything of that kind. Nothing is saved if any row has a problem.
    """
    ws = _owned(db, workspace_id, client)
    if len(payload.rows) > MAX_CSV_ROWS:
        raise HTTPException(status_code=400, detail=f"Up to {MAX_CSV_ROWS} rows per upload")
    rows = [{k: (v or "") for k, v in r.items()} for r in payload.rows]

    if kind == "sections":
        existing = {c.course_id: c.title for c in repo.get_courses(db, ws.id).values()}
        courses, sections, errors = csv_io.convert_section_rows(rows, existing if payload.mode == "merge" else {})
        existing_keys = {(s.course.course_id, s.section_number, s.term.name, s.year) for s in repo.get_sections(db, ws.id)}
        new = sum(1 for s in sections if s.key not in existing_keys)
        summary = {"courses": len(courses), "sections": len(sections),
                   "new": new, "updated": len(sections) - new if payload.mode == "merge" else 0}
        bundle = bundle_io.Bundle(format="easy-sched.workspace", version=1, courses=courses, sections=sections)
        parts = ["courses"]
    else:
        term, year = _default_term(db, ws.id)
        try:
            term = csv_io.parse_term(payload.term) if payload.term else term
        except csv_io.CellError as e:
            raise HTTPException(status_code=400, detail=str(e))
        applicants, errors = csv_io.convert_applicant_rows(rows, term, payload.year or year)
        existing_ids = set(repo.get_applicants(db, ws.id))
        new = sum(1 for a in applicants if a.applicant_id not in existing_ids)
        summary = {"applicants": len(applicants), "new": new,
                   "updated": len(applicants) - new if payload.mode == "merge" else 0}
        # Duplicate ids inside the file are a row problem, not a server error.
        seen: Dict[str, int] = {}
        for i, r in enumerate(rows):
            aid = (r.get("applicant_id") or "").strip()
            if aid and aid in seen:
                errors.append({"row": i + 2, "column": "Student ID", "message": f"{aid} also appears on row {seen[aid]}"})
            elif aid:
                seen[aid] = i + 2
        bundle = bundle_io.Bundle(format="easy-sched.workspace", version=1, applicants=applicants)
        parts = ["applicants"]

    if kind == "sections":
        seen_keys: Dict[tuple, int] = {}
        for i, r in enumerate(rows):
            key = tuple((r.get(k) or "").strip().upper() for k in ("course_id", "section", "term", "year"))
            if all(key) and key in seen_keys:
                errors.append({"row": i + 2, "column": "Section", "message": f"same section as row {seen_keys[key]}"})
            elif all(key):
                seen_keys[key] = i + 2

    errors.sort(key=lambda e: e["row"])
    result = {"ok": not errors, "errors": errors, "summary": summary, "imported": False}
    if errors or payload.dry_run:
        return result
    try:
        report = bundle_io.import_into(db, ws, bundle, parts, mode=payload.mode)
    except bundle_io.BundleError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "imported": True, "report": report, "workspace": ws_repo.summarize(db, ws)}


# ----------------------------------------------------------------
# Built frontend (production): one service serves the API and app
# ----------------------------------------------------------------
# Registered last, so every API route above wins. Any other GET returns a
# file from the build, or index.html so client-side routes like /assign load.

FRONTEND_DIST = Path(os.environ.get(
    "EASY_SCHED_FRONTEND_DIST", Path(__file__).resolve().parent.parent / "frontend" / "dist"
)).resolve()
_API_PREFIXES = ("api/", "health", "docs", "redoc", "openapi.json")

if (FRONTEND_DIST / "index.html").is_file():
    if (FRONTEND_DIST / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        if full_path.startswith(_API_PREFIXES):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})
