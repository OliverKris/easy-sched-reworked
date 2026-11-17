# Department profiles

A profile is one JSON file that describes a department's TA policy: who is
eligible for a slot (`hard_rules`) and how good a fit they are (`scoring`).
The solvers read compiled profiles, so a new department needs a new file, not
new code.

```python
from ta_assignment.rules import load_profile
from ta_assignment.csp_solver import SolverConfig
from ta_assignment.matching_solver import MatchingSolver

config = SolverConfig(profile=load_profile("profiles/gwu_cs.json"))
result = MatchingSolver(applicants, applications, sections, config=config).solve()
```

Files here:

| File | What it is |
| --- | --- |
| `gwu_cs.json` | GWU CS policy; reproduces the original hardcoded rules exactly |
| `example_math.json` | A fictional second department with different rules |

## Hard rules

Every rule must pass. Any rule (and any scoring term) can be narrowed with
`"positions": ["LA" | "UTA"]` and/or `"courses": ["CSCI 1111", ...]`; out of
scope means the rule is skipped.

| `rule` | Parameters | Passes when |
| --- | --- | --- |
| `applied_for_position` | | the applicant applied for this position type |
| `passed_course` | `min_grade` (e.g. `"B_PLUS"`) | they passed this course, at or above `min_grade` if given |
| `no_lecture_conflict` | `when`: `"if_required"` (default) or `"always"` | their classes don't overlap the lecture |
| `conflict_free_lab` | `allow_no_labs` (default false) | at least one lab fits their schedule |
| `cmp` | `field`, `op` (`>= > <= < == !=`), `value`, `missing` (`"fail"`/`"pass"`) | the field comparison holds |
| `all` / `any` | `rules`: list of rules | all / at least one inner rule passes |
| `not` | `inner`: a rule | the inner rule fails |

## Scoring terms

Each term has a `weight`; the score is the sum, in the order listed.

| `term` | Adds |
| --- | --- |
| `course_grade` | weight x grade points in the course / 4 |
| `teaching_experience` | weight x (`general_share` x min(prior positions, `cap`) / `cap` + `course_share` x taught this course) |
| `recommendation_strength` | weight x average strength / 5 (nothing if no recommendations) |
| `preference_rank` | weight x 1 / rank (unranked = number ranked + 1) |
| `skill_overlap` | weight x share of the course's skill tags the applicant has |
| `bonus` | weight, when its `when` rule passes |

## Fields for `cmp`

| Field | Meaning |
| --- | --- |
| `applicant.gpa` | overall GPA across completed courses |
| `applicant.prior_positions` | past LA + UTA positions |
| `applicant.prior_la_terms` / `applicant.prior_uta_terms` | past LA / UTA positions |
| `applicant.recommendation_count` | number of recommendations |
| `applicant.avg_recommendation` | average recommendation strength (1-5) |
| `course.grade_points` | grade points (0-4) in this slot's course |
| `application.preference_rank` | the applicant's rank for this course |

New fields are added in `ta_assignment/rules/fields.py`. Profiles are
validated when loaded: unknown rule types, fields, grades or keys are errors.
