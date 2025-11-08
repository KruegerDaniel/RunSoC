import { notFound } from 'next/navigation';
import ResultTabs from './ResultTabs';

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

async function getResult(id: string) {
    const res = await fetch(`http://127.0.0.1:3000/api/simulate?id=${id}`, {
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
    const res = await getResult(id);
    if (!res) return notFound();

    const results: MultiAlgorithmResult = {};

    // Helper to normalize any executionLog entry shape into ExecutionLogEntry
    const mapLog = (entries: any[] = []): ExecutionLogEntry[] =>
        entries.map((e: any) => ({
            start: e.start ?? e.start_time ?? 0,
            end: e.end ?? e.finish_time ?? 0,
            task: e.task,
            // FCFS/criticality use "instance"; main uses "eligibleTime" but has no instance.
            instance:
                e.instance ??
                e.eligibleTime ??
                0,
            // FCFS/criticality use "affinity"; main uses "core".
            affinity:
                e.affinity ??
                e.core ??
                0,
        }));

    // Case 1: "all" algorithms → res.results present (fcfs, criticality, main{...})
    if (res.results) {
        const rawResults = res.results as Record<string, any>;

        for (const [algKey, value] of Object.entries(rawResults)) {
            // Special handling for main scheduler:
            // when allocationPolicy = "all"/"both", backend returns:
            // "main": { "static": {...}, "dynamic": {...} }
            if (
                algKey === 'main' &&
                value &&
                typeof value === 'object' &&
                !('executionLog' in (value as any))
            ) {
                const mainVariants = value as Record<string, any>;
                for (const [policy, mainRes] of Object.entries(mainVariants)) {
                    const key = `main-${policy}`;
                    results[key] = {
                        totalExecutionTime: mainRes.totalExecutionTime ?? 0,
                        executionLog: mapLog(mainRes.executionLog),
                        ganttChart: mainRes.ganttChart ?? null,
                    };
                }
            } else {
                // Normal single algorithm result (fcfs, criticality, or main with single policy)
                const v = value as any;
                results[algKey] = {
                    totalExecutionTime: v.totalExecutionTime ?? 0,
                    executionLog: mapLog(v.executionLog),
                    ganttChart: v.ganttChart ?? null,
                };
            }
        }
    }
    // Case 2: algorithm == "main" with multiple policies, spread at top-level:
    // { success: true, static: {...}, dynamic: {...} }
    else if (res.static || res.dynamic) {
        (['static', 'dynamic'] as const).forEach((policy) => {
            if (res[policy]) {
                const v = res[policy] as any;
                const key = `main-${policy}`;
                results[key] = {
                    totalExecutionTime: v.totalExecutionTime ?? 0,
                    executionLog: mapLog(v.executionLog),
                    ganttChart: v.ganttChart ?? null,
                };
            }
        });
        // Fallback: if neither static/dynamic recognized, treat as single
        if (Object.keys(results).length === 0 && res.totalExecutionTime) {
            results['single'] = {
                totalExecutionTime: res.totalExecutionTime ?? 0,
                executionLog: mapLog(res.executionLog),
                ganttChart: res.ganttChart ?? null,
            };
        }
    }
    // Case 3: single algorithm response (fcfs / criticality / main with one policy)
    else {
        results['single'] = {
            totalExecutionTime: res.totalExecutionTime ?? 0,
            executionLog: mapLog(res.executionLog),
            ganttChart: res.ganttChart ?? null,
        };
    }

    const availableAlgorithms = Object.keys(results);

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
