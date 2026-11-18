import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
    createLock, createWorkspace, deleteLock, deleteWorkspace, fetchDataset, fetchLocks, finalizeSchedule,
    importAsNewWorkspace, importIntoWorkspace, renameWorkspace, resetWorkspace, runSolve, saveSettings,
    unfinalizeSchedule,
} from "../lib/api";
import { workspacesKey, type RuleSettings } from "../app/workspace";
import type { DatasetKey, LockCreate, ServerSettings, SolverKind, WorkspacePart } from "../types";

/**
 * Server state lives in TanStack Query: one key per resource, and mutations
 * invalidate the keys they affect, so the board re-solves after a lock changes
 * without any screen wiring that up by hand.
 */
export const keys = {
    dataset: (d: DatasetKey) => ["dataset", d] as const,
    locks: (d: DatasetKey) => ["locks", d] as const,
    solveAll: (d: DatasetKey) => ["solve", d] as const,
    solve: (d: DatasetKey, s: RuleSettings, solver: SolverKind) => ["solve", d, s, solver] as const,
};

export function useDataset(dataset: DatasetKey) {
    return useQuery({ queryKey: keys.dataset(dataset), queryFn: () => fetchDataset(dataset), enabled: Boolean(dataset) });
}

export function useLocks(dataset: DatasetKey) {
    return useQuery({
        queryKey: keys.locks(dataset),
        queryFn: () => fetchLocks(dataset).then((r) => r.locks),
        enabled: Boolean(dataset),
    });
}

/** Solving is read-only on the server, so it's a query: cached per settings, re-run with refetch(). */
export function useSolve(dataset: DatasetKey, settings: RuleSettings, solver: SolverKind = "matching") {
    return useQuery({
        queryKey: keys.solve(dataset, settings, solver),
        queryFn: () => runSolve({
            dataset,
            minGpa: settings.minGpa,
            minGpaUta: settings.minGpaUta,
            weights: settings.weights,
            solver,
        }),
        // Keep the old board on screen while re-solving the same workspace (not another one).
        placeholderData: (previous, previousQuery) =>
            previousQuery?.queryKey[1] === dataset ? previous : undefined,
        enabled: Boolean(dataset),
    });
}

export function useLockActions(dataset: DatasetKey) {
    const qc = useQueryClient();
    const refresh = () => Promise.all([
        qc.invalidateQueries({ queryKey: workspacesKey }),
        qc.invalidateQueries({ queryKey: keys.locks(dataset) }),
        qc.invalidateQueries({ queryKey: keys.solveAll(dataset) }),
    ]);

    const add = useMutation({
        mutationFn: (payload: LockCreate) => createLock(dataset, payload),
        onSuccess: refresh,
    });
    const remove = useMutation({
        mutationFn: (lockId: number) => deleteLock(dataset, lockId),
        onSuccess: refresh,
    });
    return { add, remove, pending: add.isPending || remove.isPending, error: add.error ?? remove.error };
}

// --- Workspaces --------------------------------------------------------------

/**
 * Mutations on workspaces. Each refreshes the workspace list (setup status,
 * counts) and anything that depends on the workspace's data or settings.
 */
export function useWorkspaceActions() {
    const qc = useQueryClient();
    const refreshAll = (id?: string) => Promise.all([
        qc.invalidateQueries({ queryKey: workspacesKey }),
        ...(id ? [
            qc.invalidateQueries({ queryKey: keys.dataset(id) }),
            qc.invalidateQueries({ queryKey: keys.locks(id) }),
            qc.invalidateQueries({ queryKey: keys.solveAll(id) }),
        ] : []),
    ]);

    return {
        create: useMutation({
            mutationFn: (v: { name: string; sample?: "extended" | "demo" }) => createWorkspace(v.name, v.sample),
            onSuccess: () => refreshAll(),
        }),
        rename: useMutation({
            mutationFn: (v: { id: string; name: string }) => renameWorkspace(v.id, v.name),
            onSuccess: () => refreshAll(),
        }),
        remove: useMutation({
            mutationFn: (id: string) => deleteWorkspace(id),
            onSuccess: () => refreshAll(),
        }),
        reset: useMutation({
            mutationFn: (id: string) => resetWorkspace(id),
            onSuccess: (_d, id) => refreshAll(id),
        }),
        saveSettings: useMutation({
            mutationFn: (v: { id: string; settings: ServerSettings }) => saveSettings(v.id, v.settings),
            onSuccess: (_d, v) => refreshAll(v.id),
        }),
        finalize: useMutation({
            mutationFn: (id: string) => finalizeSchedule(id),
            onSuccess: () => refreshAll(),
        }),
        unfinalize: useMutation({
            mutationFn: (id: string) => unfinalizeSchedule(id),
            onSuccess: () => refreshAll(),
        }),
        importNew: useMutation({
            mutationFn: (v: { bundle: unknown; parts?: WorkspacePart[] }) => importAsNewWorkspace(v.bundle, v.parts),
            onSuccess: () => refreshAll(),
        }),
        importInto: useMutation({
            mutationFn: (v: { id: string; bundle: unknown; parts?: WorkspacePart[] }) =>
                importIntoWorkspace(v.id, v.bundle, v.parts),
            onSuccess: (_d, v) => refreshAll(v.id),
        }),
    };
}
