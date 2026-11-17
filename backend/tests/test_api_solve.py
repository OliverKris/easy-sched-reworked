"""API tests for POST /api/solve: the payload the Assign screen depends on."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api
from ta_assignment.db.models import Base


@pytest.fixture()
def client():
    # One in-memory database shared across the test client's threads.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    api.app.dependency_overrides[api.get_db] = override_get_db
    with TestClient(api.app) as c:
        yield c
    api.app.dependency_overrides.clear()


def solve(client, **body):
    res = client.post("/api/solve", json={"dataset": "extended", "min_gpa": 3.0, "min_gpa_uta": 3.3, **body})
    assert res.status_code == 200, res.text
    return res.json()


def test_matching_is_default_and_optimal(client):
    data = solve(client)
    assert data["solver"] == "matching"
    assert data["optimal"] is True
    assert data["filled"] == len(data["assignments"])
    assert data["total_slots"] == len(data["slots"])


def test_matching_scores_at_least_as_high_as_csp(client):
    matching = solve(client)
    csp = solve(client, solver="csp")
    assert matching["total_score"] >= csp["total_score"] - 1e-6


def test_breakdown_adds_up_to_slot_score(client):
    data = solve(client)
    filled = [s for s in data["slots"] if s["applicant_id"]]
    assert filled
    for slot in filled:
        total = sum(b["points"] for b in slot["breakdown"])
        assert total == pytest.approx(slot["score"], abs=0.05)
        assert all(b["label"] for b in slot["breakdown"])


def test_alternatives_exclude_the_assignee_and_are_sorted(client):
    data = solve(client)
    for slot in data["slots"]:
        ids = [a["applicant_id"] for a in slot["alternatives"]]
        assert slot["applicant_id"] not in ids
        scores = [a["score"] for a in slot["alternatives"]]
        assert scores == sorted(scores, reverse=True)


def test_unfilled_slots_explain_why(client):
    data = solve(client, min_gpa=3.9, min_gpa_uta=3.95)   # strict enough to leave gaps
    empty = [s for s in data["slots"] if not s["applicant_id"]]
    assert empty, "expected some unfilled slots under a 3.9 GPA floor"
    for slot in empty:
        assert slot["unfilled_reason"]


def test_locked_assignment_is_flagged_and_kept(client):
    first = solve(client)
    slot = next(s for s in first["slots"] if s["applicant_id"])
    res = client.post("/api/locks?dataset=extended", json={
        "applicant_id": slot["applicant_id"], "section_id": slot["section_id"],
        "position": slot["position"], "lock_type": "locked",
    })
    assert res.status_code == 201, res.text

    second = solve(client)
    match = [s for s in second["slots"]
             if s["applicant_id"] == slot["applicant_id"] and s["section_id"] == slot["section_id"]]
    assert match and match[0]["locked"] is True
