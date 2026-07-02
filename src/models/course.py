from dataclasses import dataclass, field
from typing import List, Optional
from models.section import Section, parse_section


@dataclass
class Course:
    course_subject: str
    course_number: str
    title: str
    sections: List[Section] = field(default_factory=list)

    @property
    def active_sections(self) -> List[Section]:
        return [s for s in self.sections if s.status != "CANCELLED"]


@dataclass
class SectionGroup:
    """
    One logical teaching unit: a single instructor's lecture plus all
    labs/discussions linked to it. Each gets its own TA pool.
    """
    # Course identity — populated by both the raw parser and processed_parser
    course_subject: str
    course_number: str
    course_title: str
    group_id: str           # stable id, e.g. "sg_1012_nguyen"

    instructor: str
    lecture: Section
    labs: List[Section] = field(default_factory=list)

    @property
    def all_sections(self) -> List[Section]:
        return [self.lecture] + self.labs

    @property
    def all_crns(self) -> List[str]:
        return [s.crn for s in self.all_sections]


def group_sections(course: Course) -> List["SectionGroup"]:
    crn_map = {s.crn: s for s in course.active_sections}
    groups: List[SectionGroup] = []
    claimed: set = set()

    # Anchor pass: lectures that explicitly link their sub-sections,
    # but only claim linked CRNs that are NOT themselves lectures
    for section in course.active_sections:
        if section.type == "Lecture" and section.linked_sections:
            labs = [
                crn_map[crn]
                for crn in section.linked_sections
                if crn in crn_map and crn_map[crn].type != "Lecture"
            ]
            instructor = section.instructor or "TBD"
            group_id = f"sg_{course.course_number}_{instructor.split(',')[0].lower()}"
            groups.append(SectionGroup(
                course_subject=course.course_subject,
                course_number=course.course_number,
                course_title=course.title,
                group_id=group_id,
                instructor=instructor,
                lecture=section,
                labs=labs,
            ))
            claimed.add(section.crn)
            claimed.update(lab.crn for lab in labs)

    # Orphan pass: anything not yet claimed becomes its own solo group
    for section in course.active_sections:
        if section.crn not in claimed:
            instructor = section.instructor or "TBD"
            group_id = f"sg_{course.course_number}_{instructor.split(',')[0].lower()}_{section.crn}"
            groups.append(SectionGroup(
                course_subject=course.course_subject,
                course_number=course.course_number,
                course_title=course.title,
                group_id=group_id,
                instructor=instructor,
                lecture=section,
                labs=[],
            ))
            claimed.add(section.crn)

    return groups


def parse_course(c: dict) -> Course:
    return Course(
        course_subject=str(c["courseSubject"]),
        course_number=str(c["courseNumber"]),
        title=c["courseTitle"],
        sections=[parse_section(s) for s in c.get("sections", [])],
    )
