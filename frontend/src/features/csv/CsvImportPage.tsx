import { useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import { useQuery } from "@tanstack/react-query";
import { useRefreshWorkspace } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Badge, Button, Code, PageHeader, Panel, Spinner } from "../../design/components";
import { ButtonLink } from "../../design/links";
import { fetchCsvColumns, uploadCsvRows } from "../../lib/api";
import { downloadText } from "../../lib/workspaceFile";
import type { CsvColumn, CsvKind, CsvResult } from "../../types";

const COPY: Record<CsvKind, { title: string; noun: string; back: string; backLabel: string; formats: [string, string][] }> = {
    sections: {
        title: "Upload courses & sections",
        noun: "sections",
        back: "/courses",
        backLabel: "Back to courses",
        formats: [
            ["Lecture days", "MW, TR, MWF, Tue/Thu"],
            ["Times", "11:10, 2:20pm"],
            ["Labs", "Fri 10:00-11:50; Fri 12:00-13:50 (name one with “L32: Fri 10:00-11:50”)"],
            ["Yes/no columns", "yes, no, y, n, true, false"],
        ],
    },
    applicants: {
        title: "Upload applicants",
        noun: "applicants",
        back: "/applicants",
        backLabel: "Back to applicants",
        formats: [
            ["Positions", "LA, UTA, or both"],
            ["Courses taken", "CSCI 1111: A-; CSCI 1112: B+ (Spring 2026); CSCI 2113: IP"],
            ["Busy times", "MW 10:00-11:15; TR 2:20pm-3:35pm"],
            ["Prior TA roles", "LA CSCI 1111 Fall 2025; UTA CSCI 1112 Spring 2026"],
            ["Recommendations", "Prof. Kim: 5; Dr. Lee: 4 (CSCI 1112)"],
        ],
    },
};

const IGNORE = "";
const norm = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, "");

function autoMatch(headers: string[], columns: CsvColumn[]): Record<string, string> {
    const used = new Set<string>();
    const out: Record<string, string> = {};
    for (const h of headers) {
        const n = norm(h);
        const hit = columns.find((c) => !used.has(c.key) && [c.key, c.label, ...c.aliases].some((name) => norm(name) === n));
        out[h] = hit ? hit.key : IGNORE;
        if (hit) used.add(hit.key);
    }
    return out;
}

interface Parsed { name: string; headers: string[]; rows: Record<string, string>[] }

export function CsvImportPage({ kind }: { kind: CsvKind }) {
    const { current, dataset } = useWorkspace();
    const copy = COPY[kind];
    const refresh = useRefreshWorkspace();
    const columns = useQuery({ queryKey: ["csv-columns", kind], queryFn: () => fetchCsvColumns(kind).then((r) => r.columns), staleTime: Infinity });
    const input = useRef<HTMLInputElement>(null);

    const [parsed, setParsed] = useState<Parsed | null>(null);
    const [mapping, setMapping] = useState<Record<string, string>>({});
    const [mode, setMode] = useState<"merge" | "replace">("merge");
    const [check, setCheck] = useState<CsvResult | null>(null);
    const [done, setDone] = useState<CsvResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);

    const cols = columns.data ?? [];
    const mapped = new Set(Object.values(mapping).filter(Boolean));
    const missingRequired = cols.filter((c) => c.required && !mapped.has(c.key));

    const downloadTemplate = () => {
        const csv = Papa.unparse({ fields: cols.map((c) => c.label), data: [cols.map((c) => c.example)] });
        downloadText(`easy-sched-${kind}-template.csv`, csv, "text/csv");
    };

    const pick = (file: File | undefined) => {
        setError(null);
        setCheck(null);
        setDone(null);
        if (!file) return;
        Papa.parse<Record<string, string>>(file, {
            header: true,
            skipEmptyLines: "greedy",
            transformHeader: (h) => h.trim(),
            complete: (res) => {
                const headers = (res.meta.fields ?? []).filter(Boolean);
                if (headers.length === 0 || res.data.length === 0) {
                    setError(`${file.name} has no rows under a header line.`);
                    setParsed(null);
                    return;
                }
                setParsed({ name: file.name, headers, rows: res.data });
                setMapping(autoMatch(headers, cols));
            },
            error: (err) => setError(`Couldn't read ${file.name}: ${err.message}`),
        });
        if (input.current) input.current.value = "";
    };

    const rowsForServer = useMemo(() => {
        if (!parsed) return [];
        return parsed.rows.map((r) => {
            const out: Record<string, string> = {};
            for (const [header, key] of Object.entries(mapping)) if (key) out[key] = r[header] ?? "";
            return out;
        });
    }, [parsed, mapping]);

    const run = async (dryRun: boolean) => {
        setError(null);
        setBusy(true);
        try {
            const res = await uploadCsvRows(dataset, kind, rowsForServer, mode, dryRun);
            if (dryRun) setCheck(res);
            else {
                setDone(res);
                setCheck(null);
                setParsed(null);
                await refresh(dataset);
            }
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(false);
        }
    };

    const setMap = (header: string, key: string) => {
        setCheck(null);
        setMapping({ ...mapping, [header]: key });
    };

    if (!current) return null;
    const total = check ? (check.summary.sections ?? check.summary.applicants ?? 0) : 0;

    return (
        <div className="max-w-5xl flex flex-col gap-5">
            <PageHeader title={copy.title} description={<>Into <span className="text-ink font-medium">{current.name}</span>. Nothing is saved until you check the file and choose Import.</>}
                actions={<ButtonLink to={copy.back}>{copy.backLabel}</ButtonLink>} />

            {done && (
                <div role="status" className="px-4 py-3 rounded-lg bg-accent-tint border border-line flex flex-wrap items-center gap-3">
                    <span className="font-medium">
                        Imported {done.summary.sections ?? done.summary.applicants} {copy.noun}
                        {done.summary.new !== undefined && ` (${done.summary.new} new${done.summary.updated ? `, ${done.summary.updated} updated` : ""})`}.
                    </span>
                    {done.report?.notes.map((n) => <span key={n} className="text-[13px] text-ink-2">{n}</span>)}
                    <span className="ml-auto"><ButtonLink to={copy.back} variant="primary">See {copy.noun === "sections" ? "courses" : "applicants"}</ButtonLink></span>
                </div>
            )}

            <Panel>
                <div className="px-5 py-4 border-b border-line flex flex-wrap items-center justify-between gap-3">
                    <h2 className="m-0 text-[15px] font-semibold">1. Start from the template</h2>
                    <Button onClick={downloadTemplate} disabled={!cols.length}>Download CSV template</Button>
                </div>
                <div className="px-5 py-4 flex flex-col gap-3 text-[13px]">
                    <p className="m-0 text-ink-2">
                        One row per {kind === "sections" ? "section" : "applicant"}. Your own column names are fine: you'll match them next.
                        From Excel or Google Sheets, use File › Download (or Save as) › CSV.
                    </p>
                    {columns.isPending ? <Spinner /> : (
                        <div className="flex flex-wrap gap-1.5">
                            {cols.map((c) => <Badge key={c.key} tone={c.required ? "accent" : "neutral"}>{c.label}{c.required ? " *" : ""}</Badge>)}
                        </div>
                    )}
                    <dl className="m-0 grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4 gap-y-1">
                        {copy.formats.map(([label, example]) => (
                            <div key={label} className="contents">
                                <dt className="text-ink-3">{label}</dt>
                                <dd className="m-0"><Code>{example}</Code></dd>
                            </div>
                        ))}
                    </dl>
                </div>
            </Panel>

            <Panel>
                <div className="px-5 py-4 border-b border-line flex flex-wrap items-center justify-between gap-3">
                    <h2 className="m-0 text-[15px] font-semibold">2. Upload your file</h2>
                    <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" id="csv-file" onChange={(e) => pick(e.target.files?.[0])} />
                    <Button variant={parsed ? "secondary" : "primary"} onClick={() => input.current?.click()} disabled={!cols.length}>
                        {parsed ? "Choose a different file" : "Choose a CSV file"}
                    </Button>
                </div>
                {parsed && (
                    <div className="px-5 py-3 text-[13px] text-ink-2">
                        <Code>{parsed.name}</Code> · {parsed.rows.length} rows · {parsed.headers.length} columns
                    </div>
                )}
                {error && <p role="alert" className="m-0 px-5 py-3 text-[13px] text-danger">{error}</p>}
            </Panel>

            {parsed && (
                <Panel>
                    <div className="px-5 py-4 border-b border-line">
                        <h2 className="m-0 text-[15px] font-semibold">3. Match columns</h2>
                        <p className="m-0 mt-1 text-[13px] text-ink-3">
                            {Object.values(mapping).filter(Boolean).length} of {parsed.headers.length} columns matched automatically. Check them, and set anything we missed.
                        </p>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full border-collapse min-w-[600px]">
                            <thead>
                                <tr className="text-left text-xs text-ink-3">
                                    <th scope="col" className="font-medium px-5 py-2.5">Column in your file</th>
                                    <th scope="col" className="font-medium px-2 py-2.5">First value</th>
                                    <th scope="col" className="font-medium px-5 py-2.5">Imports as</th>
                                </tr>
                            </thead>
                            <tbody>
                                {parsed.headers.map((h) => (
                                    <tr key={h} className="border-t border-line-soft">
                                        <td className="px-5 py-2 font-medium">{h}</td>
                                        <td className="px-2 py-2 text-ink-3 max-w-56 truncate">{parsed.rows.find((r) => r[h])?.[h] ?? ""}</td>
                                        <td className="px-5 py-1.5">
                                            <label className="block">
                                                <span className="sr-only">Field for {h}</span>
                                                <select value={mapping[h] ?? IGNORE} onChange={(e) => setMap(h, e.target.value)}
                                                    className={`w-full min-h-9 px-2 rounded-md border bg-surface ${mapping[h] ? "border-control" : "border-line text-ink-3"}`}>
                                                    <option value={IGNORE}>Don't import</option>
                                                    {cols.map((c) => (
                                                        <option key={c.key} value={c.key} disabled={mapped.has(c.key) && mapping[h] !== c.key}>
                                                            {c.label}{c.required ? " (required)" : ""}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {missingRequired.length > 0 && (
                        <p className="m-0 px-5 py-3 text-[13px] text-warn border-t border-line-soft">
                            Still needed: {missingRequired.map((c) => c.label).join(", ")}.
                        </p>
                    )}
                </Panel>
            )}

            {parsed && (
                <Panel>
                    <div className="px-5 py-4 border-b border-line">
                        <h2 className="m-0 text-[15px] font-semibold">4. Check and import</h2>
                    </div>
                    <div className="px-5 py-4 flex flex-col gap-4">
                        <fieldset className="m-0 p-0 border-0 flex flex-col gap-2">
                            <legend className="text-[13px] font-medium mb-1.5">What to do with existing {copy.noun}</legend>
                            <label className="inline-flex items-start gap-2">
                                <input type="radio" name="mode" className="mt-1 accent-accent" checked={mode === "merge"} onChange={() => { setMode("merge"); setCheck(null); }} />
                                <span><span className="font-medium">Add and update</span> <span className="text-ink-3">New {copy.noun} are added; ones already here are updated from the file; the rest stay.</span></span>
                            </label>
                            <label className="inline-flex items-start gap-2">
                                <input type="radio" name="mode" className="mt-1 accent-accent" checked={mode === "replace"} onChange={() => { setMode("replace"); setCheck(null); }} />
                                <span><span className="font-medium">Replace all</span> <span className="text-ink-3">Every existing {kind === "sections" ? "course and section" : "applicant"} is removed and replaced by the file.</span></span>
                            </label>
                        </fieldset>

                        <div className="flex flex-wrap items-center gap-2">
                            <Button onClick={() => run(true)} disabled={busy || missingRequired.length > 0}>Check file</Button>
                            <Button variant="primary" onClick={() => run(false)} disabled={busy || !check?.ok}>
                                {check?.ok ? `Import ${total} ${copy.noun}` : "Import"}
                            </Button>
                            {busy && <Spinner label="Working" />}
                        </div>

                        {check && check.ok && (
                            <p role="status" className="m-0 text-[13px] text-accent">
                                Ready: {total} {copy.noun}
                                {check.summary.courses !== undefined && ` in ${check.summary.courses} courses`}
                                {` (${check.summary.new} new${check.summary.updated ? `, ${check.summary.updated} updated` : ""})`}. No problems found.
                            </p>
                        )}
                        {check && !check.ok && (
                            <div role="alert" className="flex flex-col gap-2">
                                <p className="m-0 text-[13px] text-danger font-medium">
                                    {check.errors.length} problem{check.errors.length === 1 ? "" : "s"} to fix in the spreadsheet. Nothing has been imported.
                                </p>
                                <div className="border border-line rounded-lg overflow-x-auto max-h-80">
                                    <table className="w-full border-collapse text-[13px]">
                                        <thead className="sticky top-0 bg-surface">
                                            <tr className="text-left text-xs text-ink-3">
                                                <th scope="col" className="font-medium px-4 py-2">Row</th>
                                                <th scope="col" className="font-medium px-2 py-2">Column</th>
                                                <th scope="col" className="font-medium px-4 py-2">Problem</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {check.errors.map((e, i) => (
                                                <tr key={i} className="border-t border-line-soft">
                                                    <td className="px-4 py-1.5 tabular-nums">{e.row}</td>
                                                    <td className="px-2 py-1.5">{e.column ?? "—"}</td>
                                                    <td className="px-4 py-1.5">{e.message}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                                <span className="text-xs text-ink-3">Row numbers match your spreadsheet (the header is row 1). Fix them, then choose the file again.</span>
                            </div>
                        )}
                    </div>
                </Panel>
            )}
        </div>
    );
}
