// ResultPage.tsx
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
    nonExecutedTasks?: string[];
    allTasks?: string[];
};


type MultiAlgorithmResult = Record<string, AlgorithmResult>;

async function getResult(id: string) {
    const baseUrl = process.env.NEXT_PUBLIC_FRONTEND_ORIGIN!;
    const res = await fetch(`${baseUrl}/api/simulate?id=${id}`, {
        cache: 'no-store',
    });
    return res.ok ? res.json() : null;
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
    if (!res || !res.success || !res.results) return notFound();

    const results: MultiAlgorithmResult = {};

    const mapLog = (entries: any[] = []): ExecutionLogEntry[] =>
        entries.map((e: any) => ({
            start: e.start ?? e.start_time ?? 0,
            end: e.end ?? e.finish_time ?? 0,
            task: e.task,
            instance: e.instance ?? e.eligibleTime ?? 0,
            affinity: e.affinity ?? e.core ?? 0,
        }));

    const backendResults = res.results as Record<string, Record<string, any>>;

    for (const [schedKey, allocMap] of Object.entries(backendResults)) {
        if (!allocMap || typeof allocMap !== 'object') continue;

        for (const [allocKey, variantRes] of Object.entries(allocMap)) {
            if (!variantRes || typeof variantRes !== 'object') continue;

            const mappedLog = mapLog(variantRes.executionLog);
            const totalExecutionTime = variantRes.totalExecutionTime ?? 0;
            const key = `${schedKey}-${allocKey}`; // e.g. "fcfs-static"
            const nonExecutedTasks: string[] = variantRes.nonExecutedTasks ?? [];
            const allTasks: string[] = variantRes.allTasks ?? [];

            results[key] = {
                totalExecutionTime,
                executionLog: mappedLog,
                ganttChart: variantRes.ganttChart ?? null,
                kpis: computeKpis(mappedLog, totalExecutionTime),
                nonExecutedTasks,
                allTasks,
            };
        }
    }

    const availableAlgorithms = Object.keys(results);
    if (!availableAlgorithms.length) {
        console.error('No parsed results for id', id, res);
        return notFound();
    }

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
