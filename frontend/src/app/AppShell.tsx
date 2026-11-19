import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { Hint, Spinner } from "../design/components";
import { getConfig } from "../lib/api";
import { Logo } from "../design/icons";
import { useWorkspace } from "./workspace";

const NAV = [
    { to: "/start", label: "Getting started" },
    { to: "/rules", label: "Rules" },
    { to: "/courses", label: "Courses & sections" },
    { to: "/applicants", label: "Applicants" },
    { to: "/assign", label: "Assignments" },
    { to: "/data", label: "Import & export" },
];

const NEW_WORKSPACE = "__new__";

/** Sidebar + content. New browsers (no workspaces yet) are sent to the welcome screen. */
export function AppShell() {
    const { status, error, workspaces, current, open } = useWorkspace();
    const navigate = useNavigate();

    if (status === "loading") return <WakingUp />;
    if (status === "error") {
        return (
            <div className="min-h-screen grid place-items-center px-6">
                <p role="alert" className="text-danger max-w-md text-center">
                    Couldn't reach the Easy-Sched server ({error?.message}). If you're running it locally, start the
                    backend on port 8000 and reload.
                </p>
            </div>
        );
    }
    if (status === "empty" || !current) return <Navigate to="/welcome" replace />;

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
                        value={current.id}
                        onChange={(e) => {
                            if (e.target.value === NEW_WORKSPACE) navigate("/welcome");
                            else open(e.target.value);
                        }}
                        className="min-h-11 px-2.5 rounded-md border border-line bg-canvas text-ink"
                    >
                        {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                        <option value={NEW_WORKSPACE}>+ New workspace…</option>
                    </select>
                    {current.sample && <span className="px-1 text-xs text-ink-3">Sample data</span>}
                </label>

                <div className="flex flex-col gap-0.5">
                    {NAV.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            className={({ isActive }) =>
                                "flex items-center justify-between min-h-9 px-2.5 rounded-md no-underline " +
                                (isActive ? "bg-accent-soft text-ink font-medium" : "text-ink-2 hover:bg-line-soft")
                            }
                        >
                            {item.label}
                            {item.to === "/start" && <SetupProgress />}
                        </NavLink>
                    ))}
                </div>

                <div className="mt-auto px-2.5 text-xs text-ink-3">Saved in this browser</div>
            </nav>

            <main className="flex-[999_1_560px] min-w-0 box-border px-8 pt-7 pb-14">
                <DemoNotice />
                <Outlet />
            </main>
        </div>
    );
}

function SetupProgress() {
    const { current } = useWorkspace();
    if (!current) return null;
    const done = Object.values(current.setup).filter(Boolean).length;
    if (done === 4) return null;
    return <span className="text-xs text-ink-3 tabular-nums" aria-label={`${done} of 4 steps done`}>{done}/4</span>;
}

/** Free hosting sleeps when idle; the first request can take ~30 s, so say why we're waiting. */
function WakingUp() {
    const [slow, setSlow] = useState(false);
    useEffect(() => {
        const t = window.setTimeout(() => setSlow(true), 2500);
        return () => window.clearTimeout(t);
    }, []);
    return (
        <div className="min-h-screen grid place-items-center px-6">
            <div className="flex flex-col items-center gap-2 text-center">
                <Spinner label={slow ? "Waking up the server…" : "Loading"} />
                {slow && <p className="text-[13px] text-ink-3 max-w-xs">The demo sleeps when nobody is using it. This takes up to a minute the first time.</p>}
            </div>
        </div>
    );
}

/** On the public demo, storage resets when the server sleeps or redeploys. */
function DemoNotice() {
    const { data } = useQuery({ queryKey: ["config"], queryFn: getConfig, staleTime: Infinity });
    if (!data?.demo_mode) return null;
    return (
        <div className="mb-6">
            <Hint id="demo-server">
                This is a public demo. Workspaces are cleared when the server sleeps, so{" "}
                <Link to="/data">export a workspace file</Link> to keep your work.
            </Hint>
        </div>
    );
}
