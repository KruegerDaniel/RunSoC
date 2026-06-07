import type {SolverResult} from './types';
import {enrichJobs, formatUs, groupBy} from './utils';

type Props = {
    result: SolverResult;
};

export function ChainView({ result }: Props) {
    const jobs = enrichJobs(result.schedule);
    const byChain = groupBy(jobs, (job) => job.chain_id);

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="text-lg font-semibold text-slate-950">
                Task chains and dependencies
            </h3>
            <p className="mt-1 text-sm text-slate-600">
                Chain instances show dependency order, latency, and deadline slack.
            </p>

            <div className="mt-4 space-y-4">
                {Object.entries(byChain).map(([chainId, chainJobs]) => {
                    const byInstance = groupBy(chainJobs, (job) =>
                        String(job.instance_index),
                    );

                    return (
                        <div
                            key={chainId}
                            className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                        >
                            <h4 className="font-semibold text-slate-900">{chainId}</h4>

                            <div className="mt-3 space-y-3">
                                {Object.entries(byInstance)
                                    .sort(([a], [b]) => Number(a) - Number(b))
                                    .slice(0, 10)
                                    .map(([instance, instanceJobs]) => {
                                        const ordered = [...instanceJobs].sort(
                                            (a, b) => a.start_time - b.start_time,
                                        );

                                        const first = ordered[0];
                                        const last = ordered[ordered.length - 1];

                                        const latency = last.finish_time - first.release_time;
                                        const slack = last.absolute_deadline - last.finish_time;

                                        return (
                                            <div
                                                key={instance}
                                                className="rounded-lg border border-slate-200 bg-white p-3"
                                            >
                                                <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                                                    <span className="font-semibold text-slate-700">
                            Instance k{instance}
                                                    </span>
                                                    <span
                                                        className={
                                                            slack < 0 ? 'text-red-700' : 'text-green-700'
                                                        }
                                                    >
                            latency {formatUs(latency)} · slack{' '}
                                                        {formatUs(slack)}
                                                    </span>
                                                </div>

                                                <div className="flex flex-wrap items-center gap-2">
                                                    {ordered.map((job, index) => (
                                                        <div
                                                            key={job.job_id}
                                                            className="flex items-center gap-2"
                                                        >
                                                            {index > 0 && (
                                                                <span className="text-slate-400">→</span>
                                                            )}
                                                            <div
                                                                className={`rounded-md border px-2 py-1 text-xs ${
                                                                    job.missedDeadline
                                                                        ? 'border-red-300 bg-red-50 text-red-900'
                                                                        : job.is_chain_root
                                                                            ? 'border-blue-300 bg-blue-50 text-blue-900'
                                                                            : 'border-slate-300 bg-slate-50 text-slate-800'
                                                                }`}
                                                                title={`${job.job_id} on ${job.assigned_core}`}
                                                            >
                                                                {job.task_name}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        );
                                    })}

                                {Object.keys(byInstance).length > 10 && (
                                    <div className="text-xs text-slate-500">
                                        Showing first 10 instances.
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