import { NavLink, Outlet } from "react-router";
import { Logo } from "../design/icons";
import { WORKSPACES, useWorkspace } from "./workspace";
import type { DatasetKey } from "../types";

const NAV = [
    { to: "/assign", label: "Assignments" },
    { to: "/courses", label: "Courses & sections" },
    { to: "/applicants", label: "Applicants" },
    { to: "/eligibility", label: "Eligibility" },
];

/** Sidebar + content. On narrow screens the sidebar wraps above the content. */
export function AppShell() {
    const { dataset, setDataset } = useWorkspace();

    return (
        <div className="flex flex-wrap min-h-screen">
            <nav
                aria-label="Main"
                className="flex-[1_1_220px] md:max-w-62 box-border px-4 py-5 border-b md:border-b-0 md:border-r border-line bg-surface flex flex-col gap-5"
            >
                <div className="flex items-center gap-2.5 px-2">
                    <Logo />
                    <span className="font-semibold text-[15px] tracking-tight">Easy-Sched</span>
                </div>

                <label className="flex flex-col gap-1">
                    <span className="px-1 text-xs text-ink-3">Workspace</span>
                    <select
                        value={dataset}
                        onChange={(e) => setDataset(e.target.value as DatasetKey)}
                        className="min-h-11 px-2.5 rounded-md border border-line bg-canvas text-ink"
                    >
                        {WORKSPACES.map((w) => (
                            <option key={w.key} value={w.key}>{w.name}</option>
                        ))}
                    </select>
                    <span className="px-1 text-xs text-ink-3">{WORKSPACES.find((w) => w.key === dataset)?.detail}</span>
                </label>

                <div className="flex flex-col gap-0.5">
                    {NAV.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                "flex items-center min-h-9 px-2.5 rounded-md no-underline " +
                                (isActive ? "bg-accent-soft text-ink font-medium" : "text-ink-2 hover:bg-line-soft")
                            }
                        >
                            {item.label}
                        </NavLink>
                    ))}
                </div>

                <div className="mt-auto px-2.5 text-xs text-ink-3">Department coordinator</div>
            </nav>

            <main className="flex-[999_1_560px] min-w-0 box-border px-8 pt-7 pb-14">
                <Outlet />
            </main>
        </div>
    );
}
