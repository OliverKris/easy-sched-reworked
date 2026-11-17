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
            <path d="M6 8h10M6 11h6M6 14h8" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
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
