import type { ReactNode } from "react";
import { useDataset } from "../api/hooks";
import { EligibilityView } from "../components/EligibilityView";
import { PageHeader, Spinner } from "../design/components";
import { useWorkspace } from "./workspace";

/* The older eligibility browser, inside the new shell. */

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

export function EligibilityPage() {
    const { dataset, data, error } = useData();
    return (
        <Page title="Eligibility">
            {data ? <EligibilityView dataset={dataset} sections={data.sections} /> : <Loading error={error} />}
        </Page>
    );
}
