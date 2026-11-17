import type { Lock, Position, SectionSummary, SolvedSlot } from "../../types";

/* Pure helpers for the Assign screen: grouping, labels, lock lookups. */

export type SlotFilter = "all" | "unfilled" | "locked";

export interface SectionGroup {
    sectionId: string;
    label: string;          // "Section 10"
    when: string;           // "MW 11:10-12:25 · 2 labs"
    slots: SolvedSlot[];
}

export interface CourseGroup {
    courseId: string;
    title: string;
    filled: number;
    total: number;
    sections: SectionGroup[];
}

/** "CSCI 1012-10 (Fall 2026)" -> "CSCI 1012-10" (also inside "… · UTA") */
export function shortSection(sectionId: string): string {
    return sectionId.replace(/\s*\([^)]*\)/g, "").trim();
}

/** "CSCI 1012-10 (Fall 2026)" -> "Section 10" */
export function sectionLabel(sectionId: string): string {
    const m = shortSection(sectionId).match(/-([^-\s]+)$/);
    return m ? `Section ${m[1]}` : shortSection(sectionId);
}

function describeSection(section: SectionSummary | undefined): string {
    if (!section) return "";
    const lecture = section.lecture_meetings[0] ?? "";
    const labs = section.labs.length;
    const labText = labs === 0 ? "no labs" : labs === 1 ? "1 lab" : `${labs} labs`;
    return [lecture, labText].filter(Boolean).join(" · ");
}

const POSITION_ORDER: Record<Position, number> = { LA: 0, UTA: 1 };

export function groupSlots(slots: SolvedSlot[], sections: SectionSummary[]): CourseGroup[] {
    const sectionInfo = new Map(sections.map((s) => [s.section_id, s]));
    const courses = new Map<string, CourseGroup>();

    for (const slot of slots) {
        const info = sectionInfo.get(slot.section_id);
        let course = courses.get(slot.course_id);
        if (!course) {
            course = { courseId: slot.course_id, title: info?.title ?? "", filled: 0, total: 0, sections: [] };
            courses.set(slot.course_id, course);
        }
        let section = course.sections.find((s) => s.sectionId === slot.section_id);
        if (!section) {
            section = {
                sectionId: slot.section_id,
                label: sectionLabel(slot.section_id),
                when: describeSection(info),
                slots: [],
            };
            course.sections.push(section);
        }
        section.slots.push(slot);
        course.total += 1;
        if (slot.applicant_id) course.filled += 1;
    }

    for (const course of courses.values()) {
        for (const section of course.sections) {
            section.slots.sort((a, b) =>
                POSITION_ORDER[a.position] - POSITION_ORDER[b.position] || a.slot_index - b.slot_index);
        }
    }
    return [...courses.values()].sort((a, b) => a.courseId.localeCompare(b.courseId));
}

export function matchesFilter(slot: SolvedSlot, filter: SlotFilter, query: string): boolean {
    if (filter === "unfilled" && slot.applicant_id) return false;
    if (filter === "locked" && !slot.locked) return false;
    if (!query) return true;
    const q = query.toLowerCase();
    return (
        slot.section_id.toLowerCase().includes(q) ||
        (slot.applicant_name ?? "").toLowerCase().includes(q)
    );
}

export function findLock(locks: Lock[], applicantId: string, sectionId: string, position: Position, type: Lock["lock_type"]) {
    return locks.find((l) =>
        l.applicant_id === applicantId && l.section_id === sectionId && l.position === position && l.lock_type === type);
}

export function ordinal(n: number): string {
    const s = ["th", "st", "nd", "rd"];
    const v = n % 100;
    return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

/** Short reason shown inside an empty slot chip. */
export function shortUnfilledReason(slot: SolvedSlot): string {
    if (slot.alternatives.length > 0) return "eligible people placed elsewhere";
    return slot.failure_counts?.length ? "no one eligible" : "no applicants";
}

/**
 * Which slot to show in the panel. The selection remembers the person as well
 * as the slot, so after a lock or re-solve moves someone to another slot of
 * the same section and role, the panel follows them.
 */
export interface Selection {
    slotId: string;
    applicantId: string | null;
}

export function resolveSelection(slots: SolvedSlot[], sel: Selection | null): SolvedSlot | undefined {
    if (sel) {
        const current = slots.find((s) => s.slot_id === sel.slotId);
        if (sel.applicantId && current?.applicant_id !== sel.applicantId && current) {
            const moved = slots.find((s) =>
                s.applicant_id === sel.applicantId &&
                s.section_id === current.section_id &&
                s.position === current.position);
            if (moved) return moved;
        }
        if (current) return current;
    }
    return slots.find((s) => !s.applicant_id) ?? slots[0];
}
