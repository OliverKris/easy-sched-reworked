"""Workspace files: export a workspace (or parts of it) to JSON and import it back.

A workspace file is how data moves between browsers, gets backed up, or is
shared with a colleague, since workspaces have no accounts. It is versioned
and validated on the way in, so a hand-edited or old file fails with a
message that says what is wrong instead of corrupting the workspace.

    {
      "format": "easy-sched.workspace", "version": 1,
      "name": "Fall 2026", "exported_at": "...",
      "settings":   {...}        # rule settings
      "courses":    [...]        # with "sections"
      "sections":   [...]
      "applicants": [...]        # each with its "application"
      "locks":      [...]
      "schedule":   {...}        # a finalized schedule
    }

Every key except format/version/name is optional; importing replaces only the
parts the file contains (and the caller selects).
"""

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..enums import Day, Grade, PositionType, Semester
from . import repository as repo
from .models import ApplicantModel, ApplicationModel, CourseModel, LockModel, SectionModel, WorkspaceModel

FORMAT = "easy-sched.workspace"
VERSION = 1
PARTS = ("settings", "courses", "applicants", "locks", "schedule")


class BundleError(ValueError):
    """The file is valid JSON in the right format but its contents don't fit together."""


# --- validation models ------------------------------------------------------

class _M(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _enum_name(enum, value: str, what: str) -> str:
    if value not in enum.__members__:
        raise ValueError(f"unknown {what} '{value}'; use one of {', '.join(enum.__members__)}")
    return value


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class TimeSlotJ(_M):
    day: str
    start: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    end: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    label: str = ""

    @model_validator(mode="after")
    def check_order(self):
        for t in (self.start, self.end):
            h, m = t.split(":")
            if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                raise ValueError(f"'{t}' isn't a valid time")
        if _minutes(self.end) <= _minutes(self.start):
            raise ValueError(f"ends ({self.end}) before it starts ({self.start})")
        return self
    @field_validator("day")
    @classmethod
    def check_day(cls, v):
        return _enum_name(Day, v, "day")


class LabJ(_M):
    lab_id: str
    capacity: Optional[int] = None
    meetings: List[TimeSlotJ] = []


class CourseJ(_M):
    course_id: str = Field(min_length=1)
    title: str
    description: str = ""
    skills: List[str] = []


class SectionJ(_M):
    course_id: str
    section_number: str = Field(min_length=1)
    term: str
    year: int
    instructor: str = ""
    lecture_meetings: List[TimeSlotJ] = []
    labs: List[LabJ] = []
    la_count: int = Field(0, ge=0)
    uta_count: int = Field(0, ge=0)
    la_hours_per_week: float = 5.0
    uta_hours_per_week: float = 10.0
    uta_must_attend_lecture: bool = False
    la_must_attend_lecture: bool = False

    @model_validator(mode="after")
    def check_labs(self):
        ids = [lab.lab_id for lab in self.labs]
        if len(ids) != len(set(ids)):
            raise ValueError("two labs share the same lab id")
        return self

    @property
    def key(self) -> tuple:
        return (self.course_id, self.section_number, self.term, self.year)

    @property
    def section_id(self) -> str:
        """Same string as the domain Section.section_id (what locks refer to)."""
        return f"{self.course_id}-{self.section_number} ({Semester[self.term].value} {self.year})"
    @field_validator("term")
    @classmethod
    def check_term(cls, v):
        return _enum_name(Semester, v, "term")


class PastCourseJ(_M):
    course_id: str
    grade: str
    term: str
    year: int
    @field_validator("grade")
    @classmethod
    def check_grade(cls, v):
        return _enum_name(Grade, v, "grade")
    @field_validator("term")
    @classmethod
    def check_term(cls, v):
        return _enum_name(Semester, v, "term")


class TeachingJ(_M):
    course_id: str
    position: str
    term: str
    year: int
    supervisor_rating: Optional[float] = None
    @field_validator("position")
    @classmethod
    def check_position(cls, v):
        return _enum_name(PositionType, v, "position")
    @field_validator("term")
    @classmethod
    def check_term(cls, v):
        return _enum_name(Semester, v, "term")


class RecommendationJ(_M):
    faculty_name: str
    course_id: Optional[str] = None
    strength: float = Field(3.0, ge=0, le=5)
    note: str = ""


class PreferenceJ(_M):
    course_id: str
    rank: int = Field(ge=1)


class ApplicationJ(_M):
    term: str
    year: int
    position_types: List[str]
    ranked_preferences: List[PreferenceJ] = []
    @field_validator("term")
    @classmethod
    def check_term(cls, v):
        return _enum_name(Semester, v, "term")

    @field_validator("position_types")
    @classmethod
    def _positions(cls, v):
        return [_enum_name(PositionType, p, "position") for p in v]

    @model_validator(mode="after")
    def check_preferences(self):
        ranks = [p.rank for p in self.ranked_preferences]
        courses = [p.course_id for p in self.ranked_preferences]
        if len(ranks) != len(set(ranks)):
            raise ValueError("two preferences share the same rank")
        if len(courses) != len(set(courses)):
            raise ValueError("the same course is ranked twice")
        return self


class ApplicantJ(_M):
    applicant_id: str = Field(min_length=1)
    name: str
    email: str = ""
    skills: List[str] = []
    past_courses: List[PastCourseJ] = []
    teaching_experience: List[TeachingJ] = []
    recommendations: List[RecommendationJ] = []
    upcoming_schedule: List[TimeSlotJ] = []
    application: Optional[ApplicationJ] = None


class LockJ(_M):
    applicant_id: str
    section_id: str
    position: Literal["LA", "UTA"]
    lock_type: Literal["locked", "blocked"]


class WeightsJ(_M):
    grade_weight: float = 3.0
    experience_weight: float = 2.5
    recommendation_weight: float = 2.0
    preference_weight: float = 2.5
    skill_match_weight: float = 1.0
    uta_readiness_bonus: float = 1.5


class SettingsJ(_M):
    min_gpa: Optional[float] = Field(None, ge=0, le=4)
    min_gpa_uta: Optional[float] = Field(None, ge=0, le=4)
    weights: WeightsJ = WeightsJ()


class ScheduledJ(_M):
    applicant_id: str
    applicant_name: str = ""
    section_id: str
    position: Literal["LA", "UTA"]
    score: float = 0.0


class ScheduleJ(_M):
    finalized_at: str
    total_score: float = 0.0
    assignments: List[ScheduledJ] = []
    unfilled: List[str] = []


class Bundle(_M):
    format: Literal["easy-sched.workspace"]
    version: Literal[1]
    name: str = "Imported workspace"
    exported_at: Optional[str] = None
    settings: Optional[SettingsJ] = None
    courses: Optional[List[CourseJ]] = None
    sections: Optional[List[SectionJ]] = None
    applicants: Optional[List[ApplicantJ]] = None
    locks: Optional[List[LockJ]] = None
    schedule: Optional[ScheduleJ] = None

    def present_parts(self) -> List[str]:
        out = []
        if self.settings is not None:
            out.append("settings")
        if self.courses is not None or self.sections is not None:
            out.append("courses")
        if self.applicants is not None:
            out.append("applicants")
        if self.locks is not None:
            out.append("locks")
        if self.schedule is not None:
            out.append("schedule")
        return out


# --- export -----------------------------------------------------------------

def export_workspace(db: Session, ws: WorkspaceModel, parts: Optional[List[str]] = None) -> dict:
    parts = list(parts or PARTS)
    out: Dict = {
        "format": FORMAT,
        "version": VERSION,
        "name": ws.name,
        "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    if "settings" in parts and ws.settings is not None:
        out["settings"] = ws.settings
    if "courses" in parts:
        out["courses"] = [repo.course_to_row_fields(c) for c in repo.get_courses(db, ws.id).values()]
        out["sections"] = [repo.section_to_row_fields(s) for s in repo.get_sections(db, ws.id)]
    if "applicants" in parts:
        rows = []
        for applicant in repo.get_applicants(db, ws.id).values():
            row = repo.applicant_to_row_fields(applicant)
            application = repo.get_application(db, ws.id, applicant.applicant_id)
            row["application"] = repo.application_to_row_fields(application) if application else None
            rows.append(row)
        out["applicants"] = rows
    if "locks" in parts:
        out["locks"] = [
            {"applicant_id": r.applicant_id, "section_id": r.section_id,
             "position": r.position, "lock_type": r.lock_type}
            for r in repo.list_lock_rows(db, ws.id)
        ]
    if "schedule" in parts and ws.schedule is not None:
        out["schedule"] = ws.schedule
    return out


# --- import -----------------------------------------------------------------

def parse_bundle(data: dict) -> Bundle:
    """Validates a file's JSON. Raises pydantic.ValidationError with field paths."""
    return Bundle.model_validate(data)


def import_into(db: Session, ws: WorkspaceModel, bundle: Bundle, parts: Optional[List[str]] = None,
                mode: Literal["replace", "merge"] = "replace") -> dict:
    """Brings the selected parts of the bundle into `ws`. All or nothing: if
    anything doesn't fit together, nothing is changed. Returns a report.

    mode="replace": each selected part replaces what the workspace had.
    mode="merge":   courses, sections and applicants in the file are added, or
                    replace the ones with the same id; everything else stays.
    """
    chosen = [p for p in (parts or bundle.present_parts()) if p in bundle.present_parts()]
    dataset = ws.id
    merge = mode == "merge"
    report = {"imported": chosen, "mode": mode, "counts": {}, "notes": []}

    try:
        if "courses" in chosen:
            courses = bundle.courses or []
            sections = bundle.sections or []
            ids = [c.course_id for c in courses]
            if len(ids) != len(set(ids)):
                raise BundleError("Two courses share the same course_id")
            keys = [s.key for s in sections]
            if len(keys) != len(set(keys)):
                dup = next(k for k in keys if keys.count(k) > 1)
                raise BundleError(f"Section {dup[0]}-{dup[1]} ({dup[2].title()} {dup[3]}) appears twice")
            existing_courses = set(repo.get_courses(db, dataset)) if merge else set()
            known = set(ids) | existing_courses
            for s in sections:
                if s.course_id not in known:
                    raise BundleError(f"Section {s.course_id}-{s.section_number} refers to course {s.course_id}, which doesn't exist")
            if merge:
                for c in courses:
                    db.execute(delete(CourseModel).where(CourseModel.dataset == dataset, CourseModel.course_id == c.course_id))
                for s in sections:
                    db.execute(delete(SectionModel).where(
                        SectionModel.dataset == dataset, SectionModel.course_id == s.course_id,
                        SectionModel.section_number == s.section_number, SectionModel.term == s.term,
                        SectionModel.year == s.year))
            else:
                db.execute(delete(SectionModel).where(SectionModel.dataset == dataset))
                db.execute(delete(CourseModel).where(CourseModel.dataset == dataset))
            for c in courses:
                db.add(CourseModel(dataset=dataset, **c.model_dump()))
            for s in sections:
                db.add(SectionModel(dataset=dataset, **s.model_dump()))
            report["counts"]["courses"] = len(courses)
            report["counts"]["sections"] = len(sections)

        if "applicants" in chosen:
            applicants = bundle.applicants or []
            ids = [a.applicant_id for a in applicants]
            if len(ids) != len(set(ids)):
                dup = next(i for i in ids if ids.count(i) > 1)
                raise BundleError(f"Applicant {dup} appears twice")
            if merge:
                for i in ids:
                    db.execute(delete(ApplicationModel).where(ApplicationModel.dataset == dataset, ApplicationModel.applicant_id == i))
                    db.execute(delete(ApplicantModel).where(ApplicantModel.dataset == dataset, ApplicantModel.applicant_id == i))
            else:
                db.execute(delete(ApplicationModel).where(ApplicationModel.dataset == dataset))
                db.execute(delete(ApplicantModel).where(ApplicantModel.dataset == dataset))
            for a in applicants:
                fields = a.model_dump(exclude={"application"})
                db.add(ApplicantModel(dataset=dataset, **fields))
                if a.application is not None:
                    db.add(ApplicationModel(dataset=dataset, applicant_id=a.applicant_id, **a.application.model_dump()))
            report["counts"]["applicants"] = len(applicants)

        db.flush()

        # Locks must point at people and sections that exist after the import.
        applicant_ids = set(repo.get_applicants(db, dataset))
        section_ids = {s.section_id for s in repo.get_sections(db, dataset)}
        if "locks" in chosen:
            db.execute(delete(LockModel).where(LockModel.dataset == dataset))
            seen = set()
            for lock in bundle.locks or []:
                if lock.applicant_id not in applicant_ids:
                    raise BundleError(f"A lock refers to applicant '{lock.applicant_id}', who isn't in the workspace")
                if lock.section_id not in section_ids:
                    raise BundleError(f"A lock refers to section '{lock.section_id}', which isn't in the workspace")
                key = (lock.applicant_id, lock.section_id, lock.position)
                if key in seen:
                    raise BundleError(f"Two locks for {lock.applicant_id} in {lock.section_id} ({lock.position})")
                seen.add(key)
                db.add(LockModel(dataset=dataset, **lock.model_dump()))
            report["counts"]["locks"] = len(bundle.locks or [])
        elif "courses" in chosen or "applicants" in chosen:
            # Replacing courses or applicants can orphan existing locks; drop those.
            stale = [r for r in repo.list_lock_rows(db, dataset)
                     if r.applicant_id not in applicant_ids or r.section_id not in section_ids]
            for r in stale:
                db.delete(r)
            if stale:
                report["notes"].append(f"Removed {len(stale)} lock(s) that pointed to people or sections no longer in the workspace.")

        if "settings" in chosen:
            ws.settings = bundle.settings.model_dump()
        if "schedule" in chosen:
            ws.schedule = bundle.schedule.model_dump()
        elif "courses" in chosen or "applicants" in chosen:
            if ws.schedule is not None:
                ws.schedule = None
                report["notes"].append("Cleared the finalized schedule because its courses or applicants changed.")

        db.commit()
    except Exception:
        db.rollback()
        raise
    return report
