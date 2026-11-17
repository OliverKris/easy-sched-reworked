import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createLock, deleteLock, fetchDataset, fetchLocks, runSolve } from "../lib/api";
import type { RuleSettings } from "../app/workspace";
import type { DatasetKey, LockCreate, SolverKind } from "../types";

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
    return useQuery({ queryKey: keys.dataset(dataset), queryFn: () => fetchDataset(dataset) });
}

export function useLocks(dataset: DatasetKey) {
    return useQuery({
        queryKey: keys.locks(dataset),
        queryFn: () => fetchLocks(dataset).then((r) => r.locks),
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
        placeholderData: (previous) => previous, // keep the old board on screen while re-solving
    });
}

export function useLockActions(dataset: DatasetKey) {
    const qc = useQueryClient();
    const refresh = () => Promise.all([
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
