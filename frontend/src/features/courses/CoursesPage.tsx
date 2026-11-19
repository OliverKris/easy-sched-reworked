import { useMemo, useState } from "react";
import { useCourses, useEditActions } from "../../api/hooks";
import { useWorkspace } from "../../app/workspace";
import { Badge, Button, Code, EmptyState, Hint, PageHeader, Spinner } from "../../design/components";
import { ConfirmDelete, EditorPanel, Field, MeetingRows, SelectInput, TextInput } from "../../design/forms";
import { ButtonLink } from "../../design/links";
import { formatMeetings, fromPatterns, patternProblem, termLabel, TERMS, toPatterns, type MeetingPattern } from "../../lib/schedule";
import type { CourseJ, CourseRecord, SectionJ, SectionRecord, Term } from "../../types";

type Selection =
    | { kind: "course"; courseId: string | null }
    | { kind: "section"; courseId: string; sectionId: number | null };

export function CoursesPage() {
    const { dataset } = useWorkspace();
    const courses = useCourses(dataset);
    const [selection, setSelection] = useState<Selection | null>(null);
    const [query, setQuery] = useState("");

    const list = useMemo(() => courses.data ?? [], [courses.data]);
    const visible = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return list;
        return list.filter((c) => c.course_id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q)
            || c.sections.some((s) => s.instructor.toLowerCase().includes(q)));
    }, [list, query]);
    const sectionCount = list.reduce((n, c) => n + c.sections.length, 0);

    return (
        <div className="max-w-[1240px] flex flex-col gap-5">
            <PageHeader
                title="Courses & sections"
                description="Each section's meeting times and how many LAs and UTAs it needs."
                actions={list.length > 0 ? <>
                    <ButtonLink to="/courses/import">Upload a spreadsheet</ButtonLink>
                    <Button variant="primary" onClick={() => setSelection({ kind: "course", courseId: null })}>Add course</Button>
                </> : undefined}
            />

            {courses.error && <p role="alert" className="m-0 text-danger">Couldn't load courses ({courses.error.message}).</p>}
            {courses.isPending && <Spinner />}

            {courses.data && list.length === 0 && !selection && (
                <EmptyState
                    title="No courses yet"
                    action={<div className="flex flex-wrap gap-2">
                        <ButtonLink to="/courses/import" variant="primary">Upload a spreadsheet</ButtonLink>
                        <Button onClick={() => setSelection({ kind: "course", courseId: null })}>Add a course by hand</Button>
                    </div>}
                >
                    Upload your course schedule as a CSV (there's a template to fill in), or add courses one at a time.
                </EmptyState>
            )}

            {(list.length > 0 || selection) && (
                <div className="flex flex-wrap gap-5 items-start">
                    <section aria-label="Courses" className="flex-[999_1_520px] min-w-0 flex flex-col gap-4">
                        {list.length > 0 && (
                            <>
                                <Hint id="courses-intro">
                                    Click a section to edit its times and staffing. Changes apply to the next assignment run.
                                </Hint>
                                <div className="flex flex-wrap items-center justify-between gap-3">
                                    <label className="flex-[1_1_260px] max-w-90 flex">
                                        <span className="sr-only">Search courses</span>
                                        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
                                            placeholder="Search courses or instructors"
                                            className="flex-1 h-9 px-2.5 rounded-md border border-control bg-surface text-ink shadow-sm focus:outline-none focus:border-accent focus:ring-3 focus:ring-accent/20" />
                                    </label>
                                    <span className="text-[13px] text-ink-3">{list.length} courses · {sectionCount} sections</span>
                                </div>
                            </>
                        )}
                        {visible.map((course) => (
                            <CourseCard key={course.course_id} course={course} selection={selection} onSelect={setSelection} />
                        ))}
                    </section>

                    {selection && (
                        <Editor
                            key={selection.kind === "course" ? `c-${selection.courseId}` : `s-${selection.sectionId}-${selection.courseId}`}
                            selection={selection}
                            courses={list}
                            onClose={() => setSelection(null)}
                            onSelect={setSelection}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

function CourseCard({ course, selection, onSelect }: {
    course: CourseRecord; selection: Selection | null; onSelect: (s: Selection) => void;
}) {
    const courseSelected = selection?.kind === "course" && selection.courseId === course.course_id;
    return (
        <div className={`bg-surface border rounded-lg ${courseSelected ? "border-accent" : "border-line"}`}>
            <div className="flex flex-wrap justify-between items-center gap-3 px-4 py-3 border-b border-line-soft">
                <div className="flex flex-col min-w-0">
                    <h2 className="m-0 text-sm font-semibold"><Code>{course.course_id}</Code> <span className="font-normal text-ink-2">{course.title}</span></h2>
                    {course.skills.length > 0 && <span className="text-xs text-ink-3">{course.skills.join(", ")}</span>}
                </div>
                <div className="flex gap-2">
                    <Button size="sm" variant="ghost" onClick={() => onSelect({ kind: "course", courseId: course.course_id })}>Edit course</Button>
                    <Button size="sm" onClick={() => onSelect({ kind: "section", courseId: course.course_id, sectionId: null })}>Add section</Button>
                </div>
            </div>
            {course.sections.length === 0 ? (
                <p className="m-0 px-4 py-3 text-[13px] text-ink-3">No sections yet. A course needs at least one section to be staffed.</p>
            ) : (
                <ul className="list-none m-0 p-0">
                    {course.sections.map((s) => (
                        <SectionRow key={s.id} section={s}
                            selected={selection?.kind === "section" && selection.sectionId === s.id}
                            onSelect={() => onSelect({ kind: "section", courseId: course.course_id, sectionId: s.id })} />
                    ))}
                </ul>
            )}
        </div>
    );
}

function SectionRow({ section, selected, onSelect }: { section: SectionRecord; selected: boolean; onSelect: () => void }) {
    const labs = section.labs.length;
    return (
        <li className="border-b border-line-soft last:border-b-0">
            <button type="button" onClick={onSelect} aria-pressed={selected}
                className={`w-full text-left grid grid-cols-[minmax(0,140px)_minmax(0,1fr)_auto] gap-x-4 gap-y-0.5 px-4 py-2.5 cursor-pointer ${selected ? "bg-accent-tint" : "hover:bg-canvas"}`}>
                <span className="flex flex-col">
                    <span className="font-medium">Section {section.section_number}</span>
                    <span className="text-xs text-ink-3">{termLabel(section.term)} {section.year}</span>
                </span>
                <span className="flex flex-col min-w-0">
                    <span className="text-[13px] truncate">{formatMeetings(section.lecture_meetings)}{section.instructor ? ` · ${section.instructor}` : ""}</span>
                    <span className="text-xs text-ink-3 truncate">
                        {labs === 0 ? "No labs" : `${labs} lab${labs === 1 ? "" : "s"}: ${section.labs.map((l) => formatMeetings(l.meetings)).join(", ")}`}
                    </span>
                </span>
                <span className="flex items-center gap-1.5 self-center">
                    {section.la_count > 0 && <Badge>{section.la_count} LA</Badge>}
                    {section.uta_count > 0 && <Badge>{section.uta_count} UTA</Badge>}
                </span>
            </button>
        </li>
    );
}

function Editor({ selection, courses, onClose, onSelect }: {
    selection: Selection; courses: CourseRecord[]; onClose: () => void; onSelect: (s: Selection) => void;
}) {
    if (selection.kind === "course") {
        const course = courses.find((c) => c.course_id === selection.courseId) ?? null;
        return <CourseEditor course={course} existingIds={courses.map((c) => c.course_id)} onClose={onClose}
            onSaved={(id, isNew) => onSelect(isNew ? { kind: "section", courseId: id, sectionId: null } : { kind: "course", courseId: id })} />;
    }
    const course = courses.find((c) => c.course_id === selection.courseId);
    if (!course) return null;
    const section = course.sections.find((s) => s.id === selection.sectionId) ?? null;
    const allSections = courses.flatMap((c) => c.sections);
    return <SectionEditor course={course} section={section} allSections={allSections} onClose={onClose}
        onSaved={(id) => onSelect({ kind: "section", courseId: course.course_id, sectionId: id })} />;
}

function splitTags(text: string): string[] {
    return [...new Set(text.split(/[;,]/).map((t) => t.trim().toLowerCase()).filter(Boolean))].sort();
}

function CourseEditor({ course, existingIds, onClose, onSaved }: {
    course: CourseRecord | null; existingIds: string[]; onClose: () => void; onSaved: (id: string, isNew: boolean) => void;
}) {
    const { dataset } = useWorkspace();
    const actions = useEditActions(dataset);
    const [code, setCode] = useState(course?.course_id ?? "");
    const [title, setTitle] = useState(course?.title ?? "");
    const [skills, setSkills] = useState(course?.skills.join(", ") ?? "");
    const [tried, setTried] = useState(false);
    const isNew = course === null;

    const codeError = !code.trim() ? "Enter a course code" : isNew && existingIds.includes(code.trim()) ? "That course already exists" : null;
    const titleError = !title.trim() ? "Enter a title" : null;
    const error = actions.saveCourse.error ?? actions.removeCourse.error;

    const save = async () => {
        setTried(true);
        if (codeError || titleError) return;
        const payload: CourseJ = { course_id: code.trim(), title: title.trim(), description: course?.description ?? "", skills: splitTags(skills) };
        await actions.saveCourse.mutateAsync(payload);
        onSaved(payload.course_id, isNew);
    };

    return (
        <EditorPanel
            title={isNew ? "New course" : course.course_id}
            subtitle={isNew ? "After saving, you'll add its first section." : course.title}
            onClose={onClose}
            footer={<>
                <Button variant="primary" onClick={save} disabled={actions.saveCourse.isPending}>{isNew ? "Save and add a section" : "Save course"}</Button>
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                {!isNew && <span className="ml-auto"><ConfirmDelete label="Delete course"
                    confirmText={`Delete ${course.course_id} and its ${course.sections.length} section(s)?`}
                    onConfirm={async () => { await actions.removeCourse.mutateAsync(course.course_id); onClose(); }} /></span>}
            </>}
        >
            <Field label="Course code" hint={isNew ? "As it appears in your catalog, e.g. CSCI 1111. Can't be changed later." : "Course codes can't be changed."}
                error={tried ? codeError : null}>
                {(id, d) => <TextInput id={id} aria-describedby={d} value={code} disabled={!isNew} invalid={tried && !!codeError}
                    onChange={(e) => setCode(e.target.value)} placeholder="CSCI 1111" />}
            </Field>
            <Field label="Title" error={tried ? titleError : null}>
                {(id, d) => <TextInput id={id} aria-describedby={d} value={title} invalid={tried && !!titleError}
                    onChange={(e) => setTitle(e.target.value)} placeholder="Introduction to Programming" />}
            </Field>
            <Field label="Skill tags" hint="Comma-separated. Applicants with matching skills score a little higher.">
                {(id, d) => <TextInput id={id} aria-describedby={d} value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="python, recursion" />}
            </Field>
            {error && <p role="alert" className="m-0 text-[13px] text-danger">{error.message}</p>}
        </EditorPanel>
    );
}

interface LabRow extends MeetingPattern { id?: string }

function defaultTermYear(sections: SectionRecord[]): { term: Term; year: number } {
    const counts = new Map<string, number>();
    for (const s of sections) counts.set(`${s.term}|${s.year}`, (counts.get(`${s.term}|${s.year}`) ?? 0) + 1);
    const top = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0];
    if (top) {
        const [term, year] = top.split("|");
        return { term: term as Term, year: Number(year) };
    }
    return { term: "FALL", year: new Date().getFullYear() };
}

function SectionEditor({ course, section, allSections, onClose, onSaved }: {
    course: CourseRecord; section: SectionRecord | null; allSections: SectionRecord[];
    onClose: () => void; onSaved: (id: number) => void;
}) {
    const { dataset } = useWorkspace();
    const actions = useEditActions(dataset);
    const isNew = section === null;
    const defaults = defaultTermYear(allSections);
    const nextNumber = String(Math.max(9, ...course.sections.map((s) => Number(s.section_number) || 0)) + 1);

    const [number, setNumber] = useState(section?.section_number ?? nextNumber);
    const [term, setTerm] = useState<Term>(section?.term ?? defaults.term);
    const [year, setYear] = useState(String(section?.year ?? defaults.year));
    const [instructor, setInstructor] = useState(section?.instructor ?? "");
    const [lecture, setLecture] = useState<MeetingPattern[]>(section ? toPatterns(section.lecture_meetings) : [{ days: [], start: "", end: "" }]);
    const [labs, setLabs] = useState<LabRow[]>(
        section ? section.labs.flatMap((l) => toPatterns(l.meetings).map((p) => ({ ...p, id: l.lab_id }))) : [],
    );
    const [laCount, setLaCount] = useState(String(section?.la_count ?? 2));
    const [utaCount, setUtaCount] = useState(String(section?.uta_count ?? 1));
    const [laAttend, setLaAttend] = useState(section?.la_must_attend_lecture ?? false);
    const [utaAttend, setUtaAttend] = useState(section?.uta_must_attend_lecture ?? false);
    const [tried, setTried] = useState(false);

    const la = Number(laCount), uta = Number(utaCount);
    const errors = {
        number: !number.trim() ? "Enter a section number" : null,
        year: !/^\d{4}$/.test(year) ? "Enter a 4-digit year" : null,
        counts: !Number.isInteger(la) || !Number.isInteger(uta) || la < 0 || uta < 0 ? "Use whole numbers"
            : la + uta === 0 ? "A section needs at least one LA or UTA" : null,
        meetings: [...lecture, ...labs].some((p) => patternProblem(p)) ? "Fix the highlighted times" : null,
        labIds: labs.some((l) => !l.id?.trim()) ? "Give each lab a name" : null,
    };
    const hasError = Object.values(errors).some(Boolean);
    const error = actions.addSection.error ?? actions.saveSection.error ?? actions.removeSection.error;

    const save = async () => {
        setTried(true);
        if (hasError) return;
        const labMap = new Map<string, MeetingPattern[]>();
        for (const l of labs) labMap.set(l.id!.trim(), [...(labMap.get(l.id!.trim()) ?? []), l]);
        const payload: SectionJ = {
            course_id: course.course_id, section_number: number.trim(), term, year: Number(year), instructor: instructor.trim(),
            lecture_meetings: fromPatterns(lecture, "Lecture"),
            labs: [...labMap.entries()].map(([lab_id, ps]) => ({ lab_id, capacity: null, meetings: fromPatterns(ps, "Lab") })),
            la_count: la, uta_count: uta, la_must_attend_lecture: laAttend, uta_must_attend_lecture: utaAttend,
            la_hours_per_week: section?.la_hours_per_week, uta_hours_per_week: section?.uta_hours_per_week,
        };
        const saved = isNew
            ? await actions.addSection.mutateAsync(payload)
            : await actions.saveSection.mutateAsync({ id: section.id, section: payload });
        onSaved(saved.id);
    };

    return (
        <EditorPanel
            title={isNew ? `New section of ${course.course_id}` : `${course.course_id} · Section ${section.section_number}`}
            subtitle={course.title}
            onClose={onClose}
            footer={<>
                <Button variant="primary" onClick={save} disabled={actions.addSection.isPending || actions.saveSection.isPending}>
                    {isNew ? "Add section" : "Save section"}
                </Button>
                <Button variant="ghost" onClick={onClose}>Cancel</Button>
                {!isNew && <span className="ml-auto"><ConfirmDelete label="Delete section"
                    confirmText={`Delete section ${section.section_number}? Locks on it are removed too.`}
                    onConfirm={async () => { await actions.removeSection.mutateAsync(section.id); onClose(); }} /></span>}
            </>}
        >
            <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-3">
                <Field label="Section" error={tried ? errors.number : null}>
                    {(id, d) => <TextInput id={id} aria-describedby={d} value={number} invalid={tried && !!errors.number} onChange={(e) => setNumber(e.target.value)} />}
                </Field>
                <Field label="Term">
                    {(id) => <SelectInput id={id} value={term} onChange={(e) => setTerm(e.target.value as Term)}>
                        {TERMS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </SelectInput>}
                </Field>
                <Field label="Year" error={tried ? errors.year : null}>
                    {(id, d) => <TextInput id={id} aria-describedby={d} inputMode="numeric" value={year} invalid={tried && !!errors.year} onChange={(e) => setYear(e.target.value)} />}
                </Field>
            </div>
            <Field label="Instructor">
                {(id) => <TextInput id={id} value={instructor} onChange={(e) => setInstructor(e.target.value)} placeholder="Optional" />}
            </Field>

            <MeetingRows label="Lecture" addLabel="Add a lecture time" value={lecture} onChange={setLecture} />

            <MeetingRows
                label="Labs"
                addLabel="Add a lab"
                value={labs}
                onChange={(rows) => setLabs(rows.map((r, i) => ({ ...r, id: r.id ?? `Lab ${i + 1}` })))}
                prefix={(i) => (
                    <input aria-label={`Lab ${i + 1} name`} value={labs[i]?.id ?? ""}
                        onChange={(e) => setLabs(labs.map((l, j) => (j === i ? { ...l, id: e.target.value } : l)))}
                        className={`w-16 min-h-9 px-2 rounded-md border bg-surface text-[13px] ${tried && !labs[i]?.id?.trim() ? "border-danger" : "border-control"}`} />
                )}
            />
            {tried && errors.labIds && <span className="text-xs text-danger -mt-3">{errors.labIds}</span>}
            <p className="m-0 -mt-3 text-xs text-ink-3">An applicant must be free for at least one lab to be placed in this section.</p>

            <fieldset className="m-0 p-0 border-0 flex flex-col gap-3">
                <legend className="text-[13px] font-medium mb-1.5">Staffing</legend>
                <div className="grid grid-cols-2 gap-3">
                    <Field label="LAs needed">
                        {(id) => <TextInput id={id} type="number" min={0} value={laCount} invalid={tried && !!errors.counts} onChange={(e) => setLaCount(e.target.value)} />}
                    </Field>
                    <Field label="UTAs needed">
                        {(id) => <TextInput id={id} type="number" min={0} value={utaCount} invalid={tried && !!errors.counts} onChange={(e) => setUtaCount(e.target.value)} />}
                    </Field>
                </div>
                {tried && errors.counts && <span className="text-xs text-danger">{errors.counts}</span>}
                <label className="inline-flex items-center gap-2"><input type="checkbox" className="w-4 h-4 accent-accent" checked={laAttend} onChange={(e) => setLaAttend(e.target.checked)} />LAs must attend lecture</label>
                <label className="inline-flex items-center gap-2"><input type="checkbox" className="w-4 h-4 accent-accent" checked={utaAttend} onChange={(e) => setUtaAttend(e.target.checked)} />UTAs must attend lecture</label>
            </fieldset>

            {tried && hasError && <p role="alert" className="m-0 text-[13px] text-danger">Fix the problems above to save.</p>}
            {error && <p role="alert" className="m-0 text-[13px] text-danger">{error.message}</p>}
        </EditorPanel>
    );
}
