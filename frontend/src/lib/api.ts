import type {
    ApplicantJ,
    ApplicantRecord,
    CourseCreate,
    CourseJ,
    CourseRecord,
    CsvColumn,
    CsvKind,
    CsvResult,
    SectionJ,
    SectionRecord,
    CourseUpdate,
    DatasetKey,
    DatasetResponse,
    EligibilityResponse,
    ImportResult,
    Lock,
    LockCreate,
    RecommendationsResponse,
    ScoringWeights,
    SectionCreate,
    SectionUpdate,
    ServerSettings,
    SolveResponse,
    SolverKind,
    WorkspaceFile,
    WorkspacePart,
    WorkspaceSummary,
} from "../types";
import { getClientId } from "./clientId";

/**
 * Every request goes through here: it identifies this browser (so the server
 * only shows its own workspaces) and turns FastAPI's {"detail": ...} error
 * bodies into readable Error messages.
 */
async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("X-Client-Id", getClientId());
    if (init.body !== undefined && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

    const res = await fetch(url, { ...init, headers });
    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
            const parsed = await res.json();
            if (typeof parsed?.detail === "string") detail = parsed.detail;
            else if (parsed?.detail) detail = JSON.stringify(parsed.detail);
        } catch {
            // body wasn't JSON; keep the status text
        }
        throw new Error(detail);
    }
    if (res.status === 204) return null as T;
    const type = res.headers.get("Content-Type") ?? "";
    return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const getJSON = <T>(url: string) => request<T>(url);
const sendJSON = <T>(url: string, method: "POST" | "PUT" | "PATCH" | "DELETE", body?: unknown) =>
    request<T>(url, { method, body: body !== undefined ? JSON.stringify(body) : undefined });

const ds = (dataset: DatasetKey) => encodeURIComponent(dataset);

// --- Workspaces ----------------------------------------------------------------

/** Facts about the server, e.g. whether it's a public demo whose storage can reset. */
export function getConfig(): Promise<{ demo_mode: boolean }> {
    return getJSON("/api/config");
}

export function listWorkspaces(): Promise<{ workspaces: WorkspaceSummary[] }> {
    return getJSON("/api/workspaces");
}

export function createWorkspace(name: string, sample?: "extended" | "demo"): Promise<WorkspaceSummary> {
    return sendJSON("/api/workspaces", "POST", { name, sample: sample ?? null });
}

export function renameWorkspace(id: string, name: string): Promise<WorkspaceSummary> {
    return sendJSON(`/api/workspaces/${ds(id)}`, "PATCH", { name });
}

export function deleteWorkspace(id: string): Promise<null> {
    return sendJSON(`/api/workspaces/${ds(id)}`, "DELETE");
}

export function resetWorkspace(id: string): Promise<WorkspaceSummary> {
    return sendJSON(`/api/workspaces/${ds(id)}/reset`, "POST");
}

export function saveSettings(id: string, settings: ServerSettings): Promise<WorkspaceSummary> {
    return sendJSON(`/api/workspaces/${ds(id)}/settings`, "PUT", settings);
}

export function finalizeSchedule(id: string): Promise<WorkspaceSummary> {
    return sendJSON(`/api/workspaces/${ds(id)}/schedule`, "POST");
}

export function unfinalizeSchedule(id: string): Promise<null> {
    return sendJSON(`/api/workspaces/${ds(id)}/schedule`, "DELETE");
}

export function exportWorkspace(id: string, parts?: WorkspacePart[]): Promise<WorkspaceFile> {
    const q = parts && parts.length ? `?parts=${parts.join(",")}` : "";
    return getJSON(`/api/workspaces/${ds(id)}/export${q}`);
}

export function fetchScheduleCsv(id: string): Promise<string> {
    return request<string>(`/api/workspaces/${ds(id)}/schedule.csv`);
}

export function importAsNewWorkspace(bundle: unknown, parts?: WorkspacePart[], name?: string): Promise<ImportResult> {
    return sendJSON("/api/workspaces/import", "POST", { bundle, parts: parts ?? null, name: name ?? null });
}

export function importIntoWorkspace(id: string, bundle: unknown, parts?: WorkspacePart[]): Promise<ImportResult> {
    return sendJSON(`/api/workspaces/${ds(id)}/import`, "POST", { bundle, parts: parts ?? null });
}

// --- Workspace data ------------------------------------------------------------

export function fetchDataset(dataset: DatasetKey): Promise<DatasetResponse> {
    return getJSON(`/api/dataset?dataset=${ds(dataset)}`);
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
    dataset: DatasetKey;
    minGpa?: number | null;
    minGpaUta?: number | null;
    weights: ScoringWeights;
    solver?: SolverKind;
}

export function runSolve(params: SolveParams): Promise<SolveResponse> {
    return sendJSON("/api/solve", "POST", {
        dataset: params.dataset,
        min_gpa: params.minGpa ?? null,
        min_gpa_uta: params.minGpaUta ?? null,
        weights: params.weights,
        solver: params.solver ?? "matching",
    });
}

// --- Locks / blocks ------------------------------------------------------------

export function fetchLocks(dataset: DatasetKey): Promise<{ locks: Lock[] }> {
    return getJSON(`/api/locks?dataset=${ds(dataset)}`);
}

export function createLock(dataset: DatasetKey, payload: LockCreate): Promise<Lock> {
    return sendJSON(`/api/locks?dataset=${ds(dataset)}`, "POST", payload);
}

export function deleteLock(dataset: DatasetKey, lockId: number): Promise<null> {
    return sendJSON(`/api/locks/${lockId}?dataset=${ds(dataset)}`, "DELETE");
}

// --- Recommendations -----------------------------------------------------------

export function fetchRecommendations(
    dataset: DatasetKey,
    sectionId: string,
    position: "LA" | "UTA",
    limit = 5,
    minGpa?: number | null,
    minGpaUta?: number | null,
): Promise<RecommendationsResponse> {
    const params = new URLSearchParams({ dataset, section_id: sectionId, position, limit: String(limit) });
    if (minGpa !== null && minGpa !== undefined) params.set("min_gpa", String(minGpa));
    if (minGpaUta !== null && minGpaUta !== undefined) params.set("min_gpa_uta", String(minGpaUta));
    return getJSON(`/api/recommendations?${params.toString()}`);
}

// --- Course / section CRUD -----------------------------------------------------

export function createCourse(dataset: DatasetKey, payload: CourseCreate) {
    return sendJSON(`/api/courses?dataset=${ds(dataset)}`, "POST", payload);
}

export function updateCourse(dataset: DatasetKey, courseId: string, payload: CourseUpdate) {
    return sendJSON(`/api/courses/${encodeURIComponent(courseId)}?dataset=${ds(dataset)}`, "PUT", payload);
}

export function deleteCourse(dataset: DatasetKey, courseId: string) {
    return sendJSON(`/api/courses/${encodeURIComponent(courseId)}?dataset=${ds(dataset)}`, "DELETE");
}

export function createSection(dataset: DatasetKey, payload: SectionCreate) {
    return sendJSON(`/api/sections?dataset=${ds(dataset)}`, "POST", payload);
}

export function updateSection(dataset: DatasetKey, sectionDbId: number, payload: SectionUpdate) {
    return sendJSON(`/api/sections/${sectionDbId}?dataset=${ds(dataset)}`, "PUT", payload);
}

export function deleteSection(dataset: DatasetKey, sectionDbId: number) {
    return sendJSON(`/api/sections/${sectionDbId}?dataset=${ds(dataset)}`, "DELETE");
}

// --- Editing (workspace-scoped, validated) ---------------------------------------

export function listCourses(ws: string): Promise<{ courses: CourseRecord[] }> {
    return getJSON(`/api/workspaces/${ds(ws)}/courses`);
}

export function saveCourse(ws: string, course: CourseJ): Promise<CourseRecord> {
    return sendJSON(`/api/workspaces/${ds(ws)}/courses/${encodeURIComponent(course.course_id)}`, "PUT", course);
}

export function removeCourse(ws: string, courseId: string): Promise<null> {
    return sendJSON(`/api/workspaces/${ds(ws)}/courses/${encodeURIComponent(courseId)}`, "DELETE");
}

export function addSection(ws: string, section: SectionJ): Promise<SectionRecord> {
    return sendJSON(`/api/workspaces/${ds(ws)}/sections`, "POST", section);
}

export function saveSection(ws: string, id: number, section: SectionJ): Promise<SectionRecord> {
    return sendJSON(`/api/workspaces/${ds(ws)}/sections/${id}`, "PUT", section);
}

export function removeSection(ws: string, id: number): Promise<null> {
    return sendJSON(`/api/workspaces/${ds(ws)}/sections/${id}`, "DELETE");
}

export function listApplicants(ws: string): Promise<{ applicants: ApplicantRecord[] }> {
    return getJSON(`/api/workspaces/${ds(ws)}/applicants`);
}

export function saveApplicant(ws: string, applicant: ApplicantJ): Promise<ApplicantRecord> {
    return sendJSON(`/api/workspaces/${ds(ws)}/applicants/${encodeURIComponent(applicant.applicant_id)}`, "PUT", applicant);
}

export function removeApplicant(ws: string, applicantId: string): Promise<null> {
    return sendJSON(`/api/workspaces/${ds(ws)}/applicants/${encodeURIComponent(applicantId)}`, "DELETE");
}

// --- CSV upload ----------------------------------------------------------------

export function fetchCsvColumns(kind: CsvKind): Promise<{ columns: CsvColumn[] }> {
    return getJSON(`/api/csv/columns/${kind}`);
}

export function uploadCsvRows(
    ws: string, kind: CsvKind, rows: Record<string, string>[], mode: "merge" | "replace", dryRun: boolean,
): Promise<CsvResult> {
    return sendJSON(`/api/workspaces/${ds(ws)}/csv/${kind}`, "POST", { rows, mode, dry_run: dryRun });
}
