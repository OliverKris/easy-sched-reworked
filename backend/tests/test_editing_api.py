"""API tests for editing courses, sections and applicants, and CSV upload."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api
from ta_assignment.db.models import Base

ME = {"X-Client-Id": "browser-me"}
OTHER = {"X-Client-Id": "browser-other"}


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


def workspace(client, **body):
    return client.post("/api/workspaces", json={"name": "Test", **body}, headers=ME).json()["id"]


SECTION = {
    "course_id": "CSCI 1111", "section_number": "10", "term": "FALL", "year": 2026, "instructor": "Kim",
    "lecture_meetings": [{"day": "MON", "start": "11:10", "end": "12:25", "label": "Lecture"}],
    "labs": [{"lab_id": "Lab 1", "meetings": [{"day": "FRI", "start": "10:00", "end": "11:50"}]}],
    "la_count": 2, "uta_count": 1,
}

APPLICANT = {
    "applicant_id": "G1", "name": "Jordan Ellis", "email": "j@example.edu",
    "past_courses": [{"course_id": "CSCI 1111", "grade": "A", "term": "FALL", "year": 2025}],
    "upcoming_schedule": [],
    "application": {"term": "FALL", "year": 2026, "position_types": ["LA"],
                    "ranked_preferences": [{"course_id": "CSCI 1111", "rank": 1}]},
}


def add_course_and_section(client, wid):
    res = client.put(f"/api/workspaces/{wid}/courses/CSCI 1111", json={"course_id": "CSCI 1111", "title": "Intro"}, headers=ME)
    assert res.status_code == 200, res.text
    res = client.post(f"/api/workspaces/{wid}/sections", json=SECTION, headers=ME)
    assert res.status_code == 201, res.text
    return res.json()


# --- editing -----------------------------------------------------------------------

def test_create_and_list_course_with_section(client):
    wid = workspace(client)
    sec = add_course_and_section(client, wid)
    assert sec["section_id"] == "CSCI 1111-10 (Fall 2026)"
    courses = client.get(f"/api/workspaces/{wid}/courses", headers=ME).json()["courses"]
    assert courses[0]["title"] == "Intro" and courses[0]["sections"][0]["id"] == sec["id"]


def test_section_needs_an_existing_course_and_a_unique_key(client):
    wid = workspace(client)
    res = client.post(f"/api/workspaces/{wid}/sections", json=SECTION, headers=ME)
    assert res.status_code == 400 and "Add the course first" in res.json()["detail"]
    add_course_and_section(client, wid)
    assert client.post(f"/api/workspaces/{wid}/sections", json=SECTION, headers=ME).status_code == 409


def test_bad_values_are_refused_with_a_readable_message(client):
    wid = workspace(client)
    client.put(f"/api/workspaces/{wid}/courses/CSCI 1111", json={"course_id": "CSCI 1111", "title": "Intro"}, headers=ME)
    bad = {**SECTION, "term": "WINTER"}
    res = client.post(f"/api/workspaces/{wid}/sections", json=bad, headers=ME)
    assert res.status_code == 422 and "term" in res.json()["detail"] and "WINTER" in res.json()["detail"]
    backwards = {**SECTION, "lecture_meetings": [{"day": "MON", "start": "12:00", "end": "11:00"}]}
    res = client.post(f"/api/workspaces/{wid}/sections", json=backwards, headers=ME)
    assert res.status_code == 422 and "before it starts" in res.json()["detail"]


def test_renaming_a_section_keeps_its_locks(client):
    wid = workspace(client)
    sec = add_course_and_section(client, wid)
    client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=ME)
    res = client.post(f"/api/locks?dataset={wid}", headers=ME, json={
        "applicant_id": "G1", "section_id": sec["section_id"], "position": "LA", "lock_type": "locked"})
    assert res.status_code == 201, res.text

    res = client.put(f"/api/workspaces/{wid}/sections/{sec['id']}", json={**SECTION, "section_number": "20"}, headers=ME)
    assert res.status_code == 200
    locks = client.get(f"/api/locks?dataset={wid}", headers=ME).json()["locks"]
    assert [l["section_id"] for l in locks] == ["CSCI 1111-20 (Fall 2026)"]


def test_deleting_removes_dependent_locks(client):
    wid = workspace(client)
    sec = add_course_and_section(client, wid)
    client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=ME)
    client.post(f"/api/locks?dataset={wid}", headers=ME, json={
        "applicant_id": "G1", "section_id": sec["section_id"], "position": "LA", "lock_type": "blocked"})
    assert client.delete(f"/api/workspaces/{wid}/applicants/G1", headers=ME).status_code == 204
    assert client.get(f"/api/locks?dataset={wid}", headers=ME).json()["locks"] == []

    client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=ME)
    client.post(f"/api/locks?dataset={wid}", headers=ME, json={
        "applicant_id": "G1", "section_id": sec["section_id"], "position": "LA", "lock_type": "blocked"})
    assert client.delete(f"/api/workspaces/{wid}/courses/CSCI 1111", headers=ME).status_code == 204
    assert client.get(f"/api/locks?dataset={wid}", headers=ME).json()["locks"] == []
    assert client.get(f"/api/workspaces/{wid}/courses", headers=ME).json()["courses"] == []


def test_applicant_save_and_replace(client):
    wid = workspace(client)
    saved = client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=ME).json()
    assert saved["gpa"] == 4.0 and saved["application"]["position_types"] == ["LA"]
    updated = client.put(f"/api/workspaces/{wid}/applicants/G1",
                         json={**APPLICANT, "name": "Jordan E.", "application": {**APPLICANT["application"], "position_types": ["LA", "UTA"]}},
                         headers=ME).json()
    assert updated["name"] == "Jordan E." and updated["application"]["position_types"] == ["LA", "UTA"]
    assert len(client.get(f"/api/workspaces/{wid}/applicants", headers=ME).json()["applicants"]) == 1


def test_ids_cannot_be_changed_through_the_path(client):
    wid = workspace(client)
    res = client.put(f"/api/workspaces/{wid}/applicants/G2", json=APPLICANT, headers=ME)
    assert res.status_code == 400


def test_editing_is_private_to_the_browser(client):
    wid = workspace(client)
    add_course_and_section(client, wid)
    assert client.get(f"/api/workspaces/{wid}/courses", headers=OTHER).status_code == 404
    assert client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=OTHER).status_code == 404


def test_edited_workspace_solves(client):
    wid = workspace(client)
    add_course_and_section(client, wid)
    client.put(f"/api/workspaces/{wid}/applicants/G1", json=APPLICANT, headers=ME)
    res = client.post("/api/solve", json={"dataset": wid, "min_gpa": 3.0}, headers=ME).json()
    assert res["filled"] == 1 and res["slots"][0]["applicant_id"] == "G1"


# --- CSV upload ---------------------------------------------------------------------

SECTION_ROWS = [
    {"course_id": "CSCI 1111", "course_title": "Intro", "section": "10", "term": "Fall", "year": "2026",
     "lecture_days": "MW", "lecture_start": "11:10", "lecture_end": "12:25", "labs": "Fri 10:00-11:50",
     "la_count": "2", "uta_count": "1"},
    {"course_id": "CSCI 1111", "course_title": "", "section": "11", "term": "Fall", "year": "2026",
     "lecture_days": "TR", "lecture_start": "2:20pm", "lecture_end": "3:35pm", "labs": "Thu 4:00pm-5:50pm",
     "la_count": "1", "uta_count": "0"},
]

APPLICANT_ROWS = [
    {"applicant_id": "G1", "name": "Jordan Ellis", "positions": "LA", "transcript": "CSCI 1111: A",
     "pref_1": "CSCI 1111"},
    {"applicant_id": "G2", "name": "Sam Okafor", "positions": "both", "transcript": "CSCI 1111: A-",
     "pref_1": "CSCI 1111"},
]


def test_dry_run_reports_without_saving(client):
    wid = workspace(client)
    res = client.post(f"/api/workspaces/{wid}/csv/sections", json={"rows": SECTION_ROWS}, headers=ME).json()
    assert res["ok"] and not res["imported"]
    assert res["summary"] == {"courses": 1, "sections": 2, "new": 2, "updated": 0}
    assert client.get(f"/api/workspaces/{wid}/courses", headers=ME).json()["courses"] == []


def test_csv_import_then_solve(client):
    wid = workspace(client)
    res = client.post(f"/api/workspaces/{wid}/csv/sections", json={"rows": SECTION_ROWS, "dry_run": False}, headers=ME).json()
    assert res["imported"] and res["workspace"]["counts"]["sections"] == 2
    res = client.post(f"/api/workspaces/{wid}/csv/applicants", json={"rows": APPLICANT_ROWS, "dry_run": False}, headers=ME).json()
    assert res["imported"] and res["workspace"]["counts"]["applicants"] == 2
    people = client.get(f"/api/workspaces/{wid}/applicants", headers=ME).json()["applicants"]
    assert {p["application"]["term"] for p in people} == {"FALL"}   # took the term from the sections
    solved = client.post("/api/solve", json={"dataset": wid, "min_gpa": 3.0}, headers=ME).json()
    assert solved["filled"] >= 2


def test_any_bad_row_means_nothing_is_saved(client):
    wid = workspace(client)
    rows = SECTION_ROWS + [{**SECTION_ROWS[0], "section": "12", "lecture_start": "noon"}]
    res = client.post(f"/api/workspaces/{wid}/csv/sections", json={"rows": rows, "dry_run": False}, headers=ME).json()
    assert not res["ok"] and not res["imported"]
    assert res["errors"] == [{"row": 4, "column": "Lecture days", "message": "'noon' isn't a time (try 9:35 or 2:20pm)"}]
    assert client.get(f"/api/workspaces/{wid}/courses", headers=ME).json()["courses"] == []


def test_duplicate_rows_are_flagged(client):
    wid = workspace(client)
    res = client.post(f"/api/workspaces/{wid}/csv/applicants",
                      json={"rows": APPLICANT_ROWS + [APPLICANT_ROWS[0]]}, headers=ME).json()
    assert any(e["row"] == 4 and "row 2" in e["message"] for e in res["errors"])
    res = client.post(f"/api/workspaces/{wid}/csv/sections", json={"rows": SECTION_ROWS + [SECTION_ROWS[0]]}, headers=ME).json()
    assert any(e["row"] == 4 and "row 2" in e["message"] for e in res["errors"])


def test_merge_updates_matching_and_keeps_the_rest(client):
    wid = workspace(client, sample="extended")
    before = client.get(f"/api/workspaces/{wid}", headers=ME).json()["counts"]["applicants"]
    some_id = client.get(f"/api/workspaces/{wid}/applicants", headers=ME).json()["applicants"][0]["applicant_id"]
    rows = [{"applicant_id": some_id, "name": "Renamed Person", "positions": "LA", "transcript": "CSCI 1012: A"},
            {"applicant_id": "NEW1", "name": "New Person", "positions": "LA"}]
    res = client.post(f"/api/workspaces/{wid}/csv/applicants", json={"rows": rows, "dry_run": False}, headers=ME).json()
    assert res["summary"]["new"] == 1 and res["summary"]["updated"] == 1
    people = {p["applicant_id"]: p for p in client.get(f"/api/workspaces/{wid}/applicants", headers=ME).json()["applicants"]}
    assert len(people) == before + 1 and people[some_id]["name"] == "Renamed Person"


def test_replace_swaps_out_everything_of_that_kind(client):
    wid = workspace(client, sample="extended")
    res = client.post(f"/api/workspaces/{wid}/csv/applicants",
                      json={"rows": APPLICANT_ROWS, "mode": "replace", "dry_run": False}, headers=ME).json()
    assert res["imported"]
    assert len(client.get(f"/api/workspaces/{wid}/applicants", headers=ME).json()["applicants"]) == 2


def test_columns_endpoint_serves_labels_and_examples(client):
    cols = client.get("/api/csv/columns/sections").json()["columns"]
    assert cols[0]["key"] == "course_id" and cols[0]["required"] is True and cols[0]["example"]
