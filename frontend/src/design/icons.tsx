import type React from "react";
/* Inline stroke icons, sized to text. Decorative unless given a label. */

interface IconProps {
    size?: number;
    label?: string;
    className?: string;
}

function a11y(label?: string) {
    return label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const };
}

export function LockIcon({ size = 12, label, className }: IconProps) {
    return (
        <svg width={size} height={size} viewBox="0 0 12 12" className={className} {...a11y(label)}>
            <rect x="2.5" y="5.5" width="7" height="5" rx="1" fill="none" stroke="currentColor" strokeWidth="1.2" />
            <path d="M4 5.5V4a2 2 0 0 1 4 0v1.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
        </svg>
    );
}

export function CheckIcon({ size = 12, label, className }: IconProps) {
    return (
        <svg width={size} height={size} viewBox="0 0 12 12" className={className} {...a11y(label)}>
            <path d="M2.5 6.2 5 8.5l4.5-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    );
}

export function AlertIcon({ size = 16, label, className }: IconProps) {
    return (
        <svg width={size} height={size} viewBox="0 0 16 16" className={className} {...a11y(label)}>
            <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.4" />
            <path d="M8 4.5v4.2M8 11.2v.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
    );
}

export function Logo({ size = 22 }: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 22 22" aria-hidden="true">
            <rect x="1" y="1" width="20" height="20" rx="5" fill="var(--color-accent)" />
            <path d="M6 8h10M6 11h6M6 14h8" stroke="var(--es-on-accent)" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
    );
}

export function CloseIcon({ size = 14, label, className }: IconProps) {
    return (
        <svg width={size} height={size} viewBox="0 0 14 14" className={className} {...a11y(label)}>
            <path d="M3.5 3.5l7 7M10.5 3.5l-7 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
    );
}

/* 16px navigation and UI icons (1.5 stroke). */

function Icon16({ children, size = 16, label, className }: IconProps & { children: React.ReactNode }) {
    return (
        <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
            strokeLinecap="round" strokeLinejoin="round" className={className} {...a11y(label)}>
            {children}
        </svg>
    );
}

export const ChecklistIcon = (p: IconProps) => <Icon16 {...p}><path d="M2.5 4 4 5.5 6.5 3M2.5 10l1.5 1.5L6.5 9M9 4.5h4.5M9 10.5h4.5" /></Icon16>;
export const SlidersIcon = (p: IconProps) => <Icon16 {...p}><path d="M3 4h6M12 4h1M3 8h2M8 8h5M3 12h7M13 12h0" /><circle cx="10.5" cy="4" r="1.5" /><circle cx="6.5" cy="8" r="1.5" /><circle cx="11.5" cy="12" r="1.5" /></Icon16>;
export const BookIcon = (p: IconProps) => <Icon16 {...p}><path d="M3 3.5A1.5 1.5 0 0 1 4.5 2H13v10H4.5A1.5 1.5 0 0 0 3 13.5v-10Z" /><path d="M3 13.5A1.5 1.5 0 0 0 4.5 15H13v-3" /></Icon16>;
export const UsersIcon = (p: IconProps) => <Icon16 {...p}><circle cx="6" cy="5.5" r="2.5" /><path d="M1.5 14c.5-2.5 2.3-4 4.5-4s4 1.5 4.5 4" /><path d="M10.5 3.2a2.5 2.5 0 0 1 0 4.6M12 10.3c1.3.5 2.2 1.8 2.5 3.7" /></Icon16>;
export const GridIcon = (p: IconProps) => <Icon16 {...p}><rect x="2" y="2" width="5" height="5" rx="1" /><rect x="9" y="2" width="5" height="5" rx="1" /><rect x="2" y="9" width="5" height="5" rx="1" /><rect x="9" y="9" width="5" height="5" rx="1" /></Icon16>;
export const TransferIcon = (p: IconProps) => <Icon16 {...p}><path d="M3 5h10M10 2l3 3-3 3M13 11H3M6 8l-3 3 3 3" /></Icon16>;
export const SunIcon = (p: IconProps) => <Icon16 {...p}><circle cx="8" cy="8" r="3" /><path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7" /></Icon16>;
export const MoonIcon = (p: IconProps) => <Icon16 {...p}><path d="M13.5 9.5A5.5 5.5 0 0 1 6.5 2.5a5.5 5.5 0 1 0 7 7Z" /></Icon16>;
export const MonitorIcon = (p: IconProps) => <Icon16 {...p}><rect x="1.5" y="2.5" width="13" height="9" rx="1.5" /><path d="M5.5 14.5h5M8 11.5v3" /></Icon16>;
export const ChevronsIcon = (p: IconProps) => <Icon16 {...p}><path d="M5 6l3-3 3 3M5 10l3 3 3-3" /></Icon16>;
