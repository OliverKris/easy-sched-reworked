/**
 * The anonymous id that makes workspaces belong to this browser.
 *
 * Generated once and kept in localStorage. There are no accounts: clearing
 * site data starts a fresh browser identity, which is why workspaces can be
 * exported to a file and imported again.
 */
const KEY = "easy-sched.client";

let memoryFallback: string | null = null;

function newId(): string {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
    return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function getClientId(): string {
    try {
        const existing = window.localStorage.getItem(KEY);
        if (existing) return existing;
        const id = newId();
        window.localStorage.setItem(KEY, id);
        return id;
    } catch {
        // Storage blocked (private mode, embedded frame): work for this visit only.
        memoryFallback ??= newId();
        return memoryFallback;
    }
}

/** True when workspaces can't outlive this tab because storage is unavailable. */
export function storageIsEphemeral(): boolean {
    try {
        const probe = "easy-sched.probe";
        window.localStorage.setItem(probe, "1");
        window.localStorage.removeItem(probe);
        return false;
    } catch {
        return true;
    }
}
