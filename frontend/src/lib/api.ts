import type {
    CourseCreate,
    CourseUpdate,
    DatasetKey,
    DatasetResponse,
    EligibilityResponse,
    Lock,
    LockCreate,
    RecommendationsResponse,
    ScoringWeights,
    SectionCreate,
    SectionUpdate,
    SolveResponse,
} from "../types";

// Generic async function for API requests
async function getJSON<T>(url: string): Promise<T> {
    const res = await fetch(url);
    if (!res.ok) {
        throw new Error(`${url} -> ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<T>
}

async function sendJSON<T>(url: string, method: "POST" | "PUT" | "DELETE", body?: unknown): Promise<T | null> {
    const res = await fetch(url, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if(!res.ok) {
        // FastAPI error bodies are {"detail": "..."} -- surface that if present.
        let detail = `${res.status} ${res.statusText}`;
        try {
            const parsed = await res.json()
            if(parsed?.detail) detail = parsed.detail
        } catch {
            // body wasn't JSON; fall back to statusText
        }
        throw new Error(detail);
    }
    if (res.status === 204) return null; // no body
    return res.json() as Promise<T>
}

export function fetchDataset(dataset: DatasetKey): Promise<DatasetResponse> {
    return getJSON(`/api/dataset?dataset=${dataset}`);
}

export function fetchEligibility(
    dataset: DatasetKey,
    minGpa?: number | null,
    minGpaUta?: number | null,
): Promise<EligibilityResponse> {
    const params = new URLSearchParams({ dataset });
    if (minGpa !== null && minGpa !== undefined) params.set("min_gpa", String(minGpa));
    if (minGpaUta !== null && minGpaUta !== undefined) params.set("min_gpa_uta", String(minGpaUta));
    return getJSON(`/api/eligibility?${params.toString()}`);
}

export interface SolveParams {
    dataset: DatasetKey,
    minGpa?: number | null;
    minGpaUta?: number | null;
    weights: ScoringWeights;
}

export async function runSolve(params: SolveParams): Promise<SolveResponse> {
    const res = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            dataset: params.dataset,
            min_gpa: params.minGpa ?? null,
            min_gpa_uta: params.minGpaUta ?? null,
            weights: params.weights,
        }),
    });
    if (!res.ok) {
        throw new Error(`/api/solve -> ${res.status} ${res.statusText}`);
    }
    return res.json();
}

// Locks / Blocks

export function fetchLocks(dataset: DatasetKey): Promise<{ locks: Lock[] }> {
    return getJSON(`/api/locks?dataset=${dataset}`);
}

export function createLock(dataset: DatasetKey, payload: LockCreate): Promise<Lock> {
    return sendJSON<Lock>(`/api/locks?dataset=${dataset}`, "POST", payload) as Promise<Lock>;
}

export function deleteLock(dataset: DatasetKey, lockId: number): Promise<null> {
    return sendJSON<null>(`/api/locks/${lockId}?dataset=${dataset}`, "DELETE");
}

// Recommendations

export function fetchRecommendations(
    dataset: DatasetKey,
    sectionId: string,
    position: "LA" | "UTA",
    limit = 5,
    minGpa?: number | null,
    minGpaUta?: number | null,
): Promise<RecommendationsResponse> {
    const params = new URLSearchParams({
        dataset, section_id: sectionId, position, limit: String(limit),
    });
    if (minGpa !== null && minGpa !== undefined) params.set("min_gpa", String(minGpa));
    if (minGpaUta !== null && minGpaUta !== undefined) params.set("min_gpa_uta", String(minGpaUta));
    return getJSON(`/api/recommendations?${params.toString()}`);
}

// Course / Section CRUD

export function createCourse(dataset: DatasetKey, payload: CourseCreate) {
    return sendJSON(`/api/courses?dataset=${dataset}`, "POST", payload);
}

export function updateCourse(dataset: DatasetKey, courseId: string, payload: CourseUpdate) {
    return sendJSON(`/api/courses/${encodeURIComponent(courseId)}?dataset=${dataset}`, "PUT", payload);
}

export function deleteCourse(dataset: DatasetKey, courseId: string) {
    return sendJSON(`/api/courses/${encodeURIComponent(courseId)}?dataset=${dataset}`, "DELETE");
}

export function createSection(dataset: DatasetKey, payload: SectionCreate) {
    return sendJSON(`/api/sections?dataset=${dataset}`, "POST", payload);
}

export function updateSection(dataset: DatasetKey, sectionDbId: number, payload: SectionUpdate) {
    return sendJSON(`/api/sections/${sectionDbId}?dataset=${dataset}`, "PUT", payload);
}

export function deleteSection(dataset: DatasetKey, sectionDbId: number) {
    return sendJSON(`/api/sections/${sectionDbId}?dataset=${dataset}`, "DELETE");
}