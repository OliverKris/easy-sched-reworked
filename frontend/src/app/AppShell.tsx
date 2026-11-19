import { useEffect, useState, type ComponentType } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { Hint, Spinner } from "../design/components";
import {
    BookIcon, ChecklistIcon, ChevronsIcon, GridIcon, Logo, MonitorIcon, MoonIcon, SlidersIcon, SunIcon, TransferIcon, UsersIcon,
} from "../design/icons";
import { getConfig } from "../lib/api";
import { useTheme, type ThemePref } from "../lib/theme";
import { useWorkspace } from "./workspace";

interface NavItem { to: string; label: string; icon: ComponentType<{ className?: string }> }

/* Grouped by the coordinator's workflow: set the term up, build the schedule, take it out. */
const NAV: { group: string; items: NavItem[] }[] = [
    {
        group: "Set up",
        items: [
            { to: "/start", label: "Getting started", icon: ChecklistIcon },
            { to: "/rules", label: "Rules", icon: SlidersIcon },
            { to: "/courses", label: "Courses & sections", icon: BookIcon },
            { to: "/applicants", label: "Applicants", icon: UsersIcon },
        ],
    },
    { group: "Schedule", items: [{ to: "/assign", label: "Assignments", icon: GridIcon }] },
    { group: "Data", items: [{ to: "/data", label: "Import & export", icon: TransferIcon }] },
];

const NEW_WORKSPACE = "__new__";

/** Sidebar + content. New browsers (no workspaces yet) are sent to the welcome screen. */
export function AppShell() {
    const { status, error, workspaces, current, open } = useWorkspace();
    const navigate = useNavigate();
    const location = useLocation();

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
                className="flex-[1_1_232px] md:max-w-58 box-border md:sticky md:top-0 md:h-screen px-3 py-4 border-b md:border-b-0 md:border-r border-line bg-sidebar flex flex-col gap-4"
            >
                <Link to="/start" className="flex items-center gap-2.5 px-2 h-8 text-ink no-underline">
                    <Logo size={20} />
                    <span className="font-semibold text-[14px] tracking-tight">Easy-Sched</span>
                </Link>

                <label className="relative block">
                    <span className="sr-only">Workspace</span>
                    <select
                        value={current.id}
                        onChange={(e) => {
                            if (e.target.value === NEW_WORKSPACE) navigate("/welcome");
                            else open(e.target.value);
                        }}
                        className="appearance-none w-full h-9 pl-2.5 pr-8 rounded-md border border-line bg-surface text-ink text-[13px] font-medium shadow-sm cursor-pointer hover:border-control focus:outline-none focus:ring-3 focus:ring-accent/20 focus:border-accent"
                    >
                        {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                        <option value={NEW_WORKSPACE}>+ New workspace…</option>
                    </select>
                    <ChevronsIcon className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-3 pointer-events-none" />
                </label>

                <div className="flex flex-col gap-4">
                    {NAV.map(({ group, items }) => (
                        <div key={group} className="flex flex-col gap-px">
                            <span className="px-2 pb-1 text-[11px] font-medium uppercase tracking-[0.06em] text-ink-3">{group}</span>
                            {items.map((item) => (
                                <NavLink
                                    key={item.to}
                                    to={item.to}
                                    className={({ isActive }) =>
                                        "group relative flex items-center gap-2.5 h-8 px-2 rounded-md no-underline text-[13.5px] transition-colors duration-150 " +
                                        (isActive ? "bg-line-soft text-ink font-medium" : "text-ink-2 hover:bg-line-soft/70 hover:text-ink")
                                    }
                                >
                                    {({ isActive }) => (
                                        <>
                                            {isActive && <span aria-hidden="true" className="absolute -left-3 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />}
                                            <item.icon className={isActive ? "text-accent" : "text-ink-3 group-hover:text-ink-2"} />
                                            <span className="flex-1">{item.label}</span>
                                            {item.to === "/start" && <SetupProgress />}
                                        </>
                                    )}
                                </NavLink>
                            ))}
                        </div>
                    ))}
                </div>

                <div className="mt-auto flex flex-col gap-3">
                    <ThemeToggle />
                    <div className="px-2 flex items-center gap-1.5 text-[12px] text-ink-3">
                        <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-accent" />
                        {current.sample ? "Sample data · this browser" : "Saved in this browser"}
                    </div>
                </div>
            </nav>

            <main className="flex-[999_1_560px] min-w-0 box-border px-6 md:px-10 pt-8 pb-16">
                <div className="max-w-[1280px] mx-auto">
                    <DemoNotice />
                    {/* Keyed on the route so each screen eases in when you navigate. */}
                    <div key={location.pathname} className="animate-enter">
                        <Outlet />
                    </div>
                </div>
            </main>
        </div>
    );
}

function SetupProgress() {
    const { current } = useWorkspace();
    if (!current) return null;
    const done = Object.values(current.setup).filter(Boolean).length;
    if (done === 4) return null;
    return (
        <span className="text-[11px] font-medium text-ink-3 tabular-nums px-1.5 rounded bg-line-soft group-hover:bg-surface" aria-label={`${done} of 4 steps done`}>
            {done}/4
        </span>
    );
}

const THEMES: { value: ThemePref; label: string; icon: ComponentType<{ className?: string }> }[] = [
    { value: "light", label: "Light", icon: SunIcon },
    { value: "dark", label: "Dark", icon: MoonIcon },
    { value: "system", label: "System", icon: MonitorIcon },
];

function ThemeToggle() {
    const [pref, setPref] = useTheme();
    return (
        <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 p-0.5 rounded-md bg-line-soft border border-line">
            {THEMES.map((t) => {
                const on = pref === t.value;
                return (
                    <button
                        key={t.value}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        title={t.label}
                        onClick={() => setPref(t.value)}
                        className={
                            "h-7 inline-flex items-center justify-center gap-1.5 rounded text-[12px] cursor-pointer transition-all duration-150 " +
                            (on ? "bg-surface text-ink shadow-sm" : "text-ink-3 hover:text-ink")
                        }
                    >
                        <t.icon />
                        <span className="sr-only">{t.label}</span>
                    </button>
                );
            })}
        </div>
    );
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
            <div className="flex flex-col items-center gap-3 text-center animate-fade">
                <Logo size={28} />
                <Spinner label={slow ? "Waking up the server…" : "Loading"} />
                {slow && <p className="m-0 text-[13px] text-ink-3 max-w-xs animate-fade">The demo sleeps when nobody is using it. This takes up to a minute the first time.</p>}
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
