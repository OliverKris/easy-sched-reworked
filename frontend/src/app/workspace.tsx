import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { listWorkspaces } from "../lib/api";
import type { ScoringWeights, WorkspaceSummary } from "../types";

/**
 * Which of this browser's workspaces is open. The list comes from the server
 * (workspaces belong to this browser's client id); only the choice of which
 * one is open is remembered locally.
 */
export interface RuleSettings {
    minGpa: number | null;
    minGpaUta: number | null;
    weights: ScoringWeights;
}

interface WorkspaceValue {
    status: "loading" | "error" | "empty" | "ready";
    error: Error | null;
    workspaces: WorkspaceSummary[];
    current: WorkspaceSummary | null;
    /** The open workspace's id, used as the `dataset` key on data requests. */
    dataset: string;
    settings: RuleSettings;
    open: (id: string) => void;
}

const STORAGE_KEY = "easy-sched.workspace";

function readStored(): string | null {
    try {
        return window.localStorage.getItem(STORAGE_KEY);
    } catch {
        return null;
    }
}

// eslint-disable-next-line react-refresh/only-export-components
export const workspacesKey = ["workspaces"] as const;

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
    const [chosenId, setChosenId] = useState<string | null>(readStored);
    const query = useQuery({ queryKey: workspacesKey, queryFn: () => listWorkspaces().then((r) => r.workspaces) });

    const value = useMemo<WorkspaceValue>(() => {
        const workspaces = query.data ?? [];
        const current = workspaces.find((w) => w.id === chosenId) ?? workspaces[0] ?? null;
        const s = current?.settings;
        return {
            status: query.isPending ? "loading" : query.isError ? "error" : workspaces.length === 0 ? "empty" : "ready",
            error: query.error,
            workspaces,
            current,
            dataset: current?.id ?? "",
            settings: {
                minGpa: s?.min_gpa ?? null,
                minGpaUta: s?.min_gpa_uta ?? null,
                weights: s?.weights ?? {
                    grade_weight: 3, experience_weight: 2.5, recommendation_weight: 2,
                    preference_weight: 2.5, skill_match_weight: 1, uta_readiness_bonus: 1.5,
                },
            },
            open: (id: string) => {
                setChosenId(id);
                try { window.localStorage.setItem(STORAGE_KEY, id); } catch { /* storage unavailable */ }
            },
        };
    }, [query.data, query.isPending, query.isError, query.error, chosenId]);

    return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace(): WorkspaceValue {
    const ctx = useContext(WorkspaceContext);
    if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
    return ctx;
}
