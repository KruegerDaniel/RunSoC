import type { EnrichedJob, ScheduledJob, SolverResult } from './types';

export function enrichJobs(schedule: ScheduledJob[]): EnrichedJob[] {
    return schedule.map((job) => ({
        ...job,
        duration: job.finish_time - job.start_time,
        slack: job.absolute_deadline - job.finish_time,
        responseTime: job.finish_time - job.release_time,
        waitingTime: job.start_time - job.eligible_time,
        missedDeadline: job.finish_time > job.absolute_deadline,
    }));
}

export function groupBy<T>(
    items: T[],
    keyFn: (item: T) => string,
): Record<string, T[]> {
    return items.reduce<Record<string, T[]>>((acc, item) => {
        const key = keyFn(item);
        acc[key] ??= [];
        acc[key].push(item);
        return acc;
    }, {});
}

export function formatUs(value: number): string {
    return `${Number(value.toFixed(3)).toLocaleString()} µs`;
}

export function formatKb(value: number): string {
    return `${Number(value.toFixed(2)).toLocaleString()} KB`;
}

export function getCoreOrder(result: SolverResult): string[] {
    const fromMemory = result.resource_usage.core_memory
        .map((core) => core.core_id)
        .filter(Boolean) as string[];

    const fromSchedule = Array.from(
        new Set(result.schedule.map((job) => job.assigned_core)),
    );

    return Array.from(new Set([...fromMemory, ...fromSchedule]));
}

export function getClusterOrder(result: SolverResult): string[] {
    const fromMemory = result.resource_usage.cluster_memory.map(
        (cluster) => cluster.cluster_id,
    );

    const fromSchedule = Array.from(
        new Set(result.schedule.map((job) => job.assigned_cluster)),
    );

    return Array.from(new Set([...fromMemory, ...fromSchedule]));
}

export function penaltyEntries(result: SolverResult) {
    return Object.entries(result.objective_breakdown ?? {}).map(
        ([name, value]) => ({
            name,
            value: Number(value ?? 0),
        }),
    );
}

export function getMaxPenalty(result: SolverResult): number {
    return Math.max(1, ...penaltyEntries(result).map((entry) => entry.value));
}

export function getMemoryPercent(used: number, budget: number): number {
    if (budget <= 0) return 0;
    return Math.min(100, (used / budget) * 100);
}

export function getOverflowPercent(overflow: number, budget: number): number {
    if (budget <= 0) return overflow > 0 ? 100 : 0;
    return Math.min(100, (overflow / budget) * 100);
}