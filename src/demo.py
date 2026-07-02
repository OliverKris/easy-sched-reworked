"""Quick sanity check: for each section, print each applicant's eligibility
and (if eligible) their score for LA and UTA. Run with:
    python -m src.demo
"""

from .enums import PositionType
from .scoring import EligibilityConfig, check_eligibility, DefaultScoringStrategy
from .csp_solver import CSPSolver, SolverConfig
from .test_data import load_demo_data

def print_eligibility_matrix(sections, applicants, apps_by_id, elig_config, scorer):
    for section in sections:
        print(f"\n=== {section.section_id} ===")
        print(f"  Needs: {section.position_requirements.la_count} LA, "
              f"{section.position_requirements.uta_count} UTA")
        for applicant in applicants.values():
            application = apps_by_id.get(applicant.applicant_id)
            if application is None:
                continue
            gpa = applicant.overall_gpa
            gpa_str = f"{gpa:.2f}" if gpa is not None else "N/A"
            for position in (PositionType.LA, PositionType.UTA):
                result = check_eligibility(applicant, application, section, position, elig_config)
                if result.eligible:
                    score = scorer.score(applicant, application, section, position)
                    print(f"  [OK] {applicant.name:16s} (GPA {gpa_str}) as {position.name:3s}  score={score:.2f}")
                else:
                    reasons = "; ".join(result.reasons)
                    print(f"  [--] {applicant.name:16s} (GPA {gpa_str}) as {position.name:3s}  ineligible: {reasons}")

def main():
    courses, sections, applicants, applications = load_demo_data()
    apps_by_id = {a.applicant_id: a for a in applications}


    # Admin sets a 3.0 GPA floor overall, with a stricter 3.3 floor for UTAs.
    elig_config = EligibilityConfig(min_gpa=3.0, min_gpa_uta=3.3)
    scorer = DefaultScoringStrategy()

    print("############ ELIGIBILITY + SCORING (GPA threshold applied) ############")
    print_eligibility_matrix(sections, applicants, apps_by_id, elig_config, scorer)

    print("\n\n############ CSP SOLVER: OPTIMAL ASSIGNMENT ############")
    solver = CSPSolver(
        applicants, applications, sections,
        config=SolverConfig(eligibility=elig_config, scorer=scorer),
    )
    result = solver.solve()
    print(result)
 
 
if __name__ == "__main__":
    main()