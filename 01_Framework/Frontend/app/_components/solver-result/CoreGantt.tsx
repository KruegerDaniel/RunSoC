'use client';

import { useMemo, useState } from 'react';
import type { SolverResult } from './types';
import { enrichJobs, formatUs, getCoreOrder, groupBy } from './utils';

type Props = {
    result: SolverResult;
};

const MIN_WIDTH = 1200;
const ROW_HEIGHT = 42;
const LEFT_WIDTH = 240;

export function CoreGantt({ result }: Props) {
    const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

    const jobs = useMemo(() => enrichJobs(result.schedule), [result.schedule]);
    const jobsByCore = useMemo(
        () => groupBy(jobs, (job) => job.assigned_core),
        [jobs],
    );
    const coreOrder = useMemo(() => getCoreOrder(result), [result]);

    const selectedJob = selectedJobId
        ? jobs.find((job) => job.job_id === selectedJobId)
        : null;

    const horizon = Math.max(result.summary.horizon, result.makespan, 1);

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-semibold text-slate-950">
                        Schedule by core
                    </h3>
                    <p className="text-sm text-slate-600">
                        Bars show start and finish time per scheduled job.
                    </p>
                </div>
                <div className="text-sm text-slate-500">
                    Horizon: {formatUs(result.summary.horizon)}
                </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-slate-200">
                <div style={{ minWidth: MIN_WIDTH }}>
                    <div className="sticky top-0 z-10 flex border-b border-slate-200 bg-slate-50">
                        <div
                            className="shrink-0 border-r border-slate-200 px-3 py-2 text-xs font-semibold uppercase text-slate-500"
                            style={{ width: LEFT_WIDTH }}
                        >
                            Core
                        </div>
                        <div className="relative h-9 flex-1">
                            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
                                <div
                                    key={ratio}
                                    className="absolute top-0 h-full border-l border-slate-200 text-xs text-slate-500"
                                    style={{ left: `${ratio * 100}%` }}
                                >
                                    <span className="ml-1">
                                        {formatUs(result.summary.horizon * ratio)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {coreOrder.map((coreId) => {
                        const rowJobs = jobsByCore[coreId] ?? [];

                        return (
                            <div
                                key={coreId}
                                className="flex border-b border-slate-100 last:border-b-0"
                                style={{ height: ROW_HEIGHT }}
                            >
                                <div
                                    className="flex shrink-0 items-center border-r border-slate-200 bg-slate-50 px-3 text-xs font-medium text-slate-700"
                                    style={{ width: LEFT_WIDTH }}
                                    title={coreId}
                                >
                                    <span className="truncate">{coreId}</span>
                                </div>

                                <div className="relative flex-1">
                                    {rowJobs.map((job) => {
                                        const left = (job.start_time / horizon) * 100;
                                        const width =
                                            ((job.finish_time - job.start_time) / horizon) * 100;

                                        return (
                                            <button
                                                key={job.job_id}
                                                type="button"
                                                onClick={() => setSelectedJobId(job.job_id)}
                                                className={`absolute top-2 h-6 overflow-hidden rounded-md border px-1 text-left text-[11px] leading-6 shadow-sm ${
                                                    job.missedDeadline
                                                        ? 'border-red-400 bg-red-100 text-red-900'
                                                        : job.is_chain_root
                                                            ? 'border-blue-300 bg-blue-100 text-blue-900'
                                                            : 'border-slate-300 bg-slate-100 text-slate-900'
                                                }`}
                                                style={{
                                                    left: `${left}%`,
                                                    width: `${Math.max(width, 0.25)}%`,
                                                }}
                                                title={`${job.task_name} · ${formatUs(
                                                    job.start_time,
                                                )} → ${formatUs(job.finish_time)}`}
                                            >
                                                <span className="truncate">{job.task_name}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>

            {selectedJob && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
                    <div className="mb-2 flex items-center justify-between gap-3">
                        <h4 className="font-semibold text-slate-950">
                            {selectedJob.task_name}
                        </h4>
                        <span className="text-xs text-slate-500">
                            {selectedJob.job_id}
                        </span>
                    </div>

                    <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <dt className="text-slate-500">Core</dt>
                            <dd className="font-medium">{selectedJob.assigned_core}</dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Cluster</dt>
                            <dd className="font-medium">{selectedJob.assigned_cluster}</dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Start</dt>
                            <dd className="font-medium">{formatUs(selectedJob.start_time)}</dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Finish</dt>
                            <dd className="font-medium">
                                {formatUs(selectedJob.finish_time)}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Deadline</dt>
                            <dd className="font-medium">
                                {formatUs(selectedJob.absolute_deadline)}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Slack</dt>
                            <dd
                                className={`font-medium ${
                                    selectedJob.slack < 0 ? 'text-red-700' : 'text-green-700'
                                }`}
                            >
                                {formatUs(selectedJob.slack)}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Task memory footprint</dt>
                            <dd className="font-medium">{selectedJob.memory} KB</dd>
                        </div>
                        <div>
                            <dt className="text-slate-500">Domain</dt>
                            <dd className="font-medium">{selectedJob.required_domain}</dd>
                        </div>
                    </dl>
                </div>
            )}
        </section>
    );
}
