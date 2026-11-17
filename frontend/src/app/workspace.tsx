import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_WEIGHTS, type DatasetKey, type ScoringWeights } from "../types";

/**
 * The workspace the coordinator is working in (which dataset/term) and the
 * rule settings every solve uses. Lives in context so the sidebar's switcher
 * and every screen agree.
 */
export interface RuleSettings {
    minGpa: number | null;
    minGpaUta: number | null;
    weights: ScoringWeights;
}

interface WorkspaceValue {
    dataset: DatasetKey;
    setDataset: (d: DatasetKey) => void;
    settings: RuleSettings;
    setSettings: (s: RuleSettings) => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const WORKSPACES: { key: DatasetKey; name: string; detail: string }[] = [
    { key: "extended", name: "Fall 2026 sample", detail: "14 applicants, edge cases" },
    { key: "demo", name: "Small demo", detail: "4 applicants" },
];

const DEFAULT_SETTINGS: RuleSettings = { minGpa: 3.0, minGpaUta: 3.3, weights: DEFAULT_WEIGHTS };
const STORAGE_KEY = "easy-sched.workspace";

function readStoredDataset(): DatasetKey {
    try {
        const v = window.localStorage.getItem(STORAGE_KEY);
        return v === "demo" || v === "extended" ? v : "extended";
    } catch {
        return "extended";
    }
}

const WorkspaceContext = createContext<WorkspaceValue | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
    const [dataset, setDatasetState] = useState<DatasetKey>(readStoredDataset);
    const [settings, setSettings] = useState<RuleSettings>(DEFAULT_SETTINGS);

    const value = useMemo<WorkspaceValue>(() => ({
        dataset,
        setDataset: (d) => {
            setDatasetState(d);
            try { window.localStorage.setItem(STORAGE_KEY, d); } catch { /* storage unavailable */ }
        },
        settings,
        setSettings,
    }), [dataset, settings]);

    return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useWorkspace(): WorkspaceValue {
    const ctx = useContext(WorkspaceContext);
    if (!ctx) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
    return ctx;
}
