import { useWorkspace } from "../../app/workspace";
import { Badge, Hint, PageHeader } from "../../design/components";
import { CheckIcon } from "../../design/icons";
import { ButtonLink } from "../../design/links";

interface Step {
    key: "rules" | "courses" | "applicants" | "schedule";
    title: string;
    detail: string;
    doneText: string;
    to: string;
    cta: string;
    alt?: { to: string; label: string };
}

/** The setup checklist: what's done, what's next, and a link to do it. */
export function StartPage() {
    const { current } = useWorkspace();
    if (!current) return null;
    const { setup, counts } = current;

    const steps: Step[] = [
        {
            key: "rules", title: "Set your rules", to: "/rules", cta: setup.rules ? "Review rules" : "Set rules",
            detail: "Who can be assigned (GPA floors, availability) and what makes a good fit.",
            doneText: "Rules saved",
        },
        {
            key: "courses", title: "Add courses and sections", to: "/courses", cta: "Open courses",
            detail: "Each section's meeting times and how many LAs and UTAs it needs.",
            doneText: `${counts.sections} section${counts.sections === 1 ? "" : "s"} in ${counts.courses} course${counts.courses === 1 ? "" : "s"}`,
            alt: { to: "/data", label: "Import from a file" },
        },
        {
            key: "applicants", title: "Add applicants", to: "/applicants", cta: "Open applicants",
            detail: "Transcripts, schedules, experience, and the courses each person ranked.",
            doneText: `${counts.applicants} applicant${counts.applicants === 1 ? "" : "s"}`,
            alt: { to: "/data", label: "Import from a file" },
        },
        {
            key: "schedule", title: "Assign and finalize", to: "/assign", cta: "Go to assignments",
            detail: "Run the solver, adjust with locks, then mark the schedule final and download it.",
            doneText: current.finalized_at ? `Finalized ${new Date(current.finalized_at).toLocaleDateString()}` : "Finalized",
        },
    ];
    const done = steps.filter((s) => setup[s.key]).length;
    const nextKey = steps.find((s) => !setup[s.key])?.key;
    const canAssign = setup.courses && setup.applicants;

    return (
        <div className="max-w-3xl flex flex-col gap-6">
            <PageHeader
                title="Getting started"
                description={<>Four steps to a finished schedule for <span className="text-ink font-medium">{current.name}</span>. Do them in any order and come back any time.</>}
            />

            {current.sample && (
                <Hint id="sample-workspace">
                    This is a sample workspace with made-up data. Change anything you like: you can reset it from
                    Import &amp; export. When you're ready, start your own term from the workspace menu.
                </Hint>
            )}

            <div className="flex flex-col gap-2">
                <div className="flex justify-between text-[13px] text-ink-2">
                    <span>{done} of {steps.length} done</span>
                    {done === steps.length && <Badge tone="accent"><CheckIcon />Schedule finalized</Badge>}
                </div>
                <div className="h-1.5 rounded-full bg-line-soft overflow-hidden" aria-hidden="true">
                    <div className="h-full bg-accent transition-all" style={{ width: `${(done / steps.length) * 100}%` }} />
                </div>
            </div>

            <ol className="list-none m-0 p-0 flex flex-col gap-3">
                {steps.map((step, i) => {
                    const isDone = setup[step.key];
                    const isNext = step.key === nextKey;
                    const blocked = step.key === "schedule" && !canAssign;
                    return (
                        <li
                            key={step.key}
                            className={`flex flex-wrap items-center gap-4 p-4 rounded-lg border bg-surface ${isNext ? "border-accent" : "border-line"}`}
                        >
                            <span
                                className={`flex-none w-7 h-7 rounded-full inline-flex items-center justify-center text-[13px] font-semibold ${isDone ? "bg-accent text-white" : isNext ? "bg-accent-soft text-accent" : "bg-line-soft text-ink-3"}`}
                                aria-hidden="true"
                            >
                                {isDone ? <CheckIcon size={13} /> : i + 1}
                            </span>
                            <div className="flex-[1_1_280px] min-w-0 flex flex-col gap-0.5">
                                <span className="font-medium">
                                    {step.title}
                                    <span className="sr-only">{isDone ? " (done)" : isNext ? " (next)" : ""}</span>
                                </span>
                                <span className="text-[13px] text-ink-3">
                                    {isDone ? step.doneText : blocked ? "Add courses and applicants first." : step.detail}
                                </span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {step.alt && !isDone && <ButtonLink to={step.alt.to} variant="ghost">{step.alt.label}</ButtonLink>}
                                <ButtonLink to={step.to} variant={isNext && !blocked ? "primary" : "secondary"}>{step.cta}</ButtonLink>
                            </div>
                        </li>
                    );
                })}
            </ol>
        </div>
    );
}
