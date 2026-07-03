export type ViewKey = "sections" | "applicants" | "eligibility" | "solver";

const TABS: { key: ViewKey, label: string, index: string }[] = [
    { key: "sections", label: "Sections", index: "01" },
    { key: "applicants", label: "Applicants", index: "02" },
    { key: "eligibility", label: "Eligibility Ledger", index: "03" },
    { key: "solver", label: "Run Solver", index: "04" },
]

interface Props {
    active: ViewKey;
    onChange: (v: ViewKey) => void;
}

export function Tabs({ active, onChange }: Props) {
    return (
        <nav className="flex gap-0.5 px-10 border-b border-line bg-paper-raised">
            {TABS.map((tab) => (
                <button
                    key={tab.key}
                    onClick={() => onChange(tab.key)}
                    className={`text-[13px] font-medium px-4.5 py-3.5 border-b-2 -mb-px transition-colors ${
                        active === tab.key
                            ? "text-ink border-forest"
                            : "text-ink-soft border-transparent hover:text-ink"
                    }`}
                >
                    <span className="font-mono text-[10px] text-brass mr-1.5">{tab.index}</span>
                    {tab.label}
                </button>
            ))}
        </nav>
    );
}