import type { ReactNode } from "react";
import { useDataset } from "../api/hooks";
import { ApplicantsView } from "../components/ApplicantsView";
import { EligibilityView } from "../components/EligibilityView";
import { SectionsView } from "../components/SectionsView";
import { Spinner } from "../design/components";
import { useWorkspace } from "./workspace";

/*
  The existing browse views, mounted inside the new shell. They pick up the new
  palette through the remapped legacy tokens; each gets a proper redesign later.
*/

function Page({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div className="max-w-5xl flex flex-col gap-5">
            <h1 className="m-0 text-[26px] font-semibold tracking-tight">{title}</h1>
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
    if (error) {
        return <p className="text-danger">Couldn't reach the API ({error.message}). Is the backend running on port 8000?</p>;
    }
    return <Spinner />;
}

export function CoursesPage() {
    const { data, error } = useData();
    return <Page title="Courses & sections">{data ? <SectionsView sections={data.sections} /> : <Loading error={error} />}</Page>;
}

export function ApplicantsPage() {
    const { data, error } = useData();
    return <Page title="Applicants">{data ? <ApplicantsView applicants={data.applicants} /> : <Loading error={error} />}</Page>;
}

export function EligibilityPage() {
    const { dataset, data, error } = useData();
    return (
        <Page title="Eligibility">
            {data ? <EligibilityView dataset={dataset} sections={data.sections} /> : <Loading error={error} />}
        </Page>
    );
}
