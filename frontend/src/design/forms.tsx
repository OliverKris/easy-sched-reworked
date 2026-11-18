import { useId, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { DAYS, DAY_LETTER, DAY_NAME, patternProblem, type MeetingPattern } from "../lib/schedule";
import type { Day } from "../types";
import { Button } from "./components";
import { CloseIcon } from "./icons";

/* Form building blocks for the editors. Every control has a real label;
   errors are tied to their field with aria-describedby. */

const control = "min-h-10 px-3 rounded-md border bg-surface text-ink w-full";

export function Field({ label, hint, error, children, id }: {
    label: string; hint?: string; error?: string | null; children: (id: string, describedBy?: string) => ReactNode; id?: string;
}) {
    const auto = useId();
    const fieldId = id ?? auto;
    const describedBy = error ? `${fieldId}-err` : hint ? `${fieldId}-hint` : undefined;
    return (
        <div className="flex flex-col gap-1.5 min-w-0">
            <label htmlFor={fieldId} className="text-[13px] font-medium">{label}</label>
            {children(fieldId, describedBy)}
            {error ? <span id={`${fieldId}-err`} className="text-xs text-danger">{error}</span>
                : hint ? <span id={`${fieldId}-hint`} className="text-xs text-ink-3">{hint}</span> : null}
        </div>
    );
}

export function TextInput({ invalid, className = "", ...props }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
    return <input aria-invalid={invalid || undefined} className={`${control} ${invalid ? "border-danger" : "border-control"} ${className}`} {...props} />;
}

export function SelectInput({ invalid, className = "", children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & { invalid?: boolean }) {
    return (
        <select aria-invalid={invalid || undefined} className={`${control} ${invalid ? "border-danger" : "border-control"} ${className}`} {...props}>
            {children}
        </select>
    );
}

/** M T W R F toggle buttons. */
export function DaysPicker({ value, onChange, label }: { value: Day[]; onChange: (d: Day[]) => void; label: string }) {
    return (
        <div role="group" aria-label={label} className="flex gap-1">
            {DAYS.map((d) => {
                const on = value.includes(d);
                return (
                    <button
                        key={d}
                        type="button"
                        aria-pressed={on}
                        aria-label={DAY_NAME[d]}
                        title={DAY_NAME[d]}
                        onClick={() => onChange(on ? value.filter((x) => x !== d) : DAYS.filter((x) => x === d || value.includes(x)))}
                        className={`w-9 h-9 rounded-md border text-[13px] font-medium cursor-pointer ${on ? "bg-accent text-white border-accent" : "bg-surface text-ink-2 border-control hover:bg-canvas"}`}
                    >
                        {DAY_LETTER[d]}
                    </button>
                );
            })}
        </div>
    );
}

/** A list of "days + start + end" rows, e.g. a lecture or a person's class schedule. */
export function MeetingRows({ value, onChange, label, addLabel, prefix }: {
    value: (MeetingPattern & { id?: string })[];
    onChange: (v: (MeetingPattern & { id?: string })[]) => void;
    label: string;
    addLabel: string;
    prefix?: (index: number) => ReactNode;
}) {
    const update = (i: number, patch: Partial<MeetingPattern & { id?: string }>) =>
        onChange(value.map((p, j) => (j === i ? { ...p, ...patch } : p)));
    return (
        <fieldset className="m-0 p-0 border-0 flex flex-col gap-2 min-w-0">
            <legend className="text-[13px] font-medium mb-1.5">{label}</legend>
            {value.map((p, i) => {
                const problem = patternProblem(p);
                return (
                    <div key={i} className="flex flex-col gap-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                            {prefix?.(i)}
                            <DaysPicker value={p.days} onChange={(days) => update(i, { days })} label={`${label} ${i + 1} days`} />
                            <span className="inline-flex items-center gap-1">
                                <input type="time" aria-label={`${label} ${i + 1} start`} value={p.start}
                                    onChange={(e) => update(i, { start: e.target.value })}
                                    className="w-[108px] min-h-9 px-1.5 rounded-md border border-control bg-surface tabular-nums text-[13px]" />
                                <span className="text-ink-3" aria-hidden="true">–</span>
                                <input type="time" aria-label={`${label} ${i + 1} end`} value={p.end}
                                    onChange={(e) => update(i, { end: e.target.value })}
                                    className="w-[108px] min-h-9 px-1.5 rounded-md border border-control bg-surface tabular-nums text-[13px]" />
                            </span>
                            <button type="button" onClick={() => onChange(value.filter((_, j) => j !== i))}
                                aria-label={`Remove ${label.toLowerCase()} ${i + 1}`}
                                className="w-8 h-8 inline-flex items-center justify-center rounded-md text-ink-3 hover:bg-line-soft cursor-pointer">
                                <CloseIcon />
                            </button>
                        </div>
                        {problem && <span className="text-xs text-danger">{problem}</span>}
                    </div>
                );
            })}
            <div>
                <Button size="sm" onClick={() => onChange([...value, { days: [], start: "", end: "" }])}>{addLabel}</Button>
            </div>
        </fieldset>
    );
}

/** A repeatable list of rows with a remove button each and an Add button. */
export function RepeatRows<T>({ legend, items, onChange, render, blank, addLabel, empty, columns }: {
    legend: string;
    /** CSS grid-template-columns for each row's fields (the remove button gets its own 32px column). */
    columns?: string;
    items: T[];
    onChange: (items: T[]) => void;
    render: (item: T, update: (patch: Partial<T>) => void, index: number) => ReactNode;
    blank: () => T;
    addLabel: string;
    empty?: string;
}) {
    return (
        <fieldset className="m-0 p-0 border-0 flex flex-col gap-2 min-w-0">
            <legend className="text-[13px] font-medium mb-1.5">{legend}</legend>
            {items.length === 0 && empty && <span className="text-[13px] text-ink-3">{empty}</span>}
            {items.map((item, i) => (
                <div key={i} className={columns ? "grid items-center gap-2" : "flex flex-wrap items-end gap-2"}
                    style={columns ? { gridTemplateColumns: `${columns} 32px` } : undefined}>
                    {render(item, (patch) => onChange(items.map((x, j) => (j === i ? { ...x, ...patch } : x))), i)}
                    <button type="button" onClick={() => onChange(items.filter((_, j) => j !== i))}
                        aria-label={`Remove ${legend.toLowerCase()} row ${i + 1}`}
                        className="w-8 h-10 inline-flex items-center justify-center rounded-md text-ink-3 hover:bg-line-soft cursor-pointer justify-self-end">
                        <CloseIcon />
                    </button>
                </div>
            ))}
            <div><Button size="sm" onClick={() => onChange([...items, blank()])}>{addLabel}</Button></div>
        </fieldset>
    );
}

/** Delete button that asks once more before acting. */
export function ConfirmDelete({ label, confirmText, onConfirm, disabled }: {
    label: string; confirmText: string; onConfirm: () => void; disabled?: boolean;
}) {
    const [asking, setAsking] = useState(false);
    if (!asking) {
        return <Button variant="ghost" className="text-danger!" disabled={disabled} onClick={() => setAsking(true)}>{label}</Button>;
    }
    return (
        <span className="flex flex-wrap items-center gap-2">
            <span className="text-[13px]">{confirmText}</span>
            <Button className="bg-danger! border-danger! text-white!" onClick={() => { setAsking(false); onConfirm(); }}>Delete</Button>
            <Button variant="ghost" onClick={() => setAsking(false)}>Cancel</Button>
        </span>
    );
}

/** The right-hand editing panel used by Courses and Applicants. */
export function EditorPanel({ title, subtitle, onClose, children, footer }: {
    title: string; subtitle?: ReactNode; onClose: () => void; children: ReactNode; footer: ReactNode;
}) {
    return (
        <aside aria-label={title} className="flex-[1_1_520px] min-w-0 max-w-160 bg-surface border border-line rounded-lg self-start lg:sticky lg:top-6 max-h-[calc(100vh-3rem)] flex flex-col">
            <div className="px-5 py-4 border-b border-line flex items-start justify-between gap-3">
                <div className="flex flex-col gap-0.5 min-w-0">
                    <h2 className="m-0 text-[17px] font-semibold">{title}</h2>
                    {subtitle && <span className="text-[13px] text-ink-3">{subtitle}</span>}
                </div>
                <button type="button" onClick={onClose} aria-label="Close editor"
                    className="w-8 h-8 inline-flex items-center justify-center rounded-md text-ink-3 hover:bg-line-soft cursor-pointer">
                    <CloseIcon />
                </button>
            </div>
            <div className="px-5 py-4 flex flex-col gap-5 overflow-y-auto">{children}</div>
            <div className="px-5 py-3.5 border-t border-line flex flex-wrap items-center gap-2">{footer}</div>
        </aside>
    );
}
