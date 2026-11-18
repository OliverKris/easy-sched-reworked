/** A workspace id (or one of the shared sample datasets, "demo" / "extended"). */
export type DatasetKey = string;

export type WorkspacePart = "settings" | "courses" | "applicants" | "locks" | "schedule";
export const WORKSPACE_PARTS: WorkspacePart[] = ["settings", "courses", "applicants", "locks", "schedule"];

/** Rule settings as the server stores them. */
export interface ServerSettings {
    min_gpa: number | null;
    min_gpa_uta: number | null;
    weights: ScoringWeights;
}

export interface WorkspaceSummary {
    id: string;
    name: string;
    sample: string | null;
    created_at: string;
    counts: { courses: number; sections: number; applicants: number; locks: number };
    setup: { rules: boolean; courses: boolean; applicants: boolean; schedule: boolean };
    settings: ServerSettings;
    finalized_at: string | null;
}

/** A workspace file (see backend/ta_assignment/db/bundle.py). */
export interface WorkspaceFile {
    format: "easy-sched.workspace";
    version: 1;
    name?: string;
    exported_at?: string;
    settings?: ServerSettings;
    courses?: unknown[];
    sections?: unknown[];
    applicants?: unknown[];
    locks?: unknown[];
    schedule?: { finalized_at: string; assignments: unknown[] };
}

export interface ImportResult {
    workspace: WorkspaceSummary;
    report: { imported: WorkspacePart[]; counts: Record<string, number>; notes: string[] };
}

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

export type Position = "LA" | "UTA";
export type SolverKind = "matching" | "csp";

export interface ScorePart {
    id: string;
    label: string;
    points: number;
}

export interface SlotAlternative {
    applicant_id: string;
    applicant_name: string;
    score: number;
    /** "section_id · LA|UTA" where this person was placed, or null if unplaced. */
    placed_in: string | null;
}

export interface IneligibleExample {
    applicant_id: string;
    applicant_name: string;
    reason: string;
}

/** One slot in a solve result, with everything the Assign screen explains. */
export interface SolvedSlot {
    slot_id: string;
    section_id: string;
    course_id: string;
    position: Position;
    slot_index: number;
    applicant_id: string | null;
    applicant_name: string | null;
    score: number | null;
    locked: boolean;
    preference_rank: number | null;
    breakdown: ScorePart[];
    alternatives: SlotAlternative[];
    ineligible_examples: IneligibleExample[];
    unfilled_reason: string | null;
    failure_counts?: { label: string; count: number }[];
}

export interface SolveResponse {
    dataset: string;
    solver: SolverKind;
    elapsed_ms: number;
    total_score: number;
    nodes_explored: number;
    optimal: boolean;
    filled: number;
    total_slots: number;
    slots: SolvedSlot[];
    assignments: Assignment[];
    unfilled_slots: string[];
    lock_conflicts: string[];
}

// Locks / Blocks

export type LockKind = "locked" | "blocked";

export interface Lock {
    id: number;
    applicant_id: string;
    section_id: string;
    position: "LA" | "UTA";
    lock_type: LockKind;
}

export interface LockCreate {
    applicant_id: string;
    section_id: string;
    position: "LA" | "UTA";
    lock_type: LockKind;
}

// Recommendations

export interface RecommendationCandidate {
    applicant_id: string;
    applicant_name: string;
    gpa: number | null;
    score: number;
}

export interface RecommendationsResponse {
    section_id: string;
    position: "LA" | "UTA";
    recommendations: RecommendationCandidate[];
}

// CRUD payloads

export interface TimeSlotIn {
    day: "MON" | "TUE" | "WED" | "THU" | "FRI" | "SAT" | "SUN";
    start: string; // "HH:MM"
    end: string;   // "HH:MM"
    label?: string;
}

export interface LabIn {
    lab_id: string;
    meetings: TimeSlotIn[];
    capacity?: number | null;
}

export interface CourseCreate {
    course_id: string;
    title: string;
    description?: string;
    skills?: string[];
}

export interface CourseUpdate {
    title?: string | null;
    description?: string | null;
    skills?: string[] | null;
}

export interface SectionCreate {
    course_id: string;
    section_number: string;
    term: "FALL" | "SPRING";
    year: number;
    instructor?: string;
    lecture_meetings?: TimeSlotIn[];
    labs?: LabIn[];
    la_count?: number;
    uta_count?: number;
    la_hours_per_week?: number;
    uta_hours_per_week?: number;
    uta_must_attend_lecture?: boolean;
    la_must_attend_lecture?: boolean;
}

export type SectionUpdate = Partial<Omit<SectionCreate, "course_id">>;
