import type { DatasetKey } from "../types";

interface Props {
    dataset: DatasetKey;
    onChange: (d: DatasetKey) => void;
}

export function Header({ dataset, onChange }: Props) {
    return (
        <header className="flex items-baseline justify-between px-10 pt-y pb-4.5 border-ink">
            {/* Title and subtitle */}
            <div>
                <div className="font-display text-[26px] font-semibold tracking-tight">
                    Easy Sched - <span className="text-brass">Assignment Desk</span>
                </div>
                <div className="text-xs text-ink-soft tracking-wide uppercase">
                    TA / LA hiring · admin console
                </div>
            </div>
            {/* Dataset select */}
            <div className="flex items-center gap-1.5">
                <label htmlFor="dataset-select" className="text-xs text-ink-soft uppercase tracking-wide mr-1">
                    Dataset
                </label>
                <select 
                    name="datasetSelect" 
                    id="dataset-select"
                    value={dataset}
                    onChange={(e) => onChange(e.target.value as DatasetKey)}
                    className="font-mono text-xs px-2.5 py-1.5 border border-ink bg-paper-raised rounded-[3px]"
                >
                    <option value="demo">demo (4 applicants)</option>
                    <option value="extended">extended (14 applicants, edge cases)</option>
                </select>
            </div>
        </header>
    );
}