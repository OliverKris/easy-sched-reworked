"""Seeds a dataset/workspace from the existing hardcoded sample data
(test_data.py / test_data_extended.py) the first time it's touched.
Later edits through the CRUD endpoints mutate the DB copy; the original
Python modules are never touched, so `reset_dataset` can always get back
to a known-good state.
"""

from sqlalchemy.orm import Session

from ..test_data import load_demo_data
from ..test_data_extended import load_extended_data
from .models import ApplicantModel, ApplicationModel, CourseModel, SectionModel
from .repository import (
    application_to_row_fields,
    applicant_to_row_fields,
    course_to_row_fields,
    dataset_is_empty,
    section_to_row_fields,
    wipe_dataset,
)

SEED_LOADERS = {
    "demo": load_demo_data,
    "extended": load_extended_data,
}


def seed_dataset(db: Session, dataset: str) -> None:
    loader = SEED_LOADERS.get(dataset)
    if loader is None:
        raise ValueError(f"No seed loader registered for dataset `{dataset}`")
    
    courses, sections, applicants, applications = loader()
    apps_by_applicant = {a.applicant_id: a for a in applications}

    for course in courses.values():
        db.add(CourseModel(dataset=dataset, **course_to_row_fields(course)))

    for section in sections:
        db.add(SectionModel(dataset=dataset, **section_to_row_fields(section)))

    for applicant in applicants.values():
        db.add(ApplicantModel(dataset=dataset, **applicant_to_row_fields(applicant)))
        application = apps_by_applicant.get(applicant.applicant_id)
        if application is not None:
            db.add(ApplicationModel(
                dataset=dataset,
                applicant_id=applicant.applicant_id,
                **application_to_row_fields(application),
            ))
    
    db.commit()


def ensure_seeded(db: Session, dataset: str) -> None:
    """Seed this workspace from its sample loader iff it has no data yet
    (a brand-new DB, or after being wiped). Never overwrites existing rows,
    so eeits persist across server restarts."""
    if dataset in SEED_LOADERS and dataset_is_empty(db, dataset):
        seed_dataset(db, dataset)


def reset_dataset(db: Session, dataset: str) -> None:
    """Explicitly discard all edits and reseed from the sample loader."""
    wipe_dataset(db, dataset)
    seed_dataset(db, dataset)
