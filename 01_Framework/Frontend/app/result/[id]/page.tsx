import { notFound } from 'next/navigation';
import ResultTabs from './ResultTabs';

export type ExecutionLogEntry = {
    start: number;
    end: number;
    task: string;
    instance: number;
    affinity: number;
};

type CoreKpi = {
    coreId: number;
    busyTime: number;
    idleTime: number;
    utilization: number;
    taskCount: number;
};

type KpiSummary = {
    totalExecutionTime: number;
    overallUtilization: number;
    avgIdleTimePerTask: number;
    totalTasksExecuted: number;
    cores: CoreKpi[];
};

export type AlgorithmResult = {
    totalExecutionTime: number;
    executionLog: ExecutionLogEntry[];
    ganttChart: string | null;
    kpis: KpiSummary;
};


type MultiAlgorithmResult = Record<string, AlgorithmResult>;

async function getResult(id: string) {
    const res = await fetch(`http://127.0.0.1:3000/api/simulate?id=${id}`, {
        cache: 'no-store',
    });
    if (!res.ok) return null;
    return res.json();
}

function computeKpis(
    executionLog: ExecutionLogEntry[],
    totalExecutionTime: number,
): KpiSummary {
    if (totalExecutionTime <= 0 || executionLog.length === 0) {
        return {
            totalExecutionTime,
            overallUtilization: 0,
            avgIdleTimePerTask: 0,
            totalTasksExecuted: 0,
            cores: [],
        };
    }

    const maxCoreId =
        executionLog.reduce(
            (max, e) => (e.affinity > max ? e.affinity : max),
            0,
        ) || 0;
    const coreCount = maxCoreId + 1;

    const cores: CoreKpi[] = [];

    let totalBusyAll = 0;
    let totalIdleAll = 0;

    for (let coreId = 0; coreId < coreCount; coreId++) {
        const coreEntries = executionLog
            .filter((e) => e.affinity === coreId)
            .slice()
            .sort((a, b) => a.start - b.start);

        let busyTime = 0;
        let idleTime = 0;

        if (coreEntries.length === 0) {
            // core exists but never scheduled
            idleTime = totalExecutionTime;
        } else {
            let lastEnd = 0;

            for (const e of coreEntries) {
                busyTime += Math.max(0, e.end - e.start);

                if (e.start > lastEnd) {
                    idleTime += e.start - lastEnd;
                }

                if (e.end > lastEnd) {
                    lastEnd = e.end;
                }
            }

            if (lastEnd < totalExecutionTime) {
                idleTime += totalExecutionTime - lastEnd;
            }
        }

        const utilization = busyTime / totalExecutionTime;

        cores.push({
            coreId,
            busyTime,
            idleTime,
            utilization,
            taskCount: coreEntries.length,
        });

        totalBusyAll += busyTime;
        totalIdleAll += idleTime;
    }

    const totalTasksExecuted = executionLog.length;
    const overallUtilization = totalBusyAll / (totalExecutionTime * coreCount);
    const avgIdleTimePerTask =
        totalTasksExecuted > 0 ? totalIdleAll / totalTasksExecuted : 0;

    return {
        totalExecutionTime,
        overallUtilization,
        avgIdleTimePerTask,
        totalTasksExecuted,
        cores,
    };
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
                    const mappedLog = mapLog(mainRes.executionLog);
                    const totalExecutionTime = mainRes.totalExecutionTime ?? 0;
                    const key = `main-${policy}`;
                    results[key] = {
                        totalExecutionTime,
                        executionLog: mappedLog,
                        ganttChart: mainRes.ganttChart ?? null,
                        kpis: computeKpis(mappedLog, totalExecutionTime),
                    };
                }
            } else {
                // Normal single algorithm result (fcfs, criticality, or main with single policy)
                const v = value as any;
                const mappedLog = mapLog(v.executionLog);
                const totalExecutionTime = v.totalExecutionTime ?? 0;
                results[algKey] = {
                    totalExecutionTime,
                    executionLog: mappedLog,
                    ganttChart: v.ganttChart ?? null,
                    kpis: computeKpis(mappedLog, totalExecutionTime),
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
                const mappedLog = mapLog(v.executionLog);
                const totalExecutionTime = v.totalExecutionTime ?? 0;
                results[key] = {
                    totalExecutionTime,
                    executionLog: mappedLog,
                    ganttChart: v.ganttChart ?? null,
                    kpis: computeKpis(mappedLog, totalExecutionTime),
                };
            }
        });
        // Fallback: if neither static/dynamic recognized, treat as single
        if (Object.keys(results).length === 0 && res.totalExecutionTime) {
            const mappedLog = mapLog(res.executionLog);
            const totalExecutionTime = res.totalExecutionTime ?? 0;
            results['single'] = {
                totalExecutionTime,
                executionLog: mappedLog,
                ganttChart: res.ganttChart ?? null,
                kpis: computeKpis(mappedLog, totalExecutionTime),
            };
        }
    }
    // Case 3: single algorithm response (fcfs / criticality / main with one policy)
    else {
        const mappedLog = mapLog(res.executionLog);
        const totalExecutionTime = res.totalExecutionTime ?? 0;
        results['single'] = {
            totalExecutionTime,
            executionLog: mappedLog,
            ganttChart: res.ganttChart ?? null,
            kpis: computeKpis(mappedLog, totalExecutionTime),
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
