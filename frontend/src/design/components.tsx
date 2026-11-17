import type { ButtonHTMLAttributes, ReactNode } from "react";

/* Small, owned building blocks. Everything else is composed from these. */

type ButtonVariant = "primary" | "secondary" | "ghost";

const buttonBase =
    "inline-flex items-center justify-center gap-2 rounded-md px-3.5 min-h-10 font-medium " +
    "transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer";

const buttonVariants: Record<ButtonVariant, string> = {
    primary: "bg-accent text-white border border-accent hover:bg-accent-hover",
    secondary: "bg-surface text-ink border border-control hover:bg-canvas",
    ghost: "bg-transparent text-ink-2 border border-transparent hover:bg-line-soft",
};

export function Button({
    variant = "secondary",
    size = "md",
    className = "",
    ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: "md" | "sm" }) {
    const sizing = size === "sm" ? " min-h-8 px-2.5 text-[13px]" : "";
    return <button type="button" className={`${buttonBase} ${buttonVariants[variant]}${sizing} ${className}`} {...props} />;
}

type Tone = "accent" | "warn" | "danger" | "neutral";

const tones: Record<Tone, string> = {
    accent: "bg-accent-soft text-accent-hover",
    warn: "bg-warn-soft text-warn",
    danger: "bg-danger-soft text-danger",
    neutral: "bg-line-soft text-ink-2",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
    return (
        <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${tones[tone]}`}>
            {children}
        </span>
    );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
    return <section className={`bg-surface border border-line rounded-lg ${className}`}>{children}</section>;
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
