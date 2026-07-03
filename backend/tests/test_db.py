"""Tests for ta_assignment.db.* -- run against a fresh in-memory SQLite DB
per test (not the on-disk easy_sched.db the API uses), so these never
interfere with real workspace data

Run with:
    python -m pytest backend/tests/ -v
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ta_assignment.db import repository as repo
from ta_assignment.db.models import Base
from ta_assignment.db.seed import ensure_seeded, reset_dataset, seed_dataset


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestSeeding:
    def test_seed_extended_matches_loader_counts(self, db):
        seed_dataset(db, "extended")
        assert len(repo.get_courses(db, "extended")) >= 6
        assert len(repo.get_sections(db, "extended")) == 6
        assert len(repo.get_applicants(db, "extended")) == 14

    def test_ensure_seeded_is_idempotent(self, db):
        ensure_seeded(db, "demo")
        ensure_seeded(db, "demo")  # should not duplicate rows
        assert len(repo.get_sections(db, "demo")) == 4

    def test_workspaces_are_isolated(self, db):
        ensure_seeded(db, "demo")
        ensure_seeded(db, "extended")
        assert len(repo.get_sections(db, "demo")) == 4
        assert len(repo.get_sections(db, "extended")) == 6


class TestCourseCRUD:
    def test_create_update_delete_course(self, db):
        ensure_seeded(db, "demo")
        repo.create_course(db, "demo", "CSCI 5000", "New Course", "", ["testing"])
        assert "CSCI 5000" in repo.get_courses(db, "demo")

        repo.update_course(db, "demo", "CSCI 5000", title="Renamed")
        assert repo.get_courses(db, "demo")["CSCI 5000"].title == "Renamed"

        assert repo.delete_course(db, "demo", "CSCI 5000") is True
        assert "CSCI 5000" not in repo.get_courses(db, "demo")

    def test_delete_course_cascades_its_sections(self, db):
        ensure_seeded(db, "extended")
        before = len(repo.get_sections(db, "extended"))
        repo.delete_course(db, "extended", "CSCI 3212")  # has a section in the seed data
        after = len(repo.get_sections(db, "extended"))
        assert after < before

    def test_delete_missing_course_returns_false(self, db):
        ensure_seeded(db, "demo")
        assert repo.delete_course(db, "demo", "NOPE 9999") is False


class TestApplicantCRUD:
    def test_create_and_update_applicant_and_application(self, db):
        ensure_seeded(db, "extended")
        repo.create_applicant(
            db, "extended",
            {"applicant_id": "Z001", "name": "Zed", "email": "z@x.edu", "skills": ["python"],
             "past_courses": [], "teaching_experience": [], "recommendations": [], "upcoming_schedule": []},
            {"term": "FALL", "year": 2026, "position_types": ["LA"], "ranked_preferences": []},
        )
        applicants = repo.get_applicants(db, "extended")
        assert "Z001" in applicants

        repo.update_applicant(db, "extended", "Z001", {"email": "new@x.edu"}, {})
        assert repo.get_applicants(db, "extended")["Z001"].email == "new@x.edu"

    def test_delete_applicant_removes_application_too(self, db):
        ensure_seeded(db, "extended")
        assert repo.delete_applicant(db, "extended", "A001") is True
        applications = repo.get_applications(db, "extended")
        assert not any(a.applicant_id == "A001" for a in applications)


class TestResetDataset:
    def test_reset_discards_edits(self, db):
        ensure_seeded(db, "extended")
        repo.create_course(db, "extended", "CSCI 5000", "Temp", "", [])
        assert "CSCI 5000" in repo.get_courses(db, "extended")

        reset_dataset(db, "extended")
        assert "CSCI 5000" not in repo.get_courses(db, "extended")
        assert len(repo.get_sections(db, "extended")) == 6
