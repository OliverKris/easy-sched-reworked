import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { CheckIcon, CloseIcon } from "./icons";

/*
  Small notices in the bottom-right corner that confirm what just happened,
  optionally with one action (usually Undo). They disappear on their own, and
  the region is announced politely to screen readers.
*/

export interface ToastOptions {
    message: ReactNode;
    tone?: "success" | "neutral" | "danger";
    action?: { label: string; onClick: () => void };
    /** ms before it disappears; longer when there's an action to take */
    duration?: number;
}

interface ToastItem extends ToastOptions {
    id: number;
    leaving: boolean;
}

const ToastContext = createContext<((t: ToastOptions) => void) | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
    const [items, setItems] = useState<ToastItem[]>([]);
    const nextId = useRef(1);

    const dismiss = useCallback((id: number) => {
        setItems((all) => all.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
        window.setTimeout(() => setItems((all) => all.filter((t) => t.id !== id)), 180);
    }, []);

    const show = useCallback((t: ToastOptions) => {
        const id = nextId.current++;
        setItems((all) => [...all.slice(-2), { ...t, id, leaving: false }]);
        window.setTimeout(() => dismiss(id), t.duration ?? (t.action ? 6000 : 3500));
    }, [dismiss]);

    return (
        <ToastContext.Provider value={show}>
            {children}
            <div
                role="region"
                aria-label="Notifications"
                aria-live="polite"
                className="fixed z-50 bottom-4 right-4 left-4 sm:left-auto flex flex-col items-end gap-2 pointer-events-none"
            >
                {items.map((t) => (
                    <div
                        key={t.id}
                        className={
                            "pointer-events-auto flex items-center gap-3 min-h-11 max-w-sm pl-3.5 pr-2 py-2 rounded-lg " +
                            "bg-raised text-ink border border-line shadow-lg text-[13px] transition-all duration-150 " +
                            (t.leaving ? "opacity-0 translate-y-1" : "animate-toast-in")
                        }
                    >
                        {t.tone !== "neutral" && (
                            <span className={`flex-none inline-flex items-center justify-center w-5 h-5 rounded-full ${
                                t.tone === "danger" ? "bg-danger-soft text-danger" : "bg-accent-soft text-accent"}`}>
                                {t.tone === "danger" ? <span className="font-bold text-xs">!</span> : <CheckIcon size={11} />}
                            </span>
                        )}
                        <span className="flex-1 min-w-0">{t.message}</span>
                        {t.action && (
                            <button
                                type="button"
                                onClick={() => { t.action!.onClick(); dismiss(t.id); }}
                                className="flex-none px-2 h-7 rounded-md font-medium text-accent hover:bg-accent-soft cursor-pointer"
                            >
                                {t.action.label}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => dismiss(t.id)}
                            aria-label="Dismiss"
                            className="flex-none w-7 h-7 inline-flex items-center justify-center rounded-md text-ink-3 hover:bg-line-soft cursor-pointer"
                        >
                            <CloseIcon size={12} />
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
    const show = useContext(ToastContext);
    if (!show) throw new Error("useToast must be used inside <ToastProvider>");
    return show;
}
