# section.py

from dataclasses import dataclass, field
from typing import List, Optional


# A location and time where a section meets.
@dataclass
class MeetingTime:
    days: str
    start_time: str
    end_time: str
    building: Optional[str]
    room: Optional[str]

# A single section of a course, which may be a lecture or a lab
@dataclass
class Section:
    crn: str                    # keep as str — used as dict key and in linkedSections
    section_number: str
    status: str                 # OPEN, CLOSED, WAITLIST, CANCELLED
    type: str
    instructor: Optional[str]
    credits: str                # str because JSON has "1.00 TO 3.00" edge cases
    meetings: List[MeetingTime] = field(default_factory=list)
    linked_sections: List[str] = field(default_factory=list)


def parse_meeting(m: dict) -> MeetingTime:
    return MeetingTime(
        days=m.get("days"),
        start_time=m.get("startTime"),
        end_time=m.get("endTime"),
        building=m.get("building"),
        room=m.get("room"),
    )


def parse_section(s: dict) -> Section:
    return Section(
        crn=str(s["crn"]),
        section_number=s.get("sectionNumber", ""),
        status=s.get("status", "OPEN"),
        type=s.get("sectionType", ""),
        instructor=s.get("instructor"),
        credits=str(s.get("credits", "0.00")),
        meetings=[parse_meeting(m) for m in s.get("meetings", [])],
        linked_sections=[str(crn) for crn in s.get("linkedSections", [])],
    )
