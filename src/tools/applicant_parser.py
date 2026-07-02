import json
from typing import List
from models.application import (
    StudentApplication, StudentLevel, ScheduledCourse,
    CoursePreference, ProfessorRecommendation,
)
from models.assignment import PositionType

# Map JSON string values to enums
_LEVEL_MAP = {
    "Undergraduate": StudentLevel.UNDERGRADUATE,
    "Graduate":      StudentLevel.GRADUATE,
}
_POSITION_MAP = {
    "LA":  PositionType.LA,
    "UTA": PositionType.UTA,
    "GTA": PositionType.GTA,
}


def load_applications(path: str) -> List[StudentApplication]:
    with open(path) as f:
        data = json.load(f)

    apps = []
    for a in data["applicants"]:
        app = StudentApplication(
            student_id=a["student_id"],
            name=a["name"],
            email=a["email"],
            student_level=_LEVEL_MAP[a["student_level"]],
            term=a["term"],
            gpa=a.get("gpa"),
            positions_applied=[_POSITION_MAP[p] for p in a["positions_applied"]],
            preferred_courses=[
                CoursePreference(
                    course_title=cp["course_title"],
                    course_number=cp["course_number"],
                    preference_rank=cp["preference_rank"],
                    prior_experience=cp.get("prior_experience", False),
                )
                for cp in a.get("preferred_courses", [])
            ],
            skills=a.get("skills", []),
            current_schedule=[
                ScheduledCourse(
                    course_name=sc["course_name"],
                    days=sc["days"],
                    start_time=sc["start_time"],
                    end_time=sc["end_time"],
                )
                for sc in a.get("current_schedule", [])
            ],
            recommendations=[
                ProfessorRecommendation(
                    professor_name=r["professor_name"],
                    course_taught=r["course_taught"],
                    comments=r.get("comments"),
                )
                for r in a.get("recommendations", [])
            ],
            statement=a.get("statement"),
        )

        # Attach extra scoring fields directly onto the object.
        # These live in the JSON but not in the dataclass definition;
        # the evaluation pipeline reads them via getattr(..., default).
        app.course_grades = a.get("course_grades", [])
        app.ta_history    = a.get("ta_history", [])
        app.max_ta_slots  = a.get("max_ta_slots", 1)

        # Enrich each ProfessorRecommendation with tone + seniority from JSON
        for rec, raw_rec in zip(app.recommendations, a.get("recommendations", [])):
            rec.tone                  = raw_rec.get("tone", "neutral")
            rec.recommender_seniority = raw_rec.get("recommender_seniority", "faculty")

        apps.append(app)

    return apps
