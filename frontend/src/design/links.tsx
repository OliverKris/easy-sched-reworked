import type { ReactNode } from "react";
import { Link } from "react-router";
import { buttonClass } from "./components";

/** A router link that looks like a button (for navigation, not actions). */
export function ButtonLink({
    to, children, variant = "secondary", size = "md",
}: { to: string; children: ReactNode; variant?: "primary" | "secondary" | "ghost"; size?: "md" | "sm" }) {
    return <Link to={to} className={buttonClass(variant, size)}>{children}</Link>;
}
