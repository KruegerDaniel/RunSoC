import type {MemoryUsage, SolverResult} from './types';
import {formatKb} from './utils';

type Props = {
    result: SolverResult;
};

function MemoryRow({
    label,
    sublabel,
    item,
}: {
    label: string;
    sublabel?: string;
    item: MemoryUsage;
}) {
    const computedOverflow = Math.max(0, item.used - item.budget);
    const reportedOverflow = item.overflow ?? computedOverflow;
    const effectiveOverflow = reportedOverflow;

    const hasOverflow = effectiveOverflow > 0;
    const hasMismatch = Math.abs(computedOverflow - reportedOverflow) > 1e-6;
    const assignedJobCount = item.assigned_job_count ?? item.assigned_jobs.length;
    const assignedTaskCount = item.assigned_task_count ?? item.assigned_tasks?.length ?? 0;

    const usageRatio = item.budget > 0 ? item.used / item.budget : 0;
    const visiblePercent = Math.min(100, usageRatio * 100);

    return (
        <tr className={hasOverflow ? 'bg-red-50' : undefined}>
            <td className="whitespace-nowrap px-3 py-3 text-sm font-medium text-slate-900">
                {label}
                {sublabel && (
                    <div className="text-xs font-normal text-slate-500">{sublabel}</div>
                )}

                {hasMismatch && (
                    <div className="mt-1 text-xs font-semibold text-orange-700">
                        task overflow mismatch
                    </div>
                )}
            </td>

            <td className="px-3 py-3 text-sm text-slate-700">
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                    <div
                        className={hasOverflow ? 'h-full bg-red-500' : 'h-full bg-blue-500'}
                        style={{ width: `${visiblePercent}%` }}
                    />
                </div>

                <div
                    className={`mt-1 text-xs ${
                        hasOverflow ? 'font-semibold text-red-700' : 'text-slate-500'
                    }`}
                >
                    {(usageRatio * 100).toFixed(1)}% of budget
                </div>
            </td>

            <td className="px-3 py-3 text-sm text-slate-700">
                {formatKb(item.used)}
            </td>

            <td className="px-3 py-3 text-sm text-slate-700">
                {formatKb(item.budget)}
            </td>

            <td
                className={`px-3 py-3 text-sm font-semibold ${
                    hasOverflow ? 'text-red-700' : 'text-green-700'
                }`}
            >
                {formatKb(effectiveOverflow)}

                {hasMismatch && (
                    <div className="text-xs font-normal text-orange-700">
                        computed from task memory: {formatKb(computedOverflow)}
                    </div>
                )}
            </td>

            <td className="px-3 py-3 text-sm text-slate-700">
                <div>{assignedJobCount} jobs</div>
                <div className="text-xs text-slate-500">
                    {assignedTaskCount} tasks
                </div>
            </td>
        </tr>
    );
}

export function MemoryHeatmap({ result }: Props) {
    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-950">
                Memory pressure
            </h3>
            <p className="mt-1 text-sm text-slate-600">
                Core-local and cluster-level task memory usage. Task overflow is
                backend-reported solver overflow based on unique task footprints assigned
                to each core or cluster.
            </p>

            <div className="mt-4 overflow-x-auto">
                <h4 className="mb-2 text-sm font-semibold text-slate-800">
                    Core task memory
                </h4>
                <table className="min-w-full border-separate border-spacing-0 overflow-hidden rounded-xl border border-slate-200">
                    <thead className="bg-slate-50">
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Core
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Usage
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Task memory
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Budget
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Task overflow
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Jobs / tasks
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {result.resource_usage.core_memory.map((core) => (
                            <MemoryRow
                                key={core.core_id}
                                label={core.core_id ?? 'unknown-core'}
                                sublabel={core.cluster_id}
                                item={core}
                            />
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mt-6 overflow-x-auto">
                <h4 className="mb-2 text-sm font-semibold text-slate-800">
                    Cluster task memory
                </h4>
                <table className="min-w-full border-separate border-spacing-0 overflow-hidden rounded-xl border border-slate-200">
                    <thead className="bg-slate-50">
                        <tr>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Cluster
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Usage
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Task memory
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Budget
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Task overflow
                            </th>
                            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500">
                            Jobs / tasks
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {result.resource_usage.cluster_memory.map((cluster) => (
                            <MemoryRow
                                key={cluster.cluster_id}
                                label={cluster.cluster_name ?? cluster.cluster_id}
                                sublabel={cluster.cluster_id}
                                item={cluster}
                            />
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
