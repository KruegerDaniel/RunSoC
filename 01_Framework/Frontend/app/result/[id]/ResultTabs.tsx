'use client';
import {useState} from 'react';
import {AlgorithmResult, ExecutionLogEntry} from '@/app/result/[id]/page';

type MultiAlgorithmResult = Record<string, AlgorithmResult>

const ALGORITHM_LABELS: Record<string, string> = {
    fcfs: 'First come - first serve',
    criticality: 'Priority-aware',
};

type ResultTabsProps = {
    availableAlgorithms: string[]
    results: MultiAlgorithmResult
}

function formatPercent(v: number) {
    return `${(v * 100).toFixed(2)}%`;
}

export default function ResultTabs({availableAlgorithms, results}: ResultTabsProps) {
    const [selected, setSelected] = useState<string>(availableAlgorithms[0]);
    const selectedResult = results[selected];
    const {kpis} = selectedResult;
    const nonExecutedTasks = selectedResult.nonExecutedTasks ?? [];
    const allTasks = selectedResult.allTasks ?? [];

    return (
        <>
            <div className="mb-6">
                <div className="border-b mb-4">
                    <nav className="flex gap-4">
                        {availableAlgorithms.map((alg) => (
                            <button
                                key={alg}
                                className={`py-2 px-4 border-b-2 ${
                                    selected === alg
                                        ? 'border-indigo-500 font-semibold'
                                        : 'border-transparent text-gray-500'
                                }`}
                                onClick={() => setSelected(alg)}
                            >
                                {ALGORITHM_LABELS[alg] || alg}
                            </button>
                        ))}
                    </nav>
                </div>

                {/* Gantt chart image */}
                {selectedResult.ganttChart ? (
                    <div className="flex justify-center items-center min-h-[300px] bg-gray-50 border rounded">
                        <img
                            src={
                                selectedResult.ganttChart.startsWith('data:')
                                    ? selectedResult.ganttChart
                                    : `data:image/png;base64,${selectedResult.ganttChart}`
                            }
                            alt="Gantt Chart"
                            className="max-h-[400px] max-w-full object-contain"
                        />
                    </div>
                ) : (
                    <div className="flex justify-center items-center min-h-[300px] bg-gray-50 border rounded">
                        <span className="text-gray-400">No Gantt chart available</span>
                    </div>
                )}

                <div className="mt-4">
                    {nonExecutedTasks.length > 0 ? (
                        <div className="border rounded-lg p-4 bg-red-50">
                            <div className="text-sm font-medium text-red-700">
                                Non-executed tasks ({nonExecutedTasks.length}) out of {allTasks.length} total tasks:
                            </div>
                            <p className="text-xs text-red-600 mt-1 mb-2">
                                These tasks were defined but never scheduled within the simulation horizon.
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {nonExecutedTasks.map((name) => (
                                    <span
                                        key={name}
                                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700 border border-red-200"
                                    >
                                        {name}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="border rounded-lg p-3 bg-green-50 text-xs text-green-700">
                            All tasks were executed at least once.
                        </div>
                    )}
                </div>

                <div className="mt-6 space-y-4">
                    {/* High-level KPIs */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div className="border rounded-lg p-4">
                            <div className="text-sm text-gray-500">Execution time</div>
                            <div className="text-xl font-semibold">
                                {kpis.totalExecutionTime}
                            </div>
                        </div>

                        <div className="border rounded-lg p-4">
                            <div className="text-sm text-gray-500">Core utilization</div>
                            <div className="text-xl font-semibold">
                                {formatPercent(kpis.overallUtilization)}
                            </div>
                        </div>

                        <div className="border rounded-lg p-4">
                            <div className="text-sm text-gray-500">
                                Avg idle time per task
                            </div>
                            <div className="text-xl font-semibold">
                                {kpis.avgIdleTimePerTask.toFixed(2)}
                            </div>
                        </div>
                    </div>

                    {/* Per-core breakdown */}
                    <div className="border rounded-lg p-4">
                        <div className="text-sm font-medium mb-2">
                            Executed task count & utilization per core
                        </div>
                        <div className="overflow-x-auto">
                            <table className="min-w-full text-sm">
                                <thead>
                                    <tr className="text-left border-b">
                                        <th className="py-1 pr-4">Core</th>
                                        <th className="py-1 pr-4">Task count</th>
                                        <th className="py-1 pr-4">Busy time (ms)</th>
                                        <th className="py-1 pr-4">Idle time (ms)</th>
                                        <th className="py-1 pr-4">Utilization</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {kpis.cores.map((core) => (
                                        <tr key={core.coreId} className="border-b last:border-0">
                                            <td className="py-1 pr-4">{core.coreId}</td>
                                            <td className="py-1 pr-4">{core.taskCount}</td>
                                            <td className="py-1 pr-4">{core.busyTime}</td>
                                            <td className="py-1 pr-4">{core.idleTime}</td>
                                            <td className="py-1 pr-4">
                                                {formatPercent(core.utilization)}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            {/* Existing Execution Log */}
            <div>
                <h2 className="text-xl font-semibold mb-2">Execution Log</h2>
                <div className="overflow-x-auto">
                    <table className="min-w-full border">
                        <thead>
                            <tr>
                                <th className="border px-2 py-1">Start</th>
                                <th className="border px-2 py-1">End</th>
                                <th className="border px-2 py-1">Task</th>
                                <th className="border px-2 py-1">Instance</th>
                                <th className="border px-2 py-1">Core</th>
                            </tr>
                        </thead>
                        <tbody>
                            {selectedResult.executionLog &&
                        selectedResult.executionLog.length > 0 ? (
                                    (selectedResult.executionLog as ExecutionLogEntry[]).map(
                                        (entry, i) => (
                                            <tr key={i}>
                                                <td className="border px-2 py-1">{entry.start}</td>
                                                <td className="border px-2 py-1">{entry.end}</td>
                                                <td className="border px-2 py-1">{entry.task}</td>
                                                <td className="border px-2 py-1">{entry.instance}</td>
                                                <td className="border px-2 py-1">{entry.affinity}</td>
                                            </tr>
                                        ),
                                    )
                                ) : (
                                    <tr>
                                        <td className="border px-2 py-1" colSpan={5}>
                                    No execution log available
                                        </td>
                                    </tr>
                                )}
                        </tbody>
                    </table>
                </div>
            </div>
        </>
    );
}
