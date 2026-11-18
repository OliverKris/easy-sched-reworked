import type { Day, GradeName, Term, TimeSlotJ } from "../types";

/* Converting between stored meetings (one TimeSlot per day) and the patterns
   people think in ("MW 11:10–12:25"), plus display labels. */

export const DAYS: Day[] = ["MON", "TUE", "WED", "THU", "FRI"];
export const DAY_LETTER: Record<Day, string> = { MON: "M", TUE: "T", WED: "W", THU: "R", FRI: "F" };
export const DAY_NAME: Record<Day, string> = { MON: "Monday", TUE: "Tuesday", WED: "Wednesday", THU: "Thursday", FRI: "Friday" };

export const TERMS: { value: Term; label: string }[] = [
    { value: "FALL", label: "Fall" },
    { value: "SPRING", label: "Spring" },
];
export const termLabel = (t: Term) => (t === "FALL" ? "Fall" : "Spring");

export const GRADES: { value: GradeName; label: string }[] = [
    { value: "A", label: "A" }, { value: "A_MINUS", label: "A−" }, { value: "B_PLUS", label: "B+" },
    { value: "B", label: "B" }, { value: "B_MINUS", label: "B−" }, { value: "C_PLUS", label: "C+" },
    { value: "C", label: "C" }, { value: "C_MINUS", label: "C−" }, { value: "D_PLUS", label: "D+" },
    { value: "D", label: "D" }, { value: "D_MINUS", label: "D−" }, { value: "F", label: "F" },
    { value: "IN_PROGRESS", label: "In progress" },
];
export const gradeLabel = (g: GradeName) => GRADES.find((x) => x.value === g)?.label ?? g;

/** One row in a meeting editor: the same time on several days. */
export interface MeetingPattern {
    days: Day[];
    start: string;
    end: string;
}

export function toPatterns(slots: TimeSlotJ[]): MeetingPattern[] {
    const groups = new Map<string, MeetingPattern>();
    for (const s of slots) {
        const key = `${s.start}-${s.end}`;
        const g = groups.get(key) ?? { days: [], start: s.start, end: s.end };
        if (!g.days.includes(s.day)) g.days.push(s.day);
        groups.set(key, g);
    }
    return [...groups.values()].map((g) => ({ ...g, days: DAYS.filter((d) => g.days.includes(d)) }));
}

export function fromPatterns(patterns: MeetingPattern[], label: string): TimeSlotJ[] {
    return patterns.flatMap((p) => p.days.map((day) => ({ day, start: p.start, end: p.end, label })));
}

function clock(hhmm: string): string {
    const [h, m] = hhmm.split(":").map(Number);
    const suffix = h >= 12 ? "pm" : "am";
    const h12 = h % 12 === 0 ? 12 : h % 12;
    return `${h12}:${String(m).padStart(2, "0")}${suffix}`;
}

export function formatPattern(p: MeetingPattern): string {
    return `${p.days.map((d) => DAY_LETTER[d]).join("")} ${clock(p.start)}–${clock(p.end)}`;
}

export function formatMeetings(slots: TimeSlotJ[]): string {
    const patterns = toPatterns(slots);
    return patterns.length ? patterns.map(formatPattern).join(", ") : "—";
}

/** Problems a meeting pattern row has, for inline messages before saving. */
export function patternProblem(p: MeetingPattern): string | null {
    if (p.days.length === 0) return "Pick at least one day";
    if (!p.start || !p.end) return "Set a start and end time";
    if (p.end <= p.start) return "Ends before it starts";
    return null;
}
