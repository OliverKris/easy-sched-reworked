"""JSON <-> domain-value-object conversion for the bits stored in JSON
columns (TimeSlot, LabSection). Enum members are always serialized by
`.name` (e.g. "FALL), "A_MINUS", "LA" for unambiguous round-tripping".
"""

from datetime import time as time_cls

from ..courses import LabSection
from ..enums import Day
from ..scheduling import TimeSlot


def timeslot_to_dict(ts: TimeSlot) -> dict:
    return {
        "day": ts.day.name,
        "start": ts.start.strftime("%H:%M"),
        "end": ts.end.strftime("%H:%M"),
        "label": ts.label,
    }


def dict_to_timeslot(d: dict) -> TimeSlot:
    h, m = map(int, d["start"].split(":"))
    start = time_cls(h, m)
    h, m = map(int, d["end"].split(":"))
    end = time_cls(h, m)
    return TimeSlot(Day[d["day"]], start, end, d.get("label", ""))


def lab_to_dict(lab: LabSection) -> dict:
    return {
        "lab_id": lab.lab_id,
        "capacity": lab.capacity,
        "meetings": [timeslot_to_dict(m) for m in lab.meetings],
    }


def dict_to_lab(d: dict) -> LabSection:
    return LabSection(
        lab_id=d["lab_id"],
        meetings=[dict_to_timeslot(m) for m in d.get("meetings", [])],
        capacity=d.get("capacity"),
    )