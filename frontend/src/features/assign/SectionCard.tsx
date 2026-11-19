import { useState } from "react";
import { Code } from "../../design/components";
import { LockIcon } from "../../design/icons";
import type { SolvedSlot } from "../../types";
import { shortUnfilledReason, type CourseGroup } from "./model";

interface Props {
    course: CourseGroup;
    visible: (slot: SolvedSlot) => boolean;
    selectedId: string | null;
    onSelect: (slotId: string) => void;
}

export function CourseCard({ course, visible, selectedId, onSelect }: Props) {
    const sections = course.sections
        .map((s) => ({ ...s, slots: s.slots.filter(visible) }))
        .filter((s) => s.slots.length > 0);
    if (sections.length === 0) return null;

    return (
        <div className="bg-surface border border-line rounded-lg shadow-sm overflow-hidden">
            <div className="flex justify-between items-center gap-3 px-4 py-2.5 border-b border-line-soft bg-line-soft/40">
                <h2 className="m-0 text-sm font-semibold">
                    <Code>{course.courseId}</Code> <span className="font-normal text-ink-3">{course.title}</span>
                </h2>
                <span className="flex items-center gap-2 text-xs text-ink-3 tabular-nums">
                    {course.filled} of {course.total} filled
                    <span aria-hidden="true" className="w-14 h-1 rounded-full bg-line overflow-hidden">
                        <span
                            className={`block h-full rounded-full transition-[width] duration-500 ease-out ${course.filled === course.total ? "bg-accent" : "bg-warn-line"}`}
                            style={{ width: `${course.total ? (course.filled / course.total) * 100 : 0}%` }}
                        />
                    </span>
                </span>
            </div>
            {sections.map((section) => (
                <div key={section.sectionId} className="flex flex-wrap gap-x-4 gap-y-2.5 px-4 py-3 border-b border-line-soft last:border-b-0">
                    <div className="flex-[0_0_160px] flex flex-col">
                        <span className="font-medium">{section.label}</span>
                        <span className="text-xs text-ink-3">{section.when}</span>
                    </div>
                    <div className="flex-[1_1_360px] min-w-0 flex flex-wrap gap-2">
                        {section.slots.map((slot) => (
                            <SlotChip
                                key={slot.slot_id}
                                slot={slot}
                                selected={slot.slot_id === selectedId}
                                onSelect={() => onSelect(slot.slot_id)}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}

function SlotChip({ slot, selected, onSelect }: { slot: SolvedSlot; selected: boolean; onSelect: () => void }) {
    const empty = !slot.applicant_id;
    // When a re-solve puts someone new in this slot, flash it so the change is visible.
    const [seen, setSeen] = useState(slot.applicant_id);
    const [flash, setFlash] = useState(0);
    if (seen !== slot.applicant_id) {
        setSeen(slot.applicant_id);
        setFlash((n) => n + 1);
    }
    const look = selected
        ? "bg-accent-tint border-accent ring-3 ring-accent/20"
        : empty
            ? "bg-warn-tint border-dashed border-warn-line hover:bg-warn-soft"
            : "bg-surface border-line shadow-sm hover:border-control";

    return (
        <button
            type="button"
            aria-pressed={selected}
            onClick={onSelect}
            className={`relative flex items-center gap-2 min-h-10 px-2.5 py-1.5 rounded-md border text-left cursor-pointer transition-[background-color,border-color,box-shadow] duration-150 ${look}`}
        >
            {flash > 0 && <span key={flash} aria-hidden="true" className="absolute -inset-px rounded-md animate-flash pointer-events-none" />}
            <span className="text-[11px] font-semibold tracking-wide text-ink-3">{slot.position}</span>
            {empty ? (
                <>
                    <span className="font-medium text-warn">Unfilled</span>
                    <span className="text-xs text-ink-3">{shortUnfilledReason(slot)}</span>
                </>
            ) : (
                <>
                    <span className="font-medium text-ink">{slot.applicant_name}</span>
                    <span className="text-xs text-ink-3 tabular-nums">{slot.score?.toFixed(2)}</span>
                    {slot.locked && <LockIcon label="Locked" className="text-ink-2" />}
                </>
            )}
        </button>
    );
}
