import type {
    DatasetKey,
    DatasetResponse,
    EligibilityResponse,
    ScoringWeights,
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