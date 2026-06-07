import type { SolverResult } from './types';
import { formatKb, getClusterOrder } from './utils';

type Props = {
    result: SolverResult;
};

export function PlatformTopology({ result }: Props) {
    const clusters = getClusterOrder(result);

    const coresByCluster = result.resource_usage.core_memory.reduce<
        Record<string, typeof result.resource_usage.core_memory>
    >((acc, core) => {
        acc[core.cluster_id] ??= [];
        acc[core.cluster_id].push(core);
        return acc;
    }, {});

    const clusterMemoryById = new Map(
        result.resource_usage.cluster_memory.map((cluster) => [
            cluster.cluster_id,
            cluster,
        ]),
    );

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-950">
                MPSoC allocation topology
            </h3>
            <p className="mt-1 text-sm text-slate-600">
                Cluster and core placement with assigned job counts.
            </p>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
                {clusters.map((clusterId) => {
                    const clusterMemory = clusterMemoryById.get(clusterId);
                    const cores = coresByCluster[clusterId] ?? [];

                    return (
                        <div
                            key={clusterId}
                            className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                        >
                            <div className="mb-3 flex items-start justify-between gap-3">
                                <div>
                                    <h4 className="font-semibold text-slate-900">
                                        {clusterMemory?.cluster_name ?? clusterId}
                                    </h4>
                                    <p className="text-xs text-slate-500">{clusterId}</p>
                                </div>

                                {clusterMemory && (
                                    <div
                                        className={`rounded-full px-2 py-1 text-xs font-medium ${
                                            clusterMemory.overflow > 0
                                                ? 'bg-red-100 text-red-800'
                                                : 'bg-green-100 text-green-800'
                                        }`}
                                    >
                                        {clusterMemory.overflow > 0
                                            ? `Overflow ${formatKb(clusterMemory.overflow)}`
                                            : 'No overflow'}
                                    </div>
                                )}
                            </div>

                            {clusterMemory && (
                                <div className="mb-3 text-xs text-slate-600">
                                    Cluster memory: {formatKb(clusterMemory.used)} /{' '}
                                    {formatKb(clusterMemory.budget)}
                                </div>
                            )}

                            <div className="grid gap-2 sm:grid-cols-2">
                                {cores.map((core) => (
                                    <div
                                        key={core.core_id}
                                        className={`rounded-lg border p-3 ${
                                            core.overflow > 0
                                                ? 'border-red-300 bg-red-50'
                                                : core.assigned_jobs.length > 0
                                                    ? 'border-blue-200 bg-white'
                                                    : 'border-slate-200 bg-white opacity-70'
                                        }`}
                                    >
                                        <div className="truncate text-sm font-medium text-slate-900">
                                            {core.core_id}
                                        </div>
                                        <div className="mt-1 truncate text-xs text-slate-500">
                                            {core.core_name}
                                        </div>
                                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                                <span className="text-slate-500">Jobs</span>
                                                <div className="font-semibold">
                                                    {core.assigned_jobs.length}
                                                </div>
                                            </div>
                                            <div>
                                                <span className="text-slate-500">Memory</span>
                                                <div className="font-semibold">
                                                    {formatKb(core.used)}
                                                </div>
                                            </div>
                                            <div>
                                                <span className="text-slate-500">Budget</span>
                                                <div className="font-semibold">
                                                    {formatKb(core.budget)}
                                                </div>
                                            </div>
                                            <div>
                                                <span className="text-slate-500">Overflow</span>
                                                <div
                                                    className={`font-semibold ${
                                                        core.overflow > 0
                                                            ? 'text-red-700'
                                                            : 'text-green-700'
                                                    }`}
                                                >
                                                    {formatKb(core.overflow)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {cores.length === 0 && (
                                    <div className="rounded-lg border border-dashed border-slate-300 p-3 text-sm text-slate-500">
                                        No core memory entries for this cluster.
                                    </div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}