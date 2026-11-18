"""Per-browser workspaces, settings, finalized schedules and workspace files."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api
from ta_assignment.db.models import Base

ALICE = {"X-Client-Id": "browser-alice"}
BOB = {"X-Client-Id": "browser-bob"}


@pytest.fixture()
def client():
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


def make(client, headers=ALICE, **body):
    res = client.post("/api/workspaces", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def solve(client, ws_id, headers=ALICE):
    res = client.post("/api/solve", json={"dataset": ws_id, "min_gpa": 3.0, "min_gpa_uta": 3.3}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- workspaces ----------------------------------------------------------------

def test_workspace_endpoints_need_a_client_id(client):
    assert client.get("/api/workspaces").status_code == 400


def test_blank_workspace_starts_empty_with_nothing_set_up(client):
    ws = make(client, name="Fall 2026")
    assert ws["name"] == "Fall 2026"
    assert ws["counts"] == {"courses": 0, "sections": 0, "applicants": 0, "locks": 0}
    assert ws["setup"] == {"rules": False, "courses": False, "applicants": False, "schedule": False}
    data = client.get(f"/api/dataset?dataset={ws['id']}", headers=ALICE).json()
    assert data["sections"] == [] and data["applicants"] == []


def test_sample_workspace_is_ready_to_solve(client):
    ws = make(client, name="Sample", sample="extended")
    assert ws["counts"]["applicants"] == 14
    assert ws["setup"]["rules"] and ws["setup"]["courses"] and ws["setup"]["applicants"]
    assert solve(client, ws["id"])["optimal"] is True


def test_browsers_cannot_see_each_others_workspaces(client):
    ws = make(client, sample="extended")
    wid = ws["id"]
    assert [w["id"] for w in client.get("/api/workspaces", headers=BOB).json()["workspaces"]] == []
    assert client.get(f"/api/workspaces/{wid}", headers=BOB).status_code == 404
    assert client.get(f"/api/dataset?dataset={wid}", headers=BOB).status_code == 404
    assert client.get(f"/api/locks?dataset={wid}", headers=BOB).status_code == 404
    assert client.post("/api/solve", json={"dataset": wid}, headers=BOB).status_code == 404
    assert client.get(f"/api/workspaces/{wid}/export", headers=BOB).status_code == 404
    assert client.delete(f"/api/workspaces/{wid}", headers=BOB).status_code == 404
    # ... and no header at all is also refused for a private workspace
    assert client.get(f"/api/dataset?dataset={wid}").status_code == 404


def test_shared_sample_datasets_still_work_without_a_client(client):
    assert client.get("/api/dataset?dataset=demo").status_code == 200


def test_rename_and_delete(client):
    ws = make(client, sample="demo")
    renamed = client.patch(f"/api/workspaces/{ws['id']}", json={"name": "Spring 2027"}, headers=ALICE).json()
    assert renamed["name"] == "Spring 2027"
    assert client.delete(f"/api/workspaces/{ws['id']}", headers=ALICE).status_code == 204
    assert client.get(f"/api/workspaces/{ws['id']}", headers=ALICE).status_code == 404
    assert client.get("/api/workspaces", headers=ALICE).json()["workspaces"] == []


def test_reset_restores_a_sample_and_refuses_a_blank(client):
    ws = make(client, sample="extended")
    person = client.get(f"/api/dataset?dataset={ws['id']}", headers=ALICE).json()["applicants"][0]
    res = client.delete(f"/api/applicants/{person['applicant_id']}?dataset={ws['id']}", headers=ALICE)
    assert res.status_code == 204
    assert client.get(f"/api/workspaces/{ws['id']}", headers=ALICE).json()["counts"]["applicants"] == 13
    reset = client.post(f"/api/workspaces/{ws['id']}/reset", headers=ALICE)
    assert reset.status_code == 200 and reset.json()["counts"]["applicants"] == 14
    blank = make(client)
    assert client.post(f"/api/workspaces/{blank['id']}/reset", headers=ALICE).status_code == 400


def test_settings_are_saved_per_workspace(client):
    ws = make(client)
    body = {"min_gpa": 3.2, "min_gpa_uta": 3.5, "weights": {"grade_weight": 4.0}}
    saved = client.put(f"/api/workspaces/{ws['id']}/settings", json=body, headers=ALICE).json()
    assert saved["setup"]["rules"] is True
    assert saved["settings"]["min_gpa"] == 3.2
    assert saved["settings"]["weights"]["grade_weight"] == 4.0
    assert saved["settings"]["weights"]["preference_weight"] == 2.5   # untouched weights keep defaults


# --- finalized schedule -----------------------------------------------------------

def test_finalize_records_the_schedule_and_exports_csv(client):
    ws = make(client, sample="extended")
    done = client.post(f"/api/workspaces/{ws['id']}/schedule", headers=ALICE).json()
    assert done["setup"]["schedule"] is True and done["finalized_at"]
    csv_res = client.get(f"/api/workspaces/{ws['id']}/schedule.csv", headers=ALICE)
    assert csv_res.status_code == 200
    lines = csv_res.text.strip().splitlines()
    assert lines[0] == "section,position,applicant_id,name,score"
    assert len(lines) > 1
    assert client.delete(f"/api/workspaces/{ws['id']}/schedule", headers=ALICE).status_code == 204
    assert client.get(f"/api/workspaces/{ws['id']}/schedule.csv", headers=ALICE).status_code == 404


def test_finalize_refuses_an_empty_workspace(client):
    ws = make(client)
    assert client.post(f"/api/workspaces/{ws['id']}/schedule", headers=ALICE).status_code == 400


# --- workspace files ---------------------------------------------------------------

def _lock_first_assignment(client, ws_id):
    slot = next(s for s in solve(client, ws_id)["slots"] if s["applicant_id"])
    res = client.post(f"/api/locks?dataset={ws_id}", headers=ALICE, json={
        "applicant_id": slot["applicant_id"], "section_id": slot["section_id"],
        "position": slot["position"], "lock_type": "locked"})
    assert res.status_code == 201


def test_export_then_import_into_another_browser_round_trips(client):
    ws = make(client, name="Fall 2026", sample="extended")
    _lock_first_assignment(client, ws["id"])
    client.post(f"/api/workspaces/{ws['id']}/schedule", headers=ALICE)
    original = solve(client, ws["id"])

    exported = client.get(f"/api/workspaces/{ws['id']}/export", headers=ALICE).json()
    assert exported["format"] == "easy-sched.workspace" and exported["version"] == 1
    assert {"settings", "courses", "sections", "applicants", "locks", "schedule"} <= exported.keys()

    res = client.post("/api/workspaces/import", json={"bundle": exported}, headers=BOB)
    assert res.status_code == 201, res.text
    copy = res.json()["workspace"]
    assert copy["name"] == "Fall 2026"
    assert copy["counts"] == ws["counts"] | {"locks": 1}
    assert copy["finalized_at"] is not None

    again = solve(client, copy["id"], headers=BOB)
    assert again["total_score"] == pytest.approx(original["total_score"])
    assert sorted((a["applicant_id"], a["section_id"]) for a in again["assignments"]) == \
        sorted((a["applicant_id"], a["section_id"]) for a in original["assignments"])


def test_import_only_selected_parts_into_an_existing_workspace(client):
    source = make(client, sample="extended")
    exported = client.get(f"/api/workspaces/{source['id']}/export", headers=ALICE).json()
    target = make(client, name="Blank")

    res = client.post(f"/api/workspaces/{target['id']}/import",
                      json={"bundle": exported, "parts": ["courses"]}, headers=ALICE)
    assert res.status_code == 200, res.text
    after = res.json()["workspace"]
    assert after["counts"]["sections"] == source["counts"]["sections"]
    assert after["counts"]["applicants"] == 0
    assert after["setup"]["rules"] is False   # settings weren't selected


def test_partial_export_contains_only_those_parts(client):
    ws = make(client, sample="demo")
    exported = client.get(f"/api/workspaces/{ws['id']}/export?parts=settings,applicants", headers=ALICE).json()
    assert "applicants" in exported and "settings" in exported
    assert "courses" not in exported and "locks" not in exported


def test_replacing_courses_drops_locks_that_no_longer_fit(client):
    ws = make(client, sample="extended")
    _lock_first_assignment(client, ws["id"])
    empty_courses = {"format": "easy-sched.workspace", "version": 1, "courses": [], "sections": []}
    res = client.post(f"/api/workspaces/{ws['id']}/import", json={"bundle": empty_courses}, headers=ALICE).json()
    assert res["workspace"]["counts"]["locks"] == 0
    assert any("lock" in n for n in res["report"]["notes"])


def test_invalid_file_is_rejected_with_the_field_that_is_wrong(client):
    ws = make(client)
    bad = {"format": "easy-sched.workspace", "version": 1,
           "courses": [{"course_id": "CSCI 1111", "title": "Intro"}],
           "sections": [{"course_id": "CSCI 1111", "section_number": "10", "term": "WINTER", "year": 2026}]}
    res = client.post(f"/api/workspaces/{ws['id']}/import", json={"bundle": bad}, headers=ALICE)
    assert res.status_code == 422
    assert "sections.0.term" in res.json()["detail"] and "WINTER" in res.json()["detail"]


def test_wrong_format_is_rejected(client):
    ws = make(client)
    res = client.post(f"/api/workspaces/{ws['id']}/import", json={"bundle": {"hello": "world"}}, headers=ALICE)
    assert res.status_code == 422


def test_import_is_all_or_nothing(client):
    ws = make(client, sample="extended")
    before = client.get(f"/api/workspaces/{ws['id']}", headers=ALICE).json()["counts"]
    broken = {"format": "easy-sched.workspace", "version": 1,
              "courses": [{"course_id": "A", "title": "A"}],
              "sections": [{"course_id": "MISSING", "section_number": "1", "term": "FALL", "year": 2026}]}
    res = client.post(f"/api/workspaces/{ws['id']}/import", json={"bundle": broken}, headers=ALICE)
    assert res.status_code == 400 and "doesn't exist" in res.json()["detail"]
    assert client.get(f"/api/workspaces/{ws['id']}", headers=ALICE).json()["counts"] == before


def test_failed_import_as_new_leaves_no_half_made_workspace(client):
    broken = {"format": "easy-sched.workspace", "version": 1,
              "locks": [{"applicant_id": "ghost", "section_id": "X-1 (Fall 2026)", "position": "LA", "lock_type": "locked"}]}
    res = client.post("/api/workspaces/import", json={"bundle": broken}, headers=ALICE)
    assert res.status_code == 400
    assert client.get("/api/workspaces", headers=ALICE).json()["workspaces"] == []
