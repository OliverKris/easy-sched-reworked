import { useLockActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Button, Code, ScoreBar } from "../../design/components";
import { LockIcon } from "../../design/icons";
import type { ApplicantSummary, Lock, SolvedSlot } from "../../types";
import { findLock, ordinal, sectionLabel, shortSection } from "./model";

interface Props {
    slot: SolvedSlot;
    locks: Lock[];
    applicants: ApplicantSummary[];
}

/** Everything about one slot: who is there and why, who else could be, and the controls to change it. */
export function SlotPanel({ slot, locks, applicants }: Props) {
    const { dataset } = useWorkspace();
    const actions = useLockActions(dataset);
    const names = new Map(applicants.map((a) => [a.applicant_id, a.name]));
    const lockedSomewhere = new Set(locks.filter((l) => l.lock_type === "locked").map((l) => l.applicant_id));
    const keptOut = locks.filter((l) =>
        l.lock_type === "blocked" && l.section_id === slot.section_id && l.position === slot.position);

    const aid = slot.applicant_id;
    const lock = aid ? findLock(locks, aid, slot.section_id, slot.position, "locked") : undefined;
    const maxPoints = Math.max(0.01, ...slot.breakdown.map((b) => b.points));

    const place = (applicantId: string, lockType: "locked" | "blocked") =>
        actions.add.mutate({ applicant_id: applicantId, section_id: slot.section_id, position: slot.position, lock_type: lockType });

    return (
        <aside
            aria-labelledby="slot-panel-title"
            className="flex-[1_1_340px] min-w-0 max-w-105 bg-surface border border-line rounded-lg self-start lg:sticky lg:top-6"
        >
            <div className="px-5 py-4 border-b border-line flex flex-col gap-1">
                <span className="text-xs text-ink-3">
                    <Code>{shortSection(slot.section_id)}</Code> · {sectionLabel(slot.section_id)} · {slot.position}
                </span>
                <h2 id="slot-panel-title" className="m-0 text-lg font-semibold flex items-center gap-2">
                    {aid ? slot.applicant_name : "Unfilled slot"}
                    {slot.locked && <LockIcon size={14} label="Locked" className="text-ink-2" />}
                </h2>
                {aid && (
                    <span className="text-[13px] text-ink-2">
                        Fit score <span className="font-semibold tabular-nums">{slot.score?.toFixed(2)}</span>
                        {slot.preference_rank && slot.preference_rank <= 3
                            ? ` · their ${ordinal(slot.preference_rank)} choice`
                            : " · not one of their ranked choices"}
                    </span>
                )}
            </div>

            {aid ? (
                <div className="px-5 py-3.5 border-b border-line-soft">
                    <h3 className="m-0 mb-2.5 text-[13px] font-semibold">Why this person fits</h3>
                    <div className="flex flex-col gap-2">
                        {slot.breakdown.map((part) => (
                            <div key={part.id} className="grid grid-cols-[minmax(0,1fr)_96px_44px] items-center gap-2.5 text-[13px]">
                                <span>{part.label}</span>
                                <ScoreBar value={part.points} max={maxPoints} />
                                <span className="text-right tabular-nums">{part.points.toFixed(2)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            ) : (
                <div className="px-5 py-3.5 border-b border-line-soft flex flex-col gap-2">
                    <h3 className="m-0 text-[13px] font-semibold">Why it's empty</h3>
                    <p className="m-0 text-[13px] text-ink-2">{slot.unfilled_reason}</p>
                </div>
            )}

            <div className="px-5 py-3.5 border-b border-line-soft">
                <h3 className="m-0 mb-2.5 text-[13px] font-semibold">
                    {aid ? "Others who could take this slot" : "Eligible people"}
                </h3>
                {slot.alternatives.length === 0 ? (
                    <p className="m-0 text-[13px] text-ink-3">No one else is eligible.</p>
                ) : (
                    <ul className="list-none m-0 p-0 flex flex-col gap-3">
                        {slot.alternatives.map((alt) => (
                            <li key={alt.applicant_id} className="flex items-start gap-3">
                                <div className="flex-1 min-w-0 flex flex-col">
                                    <span className="flex justify-between gap-2">
                                        <span className="font-medium">{alt.applicant_name}</span>
                                        <span className="text-[13px] tabular-nums text-ink-2">{alt.score.toFixed(2)}</span>
                                    </span>
                                    <span className="text-xs text-ink-3">
                                        {alt.placed_in ? `Placed in ${shortSection(alt.placed_in)}` : "Not placed anywhere"}
                                    </span>
                                </div>
                                <Button
                                    size="sm"
                                    disabled={actions.pending || lockedSomewhere.has(alt.applicant_id)}
                                    title={lockedSomewhere.has(alt.applicant_id) ? "Already locked into another slot" : undefined}
                                    onClick={() => place(alt.applicant_id, "locked")}
                                >
                                    Place here
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {slot.ineligible_examples.length > 0 && (
                <div className="px-5 py-3.5 border-b border-line-soft">
                    <h3 className="m-0 mb-2.5 text-[13px] font-semibold">Wanted this course but not eligible</h3>
                    <ul className="list-none m-0 p-0 flex flex-col gap-2">
                        {slot.ineligible_examples.map((ex) => (
                            <li key={ex.applicant_id} className="flex flex-col">
                                <span className="font-medium">{ex.applicant_name}</span>
                                <span className="text-xs text-warn">{ex.reason}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {keptOut.length > 0 && (
                <div className="px-5 py-3.5 border-b border-line-soft">
                    <h3 className="m-0 mb-2.5 text-[13px] font-semibold">Kept out of this slot</h3>
                    <ul className="list-none m-0 p-0 flex flex-col gap-2">
                        {keptOut.map((l) => (
                            <li key={l.id} className="flex items-center justify-between gap-2">
                                <span>{names.get(l.applicant_id) ?? l.applicant_id}</span>
                                <Button size="sm" variant="ghost" disabled={actions.pending} onClick={() => actions.remove.mutate(l.id)}>
                                    Undo
                                </Button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {aid && (
                <div className="px-5 py-3.5 flex flex-wrap gap-2">
                    {lock ? (
                        <Button disabled={actions.pending} onClick={() => actions.remove.mutate(lock.id)}>Unlock</Button>
                    ) : (
                        <Button variant="primary" disabled={actions.pending} onClick={() => place(aid, "locked")}>
                            Lock here
                        </Button>
                    )}
                    <Button variant="ghost" disabled={actions.pending || Boolean(lock)} onClick={() => place(aid, "blocked")}>
                        Keep out of this slot
                    </Button>
                </div>
            )}

            {actions.error && (
                <p role="alert" className="m-0 px-5 pb-4 text-[13px] text-danger">{actions.error.message}</p>
            )}
        </aside>
    );
}
