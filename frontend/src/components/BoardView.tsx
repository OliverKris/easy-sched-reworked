import { useEffect, useMemo, useState } from "react";
import {
    DndContext,
    DragOverlay,
    PointerSensor,
    useDraggable,
    useDroppable,
    useSensor,
    useSensors,
    type DragEndEvent,
    type DragStartEvent,
} from "@dnd-kit/core";
import type {
    ApplicantSummary,
    DatasetKey,
    EligibilityResponse,
    Lock,
    RecommendationCandidate,
    SectionSummary,
} from "../types";
import {
    createLock,
    deleteLock,
    fetchEligibility,
    fetchLocks,
    fetchRecommendations,
} from "../lib/api";
import { EmptyState, IdChip, Stamp } from "./ui";

type Position = "LA" | "UTA";
type FocusedSlot = { sectionId: string; position: Position } | null;

interface Props {
    dataset: DatasetKey;
    sections: SectionSummary[];
    applicants: ApplicantSummary[];
}

function slotDroppableId(sectionId: string, position: Position) {
    return `${sectionId}::${position}`;
}

export function BoardView({ dataset, sections, applicants }: Props) {
    const [locks, setLocks] = useState<Lock[]>([]);
    const [eligibility, setEligibility] = useState<EligibilityResponse | null>(null);
    const [focused, setFocused] = useState<FocusedSlot>(null);
    const [search, setSearch] = useState("");
    const [activeId, setActiveId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [recsFor, setRecsFor] = useState<{ sectionId: string; position: Position } | null>(null);
    const [recs, setRecs] = useState<RecommendationCandidate[] | null>(null);
    const [recsLoading, setRecsLoading] = useState(false);

    const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }));

    async function refreshLocks() {
        const res = await fetchLocks(dataset);
        setLocks(res.locks);
    }

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setError(null);
        refreshLocks().catch((e) => setError(e instanceof Error ? e.message : "Failed to load locks"));
        fetchEligibility(dataset).then(setEligibility).catch(() => setEligibility(null));
        setFocused(null);
        setRecsFor(null);
        setRecs(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dataset]);

    const applicantsById = useMemo(
        () => Object.fromEntries(applicants.map((a) => [a.applicant_id, a])),
        [applicants],
    );

    // Anyone LOCKED into any slot is unavailable everywhere else -- one
    // position per person, matching the solver's own rule.
    const lockedElsewhere = useMemo(
        () => new Set(locks.filter((l) => l.lock_type === "locked").map((l) => l.applicant_id)),
        [locks],
    );

    function locksFor(sectionId: string, position: Position) {
        return locks.filter((l) => l.section_id === sectionId && l.position === position);
    }

    function eligibilityFor(sectionId: string, position: Position) {
        const row = eligibility?.rows.find((r) => r.section_id === sectionId);
        return row ? row.cells.filter((c) => c.position === position) : [];
    }

    async function lockApplicant(applicantId: string, sectionId: string, position: Position) {
        setError(null);
        try {
            await createLock(dataset, { applicant_id: applicantId, section_id: sectionId, position, lock_type: "locked" });
            await refreshLocks();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Couldn't create lock");
        }
    }

    async function blockApplicant(applicantId: string, sectionId: string, position: Position) {
        setError(null);
        try {
            await createLock(dataset, { applicant_id: applicantId, section_id: sectionId, position, lock_type: "blocked" });
            await refreshLocks();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Couldn't create block");
        }
    }

    async function removeLock(lockId: number) {
        setError(null);
        try {
            await deleteLock(dataset, lockId);
            await refreshLocks();
        } catch (e) {
            setError(e instanceof Error ? e.message : "Couldn't remove");
        }
    }

    async function openRecommendations(sectionId: string, position: Position) {
        setRecsFor({ sectionId, position });
        setRecs(null);
        setRecsLoading(true);
        try {
            const res = await fetchRecommendations(dataset, sectionId, position, 5);
            setRecs(res.recommendations);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Couldn't load recommendations");
        } finally {
            setRecsLoading(false);
        }
    }

    function handleDragStart(e: DragStartEvent) {
        setActiveId(String(e.active.id));
    }

    async function handleDragEnd(e: DragEndEvent) {
        setActiveId(null);
        const { active, over } = e;
        if (!over) return;
        const [sectionId, position] = String(over.id).split("::") as [string, Position];
        await lockApplicant(String(active.id), sectionId, position);
    }

    const filteredApplicants = applicants
        .filter((a) => a.name.toLowerCase().includes(search.toLowerCase()) || a.applicant_id.includes(search))
        .sort((a, b) => {
            if (!focused) return a.name.localeCompare(b.name);
            const cells = eligibilityFor(focused.sectionId, focused.position);
            const scoreA = cells.find((c) => c.applicant_id === a.applicant_id)?.score ?? -1;
            const scoreB = cells.find((c) => c.applicant_id === b.applicant_id)?.score ?? -1;
            return scoreB - scoreA;
        });

    return (
        <div>
            <h2 className="font-display text-xl font-semibold mt-1 mb-1">Assignment Board</h2>
            <p className="text-ink-soft text-[13px] mb-5">
                Drag an applicant onto an open slot to lock them in. Click a slot to focus it and see
                eligibility/score for everyone in the sidebar, or hit "Suggest" for a ranked shortlist.
            </p>

            {error && <div className="text-brick text-[13px] mb-3">{error}</div>}

            <DndContext sensors={sensors} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
                <div className="flex gap-6 items-start">
                    {/* Sections */}
                    <div className="flex-1 min-w-0">
                        {sections.map((section) => (
                            <div key={section.section_id} className="bg-paper-raised border border-line rounded-md px-4.5 py-4 mb-3">
                                <div className="flex items-baseline justify-between mb-2.5">
                                    <div>
                                        <span className="font-mono text-xs bg-brass-soft text-brass rounded px-1.5 py-0.5 mr-2">
                                            {section.course_id}
                                        </span>
                                        <span className="font-medium text-[13.5px]">{section.title}</span>
                                        <span className="text-[11px] text-ink-soft ml-2">{section.section_id}</span>
                                    </div>
                                    <span className="text-[11px] text-ink-soft">{section.instructor}</span>
                                </div>

                                <div className="flex gap-6">
                                    <SlotGroup
                                        label="LA" count={section.la_count} sectionId={section.section_id}
                                        locks={locksFor(section.section_id, "LA")}
                                        applicantsById={applicantsById}
                                        onFocus={() => setFocused({ sectionId: section.section_id, position: "LA" })}
                                        onUnlock={removeLock}
                                        onSuggest={() => { setFocused({ sectionId: section.section_id, position: "LA" }); openRecommendations(section.section_id, "LA"); }}
                                    />
                                    <SlotGroup
                                        label="UTA" count={section.uta_count} sectionId={section.section_id}
                                        locks={locksFor(section.section_id, "UTA")}
                                        applicantsById={applicantsById}
                                        onFocus={() => setFocused({ sectionId: section.section_id, position: "UTA" })}
                                        onUnlock={removeLock}
                                        onSuggest={() => { setFocused({ sectionId: section.section_id, position: "UTA" }); openRecommendations(section.section_id, "UTA"); }}
                                    />
                                </div>

                                {recsFor?.sectionId === section.section_id && (
                                    <RecommendationsPanel
                                        position={recsFor.position}
                                        loading={recsLoading}
                                        recs={recs}
                                        onLock={(applicantId) => {
                                            lockApplicant(applicantId, section.section_id, recsFor.position);
                                            setRecsFor(null);
                                        }}
                                        onClose={() => setRecsFor(null)}
                                    />
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Applicant sidebar */}
                    <div className="w-72 shrink-0 sticky top-4">
                        <input
                            type="text" placeholder="Search applicants..."
                            value={search} onChange={(e) => setSearch(e.target.value)}
                            className="w-full font-mono text-[13px] px-2.5 py-1.5 border border-line rounded-[3px] mb-2.5"
                        />
                        {focused && (
                            <div className="text-[11px] text-ink-soft mb-2 flex items-center justify-between">
                                <span>
                                    Focused: <span className="text-brass font-mono">{focused.sectionId} - {focused.position}</span>
                                </span>
                                <button onClick={() => setFocused(null)} className="text-ink-soft hover:text-ink underline">
                                    clear
                                </button>
                            </div>
                        )}
                        <div className="max-h-[70vh] overflow-y-auto pr-1">
                            {filteredApplicants.length === 0 && <EmptyState>No applicants match.</EmptyState>}
                            {filteredApplicants.map((a) => {
                                const cell = focused
                                    ? eligibilityFor(focused.sectionId, focused.position).find((c) => c.applicant_id === a.applicant_id)
                                    : undefined;
                                const isLockedElsewhere = lockedElsewhere.has(a.applicant_id);
                                const isBlockedHere = focused
                                    ? locksFor(focused.sectionId, focused.position).some(
                                          (l) => l.lock_type === "blocked" && l.applicant_id === a.applicant_id,
                                      )
                                    : false;
                                return (
                                    <ApplicantCard
                                        key={a.applicant_id}
                                        applicant={a}
                                        disabled={isLockedElsewhere}
                                        eligibilityCell={cell}
                                        blocked={isBlockedHere}
                                        focused={focused}
                                        onBlock={() => focused && blockApplicant(a.applicant_id, focused.sectionId, focused.position)}
                                    />
                                );
                            })}
                        </div>
                    </div>
                </div>

                <DragOverlay>
                    {activeId && applicantsById[activeId] && (
                        <div className="bg-paper-raised border border-forest rounded-md px-3 py-2 shadow-lg text-[13px] font-medium">
                            {applicantsById[activeId].name}
                        </div>
                    )}
                </DragOverlay>
            </DndContext>
        </div>
    );
}

// ---------------------------------------------------------------------------

function SlotGroup({
    label, count, sectionId, locks, applicantsById, onFocus, onUnlock, onSuggest,
}: {
    label: Position; count: number; sectionId: string; locks: Lock[];
    applicantsById: Record<string, ApplicantSummary>;
    onFocus: () => void; onUnlock: (lockId: number) => void; onSuggest: () => void;
}) {
    const lockedList = locks.filter((l) => l.lock_type === "locked");
    const openCount = Math.max(count - lockedList.length, 0);
    const { setNodeRef, isOver } = useDroppable({ id: slotDroppableId(sectionId, label), disabled: openCount === 0 });

    if (count === 0) return null;

    return (
        <div className="flex-1">
            <div className="flex items-center justify-between mb-1">
                <span className="text-[10.5px] uppercase tracking-wide text-ink-soft font-mono">
                    {label} ({lockedList.length}/{count})
                </span>
                {openCount > 0 && (
                    <button onClick={onSuggest} className="text-[10.5px] text-brass hover:underline">
                        Suggest
                    </button>
                )}
            </div>
            <div ref={setNodeRef} className={`flex flex-col gap-1.5 min-h-9 rounded-md p-1 ${isOver ? "bg-forest-soft" : ""}`}>
                {lockedList.map((l) => (
                    <div key={l.id} className="flex items-center justify-between bg-forest-soft text-forest text-[12.5px] rounded px-2 py-1">
                        <span>{applicantsById[l.applicant_id]?.name ?? l.applicant_id}</span>
                        <button onClick={() => onUnlock(l.id)} className="text-forest/70 hover:text-brick ml-2" title="Unlock">
                            remove
                        </button>
                    </div>
                ))}
                {Array.from({ length: openCount }).map((_, i) => (
                    <button
                        key={i} onClick={onFocus}
                        className="border border-dashed border-line rounded px-2 py-1 text-[11.5px] text-ink-soft text-left hover:border-brass hover:text-brass"
                    >
                        open slot -- drop here or click to focus
                    </button>
                ))}
            </div>
        </div>
    );
}

function ApplicantCard({
    applicant, disabled, eligibilityCell, blocked, focused, onBlock,
}: {
    applicant: ApplicantSummary; disabled: boolean;
    eligibilityCell?: { eligible: boolean; reasons: string[]; score: number | null };
    blocked: boolean; focused: FocusedSlot; onBlock: () => void;
}) {
    const { attributes, listeners, setNodeRef, transform } = useDraggable({
        id: applicant.applicant_id, disabled: disabled || blocked,
    });
    const style = transform ? { transform: `translate(${transform.x}px, ${transform.y}px)` } : undefined;

    return (
        <div
            ref={setNodeRef} style={style} {...listeners} {...attributes}
            className={`border border-line rounded-md px-2.5 py-2 mb-1.5 bg-paper-raised ${
                disabled || blocked ? "opacity-50 cursor-not-allowed" : "cursor-grab hover:border-brass"
            }`}
            title={disabled ? "Already locked into another slot" : blocked ? "Blocked from this slot" : "Drag onto a slot to lock"}
        >
            <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium">{applicant.name}</span>
                <IdChip>{applicant.applicant_id}</IdChip>
            </div>
            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                {applicant.gpa !== null && <span className="text-[11px] font-mono text-ink-soft">GPA {applicant.gpa}</span>}
                {focused && eligibilityCell && (
                    <Stamp ok={eligibilityCell.eligible}>
                        {eligibilityCell.eligible ? `score ${eligibilityCell.score?.toFixed(2)}` : "ineligible"}
                    </Stamp>
                )}
                {blocked && <Stamp ok={false}>blocked here</Stamp>}
            </div>
            {focused && eligibilityCell && !eligibilityCell.eligible && eligibilityCell.reasons.length > 0 && (
                <div className="text-[10.5px] text-ink-soft mt-1">{eligibilityCell.reasons.join("; ")}</div>
            )}
            {focused && !blocked && (
                <button
                    onPointerDown={(e) => e.stopPropagation()}
                    onClick={onBlock}
                    className="text-[10.5px] text-brick hover:underline mt-1"
                >
                    Block from this slot
                </button>
            )}
        </div>
    );
}

function RecommendationsPanel({
    position, loading, recs, onLock, onClose,
}: {
    position: Position; loading: boolean; recs: RecommendationCandidate[] | null;
    onLock: (applicantId: string) => void; onClose: () => void;
}) {
    return (
        <div className="mt-3 border border-brass rounded-md px-3 py-2.5 bg-brass-soft/40">
            <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] uppercase tracking-wide text-brass font-mono">
                    Top picks -- {position}
                </span>
                <button onClick={onClose} className="text-ink-soft hover:text-ink text-[11px]">close</button>
            </div>
            {loading && <div className="text-[12.5px] text-ink-soft">Loading...</div>}
            {!loading && recs && recs.length === 0 && (
                <div className="text-[12.5px] text-ink-soft">No eligible, unlocked candidates left for this slot.</div>
            )}
            {!loading && recs && recs.map((r) => (
                <div key={r.applicant_id} className="flex items-center justify-between text-[12.5px] py-1">
                    <span>
                        {r.applicant_name} <span className="text-ink-soft font-mono text-[11px]">
                            {r.gpa !== null ? `GPA ${r.gpa} - ` : ""}score {r.score.toFixed(2)}
                        </span>
                    </span>
                    <button
                        onClick={() => onLock(r.applicant_id)}
                        className="bg-forest hover:bg-forest-hover text-white text-[11px] rounded px-2 py-1"
                    >
                        Lock in
                    </button>
                </div>
            ))}
        </div>
    );
}
