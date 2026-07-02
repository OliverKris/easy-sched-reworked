import json
from typing import List
from models.course import SectionGroup
from models.section import Section, MeetingTime


def _parse_section_entry(entry: dict) -> Section:
    days  = entry.get("days")
    start = entry.get("start_time")
    end   = entry.get("end_time")

    meetings = []
    if days and start and end:
        meetings = [MeetingTime(
            days=days,
            start_time=start,
            end_time=end,
            building=entry.get("building"),
            room=entry.get("room"),
        )]

    return Section(
        crn=str(entry["crn"]),
        section_number=entry.get("section_number", ""),
        status="OPEN",
        type=entry.get("type", ""),
        instructor=None,
        credits="",
        meetings=meetings,
        linked_sections=[],
    )


def load_section_groups(path: str) -> List[SectionGroup]:
    with open(path) as f:
        data = json.load(f)

    groups = []
    for sg in data["section_groups"]:
        group = SectionGroup(
            course_subject=sg["course_subject"],
            course_number=sg["course_number"],
            course_title=sg["course_title"],
            group_id=sg["id"],
            instructor=sg["instructor"],
            lecture=_parse_section_entry(sg["lecture"]),
            labs=[_parse_section_entry(lab) for lab in sg.get("labs", [])],
        )

        # Attach skills_required directly — needed by the evaluation pipeline's
        # skill-match scorer. Read via getattr(..., []) so missing keys are safe.
        group.skills_required = sg.get("skills_required", [])

        groups.append(group)

    return groups
