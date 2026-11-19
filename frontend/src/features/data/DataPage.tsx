import { useRef, useState } from "react";
import { useNavigate } from "react-router";
import { useWorkspaceActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Button, Hint, PageHeader, Panel } from "../../design/components";
import { exportWorkspace, fetchScheduleCsv } from "../../lib/api";
import { PART_LABELS, downloadText, readWorkspaceFile, safeFilename, type ReadFile } from "../../lib/workspaceFile";
import { WORKSPACE_PARTS, type ImportResult, type WorkspacePart } from "../../types";

/** Workspace files in and out, plus renaming, resetting and deleting the workspace. */
export function DataPage() {
    const { current } = useWorkspace();
    if (!current) return null;
    return (
        <div key={current.id} className="max-w-4xl flex flex-col gap-6">
            <PageHeader
                title="Import & export"
                description="Workspace files carry your rules, courses, applicants, locks and finalized schedule. Use them to back up, move to another computer, or share with a colleague."
            />
            <Hint id="data-intro">
                Your workspaces live in this browser only. Download a workspace file now and then, so clearing
                your browser data never costs you your work.
            </Hint>
            <ExportPanel />
            <ImportPanel />
            <ManagePanel />
        </div>
    );
}

function PartChecklist({ legend, available, chosen, setChosen, disabled = [] }: {
    legend: string;
    available: WorkspacePart[];
    chosen: WorkspacePart[];
    setChosen: (p: WorkspacePart[]) => void;
    disabled?: WorkspacePart[];
}) {
    return (
        <fieldset className="m-0 p-0 border-0 flex flex-wrap gap-x-5 gap-y-2">
            <legend className="sr-only">{legend}</legend>
            {available.map((p) => (
                <label key={p} className={`inline-flex items-center gap-2 min-h-8 ${disabled.includes(p) ? "text-ink-3" : ""}`}>
                    <input
                        type="checkbox"
                        className="w-4 h-4 accent-accent"
                        checked={chosen.includes(p) && !disabled.includes(p)}
                        disabled={disabled.includes(p)}
                        onChange={(e) => setChosen(e.target.checked ? [...chosen, p] : chosen.filter((x) => x !== p))}
                    />
                    {PART_LABELS[p]}
                </label>
            ))}
        </fieldset>
    );
}

function ExportPanel() {
    const { current } = useWorkspace();
    const ws = current!;
    const [chosen, setChosen] = useState<WorkspacePart[]>([...WORKSPACE_PARTS]);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const disabled: WorkspacePart[] = [
        ...(ws.setup.rules ? [] : ["settings" as const]),
        ...(ws.finalized_at ? [] : ["schedule" as const]),
    ];
    const parts = chosen.filter((p) => !disabled.includes(p));

    const download = async () => {
        setError(null);
        setBusy(true);
        try {
            const file = await exportWorkspace(ws.id, parts);
            downloadText(`${safeFilename(ws.name)}.easysched.json`, JSON.stringify(file, null, 2));
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const downloadCsv = async () => {
        setError(null);
        try {
            downloadText(`${safeFilename(ws.name)}-schedule.csv`, await fetchScheduleCsv(ws.id), "text/csv");
        } catch (e) {
            setError((e as Error).message);
        }
    };

    return (
        <Panel>
            <div className="px-5 py-4 border-b border-line">
                <h2 className="m-0 text-[15px] font-semibold">Export</h2>
            </div>
            <div className="px-5 py-4 flex flex-col gap-4">
                <PartChecklist legend="Parts to export" available={WORKSPACE_PARTS} chosen={chosen} setChosen={setChosen} disabled={disabled} />
                <div className="flex flex-wrap gap-2">
                    <Button variant="primary" onClick={download} disabled={busy || parts.length === 0}>Download workspace file</Button>
                    <Button onClick={downloadCsv} disabled={!ws.finalized_at}>Download final schedule (CSV)</Button>
                </div>
                {!ws.finalized_at && <span className="text-xs text-ink-3">The schedule CSV is available once you mark a schedule final on Assignments.</span>}
                {error && <p role="alert" className="m-0 text-[13px] text-danger">{error}</p>}
            </div>
        </Panel>
    );
}

function ImportPanel() {
    const { current, open } = useWorkspace();
    const ws = current!;
    const actions = useWorkspaceActions();
    const navigate = useNavigate();
    const input = useRef<HTMLInputElement>(null);
    const [picked, setPicked] = useState<(ReadFile & { name: string }) | null>(null);
    const [chosen, setChosen] = useState<WorkspacePart[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<ImportResult | null>(null);
    const busy = actions.importInto.isPending || actions.importNew.isPending;

    const pick = async (f: File | undefined) => {
        setError(null);
        setResult(null);
        if (!f) return;
        try {
            const read = await readWorkspaceFile(f);
            setPicked({ ...read, name: f.name });
            setChosen(read.parts);
        } catch (e) {
            setPicked(null);
            setError((e as Error).message);
        } finally {
            if (input.current) input.current.value = "";
        }
    };

    const run = async (asNew: boolean) => {
        if (!picked) return;
        setError(null);
        try {
            if (asNew) {
                const r = await actions.importNew.mutateAsync({ bundle: picked.file, parts: chosen });
                open(r.workspace.id);
                navigate("/start");
            } else {
                setResult(await actions.importInto.mutateAsync({ id: ws.id, bundle: picked.file, parts: chosen }));
                setPicked(null);
            }
        } catch (e) {
            setError((e as Error).message);
        }
    };

    return (
        <Panel>
            <div className="px-5 py-4 border-b border-line">
                <h2 className="m-0 text-[15px] font-semibold">Import</h2>
            </div>
            <div className="px-5 py-4 flex flex-col gap-4">
                <input ref={input} type="file" accept=".json,application/json" className="sr-only" id="import-file"
                    onChange={(e) => void pick(e.target.files?.[0])} />
                <div className="flex flex-wrap items-center gap-3">
                    <Button onClick={() => input.current?.click()} disabled={busy}>Choose a workspace file</Button>
                    {picked && <span className="font-mono text-[13px]">{picked.name}</span>}
                </div>

                {picked && (
                    <>
                        <div className="flex flex-col gap-2">
                            <span className="text-[13px] text-ink-2">
                                This file has: {picked.parts.map((p) =>
                                    `${PART_LABELS[p]}${picked.counts[p] !== undefined ? ` (${picked.counts[p]})` : ""}`).join(", ") || "nothing to import"}.
                                Choose what to bring in:
                            </span>
                            <PartChecklist legend="Parts to import" available={picked.parts} chosen={chosen} setChosen={setChosen} />
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button variant="primary" onClick={() => run(true)} disabled={busy || chosen.length === 0}>
                                Import as a new workspace
                            </Button>
                            <Button onClick={() => run(false)} disabled={busy || chosen.length === 0}>
                                Replace these parts in “{ws.name}”
                            </Button>
                        </div>
                        <span className="text-xs text-ink-3">
                            Replacing swaps out only the parts you selected. If the file doesn't fit together, nothing changes.
                        </span>
                    </>
                )}

                {result && (
                    <div role="status" className="px-4 py-3 rounded-lg bg-accent-tint border border-line text-[13px] flex flex-col gap-1">
                        <span className="font-medium">
                            Imported {result.report.imported.map((p) => PART_LABELS[p].toLowerCase()).join(", ")}.
                        </span>
                        {result.report.notes.map((n) => <span key={n} className="text-ink-2">{n}</span>)}
                    </div>
                )}
                {error && <p role="alert" className="m-0 text-[13px] text-danger">{error}</p>}
            </div>
        </Panel>
    );
}

function ManagePanel() {
    const { current, workspaces, open } = useWorkspace();
    const ws = current!;
    const actions = useWorkspaceActions();
    const navigate = useNavigate();
    const [name, setName] = useState(ws.name);
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [confirmReset, setConfirmReset] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const guard = async (fn: () => Promise<unknown>) => {
        setError(null);
        try { await fn(); } catch (e) { setError((e as Error).message); }
    };

    const remove = () => guard(async () => {
        await actions.remove.mutateAsync(ws.id);
        const next = workspaces.find((w) => w.id !== ws.id);
        if (next) {
            open(next.id);
            navigate("/start");
        } else {
            navigate("/welcome");
        }
    });

    return (
        <Panel>
            <div className="px-5 py-4 border-b border-line">
                <h2 className="m-0 text-[15px] font-semibold">This workspace</h2>
            </div>
            <div className="px-5 py-4 flex flex-col gap-5">
                <form className="flex flex-wrap items-end gap-2"
                    onSubmit={(e) => { e.preventDefault(); void guard(() => actions.rename.mutateAsync({ id: ws.id, name })); }}>
                    <label className="flex flex-col gap-1.5">
                        <span className="text-[13px] font-medium">Name</span>
                        <input value={name} onChange={(e) => setName(e.target.value)}
                            className="w-72 max-w-full min-h-10 px-3 rounded-md border border-control bg-surface text-ink" />
                    </label>
                    <Button type="submit" disabled={!name.trim() || name.trim() === ws.name || actions.rename.isPending}>Rename</Button>
                </form>

                {ws.sample && (
                    <div className="flex flex-wrap items-center gap-3">
                        {confirmReset ? (
                            <>
                                <span className="text-[13px]">Put the sample data, rules and locks back to how they started?</span>
                                <Button variant="primary" onClick={() => guard(async () => { await actions.reset.mutateAsync(ws.id); setConfirmReset(false); })}>Reset</Button>
                                <Button variant="ghost" onClick={() => setConfirmReset(false)}>Cancel</Button>
                            </>
                        ) : (
                            <Button onClick={() => setConfirmReset(true)}>Reset sample data</Button>
                        )}
                    </div>
                )}

                <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-line-soft">
                    {confirmDelete ? (
                        <>
                            <span className="text-[13px]">Delete “{ws.name}” and everything in it from this browser? This can't be undone.</span>
                            <Button className="bg-danger! border-danger! text-on-accent! hover:bg-danger!" onClick={remove}>Delete workspace</Button>
                            <Button variant="ghost" onClick={() => setConfirmDelete(false)}>Cancel</Button>
                        </>
                    ) : (
                        <Button variant="ghost" className="text-danger!" onClick={() => setConfirmDelete(true)}>Delete this workspace…</Button>
                    )}
                </div>
                {error && <p role="alert" className="m-0 text-[13px] text-danger">{error}</p>}
            </div>
        </Panel>
    );
}
