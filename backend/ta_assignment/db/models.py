"""SQLAlchemy ORM models backing the admin console.

Design choice: only the four top-level entities (Course, Section,
Applicant, Application) get real columns/rows. Their nested lists of
value objects -- a section's lab, an applicant's past courses / teaching
history / recommendations / upcoming schedule, an application's ranked
preferences -- are stored as JSON columns rather than their own tables.
Those lists are always read/written as a whole alongside their parent
(nothing ever queries "find all recommendations about strength 4 across
every applicant"), so normalizing them out would add a lot of join
complexity for no real benefit here.

Every table carries a `dataset` column: it's the workspace key ("demo),
"extended", or any custom workspace an admin creates that scopes all the
CRUD endpoints in api.py. One SQLite file holds every workspace.
"""

from sqlalchemy import JSON, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class CourseModel(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("dataset", "course_id", name="uq_course_dataset_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    skills: Mapped[list] = mapped_column(JSON, default=list)  # list[str]


class SectionModel(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint(
            "dataset", "course_id", "section_number", "term", "year",
            name="uq_section_dataset_course_number_term_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)  # -> CourseModel.course_id (same dataset)
    section_number: Mapped[str] = mapped_column(String)
    term: Mapped[str] = mapped_column(String)   # Semester.value, e.g. "Fall"
    year: Mapped[int] = mapped_column(Integer)
    instructor: Mapped[str] = mapped_column(String, default="")

    # list[{"day": "MON", "start": "09:35", "end": "10:50", "label": "..."}]
    lecture_meetings: Mapped[list] = mapped_column(JSON, default=list)
    # list[{"lab_id": "Lab A", "capacity": None, "meetings": [<same shape as above>]}]
    labs: Mapped[list] = mapped_column(JSON, default=list)

    la_count: Mapped[int] = mapped_column(Integer, default=2)
    uta_count: Mapped[int] = mapped_column(Integer, default=1)
    la_hours_per_week: Mapped[float] = mapped_column(Float, default=5.0)
    uta_hours_per_week: Mapped[float] = mapped_column(Float, default=10.0)
    uta_must_attend_lecture: Mapped[bool] = mapped_column(default=False)
    la_must_attend_lecture: Mapped[bool] = mapped_column(default=False)


class ApplicantModel(Base):
    __tablename__ = "applicants"
    __table_args__ = (UniqueConstraint("dataset", "applicant_id", name="uq_applicant_dataset_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, index=True)
    applicant_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    skills: Mapped[list] = mapped_column(JSON, default=list)  # list[str]

    # list[{"course_id", "grade", "term", "year"}]
    past_courses: Mapped[list] = mapped_column(JSON, default=list)
    # list[{"course_id", "position", "term", "year", "supervisor_rating"}]
    teaching_experience: Mapped[list] = mapped_column(JSON, default=list)
    # list[{"faculty_name", "course_id", "strength", "note"}]
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    # list[{"day", "start", "end", "label"}]
    upcoming_schedule: Mapped[list] = mapped_column(JSON, default=list)


class ApplicationModel(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("dataset", "applicant_id", name="uq_application_dataset_applicant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, index=True)
    applicant_id: Mapped[str] = mapped_column(String, index=True)
    term: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer)
    position_types: Mapped[list] = mapped_column(JSON, default=list)       # list[str], e.g. ["LA", "UTA"]
    ranked_preferences: Mapped[list] = mapped_column(JSON, default=list)   # list[{"course_id", "rank"}]


class LockModel(Base):
    """Reserved for the upcoming lock/block-constraint feature: pins or
    forbids a specific applicant from a specific (section, position) slot.
    Not yet read by the solver -- added now so the schema doesn't need a
    migration when that feature lands."""
    __tablename__ = "locks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset: Mapped[str] = mapped_column(String, index=True)
    applicant_id: Mapped[str] = mapped_column(String, index=True)
    section_id: Mapped[int] = mapped_column(Integer, index=True)  # -> SectionModel.id
    position: Mapped[str] = mapped_column(String)   # "LA" | "UTA"
    lock_type: Mapped[str] = mapped_column(String)  # "locked" | "blocked"
