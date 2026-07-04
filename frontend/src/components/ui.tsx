import type { ReactNode } from "react";

export function Pill({ children, tone = "forest" }: { children: ReactNode; tone?: "forest" | "brass" | "brick" }) {
    const tones = {
        forest: "bg-forest-soft text-forest",
        brass: "bg-brass-soft text-brass",
        brick: "bg-brick-soft text-brick",
    };
    return (
        <span className={`inline-block rounded-full px-2 py-0.5 font-mono text-[11px] mr-1 ${tones[tone]}`}>
            {children}
        </span>
    )
}

export function IdChip({ children }: { children: ReactNode }) {
    return (
        <span className="font-mono text-xs bg-brass-soft text-brass rounded px-1.5 py-0.5">
            {children}
        </span>
    );
}

export function Stamp({ ok, children }: { ok: boolean; children: ReactNode }) {
    return (
        <span
            className={`inline-block rounded px-1.5 py-0.5 font-mono text-xs font-medium ${
                ok ? "bg-forest-soft text-forest" : "bg-brick-soft text-brick"
            }`}
        >
            {children}
        </span>
    )
}

export function Card({ children }: { children: ReactNode }) {
    return (
        <div className="bg-paper-raised border border-line rounded-md px-4.5 py-4 mb-3">
            {children}
        </div>
    )
}

export function EmptyState({ children }: { children: ReactNode }) {
    return <div className="text-ink-soft italic py-5">{children}</div>
}