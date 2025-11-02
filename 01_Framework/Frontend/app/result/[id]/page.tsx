import { notFound } from 'next/navigation';
import ResultTabs from './ResultTabs';
import {headers} from 'next/headers';

type ExecutionLogEntry = {
    start: number;
    end: number;
    task: string;
    instance: number;
    affinity: number;
};

type AlgorithmResult = {
    totalExecutionTime: number;
    executionLog: ExecutionLogEntry[];
    ganttChart: string | null;
};

type MultiAlgorithmResult = Record<string, AlgorithmResult>;
async function getResult(baseUrl: string, id: string) {

    const res = await fetch(`${baseUrl}/api/simulate?id=${id}`, {
        cache: 'no-store',
    });

    if (!res.ok) return null;
    return res.json();
}

export default async function ResultPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;

    const h = await headers();
    const host = h.get('x-forwarded-host') || h.get('host') || 'localhost:3000';
    const proto = h.get('x-forwarded-proto') || 'http';
    const baseurl = `${proto}://${host}`;

    const res = await getResult(baseurl, id);
    if (!res) return notFound();

    const results: MultiAlgorithmResult =
        res.results ||
        ({
            single: {
                totalExecutionTime: res.totalExecutionTime,
                executionLog: res.executionLog,
                ganttChart: res.ganttChart ?? null,
            },
        } as MultiAlgorithmResult);

    const availableAlgorithms = res.results
        ? Object.keys(res.results)
        : ['single'];

    return (
        <div className="max-w-4xl mx-auto py-10 px-4">
            <h1 className="text-3xl font-bold mb-6">Simulation Result: {id}</h1>
            <ResultTabs
                availableAlgorithms={availableAlgorithms}
                results={results}
            />
        </div>
    );
}
