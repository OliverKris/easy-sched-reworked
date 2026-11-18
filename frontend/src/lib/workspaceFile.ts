import type { WorkspaceFile, WorkspacePart } from "../types";

/* Reading and saving workspace files in the browser. The server does the real
   validation; this only catches "that's not a workspace file" early. */

export interface ReadFile {
    file: WorkspaceFile;
    parts: WorkspacePart[];
    counts: Partial<Record<WorkspacePart, number>>;
}

export async function readWorkspaceFile(f: File): Promise<ReadFile> {
    let data: unknown;
    try {
        data = JSON.parse(await f.text());
    } catch {
        throw new Error(`${f.name} isn't valid JSON.`);
    }
    const file = data as WorkspaceFile;
    if (!file || typeof file !== "object" || file.format !== "easy-sched.workspace") {
        throw new Error(`${f.name} isn't an Easy-Sched workspace file.`);
    }
    if (file.version !== 1) {
        throw new Error(`${f.name} was made by a newer version of Easy-Sched (file version ${String(file.version)}).`);
    }
    const parts: WorkspacePart[] = [];
    const counts: ReadFile["counts"] = {};
    if (file.settings) parts.push("settings");
    if (file.courses || file.sections) {
        parts.push("courses");
        counts.courses = (file.sections ?? []).length;
    }
    if (file.applicants) {
        parts.push("applicants");
        counts.applicants = file.applicants.length;
    }
    if (file.locks) {
        parts.push("locks");
        counts.locks = file.locks.length;
    }
    if (file.schedule) {
        parts.push("schedule");
        counts.schedule = file.schedule.assignments?.length ?? 0;
    }
    return { file, parts, counts };
}

export function downloadText(filename: string, text: string, type = "application/json") {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function safeFilename(name: string): string {
    return name.replace(/[^A-Za-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "") || "workspace";
}

export const PART_LABELS: Record<WorkspacePart, string> = {
    settings: "Rule settings",
    courses: "Courses & sections",
    applicants: "Applicants",
    locks: "Locks & blocks",
    schedule: "Finalized schedule",
};
