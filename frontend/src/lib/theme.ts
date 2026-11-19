import { useEffect, useState } from "react";

/** "system" follows the OS setting and keeps following it if it changes. */
export type ThemePref = "light" | "dark" | "system";

const KEY = "easy-sched.theme";
const media = () => window.matchMedia("(prefers-color-scheme: dark)");

function readPref(): ThemePref {
    try {
        const v = window.localStorage.getItem(KEY);
        return v === "light" || v === "dark" ? v : "system";
    } catch {
        return "system";
    }
}

function apply(pref: ThemePref, animate: boolean) {
    const root = document.documentElement;
    const dark = pref === "dark" || (pref === "system" && media().matches);
    if (animate) {
        root.classList.add("theme-switching");
        window.setTimeout(() => root.classList.remove("theme-switching"), 250);
    }
    root.dataset.theme = dark ? "dark" : "light";
}

export function useTheme(): [ThemePref, (p: ThemePref) => void] {
    const [pref, setPref] = useState<ThemePref>(readPref);

    useEffect(() => {
        if (pref !== "system") return;
        const mq = media();
        const onChange = () => apply("system", true);
        mq.addEventListener("change", onChange);
        return () => mq.removeEventListener("change", onChange);
    }, [pref]);

    return [
        pref,
        (next: ThemePref) => {
            setPref(next);
            try { window.localStorage.setItem(KEY, next); } catch { /* storage unavailable */ }
            apply(next, true);
        },
    ];
}
