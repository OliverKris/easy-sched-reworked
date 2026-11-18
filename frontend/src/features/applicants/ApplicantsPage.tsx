import { useMemo, useState } from "react";
import { useApplicants, useCourses, useEditActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Badge, Button, EmptyState, Hint, PageHeader, Spinner } from "../../design/components";
import { ConfirmDelete, EditorPanel, Field, MeetingRows, RepeatRows, SelectInput, TextInput } from "../../design/forms";
import { ButtonLink } from "../../design/links";
import { fromPatterns, GRADES, gradeLabel, patternProblem, TERMS, toPatterns, type MeetingPattern } from "../../lib/schedule";
import type {
    ApplicantJ, ApplicantRecord, CourseRecord, PastCourseJ, Position, RecommendationJ, TeachingJ, Term,
} from "../../types";

export function ApplicantsPage() {
    const { dataset } = useWorkspace();
    const applicants = useApplicants(dataset);
    const courses = useCourses(dataset);
    const [selected, setSelected] = useState<string | "new" | null>(null);
    const [query, setQuery] = useState("");

    const list = useMemo(() => applicants.data ?? [], [applicants.data]);
    const visible = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return list;
        return list.filter((a) => a.name.toLowerCase().includes(q) || a.applicant_id.toLowerCase().includes(q)
            || a.application?.ranked_preferences.some((p) => p.course_id.toLowerCase().includes(q)));
    }, [list, query]);

    const current = selected && selected !== "new" ? list.find((a) => a.applicant_id === selected) ?? null : null;

    return (
        <div className="max-w-[1240px] flex flex-col gap-5">
            <PageHeader
                title="Applicants"
                description="Transcripts, schedules, experience and ranked course choices."
                actions={list.length > 0 ? <>
                    <ButtonLink to="/applicants/import">Upload a spreadsheet</ButtonLink>
                    <Button variant="primary" onClick={() => setSelected("new")}>Add applicant</Button>
                </> : undefined}
            />

            {applicants.error && <p role="alert" className="m-0 text-danger">Couldn't load applicants ({applicants.error.message}).</p>}
            {applicants.isPending && <Spinner />}

            {applicants.data && list.length === 0 && !selected && (
                <EmptyState
                    title="No applicants yet"
                    action={<div className="flex flex-wrap gap-2">
                        <ButtonLink to="/applicants/import" variant="primary">Upload a spreadsheet</ButtonLink>
                        <Button onClick={() => setSelected("new")}>Add an applicant by hand</Button>
                    </div>}
                >
                    Upload your application form export as a CSV (there's a template to fill in), or add people one at a time.
                </EmptyState>
            )}

            {(list.length > 0 || selected) && (
                <div className="flex flex-wrap gap-5 items-start">
                    <section aria-label="Applicants" className="flex-[999_1_520px] min-w-0 flex flex-col gap-4">
                        {list.length > 0 && (
                            <>
                                <Hint id="applicants-intro">
                                    Click a person to edit their details. GPA is worked out from the grades on their transcript.
                                </Hint>
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <label className="flex-[1_1_260px] max-w-90 flex">
                                        <span className="sr-only">Search applicants</span>
                                        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
                                            placeholder="Search by name, ID or course"
                                            className="flex-1 min-h-9 px-2.5 rounded-md border border-control bg-surface text-ink" />
                                    </label>
                                    <span className="text-[13px] text-ink-3">{list.length} applicants</span>
                                </div>
                                <div className="bg-surface border border-line rounded-lg overflow-x-auto">
                                    <table className="w-full border-collapse min-w-[560px]">
                                        <thead>
                                            <tr className="text-left text-xs text-ink-3">
                                                <th scope="col" className="font-medium px-4 py-2.5">Name</th>
                                                <th scope="col" className="font-medium px-2 py-2.5">Applying for</th>
                                                <th scope="col" className="font-medium px-2 py-2.5 text-right">GPA</th>
                                                <th scope="col" className="font-medium px-4 py-2.5">Choices</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {visible.map((a) => (
                                                <tr key={a.applicant_id}
                                                    className={`border-t border-line-soft ${selected === a.applicant_id ? "bg-accent-tint" : "hover:bg-canvas"}`}>
                                                    <td className="px-4 py-2">
                                                        <button type="button" onClick={() => setSelected(a.applicant_id)}
                                                            className="text-left cursor-pointer flex flex-col">
                                                            <span className="font-medium text-ink">{a.name}</span>
                                                            <span className="text-xs text-ink-3">{a.applicant_id}</span>
                                                        </button>
                                                    </td>
                                                    <td className="px-2 py-2">
                                                        <span className="flex gap-1">{(a.application?.position_types ?? []).map((p) => <Badge key={p}>{p}</Badge>)}</span>
                                                    </td>
                                                    <td className="px-2 py-2 text-right tabular-nums">{a.gpa?.toFixed(2) ?? "—"}</td>
                                                    <td className="px-4 py-2 text-[13px]">
                                                        {(a.application?.ranked_preferences ?? []).slice().sort((x, y) => x.rank - y.rank)
                                                            .map((p) => p.course_id).join(", ") || <span className="text-ink-3">None ranked</span>}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {visible.length === 0 && <p className="m-0 px-4 py-3 text-ink-3">No one matches.</p>}
                                </div>
                            </>
                        )}
                    </section>

                    {selected && (
                        <ApplicantEditor
                            key={selected}
                            applicant={current}
                            courses={courses.data ?? []}
                            existingIds={list.map((a) => a.applicant_id)}
                            onClose={() => setSelected(null)}
                            onSaved={(id) => setSelected(id)}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

function defaultApplication(courses: CourseRecord[]): { term: Term; year: number } {
    const first = courses.flatMap((c) => c.sections)[0];
    return first ? { term: first.term, year: first.year } : { term: "FALL", year: new Date().getFullYear() };
}

function ApplicantEditor({ applicant, courses, existingIds, onClose, onSaved }: {
    applicant: ApplicantRecord | null; courses: CourseRecord[]; existingIds: string[];
    onClose: () => void; onSaved: (id: string) => void;
}) {
    const { dataset } = useWorkspace();
    const actions = useEditActions(dataset);
    const isNew = applicant === null;
    const app = applicant?.application ?? null;
    const defaults = defaultApplication(courses);
    const courseIds = courses.map((c) => c.course_id);
    const prefs = (app?.ranked_preferences ?? []).slice().sort((a, b) => a.rank - b.rank);

    const [id, setId] = useState(applicant?.applicant_id ?? "");
    const [name, setName] = useState(applicant?.name ?? "");
    const [email, setEmail] = useState(applicant?.email ?? "");
    const [positions, setPositions] = useState<Position[]>(app?.position_types ?? ["LA"]);
    const [choices, setChoices] = useState<string[]>([0, 1, 2].map((i) => prefs[i]?.course_id ?? ""));
    const [term, setTerm] = useState<Term>(app?.term ?? defaults.term);
    const [year, setYear] = useState(String(app?.year ?? defaults.year));
    const [transcript, setTranscript] = useState<PastCourseJ[]>(applicant?.past_courses ?? []);
    const [busy, setBusy] = useState<MeetingPattern[]>(toPatterns(applicant?.upcoming_schedule ?? []));
    const [experience, setExperience] = useState<TeachingJ[]>(applicant?.teaching_experience ?? []);
    const [recs, setRecs] = useState<RecommendationJ[]>(applicant?.recommendations ?? []);
    const [skills, setSkills] = useState(applicant?.skills.join(", ") ?? "");
    const [tried, setTried] = useState(false);

    const chosen = choices.filter(Boolean);
    const errors = {
        id: !id.trim() ? "Enter a student ID" : isNew && existingIds.includes(id.trim()) ? "Someone already has this ID" : null,
        name: !name.trim() ? "Enter a name" : null,
        positions: positions.length === 0 ? "Pick at least one position" : null,
        choices: new Set(chosen).size !== chosen.length ? "Each choice must be a different course" : null,
        year: !/^\d{4}$/.test(year) ? "Enter a 4-digit year" : null,
        transcript: transcript.some((t) => !t.course_id.trim() || !/^\d{4}$/.test(String(t.year))) ? "Each course needs a code and a year" : null,
        busy: busy.some((p) => patternProblem(p)) ? "Fix the highlighted times" : null,
        experience: experience.some((x) => !x.course_id.trim() || !/^\d{4}$/.test(String(x.year))) ? "Each role needs a course and a year" : null,
        recs: recs.some((r) => !r.faculty_name.trim()) ? "Each recommendation needs a name" : null,
    };
    const hasError = Object.values(errors).some(Boolean);
    const error = actions.saveApplicant.error ?? actions.removeApplicant.error;

    const save = async () => {
        setTried(true);
        if (hasError) return;
        const payload: ApplicantJ = {
            applicant_id: id.trim(), name: name.trim(), email: email.trim(),
            skills: [...new Set(skills.split(/[;,]/).map((s) => s.trim().toLowerCase()).filter(Boolean))].sort(),
            past_courses: transcript.map((t) => ({ ...t, course_id: t.course_id.trim(), year: Number(t.year) })),
            teaching_experience: experience.map((x) => ({ ...x, course_id: x.course_id.trim(), year: Number(x.year),
                supervisor_rating: x.supervisor_rating ? Number(x.supervisor_rating) : null })),
            recommendations: recs.map((r) => ({ ...r, faculty_name: r.faculty_name.trim(), course_id: r.course_id || null })),
            upcoming_schedule: fromPatterns(busy, "Class"),
            application: {
                term, year: Number(year), position_types: positions,
                ranked_preferences: choices.map((c, i) => ({ course_id: c, rank: i + 1 })).filter((p) => p.course_id),
            },
        };
        await actions.saveApplicant.mutateAsync(payload);
        onSaved(payload.applicant_id);
    };

    const lastYear = Number(year) - 1 || new Date().getFullYear() - 1;

    return (
        <EditorPanel
            title={isNew ? "New applicant" : applicant.name}
            subtitle={isNew ? undefined : <>{applicant.applicant_id}{applicant.gpa != null && ` · GPA ${applicant.gpa.toFixed(2)}`}</>}
            onClose={onClose}
            footer={<>
                <Button variant="primary" onClick={save} disabled={actions.saveApplicant.isPending}>{isNew ? "Add applicant" : "Save changes"}</Button>
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                {!isNew && <span className="ml-auto"><ConfirmDelete label="Delete"
                    confirmText={`Delete ${applicant.name}? Any locks on them are removed too.`}
                    onConfirm={async () => { await actions.removeApplicant.mutateAsync(applicant.applicant_id); onClose(); }} /></span>}
            </>}
        >
            <datalist id="course-codes">{courseIds.map((c) => <option key={c} value={c} />)}</datalist>

            <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3">
                <Field label="Name" error={tried ? errors.name : null}>
                    {(fid, d) => <TextInput id={fid} aria-describedby={d} value={name} invalid={tried && !!errors.name} onChange={(e) => setName(e.target.value)} />}
                </Field>
                <Field label="Student ID" error={tried ? errors.id : null} hint={isNew ? undefined : "IDs can't be changed."}>
                    {(fid, d) => <TextInput id={fid} aria-describedby={d} value={id} disabled={!isNew} invalid={tried && !!errors.id} onChange={(e) => setId(e.target.value)} />}
                </Field>
            </div>
            <Field label="Email">
                {(fid) => <TextInput id={fid} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Optional" />}
            </Field>

            <fieldset className="m-0 p-0 border-0 flex flex-col gap-2">
                <legend className="text-[13px] font-medium mb-1.5">Applying for</legend>
                <div className="flex gap-5">
                    {(["LA", "UTA"] as Position[]).map((p) => (
                        <label key={p} className="inline-flex items-center gap-2">
                            <input type="checkbox" className="w-4 h-4 accent-accent" checked={positions.includes(p)}
                                onChange={(e) => setPositions(e.target.checked ? [...positions, p].sort() as Position[] : positions.filter((x) => x !== p))} />
                            {p === "LA" ? "Learning Assistant (LA)" : "Undergraduate TA (UTA)"}
                        </label>
                    ))}
                </div>
                {tried && errors.positions && <span className="text-xs text-danger">{errors.positions}</span>}
                <div className="grid grid-cols-2 gap-3 mt-1">
                    <Field label="Term">
                        {(fid) => <SelectInput id={fid} value={term} onChange={(e) => setTerm(e.target.value as Term)}>
                            {TERMS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                        </SelectInput>}
                    </Field>
                    <Field label="Year" error={tried ? errors.year : null}>
                        {(fid) => <TextInput id={fid} inputMode="numeric" value={year} invalid={tried && !!errors.year} onChange={(e) => setYear(e.target.value)} />}
                    </Field>
                </div>
            </fieldset>

            <fieldset className="m-0 p-0 border-0 flex flex-col gap-2">
                <legend className="text-[13px] font-medium mb-1.5">Course choices</legend>
                <div className="grid grid-cols-3 gap-2">
                    {["1st", "2nd", "3rd"].map((label, i) => (
                        <label key={label} className="flex flex-col gap-1">
                            <span className="text-xs text-ink-3">{label} choice</span>
                            <SelectInput value={choices[i]} invalid={tried && !!errors.choices}
                                onChange={(e) => setChoices(choices.map((c, j) => (j === i ? e.target.value : c)))}>
                                <option value="">None</option>
                                {courseIds.map((c) => <option key={c} value={c}>{c}</option>)}
                                {choices[i] && !courseIds.includes(choices[i]) && <option value={choices[i]}>{choices[i]} (not offered)</option>}
                            </SelectInput>
                        </label>
                    ))}
                </div>
                {tried && errors.choices && <span className="text-xs text-danger">{errors.choices}</span>}
            </fieldset>

            <RepeatRows<PastCourseJ>
                legend="Courses taken"
                columns="minmax(0,1fr) 92px 96px 76px"
                items={transcript}
                onChange={setTranscript}
                blank={() => ({ course_id: "", grade: "A", term: "FALL", year: lastYear })}
                addLabel="Add a course"
                empty="No courses yet. They can only be placed in courses they've passed."
                render={(t, update, i) => <>
                    <input list="course-codes" aria-label={`Course ${i + 1} code`} value={t.course_id} placeholder="CSCI 1111"
                        onChange={(e) => update({ course_id: e.target.value })}
                        className="w-full min-w-0 min-h-10 px-3 rounded-md border border-control bg-surface" />
                    <select aria-label={`Course ${i + 1} grade`} value={t.grade} onChange={(e) => update({ grade: e.target.value as PastCourseJ["grade"] })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface">
                        {GRADES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                    </select>
                    <select aria-label={`Course ${i + 1} term`} value={t.term} onChange={(e) => update({ term: e.target.value as Term })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface">
                        {TERMS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                    </select>
                    <input aria-label={`Course ${i + 1} year`} inputMode="numeric" value={t.year} onChange={(e) => update({ year: e.target.value as unknown as number })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface tabular-nums" />
                </>}
            />
            {tried && errors.transcript && <span className="text-xs text-danger -mt-3">{errors.transcript}</span>}
            {transcript.length > 0 && (
                <span className="text-xs text-ink-3 -mt-3">
                    {transcript.filter((t) => t.grade !== "IN_PROGRESS").length} graded · {transcript.map((t) => `${t.course_id || "?"} ${gradeLabel(t.grade)}`).join(", ")}
                </span>
            )}

            <MeetingRows label="Busy times (their own classes)" addLabel="Add a busy time" value={busy} onChange={setBusy} />

            <RepeatRows<TeachingJ>
                legend="Prior TA roles"
                columns="76px minmax(0,1fr) 96px 76px"
                items={experience}
                onChange={setExperience}
                blank={() => ({ course_id: "", position: "LA", term: "FALL", year: lastYear, supervisor_rating: null })}
                addLabel="Add a role"
                render={(x, update, i) => <>
                    <select aria-label={`Role ${i + 1} position`} value={x.position} onChange={(e) => update({ position: e.target.value as Position })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface">
                        <option value="LA">LA</option><option value="UTA">UTA</option>
                    </select>
                    <input list="course-codes" aria-label={`Role ${i + 1} course`} value={x.course_id} placeholder="CSCI 1111"
                        onChange={(e) => update({ course_id: e.target.value })}
                        className="w-full min-w-0 min-h-10 px-3 rounded-md border border-control bg-surface" />
                    <select aria-label={`Role ${i + 1} term`} value={x.term} onChange={(e) => update({ term: e.target.value as Term })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface">
                        {TERMS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                    <input aria-label={`Role ${i + 1} year`} inputMode="numeric" value={x.year} onChange={(e) => update({ year: e.target.value as unknown as number })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface tabular-nums" />
                </>}
            />
            {tried && errors.experience && <span className="text-xs text-danger -mt-3">{errors.experience}</span>}

            <RepeatRows<RecommendationJ>
                legend="Recommendations"
                columns="minmax(0,1fr) 96px minmax(0,0.8fr)"
                items={recs}
                onChange={setRecs}
                blank={() => ({ faculty_name: "", strength: 4, course_id: null, note: "" })}
                addLabel="Add a recommendation"
                render={(r, update, i) => <>
                    <input aria-label={`Recommendation ${i + 1} from`} value={r.faculty_name} placeholder="Prof. Kim"
                        onChange={(e) => update({ faculty_name: e.target.value })}
                        className="w-full min-w-0 min-h-10 px-3 rounded-md border border-control bg-surface" />
                    <select aria-label={`Recommendation ${i + 1} strength`} value={r.strength} onChange={(e) => update({ strength: Number(e.target.value) })}
                        className="w-full min-w-0 min-h-10 px-2 rounded-md border border-control bg-surface">
                        {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n} of 5</option>)}
                    </select>
                    <input list="course-codes" aria-label={`Recommendation ${i + 1} course`} value={r.course_id ?? ""} placeholder="Course (optional)"
                        onChange={(e) => update({ course_id: e.target.value })}
                        className="w-full min-w-0 min-h-10 px-3 rounded-md border border-control bg-surface" />
                </>}
            />
            {tried && errors.recs && <span className="text-xs text-danger -mt-3">{errors.recs}</span>}

            <Field label="Skills" hint="Comma-separated, e.g. python, git">
                {(fid, d) => <TextInput id={fid} aria-describedby={d} value={skills} onChange={(e) => setSkills(e.target.value)} />}
            </Field>

            {!isNew && applicant.application === null && (
                <p className="m-0 text-[13px] text-warn">This person had no application on file. Saving creates one with the choices above.</p>
            )}
            {tried && hasError && <p role="alert" className="m-0 text-[13px] text-danger">Fix the problems above to save.</p>}
            {error && <p role="alert" className="m-0 text-[13px] text-danger">{error.message}</p>}
        </EditorPanel>
    );
}
