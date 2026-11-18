"""Unit tests for the spreadsheet-friendly CSV parsers and row conversion."""

import pytest

from ta_assignment.db import csv_import as c


@pytest.mark.parametrize("text, days", [
    ("MW", ["MON", "WED"]), ("TR", ["TUE", "THU"]), ("TTh", ["TUE", "THU"]), ("MWF", ["MON", "WED", "FRI"]),
    ("Mon/Wed", ["MON", "WED"]), ("Tue, Thu", ["TUE", "THU"]), ("M W F", ["MON", "WED", "FRI"]),
    ("Friday", ["FRI"]), ("", []),
])
def test_parse_days(text, days):
    assert c.parse_days(text) == days


@pytest.mark.parametrize("bad", ["Funday", "XYZ", "Sat"])
def test_parse_days_rejects_nonsense(bad):
    with pytest.raises(c.CellError):
        c.parse_days(bad)


@pytest.mark.parametrize("text, hhmm", [
    ("9:35", "09:35"), ("09:35", "09:35"), ("2:20pm", "14:20"), ("2 PM", "14:00"), ("12pm", "12:00"),
    ("12:15 am", "00:15"), ("14", "14:00"), ("11:10 a.m.", "11:10"),
])
def test_parse_time(text, hhmm):
    assert c.parse_time(text) == hhmm


@pytest.mark.parametrize("bad", ["25:00", "9:75", "noon", "13pm"])
def test_parse_time_rejects_nonsense(bad):
    with pytest.raises(c.CellError):
        c.parse_time(bad)


def test_parse_meetings_expands_days_and_ranges():
    out = c.parse_meetings("MW 10:00-11:15; TR 2:20pm to 3:35pm", "Class")
    assert [(m["day"], m["start"], m["end"]) for m in out] == [
        ("MON", "10:00", "11:15"), ("WED", "10:00", "11:15"), ("TUE", "14:20", "15:35"), ("THU", "14:20", "15:35")]


@pytest.mark.parametrize("text, positions", [
    ("LA", ["LA"]), ("UTA", ["UTA"]), ("LA, UTA", ["LA", "UTA"]), ("both", ["LA", "UTA"]),
    ("Learning Assistant", ["LA"]), ("la or uta", ["LA", "UTA"]), ("", ["LA"]),
])
def test_parse_positions(text, positions):
    assert c.parse_positions(text) == positions


def test_parse_transcript_with_and_without_terms():
    out = c.parse_transcript("CSCI 1111: A-; CSCI 1112: B+ (Spring 2026); CSCI 2113 IP", "FALL", 2025)
    assert out == [
        {"course_id": "CSCI 1111", "grade": "A_MINUS", "term": "FALL", "year": 2025},
        {"course_id": "CSCI 1112", "grade": "B_PLUS", "term": "SPRING", "year": 2026},
        {"course_id": "CSCI 2113", "grade": "IN_PROGRESS", "term": "FALL", "year": 2025},
    ]


def test_parse_experience_and_recommendations():
    assert c.parse_experience("LA CSCI 1111 Fall 2025; UTA CSCI 1112 Spring 2026 (4.5)") == [
        {"position": "LA", "course_id": "CSCI 1111", "term": "FALL", "year": 2025, "supervisor_rating": None},
        {"position": "UTA", "course_id": "CSCI 1112", "term": "SPRING", "year": 2026, "supervisor_rating": 4.5},
    ]
    assert c.parse_recommendations("Prof. Kim: 5; Dr. Lee: 4 (CSCI 1112)") == [
        {"faculty_name": "Prof. Kim", "course_id": None, "strength": 5.0, "note": ""},
        {"faculty_name": "Dr. Lee", "course_id": "CSCI 1112", "strength": 4.0, "note": ""},
    ]


def section_row(**over):
    row = {"course_id": "CSCI 1111", "course_title": "Intro", "section": "10", "term": "Fall", "year": "2026",
           "lecture_days": "MW", "lecture_start": "11:10", "lecture_end": "12:25",
           "labs": "Fri 10:00-11:50; L32: Fri 12:00-13:50", "la_count": "2", "uta_count": "1",
           "uta_attend_lecture": "yes", "skills": "Python; recursion"}
    row.update(over)
    return row


def test_section_rows_build_courses_and_sections():
    courses, sections, errors = c.convert_section_rows(
        [section_row(), section_row(section="11", course_title="", lecture_days="TR")], {})
    assert errors == []
    assert [(x.course_id, x.title, x.skills) for x in courses] == [("CSCI 1111", "Intro", ["python", "recursion"])]
    assert [s.section_number for s in sections] == ["10", "11"]
    s = sections[0]
    assert [m.day for m in s.lecture_meetings] == ["MON", "WED"]
    assert [lab.lab_id for lab in s.labs] == ["Lab 1", "L32"]
    assert s.uta_must_attend_lecture is True and s.la_must_attend_lecture is False


def test_section_row_errors_name_the_row_and_column():
    _, sections, errors = c.convert_section_rows([
        section_row(),
        section_row(section="11", term="Winter"),
        section_row(section="12", lecture_end="10:00"),
        section_row(section="13", la_count="two"),
        section_row(section="14", la_count="0", uta_count="0"),
    ], {})
    assert len(sections) == 1
    by_row = {e["row"]: e for e in errors}
    assert by_row[3]["column"] == "Term" and "Winter" in by_row[3]["message"]
    assert by_row[4]["column"] == "Lecture days" and "before it starts" in by_row[4]["message"]
    assert by_row[5]["column"] == "LAs needed"
    assert "at least one LA or UTA" in by_row[6]["message"]


def test_new_course_without_title_is_an_error_but_existing_one_is_fine():
    _, _, errors = c.convert_section_rows([section_row(course_title="")], {})
    assert errors and errors[0]["column"] == "Course title"
    courses, _, errors = c.convert_section_rows([section_row(course_title="")], {"CSCI 1111": "Existing title"})
    assert errors == [] and courses[0].title == "Existing title"


def applicant_row(**over):
    row = {"applicant_id": "G1", "name": "Jordan Ellis", "email": "j@example.edu", "positions": "LA, UTA",
           "transcript": "CSCI 1111: A; CSCI 1112: B+", "busy_times": "MW 10:00-11:15",
           "pref_1": "CSCI 1112", "pref_2": "CSCI 1111", "experience": "LA CSCI 1111 Fall 2025",
           "recommendations": "Prof. Kim: 5", "skills": "python"}
    row.update(over)
    return row


def test_applicant_rows_convert():
    applicants, errors = c.convert_applicant_rows([applicant_row()], "FALL", 2026)
    assert errors == []
    a = applicants[0]
    assert a.application.position_types == ["LA", "UTA"]
    assert [(p.course_id, p.rank) for p in a.application.ranked_preferences] == [("CSCI 1112", 1), ("CSCI 1111", 2)]
    assert a.past_courses[0].year == 2025   # grades default to the year before the term being staffed
    assert [m.day for m in a.upcoming_schedule] == ["MON", "WED"]


def test_applicant_row_errors():
    _, errors = c.convert_applicant_rows([
        applicant_row(name=""),
        applicant_row(applicant_id="G2", transcript="CSCI 1111 - excellent"),
        applicant_row(applicant_id="G3", pref_2="CSCI 1112"),
        applicant_row(applicant_id="G4", positions="professor"),
    ], "FALL", 2026)
    by_row = {}
    for e in errors:
        by_row.setdefault(e["row"], []).append(e)
    assert by_row[2][0]["column"] == "Name"
    assert by_row[3][0]["column"] == "Courses taken"
    assert "ranked twice" in by_row[4][0]["message"]
    assert by_row[5][0]["column"] == "Positions"


def test_blank_lines_are_skipped():
    courses, sections, errors = c.convert_section_rows([section_row(), {k: "" for k in section_row()}], {})
    assert errors == [] and len(sections) == 1
