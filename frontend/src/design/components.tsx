import { useState, type ButtonHTMLAttributes, type ReactNode } from "react";

/* Small, owned building blocks. Everything else is composed from these. */

type ButtonVariant = "primary" | "secondary" | "ghost";

const buttonBase =
    "inline-flex items-center justify-center gap-2 rounded-md px-3 min-h-9 font-medium text-[13.5px] whitespace-nowrap " +
    "transition-[background-color,border-color,color,box-shadow,transform] duration-150 active:scale-[0.98] " +
    "disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 cursor-pointer select-none no-underline";

const buttonVariants: Record<ButtonVariant, string> = {
    primary: "bg-accent text-on-accent border border-accent hover:bg-accent-hover hover:border-accent-hover shadow-sm",
    secondary: "bg-surface text-ink border border-control hover:bg-line-soft hover:border-ink-3/40 shadow-sm",
    ghost: "bg-transparent text-ink-2 border border-transparent hover:bg-line-soft hover:text-ink",
};

/** Shared look for <Button> and <ButtonLink>. */
// eslint-disable-next-line react-refresh/only-export-components
export function buttonClass(variant: ButtonVariant = "secondary", size: "md" | "sm" = "md") {
    const sizing = size === "sm" ? " min-h-7.5 px-2.5 text-[13px]" : "";
    return `${buttonBase} ${buttonVariants[variant]}${sizing}`;
}

export function Button({
    variant = "secondary",
    size = "md",
    className = "",
    ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "md" | "sm" }) {
    return <button type="button" className={`${buttonClass(variant, size)} ${className}`} {...props} />;
}

/** A keyboard key, for shortcut hints. */
export function Kbd({ children }: { children: ReactNode }) {
    return (
        <kbd className="inline-flex items-center justify-center min-w-5 h-5 px-1 rounded border border-line bg-line-soft font-sans text-[11px] font-medium text-ink-3">
            {children}
        </kbd>
    );
}

type Tone = "accent" | "warn" | "danger" | "neutral";

const tones: Record<Tone, string> = {
    accent: "bg-accent-soft text-accent-hover dark:text-accent",
    warn: "bg-warn-soft text-warn",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-line-soft text-ink-2",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap ${tones[tone]}`}>
            {children}
        </span>
    );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
    return <section className={`bg-surface border border-line rounded-lg shadow-sm ${className}`}>{children}</section>;
}

export function Code({ children }: { children: ReactNode }) {
    return <span className="font-mono text-[13px]">{children}</span>;
}

export function ScoreBar({ value, max }: { value: number; max: number }) {
    const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
    return (
        <span className="block h-1.5 rounded-full bg-line-soft overflow-hidden" aria-hidden="true">
            <span className="block h-full bg-accent" style={{ width: `${pct}%` }} />
        </span>
    );
}

export function VisuallyHidden({ children }: { children: ReactNode }) {
    return <span className="sr-only">{children}</span>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
    return (
        <span role="status" className="inline-flex items-center gap-2 text-ink-3">
            <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14" className="animate-spin">
                <circle cx="7" cy="7" r="5.5" fill="none" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.5" />
                <path d="M12.5 7A5.5 5.5 0 0 0 7 1.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            {label}
        </span>
    );
}

/** A short, dismissible tip. Dismissal is remembered in this browser. */
export function Hint({ id, children }: { id: string; children: ReactNode }) {
    const key = `easy-sched.hint.${id}`;
    const [hidden, setHidden] = useState(() => {
        try { return window.localStorage.getItem(key) === "dismissed"; } catch { return false; }
    });
    if (hidden) return null;
    return (
        <div className="flex items-start gap-3 px-3.5 py-2.5 rounded-lg border border-line bg-surface shadow-sm text-[13px] text-ink-2 animate-fade">
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16" className="flex-none mt-0.5 text-accent">
                <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.4" />
                <path d="M8 7.2v4M8 4.6v.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <div className="flex-1 min-w-0">{children}</div>
            <button
                type="button"
                onClick={() => {
                    setHidden(true);
                    try { window.localStorage.setItem(key, "dismissed"); } catch { /* storage unavailable */ }
                }}
                className="flex-none -m-1 p-1 rounded text-ink-3 hover:text-ink cursor-pointer"
                aria-label="Dismiss tip"
            >
                <svg aria-hidden="true" width="14" height="14" viewBox="0 0 14 14"><path d="M3.5 3.5l7 7M10.5 3.5l-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
            </button>
        </div>
    );
}

/** What a screen shows when there's nothing in it yet: what's missing and the next action. */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
    return (
        <div className="flex flex-col items-start gap-3 px-6 py-10 rounded-lg border border-dashed border-control bg-surface/60">
            <h2 className="m-0 text-[15px] font-semibold">{title}</h2>
            {children && <div className="text-ink-2 max-w-xl">{children}</div>}
            {action}
        </div>
    );
}

/** Page title block shared by every screen. */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
    return (
        <header className="flex flex-wrap justify-between items-end gap-4 pb-5 border-b border-line">
            <div className="flex flex-col gap-1">
                <h1 className="m-0 text-[22px] leading-tight font-semibold">{title}</h1>
                {description && <p className="m-0 text-ink-3 text-[13.5px] max-w-2xl">{description}</p>}
            </div>
            {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
    );
}
