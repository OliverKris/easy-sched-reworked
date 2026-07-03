import { useState } from "react";
import type { DatasetKey, ScoringWeights, SolveResponse } from "../types";
import { DEFAULT_WEIGHTS } from "../types";
import { runSolve } from "../lib/api";
import { EmptyState } from "./ui";

const WEIGHT_FIELDS: { key: keyof ScoringWeights; label: string }[] = [
    { key: "grade_weight", label: "Grade weight" },
    { key: "experience_weight", label: "Experience weight" },
    { key: "recommendation_weight", label: "Recommendation weight" },
    { key: "preference_weight", label: "Preference weight" },
    { key: "skill_match_weight", label: "Skill match weight" },
    { key: "uta_readiness_bonus", label: "UTA readiness bonus" },
]

export function SolverView({ dataset }: { dataset: DatasetKey }) {
    const [minGpa, setMinGpa] = useState("")
    const [minGpaUta, setMinGpaUta] = useState("");
    const [weights, setWeights] = useState<ScoringWeights>(DEFAULT_WEIGHTS);
    const [result, setResult] = useState<SolveResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    function setWeight(key: keyof ScoringWeights, value: string) {
        setWeights((w) => ({ ...w, [key]: value === "" ? 0 : Number(value) }));
    }

    async function handleSolve() {
        setLoading(true);
        setError(null);
        try {
            const res = await runSolve({
                dataset,
                minGpa: minGpa === "" ? null : Number(minGpa),
                minGpaUta: minGpaUta === "" ? null : Number(minGpaUta),
                weights,
            });
            setResult(res);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Solve failed");
        } finally {
            setLoading(false)
        }
    }

    return (
        <div>
            <h2 className="font-display text-xl font-semibold mt-1 mb-1">Run the Solver</h2>
            <p className="text-ink-soft text-[13px] mb-5">
                Set eligibility floors and scoring weights, then solve for the optimal (max-score) assignment.
            </p>

            {/* Solver params - gpa */}
            <div className="flex gap-6 flex-wrap bg-paper-raised border border-line rounded-md px-5 py-4 mb-5">
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

            {/* Solver params - weights */}
            <div className="grid grid-cols-3 gap-x-6 gap-y-3.5 mb-4">
                {WEIGHT_FIELDS.map((f) => (
                    <div key={f.key} className="flex flex-col gap-1">
                        <label className="text-[11px] text-ink-soft uppercase tracking-wide">{f.label}</label>
                        <input 
                            type="number" step="0.1"
                            value={weights[f.key]}
                            onChange={(e) => setWeight(f.key, e.target.value)}
                            className="font-mono text-[13px] px-2 py-1.5 border border-line rounded-[3px] w-28"
                        />
                    </div>
                ))}
            </div>
            
            {/* Solve btn */}
            <button
                onClick={handleSolve}
                disabled={loading}
                className="bg-forest hover:bg-forest-hover text-white font-semibold text-[13px] rounded px-5 py-2.5 disabled:opacity-60"
            >
                {loading ? "Solving..." : "Slove assignment"}
            </button>

            <div className="mt-6">
                {error && <div className="text-brick text-[13px">{error}</div>}
                {!error && !result && <EmptyState>Run the solver to see the results here.</EmptyState>}
                {result && (
                    <>
                        {/* Solver result metadata */}
                        <div className="flex gap-5 font-mono text-[12.5px] mb-3.5">
                            <div className="bg-forest-soft text-forest px-3 py-1.5 rounded">
                                <b>Total score</b> {result.total_score}
                            </div>
                            <div className="bg-forest-soft text-forest px-3 py-1.5 rounded">
                                <b>Nodes explored</b> {result.nodes_explored}
                            </div>
                            <div className="bg-forest-soft text-forest px-3 py-1.5 rounded">
                                <b>{result.optimal ? "Optimal ✓" : "Node limit hit - best found"}</b>
                            </div>
                        </div>

                        {/* Solver result */}
                        <table className="w-full border-collapse text-[13px]">
                            <thead>
                                <tr>
                                    {["Applicant", "Section", "Position", "Score"].map((h) => (
                                        <th key={h} className="text-left font-mono text-[10.5[x] uppercase tracking-wide text-ink-soft border-b border-ink px-2.5 py-2">
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            {/* Assignments */}
                            <tbody>
                                {result.assignments.length === 0 && (
                                    <tr><td colSpan={4}><EmptyState>No assignments made.</EmptyState></td></tr>
                                )}
                                {result.assignments.map((a, i) => (
                                    <tr key={i} className="hover:bg-applicant-hover">
                                        <td className="px-2.5 py-2 border-b border-line">{a.applicant_name} ({a.applicant_id})</td>
                                        <td className="px-2.5 py-2 border-b border-line">{a.section_id}</td>
                                        <td className="px-2.5 py-2 border-b border-line">{a.position}</td>
                                        <td className="px-2.5 py-2 border-b border-line">{a.score.toFixed(2)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        {/* Unfilled slots */}
                        {result.unfilled_slots.length > 0 && (
                            <div className="mt-4">
                                <div className="text-[11px] uppercase tracking-wide text-ink-soft mb-1.5">
                                    Unfilled slots ({result.unfilled_slots.length})
                                </div>
                                <ul className="font-mono text-xs text-brick list-non pl-0 space-y-0.5">
                                    {result.unfilled_slots.map((s, i) => (
                                        <li key={i}>{s}</li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}