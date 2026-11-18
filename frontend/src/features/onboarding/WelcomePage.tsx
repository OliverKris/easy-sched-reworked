import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useWorkspaceActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Button } from "../../design/components";
import { Logo } from "../../design/icons";
import { storageIsEphemeral } from "../../lib/clientId";
import { readWorkspaceFile } from "../../lib/workspaceFile";

const STEPS = [
    ["Set your rules", "GPA floors, required courses, schedule conflicts, and what makes a good fit."],
    ["Add courses", "Sections, meeting times, and how many LAs and UTAs each one needs."],
    ["Add applicants", "Transcripts, availability, experience, and ranked course choices."],
    ["Assign", "Get the best possible assignment, see why each person was placed, and adjust it."],
];

/** First thing a new browser sees, and where new workspaces are started. */
export function WelcomePage() {
    const navigate = useNavigate();
    const { workspaces, open } = useWorkspace();
    const actions = useWorkspaceActions();
    const fileInput = useRef<HTMLInputElement>(null);
    const [name, setName] = useState("");
    const [error, setError] = useState<string | null>(null);
    const busy = actions.create.isPending || actions.importNew.isPending;

    const startBlank = async () => {
        setError(null);
        try {
            const ws = await actions.create.mutateAsync({ name: name.trim() || "Untitled term" });
            open(ws.id);
            navigate("/start");
        } catch (e) {
            setError((e as Error).message);
        }
    };

    const startSample = async () => {
        setError(null);
        try {
            const ws = await actions.create.mutateAsync({ name: "Sample: Fall 2026", sample: "extended" });
            open(ws.id);
            navigate("/assign");
        } catch (e) {
            setError((e as Error).message);
        }
    };

    const importFile = async (f: File | undefined) => {
        if (!f) return;
        setError(null);
        try {
            const { file } = await readWorkspaceFile(f);
            const result = await actions.importNew.mutateAsync({ bundle: file });
            open(result.workspace.id);
            navigate("/start");
        } catch (e) {
            setError((e as Error).message);
        } finally {
            if (fileInput.current) fileInput.current.value = "";
        }
    };

    return (
        <div className="min-h-screen bg-canvas">
            <div className="max-w-5xl mx-auto px-6 py-10 flex flex-col gap-10">
                <div className="flex items-center gap-2.5">
                    <Logo />
                    <span className="font-semibold text-[15px] tracking-tight">Easy-Sched</span>
                </div>

                <div className="flex flex-wrap gap-10 items-start">
                    <section className="flex-[1_1_380px] min-w-0 flex flex-col gap-6">
                        <div className="flex flex-col gap-3">
                            <h1 className="m-0 text-[34px] leading-tight font-semibold tracking-tight">
                                Assign TAs to courses in an afternoon
                            </h1>
                            <p className="m-0 text-[15px] text-ink-2 max-w-lg">
                                Set your department's rules, add courses and applicants, and get the best possible
                                assignment, with a reason for every placement.
                            </p>
                        </div>
                        <ol className="list-none m-0 p-0 flex flex-col gap-3">
                            {STEPS.map(([title, detail], i) => (
                                <li key={title} className="flex gap-3">
                                    <span className="flex-none w-6 h-6 rounded-full bg-accent-soft text-accent text-xs font-semibold inline-flex items-center justify-center">
                                        {i + 1}
                                    </span>
                                    <span className="flex flex-col">
                                        <span className="font-medium">{title}</span>
                                        <span className="text-[13px] text-ink-3">{detail}</span>
                                    </span>
                                </li>
                            ))}
                        </ol>
                    </section>

                    <section aria-labelledby="start-title" className="flex-[1_1_360px] min-w-0 bg-surface border border-line rounded-lg p-6 flex flex-col gap-5">
                        <h2 id="start-title" className="m-0 text-[17px] font-semibold">Start your term</h2>
                        <form
                            className="flex flex-col gap-2"
                            onSubmit={(e) => { e.preventDefault(); void startBlank(); }}
                        >
                            <label htmlFor="ws-name" className="text-[13px] font-medium">Name it</label>
                            <input
                                id="ws-name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="e.g. Fall 2026 TA assignment"
                                className="min-h-10 px-3 rounded-md border border-control bg-surface text-ink"
                            />
                            <Button type="submit" variant="primary" disabled={busy}>Set up my term</Button>
                            <span className="text-xs text-ink-3">Starts empty. A checklist walks you through each step.</span>
                        </form>

                        <div className="flex items-center gap-3 text-xs text-ink-3" aria-hidden="true">
                            <span className="flex-1 h-px bg-line" />or<span className="flex-1 h-px bg-line" />
                        </div>

                        <div className="flex flex-col gap-2">
                            <Button onClick={startSample} disabled={busy}>Explore with sample data</Button>
                            <span className="text-xs text-ink-3">A ready-made term with 14 applicants, to see how it works.</span>
                        </div>

                        <div className="flex flex-col gap-2">
                            <input
                                ref={fileInput}
                                type="file"
                                accept=".json,application/json"
                                className="sr-only"
                                id="ws-file"
                                onChange={(e) => void importFile(e.target.files?.[0])}
                            />
                            <Button variant="ghost" onClick={() => fileInput.current?.click()} disabled={busy}>
                                Import a workspace file
                            </Button>
                        </div>

                        {error && <p role="alert" className="m-0 text-[13px] text-danger">{error}</p>}
                    </section>
                </div>

                {workspaces.length > 0 && (
                    <section aria-labelledby="yours" className="flex flex-col gap-3">
                        <h2 id="yours" className="m-0 text-[15px] font-semibold">Your workspaces</h2>
                        <ul className="list-none m-0 p-0 bg-surface border border-line rounded-lg">
                            {workspaces.map((w) => (
                                <li key={w.id} className="border-b border-line-soft last:border-b-0">
                                    <Link
                                        to="/start"
                                        onClick={() => open(w.id)}
                                        className="flex justify-between gap-3 px-4 py-3 no-underline text-ink hover:bg-canvas"
                                    >
                                        <span className="font-medium">{w.name}</span>
                                        <span className="text-[13px] text-ink-3">
                                            {w.counts.sections} sections · {w.counts.applicants} applicants
                                        </span>
                                    </Link>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                <p className="m-0 text-[13px] text-ink-3 max-w-2xl">
                    {storageIsEphemeral()
                        ? "This browser isn't allowing saved data, so workspaces last only for this visit. Export a workspace file before you leave."
                        : "Workspaces are saved for this browser. Export a workspace file to back one up or move it to another computer."}
                </p>
            </div>
        </div>
    );
}
