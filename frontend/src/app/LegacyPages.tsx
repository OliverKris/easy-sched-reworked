import type { ReactNode } from "react";
import { useDataset } from "../api/hooks";
import { ApplicantsView } from "../components/ApplicantsView";
import { EligibilityView } from "../components/EligibilityView";
import { SectionsView } from "../components/SectionsView";
import { EmptyState, PageHeader, Spinner } from "../design/components";
import { ButtonLink } from "../design/links";
import { useWorkspace } from "./workspace";

/*
  The browse views for courses, applicants and eligibility, inside the new
  shell. In-app editing for courses and applicants is the next step of the
  rebuild; until then data comes in through workspace files.
*/

function Page({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
    return (
        <div className="max-w-5xl flex flex-col gap-5">
            <PageHeader title={title} description={description} />
            {children}
        </div>
    );
}

function useData() {
    const { dataset } = useWorkspace();
    const query = useDataset(dataset);
    return { dataset, ...query };
}

function Loading({ error }: { error: Error | null }) {
    if (error) return <p role="alert" className="text-danger">Couldn't load this workspace ({error.message}).</p>;
    return <Spinner />;
}

export function CoursesPage() {
    const { data, error } = useData();
    return (
        <Page title="Courses & sections" description="Each section's meeting times and how many LAs and UTAs it needs.">
            {!data ? <Loading error={error} /> : data.sections.length === 0 ? (
                <EmptyState
                    title="No courses yet"
                    action={<ButtonLink to="/data" variant="primary">Import from a workspace file</ButtonLink>}
                >
                    Bring in your courses and sections from a workspace file. You can import just the courses
                    and add applicants separately.
                </EmptyState>
            ) : <SectionsView sections={data.sections} />}
        </Page>
    );
}

export function ApplicantsPage() {
    const { data, error } = useData();
    return (
        <Page title="Applicants" description="Transcripts, schedules, experience and ranked course choices.">
            {!data ? <Loading error={error} /> : data.applicants.length === 0 ? (
                <EmptyState
                    title="No applicants yet"
                    action={<ButtonLink to="/data" variant="primary">Import from a workspace file</ButtonLink>}
                >
                    Bring in applicants from a workspace file. You can import just the applicants and keep your
                    existing courses and rules.
                </EmptyState>
            ) : <ApplicantsView applicants={data.applicants} />}
        </Page>
    );
}

export function EligibilityPage() {
    const { dataset, data, error } = useData();
    return (
        <Page title="Eligibility">
            {data ? <EligibilityView dataset={dataset} sections={data.sections} /> : <Loading error={error} />}
        </Page>
    );
}
