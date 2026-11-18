import type { ReactNode } from "react";
import { Link } from "react-router";

/** A router link that looks like a button (for navigation, not actions). */
export function ButtonLink({
    to, children, variant = "secondary", size = "md",
}: { to: string; children: ReactNode; variant?: "primary" | "secondary" | "ghost"; size?: "md" | "sm" }) {
    const look = {
        primary: "bg-accent text-white border border-accent hover:bg-accent-hover",
        secondary: "bg-surface text-ink border border-control hover:bg-canvas",
        ghost: "bg-transparent text-ink-2 border border-transparent hover:bg-line-soft",
    }[variant];
    const sizing = size === "sm" ? "min-h-8 px-2.5 text-[13px]" : "min-h-10 px-3.5";
    return (
        <Link to={to} className={`inline-flex items-center justify-center gap-2 rounded-md font-medium no-underline ${sizing} ${look}`}>
            {children}
        </Link>
    );
}
