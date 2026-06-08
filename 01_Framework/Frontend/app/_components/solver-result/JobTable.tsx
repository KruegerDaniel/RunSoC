'use client';

import {useMemo, useState} from 'react';
import type {SolverResult} from './types';
import {enrichJobs, formatUs} from './utils';

type Props = {
    result: SolverResult;
};

export function JobTable({ result }: Props) {
    const [query, setQuery] = useState('');

    const jobs = useMemo(() => enrichJobs(result.schedule), [result.schedule]);

    const filteredJobs = jobs.filter((job) => {
        const haystack = [
            job.job_id,
            job.task_id,
            job.task_name,
            job.chain_id,
            job.assigned_core,
            job.assigned_cluster,
            job.required_domain,
        ]
            .join(' ')
            .toLowerCase();

        return haystack.includes(query.toLowerCase());
    });

    return (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h3 className="text-lg font-semibold text-slate-950">Job table</h3>
                    <p className="text-sm text-slate-600">
                        Searchable low-level schedule data.
                    </p>
                </div>

                <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search jobs, cores, chains..."
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm sm:w-80"
                />
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto rounded-xl border border-slate-200">
                <table className="min-w-[1200px] border-separate border-spacing-0">
                    <thead className="sticky top-0 bg-slate-50">
                        <tr>
                            {[
                                'Job',
                                'Task',
                                'Instance',
                                'Core',
                                'Cluster',
                                'Start',
                                'Finish',
                                'Duration',
                                'Deadline',
                                'Slack',
                                'Task memory',
                            ].map((header) => (
                                <th
                                    key={header}
                                    className="border-b border-slate-200 px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500"
                                >
                                    {header}
                                </th>
                            ))}
                        </tr>
                    </thead>

                    <tbody>
                        {filteredJobs.map((job) => (
                            <tr
                                key={job.job_id}
                                className={job.missedDeadline ? 'bg-red-50' : undefined}
                            >
                                <td className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-xs font-medium text-slate-900">
                                    {job.job_id}
                                </td>
                                <td className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {job.task_name}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {job.instance_index}
                                </td>
                                <td className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {job.assigned_core}
                                </td>
                                <td className="whitespace-nowrap border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {job.assigned_cluster}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {formatUs(job.start_time)}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {formatUs(job.finish_time)}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {formatUs(job.duration)}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {formatUs(job.absolute_deadline)}
                                </td>
                                <td
                                    className={`border-b border-slate-100 px-3 py-2 text-sm font-semibold ${
                                        job.slack < 0 ? 'text-red-700' : 'text-green-700'
                                    }`}
                                >
                                    {formatUs(job.slack)}
                                </td>
                                <td className="border-b border-slate-100 px-3 py-2 text-sm text-slate-700">
                                    {job.memory} KB
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}
