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
    
Docs at http://127.0.0.1:8000/docs (FastAPI's auto-generated Swagger UI).
"""

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ta_assignment.db import repository as repo
from ta_assignment.db.seed import SEED_LOADERS, ensure_seeded, reset_dataset
from ta_assignment.db.session import get_db, init_db
from ta_assignment.enums import PositionType
from ta_assignment.scoring import EligibilityConfig, DefaultScoringStrategy, check_eligibility
from ta_assignment.csp_solver import CSPSolver, SolverConfig


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db() # create tables if they don't exist
    yield


app = FastAPI(title="Easy Sched API", lifespan=lifespan)

# allow React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def dataset_dep(db: Session = Depends(get_db), dataset: str = Query("demo")):
    """Ensures the requested workspace exists (seeding it if this is the
    first time it's been touched) and hands back (db, dataset)."""
    ensure_seeded(db, dataset)
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


@app.post("/api/solve")
def api_solve(req: SolveRequest, db: Session = Depends(get_db)):
    ensure_seeded(get_db(), req.dataset)
    sections = repo.get_sections(db, req.dataset)
    applicants = repo.get_applicants(db, req.dataset)
    applications = {a.applicant_id: repo.get_application(db, req.dataset, a.applicant_id) for a in applicants.values()}

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
def create_course(payload: CourseCreate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    ensure_seeded(db, dataset)
    try:
        row = repo.create_course(db, dataset, payload.course_id, payload.title, payload.description, payload.skills)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Course '{payload.course_id}' already exists in dataset '{dataset}'")
    return {"course_id": row.course_id, "title": row.title, "description": row.description, "skills": row.skills}


@app.put("/api/courses/{course_id}")
def update_course(course_id: str, payload: CourseUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    row = repo.update_course(db, dataset, course_id, **payload.model_dump())
    if row is None:
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found in '{dataset}'")
    return {"course_id": row.course_id, "title": row.title, "description": row.description, "skills": row.skills}


@app.delete("/api/courses/{course_id}", status_code=204)
def delete_course(course_id: str, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    if not repo.delete_course(db, dataset, course_id):
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found in '{dataset}'")


# ------------
# Section CRUD
# ------------

@app.post("/api/sections", status_code=201)
def create_section(payload: SectionCreate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    ensure_seeded(db, dataset)
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
def update_section(section_id: int, payload: SectionUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
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
def delete_section(section_id: int, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    if not repo.delete_section(db, dataset, section_id):
        raise HTTPException(status_code=404, detail=f"Section {section_id} not found in '{dataset}'")


# ---------------------------------------------------
# Applicant CRUD (bundles the linked Application row)
# ---------------------------------------------------


@app.post("/api/applicants", status_code=201)
def create_applicant(payload: ApplicantCreate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    ensure_seeded(db, dataset)
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
def update_applicant(applicant_id: str, payload: ApplicantUpdate, dataset: str = Query("demo"), db: Session = Depends(get_db)):
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
def delete_applicant(applicant_id: str, dataset: str = Query("demo"), db: Session = Depends(get_db)):
    if not repo.delete_applicant(db, dataset, applicant_id):
        raise HTTPException(status_code=404, detail=f"Applicant '{applicant_id}' not found in '{dataset}'")
