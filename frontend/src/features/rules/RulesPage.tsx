import { useState } from "react";
import { useWorkspaceActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Button, Hint, PageHeader, Panel } from "../../design/components";
import { DEFAULT_WEIGHTS, type ScoringWeights, type ServerSettings } from "../../types";

const WEIGHTS: { key: keyof ScoringWeights; label: string; hint: string }[] = [
    { key: "grade_weight", label: "Grade in the course", hint: "" },
    { key: "preference_weight", label: "Applicant's preference", hint: "1st choice scores highest" },
    { key: "experience_weight", label: "Teaching experience", hint: "any course, more for the same one" },
    { key: "recommendation_weight", label: "Recommendations", hint: "average strength" },
    { key: "skill_match_weight", label: "Skill match", hint: "course skill tags" },
    { key: "uta_readiness_bonus", label: "UTA readiness bonus", hint: "2+ terms as an LA" },
];

const DEFAULTS: ServerSettings = { min_gpa: 3.0, min_gpa_uta: 3.3, weights: DEFAULT_WEIGHTS };

function parseGpa(text: string): number | null | "invalid" {
    const t = text.trim();
    if (t === "") return null;
    const n = Number(t);
    return Number.isFinite(n) && n >= 0 && n <= 4 ? n : "invalid";
}

/** Rule settings for the open workspace: eligibility floors and fit weights. */
export function RulesPage() {
    const { current } = useWorkspace();
    if (!current) return null;
    // Re-mount the form when the workspace changes so it starts from that workspace's settings.
    return <RulesForm key={current.id} />;
}

function RulesForm() {
    const { current } = useWorkspace();
    const actions = useWorkspaceActions();
    const saved = current!.settings;
    const [minGpa, setMinGpa] = useState(saved.min_gpa?.toString() ?? "");
    const [minGpaUta, setMinGpaUta] = useState(saved.min_gpa_uta?.toString() ?? "");
    const [weights, setWeights] = useState<ScoringWeights>({ ...DEFAULT_WEIGHTS, ...saved.weights });
    const [message, setMessage] = useState<string | null>(null);

    const la = parseGpa(minGpa);
    const uta = parseGpa(minGpaUta);
    const invalid = la === "invalid" || uta === "invalid";
    const draft: ServerSettings | null = invalid ? null : { min_gpa: la as number | null, min_gpa_uta: uta as number | null, weights };
    const dirty = !current!.setup.rules || JSON.stringify(draft) !== JSON.stringify({ ...saved, weights: { ...DEFAULT_WEIGHTS, ...saved.weights } });

    const save = async () => {
        if (!draft) return;
        setMessage(null);
        await actions.saveSettings.mutateAsync({ id: current!.id, settings: draft });
        setMessage("Saved. The next assignment run uses these rules.");
    };

    const loadDefaults = () => {
        setMinGpa(String(DEFAULTS.min_gpa));
        setMinGpaUta(String(DEFAULTS.min_gpa_uta));
        setWeights(DEFAULTS.weights);
    };

    return (
        <div className="max-w-5xl flex flex-col gap-6">
            <PageHeader
                title="Rules"
                description="Who can be assigned, and what makes one eligible person a better fit than another."
                actions={<>
                    <Button onClick={loadDefaults}>Use recommended defaults</Button>
                    <Button variant="primary" onClick={save} disabled={!draft || !dirty || actions.saveSettings.isPending}>
                        Save rules
                    </Button>
                </>}
            />

            <Hint id="rules-intro">
                Besides these, applicants must have passed the course and be free for at least one of its labs (and
                its lecture, when a section requires it).
            </Hint>

            {message && !dirty && <p role="status" className="m-0 text-[13px] text-accent">{message}</p>}
            {actions.saveSettings.error && <p role="alert" className="m-0 text-[13px] text-danger">{actions.saveSettings.error.message}</p>}

            <div className="flex flex-wrap gap-6 items-start">
                <Panel className="flex-[1_1_320px] min-w-0">
                    <div className="px-5 py-4 border-b border-line">
                        <h2 className="m-0 text-[15px] font-semibold">Who can be assigned</h2>
                        <p className="m-0 mt-1 text-[13px] text-ink-3">Leave a field empty for no minimum.</p>
                    </div>
                    <div className="px-5 py-4 flex flex-col gap-4">
                        <GpaField id="gpa-la" label="Minimum GPA for Learning Assistants" value={minGpa} onChange={setMinGpa} invalid={la === "invalid"} />
                        <GpaField id="gpa-uta" label="Minimum GPA for Undergraduate TAs" value={minGpaUta} onChange={setMinGpaUta} invalid={uta === "invalid"} />
                    </div>
                </Panel>

                <Panel className="flex-[1_1_380px] min-w-0">
                    <div className="px-5 py-4 border-b border-line">
                        <h2 className="m-0 text-[15px] font-semibold">What makes a good fit</h2>
                        <p className="m-0 mt-1 text-[13px] text-ink-3">Higher weight means that factor counts for more when placing people.</p>
                    </div>
                    <div className="px-5 py-2">
                        {WEIGHTS.map((w) => (
                            <label key={w.key} className="flex flex-col gap-1.5 py-3 border-b border-line-soft last:border-b-0">
                                <span className="flex justify-between gap-3">
                                    <span><span className="font-medium">{w.label}</span> <span className="text-xs text-ink-3">{w.hint}</span></span>
                                    <span className="tabular-nums font-medium">{weights[w.key].toFixed(1)}</span>
                                </span>
                                <input
                                    type="range" min={0} max={5} step={0.5}
                                    value={weights[w.key]}
                                    onChange={(e) => setWeights({ ...weights, [w.key]: Number(e.target.value) })}
                                    className="w-full accent-accent"
                                />
                            </label>
                        ))}
                    </div>
                </Panel>
            </div>
        </div>
    );
}

function GpaField({ id, label, value, onChange, invalid }: {
    id: string; label: string; value: string; onChange: (v: string) => void; invalid: boolean;
}) {
    return (
        <div className="flex flex-col gap-1.5">
            <label htmlFor={id} className="font-medium">{label}</label>
            <input
                id={id}
                inputMode="decimal"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder="No minimum"
                aria-invalid={invalid}
                aria-describedby={invalid ? `${id}-err` : undefined}
                className={`w-40 min-h-10 px-3 rounded-md border bg-surface text-ink tabular-nums ${invalid ? "border-danger" : "border-control"}`}
            />
            {invalid && <span id={`${id}-err`} className="text-xs text-danger">Enter a number from 0 to 4.</span>}
        </div>
    );
}
