import type { SectionSummary } from "../types";
import { Card, EmptyState, Pill } from "./ui";

export function SectionsView({ sections }: { sections: SectionSummary[] }) {
    if (!sections.length) return <EmptyState>No sections in this dataset.</EmptyState>
    
    return (
        <div>
            <h2 className="font-display text-xl font-semibold mt-1 mb-1">Open Sections</h2>
            <p className="text-ink-soft text-[13px] mb-5">
                Every section offered this cycle, with its lecture/lab meeting pattern and open LA/UTA slots.
            </p>
            {sections.map((s) => (
                <Card key={s.section_id}>
                    {/* Section title */}
                    <div className="flex justify-between items-baseline mb-2">
                        <h3 className="text-[15px] font-semibold m-0">{s.title}</h3>
                        <span className="font-mono text-xs bg-brass-soft text-brass rounded px-1.5 py-0.5">
                            {s.section_id}
                        </span>
                    </div>
                    {/* Section data  */}
                    <div className="flex gap-4.5 flex-wrap text-[12.5px] text-ink-soft">
                        <span><b className="text-ink font-semibold">Term:</b> {s.term} {s.year}</span>
                        <span><b className="text-ink font-semibold">Instructor:</b> {s.instructor || "-"}</span>
                        <span><b className="text-ink font-semibold">Lecture:</b> {s.lecture_meetings.join(", ") || "-"}</span>
                    </div>
                    {/* Section staff req */}
                    <div className="flex gap-1.5 flex-wrap mt-1.5">
                        <Pill>{s.la_count} LA</Pill>
                        <Pill>{s.uta_count} UTA</Pill>
                        {s.uta_must_attend_lecture && <Pill tone="brick">UTA must attend lecture</Pill>}
                        {s.labs.length === 0 && <Pill tone="brick">No labs defined</Pill>}
                    </div>
                    <div className="text-[12.5px] text-ink-soft mt-1.5">
                        <b className="text-ink font-semibold">Labs:</b>{" "}
                        {s.labs.map((l) => `${l.lab_id} (${l.meetings.join(", ")})`).join(" · ") || "none"}
                    </div>
                </Card>
            ))}
        </div>
    );
}