export type DatasetKey = "demo" | "extended";

export interface LabMeeting {
    lab_id: string;
    meetings: string[];
}

export interface SectionSummary {
    section_id: string;
    course_id: string;
    title: string;
    instructor: string;
    term: string;
    year: number;
    la_count: number;
    uta_count: number;
    uta_must_attend_lecture: boolean;
    la_must_attend_lecture: boolean;
    lecture_meetings: string[];
    labs: LabMeeting[];
}

export interface RankedPreference {
    course_id: string;
    rank: number;
}

export interface ApplicantSummary {
    applicant_id: string;
    name: string;
    email: string;
    gpa: number | null;
    skills: string[];
    past_courses: string[];
    teaching_experience: string[];
    recommendations: string[];
    position_types: string[];
    ranked_preferences: RankedPreference[];
}

export interface DatasetResponse {
    dataset: string;
    sections: SectionSummary[];
    applicants: ApplicantSummary[];
}

export interface EligibilityCell {
    applicant_id: string;
    applicant_name: string;
    position: "LA" | "UTA";
    eligible: boolean;
    reasons: string[];
    score: number | null;
}

export interface EligibilityRow {
    section_id: string;
    cells: EligibilityCell[];
}

export interface EligibilityResponse {
    dataset: string;
    rows: EligibilityRow[];
}

export interface ScoringWeights {
    grade_weight: number;
    experience_weight: number;
    recommendation_weight: number;
    preference_weight: number;
    skill_match_weight: number;
    uta_readiness_bonus: number;
}

export const DEFAULT_WEIGHTS: ScoringWeights = {
    grade_weight: 3.0,
    experience_weight: 2.5,
    recommendation_weight: 2.0,
    preference_weight: 2.5,
    skill_match_weight: 1.0,
    uta_readiness_bonus: 1.5,
};

export interface Assignment {
    applicant_id: string;
    applicant_name: string;
    section_id: string;
    position: "LA" | "UTA";
    score: number;
}

export interface SolveResponse {
    dataset: string;
    total_score: number;
    nodes_explored: number;
    optimal: boolean;
    assignments: Assignment[];
    unfilled_slots: string[];
}
