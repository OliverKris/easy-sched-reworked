import { useMemo, useState } from "react";
import { useDataset, useLocks, useSolve } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Badge, Button, Spinner, VisuallyHidden } from "../../design/components";
import { AlertIcon, CheckIcon } from "../../design/icons";
import type { SolvedSlot } from "../../types";
import { CourseCard } from "./SectionCard";
import { SlotPanel } from "./SlotPanel";
import { groupSlots, matchesFilter, resolveSelection, type Selection, type SlotFilter } from "./model";

const fmtGpa = (v: number | null) => (v == null ? "any" : v.toFixed(1));

export function AssignPage() {
    const { dataset, settings } = useWorkspace();
    const datasetQuery = useDataset(dataset);
    const locksQuery = useLocks(dataset);
    const solveQuery = useSolve(dataset, settings);

    const [filter, setFilter] = useState<SlotFilter>("all");
    const [search, setSearch] = useState("");
    const [selection, setSelection] = useState<Selection | null>(null);

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
        <div className="flex flex-col gap-5 max-w-[1240px]">
            <header className="flex flex-wrap justify-between items-center gap-4">
                <div className="flex flex-col gap-1.5">
                    <h1 className="m-0 text-[26px] font-semibold tracking-tight">Assignments</h1>
                    {result && (
                        <div className="flex flex-wrap items-center gap-2.5 text-[13px] text-ink-2">
                            {result.optimal ? (
                                <Badge tone="accent"><CheckIcon />Best possible under your rules</Badge>
                            ) : (
                                <Badge tone="warn"><AlertIcon size={12} />Search stopped early; may not be the best</Badge>
                            )}
                            <span>Solved in {result.elapsed_ms < 1 ? "<1" : Math.round(result.elapsed_ms)} ms</span>
                            <span aria-hidden="true">·</span>
                            <span><span className="font-semibold tabular-nums">{result.filled}</span> of {result.total_slots} slots filled</span>
                            <span aria-hidden="true">·</span>
                            <span>{locked} locked</span>
                        </div>
                    )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {solveQuery.isFetching && <Spinner label="Solving" />}
                    <Button variant="primary" disabled={solveQuery.isFetching} onClick={() => solveQuery.refetch()}>
                        Re-run, keep locks
                    </Button>
                </div>
            </header>

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

            {result && (
                <>
                    <div className="flex flex-wrap gap-2 items-center">
                        <label className="flex-[1_1_260px] max-w-90 flex">
                            <VisuallyHidden>Search sections or people</VisuallyHidden>
                            <input
                                type="search"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search sections or people"
                                className="flex-1 min-h-9 px-2.5 rounded-md border border-control bg-surface text-ink"
                            />
                        </label>
                        {([
                            ["all", "All"],
                            ["unfilled", `Unfilled · ${unfilled}`],
                            ["locked", `Locked · ${locked}`],
                        ] as const).map(([key, label]) => (
                            <button
                                key={key}
                                type="button"
                                aria-pressed={filter === key}
                                onClick={() => setFilter(key)}
                                className={
                                    "min-h-9 px-3 rounded-full border text-[13px] cursor-pointer " +
                                    (filter === key ? "bg-ink text-white border-ink" : "bg-surface text-ink border-control hover:bg-canvas")
                                }
                            >
                                {label}
                            </button>
                        ))}
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
