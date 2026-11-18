"""Editing a workspace's courses, sections and applicants from the app.

Every write is validated with the same models as workspace files
(db/bundle.py), so bad values (a "WINTER" term, a lab that ends before it
starts) are refused before they reach the database. Locks stay consistent:
renaming a section moves its locks with it; deleting a section, course or
applicant removes the locks that pointed at it.
"""

from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..enums import Semester
from . import repository as repo
from .bundle import ApplicantJ, CourseJ, SectionJ
from .models import ApplicantModel, ApplicationModel, CourseModel, LockModel, SectionModel


class EditError(ValueError):
    """A request that's well-formed but conflicts with what's in the workspace."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _section_id(course_id: str, number: str, term: str, year: int) -> str:
    return f"{course_id}-{number} ({Semester[term].value} {year})"


def _row_section_id(row: SectionModel) -> str:
    return _section_id(row.course_id, row.section_number, row.term, row.year)


SECTION_FIELDS = list(SectionJ.model_fields)
APPLICANT_FIELDS = [f for f in ApplicantJ.model_fields if f != "application"]


def _section_out(row: SectionModel) -> dict:
    out = {f: getattr(row, f) for f in SECTION_FIELDS}
    out["id"] = row.id
    out["section_id"] = _row_section_id(row)
    return out


# --- courses & sections -------------------------------------------------------

def list_courses(db: Session, dataset: str) -> List[dict]:
    courses = db.scalars(select(CourseModel).where(CourseModel.dataset == dataset).order_by(CourseModel.course_id)).all()
    sections = db.scalars(select(SectionModel).where(SectionModel.dataset == dataset)).all()
    by_course: Dict[str, List[SectionModel]] = {}
    for s in sections:
        by_course.setdefault(s.course_id, []).append(s)
    out = []
    for c in courses:
        rows = sorted(by_course.get(c.course_id, []), key=lambda r: (r.year, r.term, r.section_number))
        out.append({
            "course_id": c.course_id, "title": c.title, "description": c.description, "skills": c.skills,
            "sections": [_section_out(r) for r in rows],
        })
    return out


def _course_row(db: Session, dataset: str, course_id: str) -> Optional[CourseModel]:
    return db.scalar(select(CourseModel).where(CourseModel.dataset == dataset, CourseModel.course_id == course_id))


def save_course(db: Session, dataset: str, course_id: str, course: CourseJ) -> dict:
    """Creates the course, or updates its title, description and skills."""
    if course.course_id != course_id:
        raise EditError("A course's code can't be changed. Create a new course and move its sections instead.")
    row = _course_row(db, dataset, course_id)
    if row is None:
        db.add(CourseModel(dataset=dataset, **course.model_dump()))
    else:
        row.title, row.description, row.skills = course.title, course.description, course.skills
    db.commit()
    return next(c for c in list_courses(db, dataset) if c["course_id"] == course_id)


def delete_course(db: Session, dataset: str, course_id: str) -> None:
    row = _course_row(db, dataset, course_id)
    if row is None:
        raise EditError(f"Course {course_id} not found", 404)
    sections = db.scalars(select(SectionModel).where(SectionModel.dataset == dataset, SectionModel.course_id == course_id)).all()
    section_ids = [_row_section_id(s) for s in sections]
    if section_ids:
        db.execute(delete(LockModel).where(LockModel.dataset == dataset, LockModel.section_id.in_(section_ids)))
    for s in sections:
        db.delete(s)
    db.delete(row)
    db.commit()


def _check_section(db: Session, dataset: str, section: SectionJ, exclude_id: Optional[int] = None) -> None:
    if _course_row(db, dataset, section.course_id) is None:
        raise EditError(f"Course {section.course_id} doesn't exist. Add the course first.")
    clash = db.scalar(select(SectionModel).where(
        SectionModel.dataset == dataset, SectionModel.course_id == section.course_id,
        SectionModel.section_number == section.section_number, SectionModel.term == section.term,
        SectionModel.year == section.year))
    if clash is not None and clash.id != exclude_id:
        raise EditError(f"{section.section_id} already exists.", 409)


def create_section(db: Session, dataset: str, section: SectionJ) -> dict:
    _check_section(db, dataset, section)
    row = SectionModel(dataset=dataset, **section.model_dump())
    db.add(row)
    db.commit()
    return _section_out(row)


def update_section(db: Session, dataset: str, section_db_id: int, section: SectionJ) -> dict:
    row = db.get(SectionModel, section_db_id)
    if row is None or row.dataset != dataset:
        raise EditError("Section not found", 404)
    _check_section(db, dataset, section, exclude_id=row.id)
    old_id = _row_section_id(row)
    for field, value in section.model_dump().items():
        setattr(row, field, value)
    new_id = _row_section_id(row)
    if new_id != old_id:  # locks refer to sections by this string; keep them attached
        for lock in db.scalars(select(LockModel).where(LockModel.dataset == dataset, LockModel.section_id == old_id)):
            lock.section_id = new_id
    db.commit()
    return _section_out(row)


def delete_section(db: Session, dataset: str, section_db_id: int) -> None:
    row = db.get(SectionModel, section_db_id)
    if row is None or row.dataset != dataset:
        raise EditError("Section not found", 404)
    db.execute(delete(LockModel).where(LockModel.dataset == dataset, LockModel.section_id == _row_section_id(row)))
    db.delete(row)
    db.commit()


# --- applicants ---------------------------------------------------------------

def list_applicants(db: Session, dataset: str) -> List[dict]:
    rows = db.scalars(select(ApplicantModel).where(ApplicantModel.dataset == dataset).order_by(ApplicantModel.name)).all()
    apps = {a.applicant_id: a for a in db.scalars(select(ApplicationModel).where(ApplicationModel.dataset == dataset))}
    gpas = {aid: a.overall_gpa for aid, a in repo.get_applicants(db, dataset).items()}
    out = []
    for r in rows:
        item = {f: getattr(r, f) for f in APPLICANT_FIELDS}
        app = apps.get(r.applicant_id)
        item["application"] = (
            {"term": app.term, "year": app.year, "position_types": app.position_types,
             "ranked_preferences": app.ranked_preferences} if app else None
        )
        gpa = gpas.get(r.applicant_id)
        item["gpa"] = round(gpa, 2) if gpa is not None else None
        out.append(item)
    return out


def save_applicant(db: Session, dataset: str, applicant_id: str, applicant: ApplicantJ) -> dict:
    """Creates the applicant, or replaces everything about them."""
    if applicant.applicant_id != applicant_id:
        raise EditError("An applicant's ID can't be changed.")
    row = db.scalar(select(ApplicantModel).where(ApplicantModel.dataset == dataset, ApplicantModel.applicant_id == applicant_id))
    fields = applicant.model_dump(exclude={"application"})
    if row is None:
        db.add(ApplicantModel(dataset=dataset, **fields))
    else:
        for field, value in fields.items():
            setattr(row, field, value)
    db.execute(delete(ApplicationModel).where(ApplicationModel.dataset == dataset, ApplicationModel.applicant_id == applicant_id))
    if applicant.application is not None:
        db.add(ApplicationModel(dataset=dataset, applicant_id=applicant_id, **applicant.application.model_dump()))
    db.commit()
    return next(a for a in list_applicants(db, dataset) if a["applicant_id"] == applicant_id)


def delete_applicant(db: Session, dataset: str, applicant_id: str) -> None:
    row = db.scalar(select(ApplicantModel).where(ApplicantModel.dataset == dataset, ApplicantModel.applicant_id == applicant_id))
    if row is None:
        raise EditError(f"Applicant {applicant_id} not found", 404)
    db.execute(delete(LockModel).where(LockModel.dataset == dataset, LockModel.applicant_id == applicant_id))
    db.execute(delete(ApplicationModel).where(ApplicationModel.dataset == dataset, ApplicationModel.applicant_id == applicant_id))
    db.delete(row)
    db.commit()
