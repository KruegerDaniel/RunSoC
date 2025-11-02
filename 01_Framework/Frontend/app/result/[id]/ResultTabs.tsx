'use client';
import {useState} from 'react';

type ExecutionLogEntry = {
    start: number
    end: number
    task: string
    instance: number
    affinity: number
}

type AlgorithmResult = {
    totalExecutionTime: number
    executionLog: ExecutionLogEntry[]
    ganttChart: string | null
}

type MultiAlgorithmResult = Record<string, AlgorithmResult>

const ALGORITHM_LABELS: Record<string, string> = {
    fcfs: 'First come - first serve',
    criticality: 'Priority-aware',
};

type ResultTabsProps = {
    availableAlgorithms: string[]
    results: MultiAlgorithmResult
}

export default function ResultTabs({availableAlgorithms, results}: ResultTabsProps) {
    const [selected, setSelected] = useState<string>(availableAlgorithms[0]);
    const selectedResult = results[selected];

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
            </div>
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
                                <th className="border px-2 py-1">Affinity</th>
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
