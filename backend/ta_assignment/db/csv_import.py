"""Turning spreadsheet rows into courses, sections and applicants.

Coordinators keep this data in spreadsheets and form exports, so the CSV
format favours what people actually type: days like "MW" or "Tue/Thu", times
like "2:20pm", transcripts like "CSCI 1111: A-; CSCI 1112: B+". The frontend
matches the file's headers to the column names below and sends the rows; this
module converts them, validates each with the workspace-file models, and
reports problems by spreadsheet row number and column so they can be fixed
in the sheet.

Row numbers count the header as row 1, so the first data row is row 2.
"""

import re
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from ..enums import Grade, PositionType, Semester
from .bundle import ApplicantJ, CourseJ, SectionJ

# --- column definitions (also served to the frontend for matching/templates) ---

SECTION_COLUMNS = [
    # key, label, required, aliases, example
    ("course_id", "Course code", True, ["course", "course code", "course number", "code"], "CSCI 1111"),
    ("course_title", "Course title", False, ["title", "course name", "name"], "Intro to Programming"),
    ("section", "Section", True, ["section number", "sec", "section #"], "10"),
    ("term", "Term", True, ["semester"], "Fall"),
    ("year", "Year", True, [], "2026"),
    ("instructor", "Instructor", False, ["professor", "faculty", "teacher"], "Prof. Kim"),
    ("lecture_days", "Lecture days", False, ["days", "meeting days", "lecture day"], "MW"),
    ("lecture_start", "Lecture start", False, ["start", "start time", "begins"], "11:10"),
    ("lecture_end", "Lecture end", False, ["end", "end time", "ends"], "12:25"),
    ("labs", "Labs", False, ["lab sections", "lab times", "lab"], "Fri 10:00-11:50; Fri 12:00-13:50"),
    ("la_count", "LAs needed", False, ["las", "la count", "number of las", "learning assistants"], "2"),
    ("uta_count", "UTAs needed", False, ["utas", "uta count", "number of utas", "undergraduate tas"], "1"),
    ("la_attend_lecture", "LAs attend lecture", False, ["la must attend lecture"], "no"),
    ("uta_attend_lecture", "UTAs attend lecture", False, ["uta must attend lecture"], "yes"),
    ("skills", "Skills", False, ["skill tags", "topics", "tags"], "python; recursion"),
]

APPLICANT_COLUMNS = [
    ("applicant_id", "Student ID", True, ["id", "gwid", "student id", "netid", "applicant id"], "G41029384"),
    ("name", "Name", True, ["full name", "student name", "applicant"], "Jordan Ellis"),
    ("email", "Email", False, ["email address", "e-mail", "gw email"], "jellis@example.edu"),
    ("positions", "Positions", False, ["position", "position(s)", "role", "roles", "applying for"], "LA, UTA"),
    ("transcript", "Courses taken", False, ["courses taken", "courses", "grades", "course history"], "CSCI 1111: A; CSCI 1112: B+"),
    ("busy_times", "Busy times", False, ["class schedule", "own classes", "unavailable", "schedule"], "MW 10:00-11:15; TR 14:20-15:35"),
    ("pref_1", "1st choice", False, ["first choice", "choice 1", "preference 1", "1st preference"], "CSCI 2113"),
    ("pref_2", "2nd choice", False, ["second choice", "choice 2", "preference 2", "2nd preference"], "CSCI 1112"),
    ("pref_3", "3rd choice", False, ["third choice", "choice 3", "preference 3", "3rd preference"], ""),
    ("experience", "Prior TA roles", False, ["experience", "teaching experience", "prior roles", "ta experience"], "LA CSCI 1111 Fall 2025"),
    ("recommendations", "Recommendations", False, ["recommenders", "references", "recommender"], "Prof. Kim: 5"),
    ("skills", "Skills", False, ["skill tags", "strengths"], "python; git"),
]


def column_spec(kind: str) -> List[dict]:
    cols = SECTION_COLUMNS if kind == "sections" else APPLICANT_COLUMNS
    return [{"key": k, "label": l, "required": r, "aliases": a, "example": e} for k, l, r, a, e in cols]


# --- small parsers ---------------------------------------------------------

class CellError(ValueError):
    pass


_DAY_WORDS = {
    "mon": "MON", "monday": "MON", "m": "MON",
    "tue": "TUE", "tues": "TUE", "tuesday": "TUE", "tu": "TUE", "t": "TUE",
    "wed": "WED", "wednesday": "WED", "w": "WED",
    "thu": "THU", "thur": "THU", "thurs": "THU", "thursday": "THU", "th": "THU", "r": "THU",
    "fri": "FRI", "friday": "FRI", "f": "FRI",
    "sat": "SAT", "saturday": "SAT", "sun": "SUN", "sunday": "SUN",
}


def parse_days(text: str) -> List[str]:
    """'MW', 'TR', 'TTh', 'MWF', 'Mon/Wed', 'Tue, Thu' -> ['MON', 'WED']."""
    t = text.strip()
    if not t:
        return []
    words = re.split(r"[\s,/&+]+|\band\b", t.lower())
    words = [w for w in words if w]
    if all(w in _DAY_WORDS and len(w) > 2 for w in words):
        days = [_DAY_WORDS[w] for w in words]
    else:
        # Compact letters: M T W R F, with "Th" for Thursday.
        compact = re.sub(r"[\s,/]+", "", t)
        days, i = [], 0
        while i < len(compact):
            two = compact[i:i + 2].lower()
            if two == "th":
                days.append("THU")
                i += 2
                continue
            ch = compact[i].lower()
            if ch not in "mtwrfsu" or ch in "su":
                raise CellError(f"'{text}' isn't a set of days (try MW, TR or Mon/Wed)")
            days.append(_DAY_WORDS[ch])
            i += 1
    out = []
    for d in days:
        if d not in out:
            out.append(d)
    if any(d in ("SAT", "SUN") for d in out):
        raise CellError("weekend days aren't supported")
    return out


def parse_time(text: str) -> str:
    """'9:35', '09:35', '2:20pm', '2 PM', '14' -> 'HH:MM' (24-hour)."""
    t = text.strip().lower().replace(".", "")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a|p)?", t)
    if not m:
        raise CellError(f"'{text}' isn't a time (try 9:35 or 2:20pm)")
    h, mins, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm:
        if not 1 <= h <= 12:
            raise CellError(f"'{text}' isn't a time")
        h = (h % 12) + (12 if ampm.startswith("p") else 0)
    if not (0 <= h <= 23 and 0 <= mins <= 59):
        raise CellError(f"'{text}' isn't a time")
    return f"{h:02d}:{mins:02d}"


def parse_meetings(text: str, label: str = "") -> List[dict]:
    """'MW 10:00-11:15; TR 2:20pm-3:35pm' -> timeslot dicts."""
    out = []
    for part in _split_list(text, seps=";\n"):
        m = re.fullmatch(r"(.+?)\s+(\d[\d:.\sapmAPM]*?)\s*[-–to]+\s*(\d[\d:.\sapmAPM]*)", part.strip())
        if not m:
            raise CellError(f"'{part}' should look like 'MW 10:00-11:15'")
        days = parse_days(m.group(1))
        start, end = parse_time(m.group(2)), parse_time(m.group(3))
        out.extend({"day": d, "start": start, "end": end, "label": label} for d in days)
    return out


def parse_bool(text: str, default: bool = False) -> bool:
    t = text.strip().lower()
    if not t:
        return default
    if t in ("y", "yes", "true", "1", "required", "x"):
        return True
    if t in ("n", "no", "false", "0", "optional"):
        return False
    raise CellError(f"'{text}' should be yes or no")


def parse_int(text: str, default: Optional[int] = None) -> Optional[int]:
    t = text.strip()
    if not t:
        return default
    if not re.fullmatch(r"\d+", t):
        raise CellError(f"'{text}' isn't a whole number")
    return int(t)


def parse_term(text: str) -> str:
    t = text.strip().upper()
    for member in Semester:
        if t in (member.name, member.value.upper()):
            return member.name
    raise CellError(f"'{text}' isn't a term (use {' or '.join(m.value for m in Semester)})")


_GRADES = {
    "A": "A", "A-": "A_MINUS", "B+": "B_PLUS", "B": "B", "B-": "B_MINUS", "C+": "C_PLUS", "C": "C",
    "C-": "C_MINUS", "D+": "D_PLUS", "D": "D", "D-": "D_MINUS", "F": "F",
    "IP": "IN_PROGRESS", "IN PROGRESS": "IN_PROGRESS", "CURRENT": "IN_PROGRESS",
}


def parse_grade(text: str) -> str:
    t = text.strip().upper().replace("−", "-").replace("–", "-")
    if t in _GRADES:
        return _GRADES[t]
    if t in Grade.__members__:
        return t
    raise CellError(f"'{text}' isn't a letter grade")


def parse_positions(text: str) -> List[str]:
    t = text.strip().lower()
    if not t:
        return ["LA"]
    if t in ("both", "either", "any", "la/uta", "la or uta"):
        return ["LA", "UTA"]
    out = []
    for word in re.split(r"[,;/&]+|\band\b|\bor\b", t):
        w = word.strip()
        if not w:
            continue
        if w in ("la", "learning assistant", "learning assistants"):
            out.append("LA")
        elif w in ("uta", "ta", "undergraduate ta", "undergraduate tas", "undergrad ta"):
            out.append("UTA")
        else:
            raise CellError(f"'{word.strip()}' isn't LA or UTA")
    return sorted(set(out))


def _split_list(text: str, seps: str = ";\n") -> List[str]:
    return [p.strip() for p in re.split("[" + re.escape(seps) + "]", text or "") if p.strip()]


def _split_tags(text: str) -> List[str]:
    return sorted({p.strip().lower() for p in re.split(r"[;,]", text or "") if p.strip()})


_TERM_YEAR = re.compile(r"\(?\s*(fall|spring)\s+(\d{4})\s*\)?\s*$", re.I)


def parse_transcript(text: str, default_term: str, default_year: int) -> List[dict]:
    """'CSCI 1111: A; CSCI 1112: B+ (Spring 2026)' -> past-course dicts."""
    out = []
    for part in _split_list(text):
        term, year = default_term, default_year
        tm = _TERM_YEAR.search(part)
        if tm:
            term, year = tm.group(1).upper(), int(tm.group(2))
            part = part[:tm.start()].strip()
        m = re.fullmatch(r"(.+?)\s*[:=]\s*(.+)", part) or re.fullmatch(r"(.+?)\s+([A-Fa-f][+\-−]?|IP|ip)", part)
        if not m:
            raise CellError(f"'{part}' should look like 'CSCI 1111: A-'")
        out.append({"course_id": m.group(1).strip(), "grade": parse_grade(m.group(2)), "term": term, "year": year})
    return out


def parse_experience(text: str) -> List[dict]:
    """'LA CSCI 1111 Fall 2025; UTA CSCI 1112 Spring 2026 (4.5)' -> experience dicts."""
    out = []
    for part in _split_list(text):
        rating = None
        rm = re.search(r"\((\d(?:\.\d)?)\)\s*$", part)
        if rm:
            rating = float(rm.group(1))
            part = part[:rm.start()].strip()
        m = re.fullmatch(r"(LA|UTA)\s+(.+?)\s+(fall|spring)\s+(\d{4})", part, re.I)
        if not m:
            raise CellError(f"'{part}' should look like 'LA CSCI 1111 Fall 2025'")
        out.append({"position": m.group(1).upper(), "course_id": m.group(2).strip(),
                    "term": m.group(3).upper(), "year": int(m.group(4)), "supervisor_rating": rating})
    return out


def parse_recommendations(text: str) -> List[dict]:
    """'Prof. Kim: 5; Prof. Lee: 4 (CSCI 1112)' -> recommendation dicts."""
    out = []
    for part in _split_list(text):
        course = None
        cm = re.search(r"\(([^)]+)\)\s*$", part)
        if cm:
            course = cm.group(1).strip()
            part = part[:cm.start()].strip()
        m = re.fullmatch(r"(.+?)\s*[:=-]\s*(\d(?:\.\d)?)", part)
        if not m:
            raise CellError(f"'{part}' should look like 'Prof. Kim: 5'")
        strength = float(m.group(2))
        if not 1 <= strength <= 5:
            raise CellError(f"strength {m.group(2)} should be 1 to 5")
        out.append({"faculty_name": m.group(1).strip(), "course_id": course, "strength": strength, "note": ""})
    return out


# --- row conversion -------------------------------------------------------------

def _labels(kind: str) -> Dict[str, str]:
    cols = SECTION_COLUMNS if kind == "sections" else APPLICANT_COLUMNS
    return {k: l for k, l, *_ in cols}


def _validation_messages(err: ValidationError, field_to_column: Dict[str, str]) -> List[dict]:
    out = []
    for e in err.errors():
        top = str(e["loc"][0]) if e["loc"] else ""
        out.append({"column": field_to_column.get(top), "message": e["msg"].removeprefix("Value error, ")})
    return out


def convert_section_rows(rows: List[Dict[str, str]], existing_titles: Dict[str, str]) -> Tuple[List[CourseJ], List[SectionJ], List[dict]]:
    labels = _labels("sections")
    errors: List[dict] = []
    sections: List[SectionJ] = []
    titles: Dict[str, str] = {}
    skills: Dict[str, set] = {}

    def fail(row_no, key, message):
        errors.append({"row": row_no, "column": labels.get(key), "message": message})

    for i, raw in enumerate(rows):
        row_no = i + 2
        cell = {k: (v or "").strip() for k, v in raw.items()}
        if not any(cell.values()):
            continue  # blank line
        before = len(errors)
        parsed = {}
        for key in ("course_id", "section", "term", "year"):
            if not cell.get(key):
                fail(row_no, key, "is required")
        try:
            parsed["term"] = parse_term(cell["term"]) if cell.get("term") else None
        except CellError as e:
            fail(row_no, "term", str(e))
        try:
            parsed["year"] = parse_int(cell.get("year", ""))
        except CellError as e:
            fail(row_no, "year", str(e))
        lecture = []
        try:
            days = parse_days(cell.get("lecture_days", ""))
            if days or cell.get("lecture_start") or cell.get("lecture_end"):
                if not (days and cell.get("lecture_start") and cell.get("lecture_end")):
                    raise CellError("needs days, a start and an end together")
                start, end = parse_time(cell["lecture_start"]), parse_time(cell["lecture_end"])
                lecture = [{"day": d, "start": start, "end": end, "label": "Lecture"} for d in days]
        except CellError as e:
            fail(row_no, "lecture_days", str(e))
        labs = []
        try:
            for n, part in enumerate(_split_list(cell.get("labs", "")), start=1):
                lab_id = f"Lab {n}"
                lm = re.match(r"^([^:]{1,20}):\s*(.+)$", part)
                if lm and not re.match(r"^\d", lm.group(2)) and not re.fullmatch(r"\d{1,2}", lm.group(1).strip()):
                    lab_id, part = lm.group(1).strip(), lm.group(2)
                labs.append({"lab_id": lab_id, "capacity": None, "meetings": parse_meetings(part, "Lab")})
        except CellError as e:
            fail(row_no, "labs", str(e))
        counts = {}
        for key, field, default in (("la_count", "la_count", 0), ("uta_count", "uta_count", 0)):
            try:
                counts[field] = parse_int(cell.get(key, ""), default)
            except CellError as e:
                fail(row_no, key, str(e))
        flags = {}
        for key, field in (("la_attend_lecture", "la_must_attend_lecture"), ("uta_attend_lecture", "uta_must_attend_lecture")):
            try:
                flags[field] = parse_bool(cell.get(key, ""))
            except CellError as e:
                fail(row_no, key, str(e))
        if len(errors) > before:
            continue
        if counts["la_count"] + counts["uta_count"] == 0:
            fail(row_no, "la_count", "a section needs at least one LA or UTA")
            continue
        cid = cell["course_id"]
        try:
            section = SectionJ(
                course_id=cid, section_number=cell["section"], term=parsed["term"], year=parsed["year"],
                instructor=cell.get("instructor", ""), lecture_meetings=lecture, labs=labs, **counts, **flags,
            )
        except ValidationError as e:
            for m in _validation_messages(e, {"lecture_meetings": labels["lecture_days"], "labs": labels["labs"],
                                               "section_number": labels["section"]}):
                errors.append({"row": row_no, **m})
            continue
        sections.append(section)
        if cell.get("course_title"):
            titles.setdefault(cid, cell["course_title"])
        skills.setdefault(cid, set()).update(_split_tags(cell.get("skills", "")))

    courses: List[CourseJ] = []
    for cid in dict.fromkeys(s.course_id for s in sections):
        title = titles.get(cid) or existing_titles.get(cid)
        if not title:
            first_row = next(i + 2 for i, r in enumerate(rows) if (r.get("course_id") or "").strip() == cid)
            errors.append({"row": first_row, "column": labels["course_title"],
                           "message": f"{cid} is a new course, so it needs a title"})
            continue
        courses.append(CourseJ(course_id=cid, title=title, skills=sorted(skills.get(cid, set()))))
    return courses, sections, errors


def convert_applicant_rows(rows: List[Dict[str, str]], default_term: str, default_year: int) -> Tuple[List[ApplicantJ], List[dict]]:
    labels = _labels("applicants")
    errors: List[dict] = []
    applicants: List[ApplicantJ] = []
    past_term, past_year = default_term, default_year - 1

    for i, raw in enumerate(rows):
        row_no = i + 2
        cell = {k: (v or "").strip() for k, v in raw.items()}
        if not any(cell.values()):
            continue
        before = len(errors)

        def attempt(key, fn, default):
            try:
                return fn(cell.get(key, ""))
            except CellError as e:
                errors.append({"row": row_no, "column": labels[key], "message": str(e)})
                return default

        for key in ("applicant_id", "name"):
            if not cell.get(key):
                errors.append({"row": row_no, "column": labels[key], "message": "is required"})
        positions = attempt("positions", parse_positions, ["LA"])
        transcript = attempt("transcript", lambda t: parse_transcript(t, past_term, past_year), [])
        busy = attempt("busy_times", lambda t: parse_meetings(t, "Class"), [])
        experience = attempt("experience", parse_experience, [])
        recs = attempt("recommendations", parse_recommendations, [])
        prefs = []
        for rank, key in enumerate(("pref_1", "pref_2", "pref_3"), start=1):
            if cell.get(key):
                prefs.append({"course_id": cell[key], "rank": rank})
        if len(errors) > before:
            continue
        try:
            applicants.append(ApplicantJ(
                applicant_id=cell["applicant_id"], name=cell["name"], email=cell.get("email", ""),
                skills=_split_tags(cell.get("skills", "")), past_courses=transcript,
                teaching_experience=experience, recommendations=recs, upcoming_schedule=busy,
                application={"term": default_term, "year": default_year, "position_types": positions,
                             "ranked_preferences": prefs},
            ))
        except ValidationError as e:
            for m in _validation_messages(e, {"upcoming_schedule": labels["busy_times"], "past_courses": labels["transcript"],
                                               "teaching_experience": labels["experience"], "application": labels["pref_1"]}):
                errors.append({"row": row_no, **m})
    return applicants, errors
