import type { SolverResult } from './types';
import { getMaxPenalty, penaltyEntries } from './utils';

type Props = {
    result: SolverResult;
};

export function ObjectiveBreakdown({ result }: Props) {
    const entries = penaltyEntries(result);
    const max = getMaxPenalty(result);

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-950">
                Objective breakdown
            </h3>
            <p className="mt-1 text-sm text-slate-600">
                Shows which penalty terms dominate the solver objective.
            </p>

            <div className="mt-4 space-y-3">
                {entries.map((entry) => {
                    const width = `${Math.max(1, (entry.value / max) * 100)}%`;

                    return (
                        <div key={entry.name}>
                            <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                                <span className="font-medium text-slate-800">
                                    {entry.name}
                                </span>
                                <span className="text-slate-600">{entry.value}</span>
                            </div>
                            <div className="h-3 overflow-hidden rounded-full bg-slate-200">
                                <div
                                    className={
                                        entry.value > 0 ? 'h-full bg-blue-500' : 'h-full bg-slate-300'
                                    }
                                    style={{ width }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>

            {result.objective_breakdown.memory_penalty > 0 &&
                Object.entries(result.objective_breakdown).every(
                    ([key, value]) => key === 'memory_penalty' || value === 0,
                ) && (
                <div className="mt-4 rounded-xl border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900">
                        The objective is dominated by memory penalty. Timing and
                        communication penalties are zero.
                </div>
            )}
        </section>
    );
}