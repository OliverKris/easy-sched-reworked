import type { ApplicantSummary } from "../types";
import { EmptyState, Pill } from "./ui";

export function ApplicantsView({ applicants }: { applicants: ApplicantSummary[] }) {
    return(
        <div>
            <h2 className="font-display text-xl font-semibold mt-1 mb-1">Applicant Pool</h2>
            <p className="text-ink-soft text-[13px] mb-5">
                Everyone with a live application this cycle. GPA and skills are pulled from their record on file.
            </p>
            <table className="w-full border-collapse text-[13px]">
                <thead>
                    <tr>
                        {["ID", "Name", "GPA", "Applying for", "Preferences", "Skills"].map((h) => (
                            <th
                                key={h}
                                className="text-left font-mono text-[10.5px] uppercase tracking-wide text-ink-soft border-b border-ink px-2.5 py-2"
                            >
                                {h}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {/* No applicants */}
                    {applicants.length === 0 && (
                        <tr>
                            <td colSpan={6}>
                                <EmptyState>No applicants in this dataset.</EmptyState>
                            </td>
                        </tr>
                    )}
                    {/* Applicant data row */}
                    {applicants.map((a) => (
                        <tr key={a.applicant_id} className="hover:bg-applicant-hover">
                            {/* id */}
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                <span className="font-mono text-[11px]">{a.applicant_id}</span>
                            </td>
                            {/* name + email */}
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                <b className="font-semibold">{a.name}</b>
                                <br/>
                                <span className="text-ink-soft text-[11.5px]">{a.email}</span>
                            </td>
                            {/* gpa */}
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                {a.gpa !== null ? a.gpa.toFixed(2) : "-"}
                            </td>
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                {a.position_types.join(" / ") || "-"}
                            </td>
                            {/* course ranking */}
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                {a.ranked_preferences.length
                                    ? a.ranked_preferences.map((p) => `#${p.rank} ${p.course_id}`).join(", ")
                                    : <i>no ranking</i>
                                }
                            </td>
                            {/* skills */}
                            <td className="px-2.5 py-2 border-b border-line align-top">
                                {a.skills.length
                                    ? a.skills.map((sk) => <Pill key={sk} tone="brass">{sk}</Pill>)
                                    : "-"
                                }
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}