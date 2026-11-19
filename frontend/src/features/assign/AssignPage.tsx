import { useEffect, useMemo, useRef, useState } from "react";
import { useDataset, useLocks, useSolve, useWorkspaceActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Badge, Button, EmptyState, Hint, Kbd, Spinner, VisuallyHidden } from "../../design/components";
import { useToast } from "../../design/toast";
import { ButtonLink } from "../../design/links";
import { fetchScheduleCsv } from "../../lib/api";
import { downloadText, safeFilename } from "../../lib/workspaceFile";
import { AlertIcon, CheckIcon } from "../../design/icons";
import type { SolvedSlot } from "../../types";
import { CourseCard } from "./SectionCard";
import { SlotPanel } from "./SlotPanel";
import { groupSlots, matchesFilter, resolveSelection, type Selection, type SlotFilter } from "./model";

const fmtGpa = (v: number | null) => (v == null ? "any" : v.toFixed(1));

export function AssignPage() {
    const { dataset, settings, current } = useWorkspace();
    const wsActions = useWorkspaceActions();
    const datasetQuery = useDataset(dataset);
    const locksQuery = useLocks(dataset);
    const solveQuery = useSolve(dataset, settings);

    const [filter, setFilter] = useState<SlotFilter>("all");
    const [search, setSearch] = useState("");
    const [selection, setSelection] = useState<Selection | null>(null);
    const toast = useToast();
    const searchRef = useRef<HTMLInputElement>(null);

    // "/" jumps to search, like most professional tools.
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            const t = e.target as HTMLElement;
            if (e.key !== "/" || e.metaKey || e.ctrlKey || t.closest("input, textarea, select, [contenteditable]")) return;
            e.preventDefault();
            searchRef.current?.focus();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, []);

    const result = solveQuery.data;
    const slots = useMemo(() => result?.slots ?? [], [result]);
    const courses = useMemo(
        () => groupSlots(slots, datasetQuery.data?.sections ?? []),
        [slots, datasetQuery.data],
    );

    // Defaults to the first gap; follows the selected person across re-solves.
    const selected: SolvedSlot | undefined = resolveSelection(slots, selection);
    const select = (slotId: string) => {
        const slot = slots.find((s) => s.slot_id === slotId);
        setSelection({ slotId, applicantId: slot?.applicant_id ?? null });
    };

    const unfilled = slots.filter((s) => !s.applicant_id).length;
    const locked = slots.filter((s) => s.locked).length;
    const visible = (s: SolvedSlot) => matchesFilter(s, filter, search.trim());

    const error = solveQuery.error ?? datasetQuery.error ?? locksQuery.error;

    return (
        <div className="flex flex-col gap-5">
            <header className="flex flex-wrap justify-between items-end gap-4 pb-5 border-b border-line">
                <div className="flex flex-col gap-2">
                    <h1 className="m-0 text-[22px] leading-tight font-semibold">Assignments</h1>
                    {result && (
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[13px] text-ink-3">
                            {result.optimal ? (
                                <Badge tone="accent"><CheckIcon />Best possible under your rules</Badge>
                            ) : (
                                <Badge tone="warn"><AlertIcon size={12} />Search stopped early; may not be the best</Badge>
                            )}
                            <span className="flex items-center gap-2">
                                <span aria-hidden="true" className="w-24 h-1.5 rounded-full bg-line overflow-hidden">
                                    <span
                                        className="block h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
                                        style={{ width: `${result.total_slots ? (result.filled / result.total_slots) * 100 : 0}%` }}
                                    />
                                </span>
                                <span><span className="font-semibold text-ink tabular-nums">{result.filled}</span> of {result.total_slots} filled</span>
                            </span>
                            <span aria-hidden="true">·</span>
                            <span className="tabular-nums">{locked} locked</span>
                            <span aria-hidden="true">·</span>
                            <span className="tabular-nums">{result.elapsed_ms < 1 ? "<1" : Math.round(result.elapsed_ms)} ms</span>
                        </div>
                    )}
                </div>
                {result && result.total_slots > 0 && (
                    <div className="flex flex-wrap items-center gap-2">
                        {solveQuery.isFetching && <Spinner label="Solving" />}
                        <Button disabled={solveQuery.isFetching} onClick={() => solveQuery.refetch()}>
                            Re-run, keep locks
                        </Button>
                        <Button
                            variant="primary"
                            disabled={wsActions.finalize.isPending || result.filled === 0}
                            onClick={() => current && wsActions.finalize.mutate(current.id, {
                                onSuccess: () => toast({ message: "Schedule marked final. Download it any time from this page." }),
                            })}
                        >
                            {current?.finalized_at ? "Update final schedule" : "Mark as final"}
                        </Button>
                    </div>
                )}
            </header>

            {current?.finalized_at && (
                <div className="flex flex-wrap items-center gap-3 px-4 py-2.5 rounded-lg border border-line bg-surface shadow-sm text-[13px] animate-fade">
                    <Badge tone="accent"><CheckIcon />Final</Badge>
                    <span className="text-ink-2">
                        Marked final {new Date(current.finalized_at).toLocaleString()}. Changes you make after this aren't in the
                        final schedule until you update it.
                    </span>
                    <span className="flex gap-2 ml-auto">
                        <Button size="sm" onClick={async () => downloadText(
                            `${safeFilename(current.name)}-schedule.csv`, await fetchScheduleCsv(current.id), "text/csv")}>
                            Download CSV
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => wsActions.unfinalize.mutate(current.id, {
                            onSuccess: () => toast({ message: "Final mark removed", tone: "neutral" }),
                        })}>Unmark</Button>
                    </span>
                </div>
            )}
            {wsActions.finalize.error && (
                <p role="alert" className="m-0 text-[13px] text-danger">{wsActions.finalize.error.message}</p>
            )}

            <p className="m-0 text-[13px] text-ink-3">
                Rules: GPA at least {fmtGpa(settings.minGpa)} for LAs and {fmtGpa(settings.minGpaUta ?? settings.minGpa)} for UTAs,
                must have passed the course and be free for a lab. Locks and blocks are always respected.
            </p>

            {error && (
                <p role="alert" className="m-0 px-4 py-3 rounded-lg bg-danger-soft text-danger">
                    Couldn't load assignments ({error.message}). Is the backend running on port 8000?
                </p>
            )}

            {result && result.lock_conflicts.length > 0 && (
                <div role="alert" className="px-4 py-3 rounded-lg bg-warn-soft text-warn text-[13px]">
                    <strong className="font-semibold">Some locks couldn't all be honoured:</strong>{" "}
                    {result.lock_conflicts.join("; ")}
                </div>
            )}

            {!result && !error && <Spinner label="Solving" />}

            {result && result.total_slots === 0 && (
                <EmptyState
                    title="Nothing to assign yet"
                    action={<ButtonLink to="/start" variant="primary">Back to Getting started</ButtonLink>}
                >
                    Assignments appear here once the workspace has sections that need LAs or UTAs and
                    applicants who applied for them.
                </EmptyState>
            )}

            {result && result.total_slots > 0 && (
                <Hint id="assign-intro">
                    Click any slot to see why that person was placed there and who else could take it. Lock people in or
                    keep them out, and the board re-solves around your choices.
                </Hint>
            )}

            {result && result.total_slots > 0 && (
                <>
                    <div className="flex flex-wrap gap-2 items-center">
                        <label className="relative flex-[1_1_260px] max-w-90 flex">
                            <VisuallyHidden>Search sections or people</VisuallyHidden>
                            <svg aria-hidden="true" width="14" height="14" viewBox="0 0 16 16" className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none">
                                <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
                                <path d="m10.5 10.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                            </svg>
                            <input
                                ref={searchRef}
                                type="search"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                onKeyDown={(e) => { if (e.key === "Escape") { setSearch(""); e.currentTarget.blur(); } }}
                                placeholder="Search sections or people"
                                className="flex-1 h-9 pl-8 pr-9 rounded-md border border-control bg-surface text-ink shadow-sm focus:outline-none focus:border-accent focus:ring-3 focus:ring-accent/20"
                            />
                            <span className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none"><Kbd>/</Kbd></span>
                        </label>
                        <div role="group" aria-label="Show" className="inline-flex p-0.5 rounded-md bg-line-soft border border-line">
                            {([
                                ["all", "All", null],
                                ["unfilled", "Unfilled", unfilled],
                                ["locked", "Locked", locked],
                            ] as const).map(([key, label, count]) => (
                                <button
                                    key={key}
                                    type="button"
                                    aria-pressed={filter === key}
                                    onClick={() => setFilter(key)}
                                    className={
                                        "h-8 px-3 inline-flex items-center gap-1.5 rounded text-[13px] cursor-pointer transition-all duration-150 " +
                                        (filter === key ? "bg-surface text-ink font-medium shadow-sm" : "text-ink-3 hover:text-ink")
                                    }
                                >
                                    {label}
                                    {count !== null && (
                                        <span className={`text-[11px] tabular-nums px-1 rounded ${key === "unfilled" && count > 0 ? "text-warn" : ""}`}>{count}</span>
                                    )}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-5 items-start">
                        <section aria-label="Sections" className="flex-[999_1_520px] min-w-0 flex flex-col gap-4">
                            {courses.map((course) => (
                                <CourseCard
                                    key={course.courseId}
                                    course={course}
                                    visible={visible}
                                    selectedId={selected?.slot_id ?? null}
                                    onSelect={select}
                                />
                            ))}
                            {slots.length > 0 && !slots.some(visible) && (
                                <p className="m-0 text-ink-3">No slots match.</p>
                            )}
                        </section>

                        {selected && (
                            <SlotPanel
                                key={selected.slot_id}
                                slot={selected}
                                locks={locksQuery.data ?? []}
                                applicants={datasetQuery.data?.applicants ?? []}
                            />
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
