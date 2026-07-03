import { useEffect, useState } from "react";
import type { DatasetKey, EligibilityRow, SectionSummary } from "../types";
import { fetchEligibility } from "../lib/api";
import { EmptyState, Stamp } from "./ui";

interface Props {
    dataset: DatasetKey;
    sections: SectionSummary[]
}

export function EligibilityView({ dataset, sections }: Props) {
    const [sectionId, setSectionId] = useState<string>(sections[0]?.section_id ?? "");
    const [minGpa, setMinGpa] = useState<string>("");
    const [minGpaUta, setMinGpaUta] = useState<string>("");
    const [rows, setRows] = useState<EligibilityRow[]>([]);
    const [loading, setLoading] = useState(false);

    // keep the selected section valid when the dataset changes
    useEffect(() => {
        if (sections.length && !sections.some((s) => s.section_id === sectionId)) {
            // Syncing selection to the new dataset's selection list, not app state.
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setSectionId(sections[0].section_id);
        }
    }, [sections, sectionId])

    useEffect(() => {
        let cancelled = false;
        // Flip the spinner on before the async eligibility fetch starts.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLoading(true);
        fetchEligibility(
            dataset,
            minGpa === "" ? null : Number(minGpa),
            minGpaUta === "" ? null : Number(minGpaUta),
        )
            .then((res) => {
                if (!cancelled) setRows(res.rows);
            })
            .finally(() => !cancelled && setLoading(false));
        return () => {
            cancelled = true;
        };
    }, [dataset, minGpa, minGpaUta]);

    const row = rows.find((r) => r.section_id === sectionId) ?? rows[0];
    
    return (
        <div>
            <h2 className="font-display text-xl font-semibold mt-1 mb-1">Eligibility Ledger</h2>
            <p className="text-ink-soft text-[13px] mb-5">
                Pick a section to see, for every applicant, whether they clear the hard constraints — and their score if so.
            </p>
        
            {/* Eligibility filtering */}
            <div className="flex gap-6 flex-wrap bg-paper-raised border border-line rounded-md px-5 py-4 mb-5">
                {/* Section select */}
                <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-ink-soft uppercase tracking-wide">Section</label>
                    <select 
                        name="sectionSelect" 
                        value={sectionId}
                        onChange={(e) => setSectionId(e.target.value)}
                        className="font-mono text-[13px] px-2 py-1.5 border border-line rounded-[3px] w-64"
                    >
                        {sections.map((s) => (
                            <option key={s.section_id} value={s.section_id}>{s.section_id}</option>
                        ))}
                    </select>
                </div>

                <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-ink-soft uppercase tracking-wide">Min GPA (overall)</label>
                    <input 
                        type="number" step="0.1" placeholder="none"
                        value={minGpa} onChange={(e) => setMinGpa(e.target.value)}
                        className="font-mono text-[13px] px-2 py-1.5 border border-line rounded-[3px] w-28"
                    />
                </div>
                <div className="flex flex-col gap-1">
                    <label className="text-[11px] text-ink-soft uppercase tracking-wide">Min GPA (UTA)</label>
                    <input
                        type="number" step="0.1" placeholder="none"
                        value={minGpaUta} onChange={(e) => setMinGpaUta(e.target.value)}
                        className="font-mono text-[13px] px-2 py-1.5 border border-line rounded-[3px] w-28"
                    />
                </div>
            </div>

            {loading && <EmptyState>Loading...</EmptyState>}
            {!loading && !row && <EmptyState>No sections available.</EmptyState>}
            {/* Applicant table */}
            {!loading && row && (
                <table className="w-full border-collapse text-[13px]">
                    <thead>
                        <tr>
                            {["Applicant", "Position", "Status", "Score"].map((h) => (
                                <th key={h} className="text-left font-mono text-[10.5px] uppercase tracking-wide text-ink-soft border-b border-ink px-2.5 py-2">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {row.cells.map((c, i) => (
                            <tr key={`${c.applicant_id}-${c.position}-${i}`} className="hover:bg-applicant-hover">
                                <td className="px-2.5 py-2 border-b border-line align-top">
                                    {c.applicant_name} <span className="text-ink-soft text-[11px]">({c.applicant_id})</span>
                                </td>
                                <td className="px-2.5 py-2 border-b border-line align-top">{c.position}</td>
                                <td className="px-2.5 py-2 border-b border-line align-top">
                                    <Stamp ok={c.eligible}>{c.eligible ? "ELIGIBLE" : "INELIGIBLE"}</Stamp>
                                    {!c.eligible &&
                                        <div className="text-[11.5px] text-brick mt-0.5">{c.reasons.join(" · ")}</div>
                                    }
                                </td>
                                <td className="px-2.5 py-2 border-b border-line align-top">
                                    {c.score !== null ? c.score.toFixed(2) : "-"}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
}