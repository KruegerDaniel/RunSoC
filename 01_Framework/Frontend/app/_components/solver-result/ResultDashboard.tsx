import type { SolverResult } from './types';
import { formatKb, formatUs } from './utils';

type Props = {
    result: SolverResult;
};

function KpiCard({
    label,
    value,
    tone = 'default',
}: {
    label: string;
    value: string | number;
    tone?: 'default' | 'good' | 'warn' | 'bad';
}) {
    const toneClass =
        tone === 'good'
            ? 'border-green-300 bg-green-50'
            : tone === 'warn'
                ? 'border-yellow-300 bg-yellow-50'
                : tone === 'bad'
                    ? 'border-red-300 bg-red-50'
                    : 'border-slate-200 bg-white';

    return (
        <div className={`rounded-xl border p-4 shadow-sm ${toneClass}`}>
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {label}
            </div>
            <div className="mt-1 text-xl font-semibold text-slate-900">{value}</div>
        </div>
    );
}

export function ResultDashboard({ result }: Props) {
    const deadlineViolations = result.derived_metrics.deadline_violation;
    const memoryOverflow = result.derived_metrics.total_memory_overflow_kb;

    return (
        <section className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                        <h2 className="text-2xl font-semibold text-slate-950">
                            Solver result
                        </h2>
                        <p className="mt-1 text-sm text-slate-600">
                            {result.evaluation?.platform_name ?? 'Unknown platform'} ·{' '}
                            {result.solver}
                        </p>
                    </div>

                    <div
                        className={`rounded-full px-4 py-2 text-sm font-semibold ${
                            result.feasible
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                        }`}
                    >
                        {result.status}
                    </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <KpiCard
                        label="Feasible"
                        value={result.feasible ? 'Yes' : 'No'}
                        tone={result.feasible ? 'good' : 'bad'}
                    />
                    <KpiCard label="Objective" value={result.objective} />
                    <KpiCard label="Makespan" value={formatUs(result.makespan)} />
                    <KpiCard
                        label="Scheduled jobs"
                        value={`${result.summary.scheduled_job_count} / ${result.summary.job_count}`}
                        tone={
                            result.summary.scheduled_job_count === result.summary.job_count
                                ? 'good'
                                : 'warn'
                        }
                    />
                    <KpiCard
                        label="Bottleneck"
                        value={result.derived_metrics.bottleneck}
                        tone={
                            result.derived_metrics.bottleneck === 'none' ? 'good' : 'warn'
                        }
                    />
                    <KpiCard
                        label="Deadline violations"
                        value={deadlineViolations}
                        tone={deadlineViolations === 0 ? 'good' : 'bad'}
                    />
                    <KpiCard
                        label="Memory overflow"
                        value={formatKb(memoryOverflow)}
                        tone={memoryOverflow === 0 ? 'good' : 'bad'}
                    />
                    <KpiCard
                        label="Compute pressure"
                        value={`${(result.derived_metrics.compute_pressure * 100).toFixed(
                            3,
                        )}%`}
                    />
                </div>
            </div>
        </section>
    );
}