"""Repository layer: turns ORM rows into the domain dataclasses that
scoring.py and scp_solver.py already know how to work with, and back again
for writes. Nothing outside this model (and seed.py) should import
SQLAlchemy models directly.
"""

from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..applicants import Applicant, PastCourseRecord, Recommendation, TeachingExperienceRecord
from ..applications import Application, CoursePreference
from ..courses import Course, PositionRequirement, Section
from ..enums import Grade, PositionType, Semester
from .json_shapes import dict_to_lab, dict_to_timeslot, lab_to_dict, timeslot_to_dict
from .models import ApplicantModel, ApplicationModel, CourseModel, SectionModel

def _course_from_row(row: CourseModel) -> Course:
    return Course(
        course_id=row.course_id,
        title=row.title,
        description=row.description,
        skills=row.skills,
    )


def _section_from_row(row: SectionModel, course: Course) -> Section:
    return Section(
        course=course,
        section_number=row.section_number,
        term=Semester[row.term],
        year=row.year,
        instructor=row.instructor,
        lecture_meetings=[dict_to_timeslot(m) for m in row.lecture_meetings],
        labs=[dict_to_lab(l) for l in row.labs],
        position_requirements=PositionRequirement(
            la_count=row.la_count,
            uta_count=row.uta_count,
            la_hours_per_week=row.la_hours_per_week,
            uta_hours_per_week=row.uta_hours_per_week,
            uta_must_attend_lecture=row.uta_must_attend_lecture,
            la_must_attend_lecture=row.la_must_attend_lecture,
        ),
    )


def _applicant_from_row(row: ApplicantModel) -> Applicant:
    return Applicant(
        applicant_id=row.applicant_id,
        name=row.name,
        email=row.email,
        past_courses=[
            PastCourseRecord(d["course_id"], Grade[d["grade"]], Semester[d["term"]], d["year"])
            for d in row.past_courses
        ],
        teaching_experience=[
            TeachingExperienceRecord(
                d["course_id"], PositionType[d["position"]], Semester[d["term"]], d["year"],
                d.get("supervisor_rating")
            )
            for d in row.teaching_experience
        ],
        recommendations=[
            Recommendation(d["faculty_name"], d.get("course_id"), d.get("strength", 3.0), d.get("note", ""))
            for d in row.recommendations
        ],
        upcoming_schedule=[dict_to_timeslot(d) for d in row.upcoming_schedule],
        skills=set(row.skills),
    )


def _application_from_row(row: ApplicationModel) -> Application:
    return Application(
        applicant_id=row.applicant_id,
        term=Semester[row.term],
        year=row.year,
        position_types={PositionType[p] for p in row.position_types},
        ranked_preferences=[CoursePreference(d["course_id"], d["rank"]) for d in row.ranked_preferences],
    )


def get_courses(db: Session, dataset: str) -> Dict[str, Course]:
    rows = db.scalars(select(CourseModel).where(CourseModel.dataset == dataset)).all()
    return {row.course_id: _course_from_row(row) for row in rows}


def get_sections(db: Session, dataset: str) -> List[Section]:
    courses = get_courses(db, dataset)
    rows = db.scalars(select(SectionModel).where(SectionModel.dataset == dataset)).all()
    out = []
    for row in rows:
        course = courses.get(row.course_id)
        if course is None:
            continue  # orphaned section (its course was deleted); skip rather than crash
        out.append(_section_from_row(row, course))
    return out


def get_applicants(db: Session, dataset: str) -> Dict[str, Applicant]:
    rows = db.scalars(select(ApplicantModel).where(ApplicantModel.dataset == dataset)).all()
    return {row.applicant_id: _applicant_from_row(row) for row in rows}


def get_applications(db: Session, dataset: str) -> List[Application]:
    rows = db.scalars(select(ApplicationModel).where(ApplicationModel.dataset == dataset)).all()
    return [_application_from_row(row) for row in rows]


def dataset_is_empty(db: Session, dataset: str) -> bool:
    return db.scalar(select(CourseModel.id).where(CourseModel.dataset == dataset).limit(1)) is None


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def wipe_dataset(db: Session, dataset: str) -> None:
    for model in (CourseModel, SectionModel, ApplicantModel, ApplicationModel):
        db.execute(delete(model).where(model.dataset == dataset))
    db.commit()


# -- Courses ------------------------------------------------------------

def create_course(db: Session, dataset: str, course_id: str, title: str, description: str, skills: List[str]) -> CourseModel:
    row = CourseModel(dataset=dataset, course_id=course_id, title=title, description=description, skills=skills)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_course(db: Session, dataset: str, course_id: str, **fields) -> Optional[CourseModel]:
    row = db.scalar(select(CourseModel).where(CourseModel.dataset == dataset, CourseModel.course_id == course_id))
    if row is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_course(db: Session, dataset: str, course_id: str) -> bool:
    row = db.scalar(select(CourseModel).where(CourseModel.dataset == dataset, CourseModel.course_id == course_id))
    if row is None:
        return False
    # cascade: sections without a course would silently vanish from every
    # read (get_sections skips rows whose course_id doesn't resolve) but
    # remain as dead rows in the DB forever. Delete them explicitly instead.
    db.execute(delete(SectionModel).where(SectionModel.dataset == dataset, SectionModel.course_id == course_id))
    db.delete(row)
    db.commit()
    return True


# -- Sections -------------------------------------------------------------

def create_section(db: Session, dataset: str, **fields) -> SectionModel:
    row = SectionModel(dataset=dataset, **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_section(db: Session, dataset: str, section_db_id: int, **fields) -> Optional[SectionModel]:
    row = db.scalar(select(SectionModel).where(SectionModel.dataset == dataset, SectionModel.id == section_db_id))
    if row is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_section(db: Session, dataset: str, section_db_id: int) -> bool:
    row = db.scalar(select(SectionModel).where(SectionModel.dataset == dataset, SectionModel.id == section_db_id))
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


# -- Applicants (+ their application row) ----------------------------------

def create_applicant(db: Session, dataset: str, applicant_fields: dict, application_fields: dict) -> ApplicantModel:
    row = ApplicantModel(dataset=dataset, **applicant_fields)
    db.add(row)
    app_row = ApplicationModel(dataset=dataset, applicant_id=applicant_fields["applicant_id"], **application_fields)
    db.add(app_row)
    db.commit()
    db.refresh(row)
    return row


def update_applicant(
    db: Session, dataset: str, applicant_id: str, applicant_fields: dict, application_fields: dict,
) -> Optional[ApplicantModel]:
    row = db.scalar(
        select(ApplicantModel).where(ApplicantModel.dataset == dataset, ApplicantModel.applicant_id == applicant_id)
    )
    if row is None:
        return None
    for key, value in applicant_fields.items():
        if value is not None:
            setattr(row, key, value)

    app_row = db.scalar(
        select(ApplicationModel).where(ApplicationModel.dataset == dataset, ApplicationModel.applicant_id == applicant_id)
    )
    if app_row is not None:
        for key, value in application_fields.items():
            if value is not None:
                setattr(app_row, key, value)

    db.commit()
    db.refresh(row)
    return row


def delete_applicant(db: Session, dataset: str, applicant_id: str) -> bool:
    row = db.scalar(
        select(ApplicantModel).where(ApplicantModel.dataset == dataset, ApplicantModel.applicant_id == applicant_id)
    )
    if row is None:
        return False
    db.execute(
        delete(ApplicationModel).where(ApplicationModel.dataset == dataset, ApplicationModel.applicant_id == applicant_id)
    )
    db.delete(row)
    db.commit()
    return True


# -- helpers for building JSON-column payloads from domain objects ---------
# (used by seed.py, and reusable by api.py if it ever needs to go
# domain-object -> dict directly instead of building dicts from a request)

def course_to_row_fields(course: Course) -> dict:
    return {
        "course_id": course.course_id,
        "title": course.title,
        "description": course.description,
        "skills": sorted(course.skills),
    }


def section_to_row_fields(section: Section) -> dict:
    reqs = section.position_requirements
    return {
        "course_id": section.course.course_id,
        "section_number": section.section_number,
        "term": section.term.name,
        "year": section.year,
        "instructor": section.instructor,
        "lecture_meetings": [timeslot_to_dict(m) for m in section.lecture_meetings],
        "labs": [lab_to_dict(lab) for lab in section.labs],
        "la_count": reqs.la_count,
        "uta_count": reqs.uta_count,
        "la_hours_per_week": reqs.la_hours_per_week,
        "uta_hours_per_week": reqs.uta_hours_per_week,
        "uta_must_attend_lecture": reqs.uta_must_attend_lecture,
        "la_must_attend_lecture": reqs.la_must_attend_lecture,
    }


def applicant_to_row_fields(applicant: Applicant) -> dict:
    return {
        "applicant_id": applicant.applicant_id,
        "name": applicant.name,
        "email": applicant.email,
        "skills": sorted(applicant.skills),
        "past_courses": [
            {"course_id": r.course_id, "grade": r.grade.name, "term": r.term.name, "year": r.year}
            for r in applicant.past_courses
        ],
        "teaching_experience": [
            {
                "course_id": r.course_id, "position": r.position.name, "term": r.term.name,
                "year": r.year, "supervisor_rating": r.supervisor_rating,
            }
            for r in applicant.teaching_experience
        ],
        "recommendations": [
            {"faculty_name": r.faculty_name, "course_id": r.course_id, "strength": r.strength, "note": r.note}
            for r in applicant.recommendations
        ],
        "upcoming_schedule": [timeslot_to_dict(t) for t in applicant.upcoming_schedule],
    }


def application_to_row_fields(application: Application) -> dict:
    return {
        "term": application.term.name,
        "year": application.year,
        "position_types": sorted(p.name for p in application.position_types),
        "ranked_preferences": [{"course_id": p.course_id, "rank": p.rank} for p in application.ranked_preferences],
    }
