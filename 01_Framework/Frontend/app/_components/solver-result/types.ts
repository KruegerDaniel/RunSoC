export type SolverStatus =
    | 'OPTIMAL'
    | 'FEASIBLE'
    | 'INFEASIBLE'
    | 'UNKNOWN'
    | string;

export type ScheduledJob = {
    job_id: string;
    task_id: string;
    chain_id: string;
    instance_index: number;
    job_name: string;
    task_name: string;
    task_type: 'periodic' | 'event' | string;
    is_chain_root: boolean;
    assigned_core: string;
    assigned_cluster: string;
    release_time: number;
    absolute_deadline: number;
    eligible_time: number;
    start_time: number;
    finish_time: number;
    base_duration: number;
    scheduled_duration: number;
    memory: number;
    required_domain: string;
    predecessors: string[];
    notes?: string;
};

export type MemoryAccounting = 'task_level' | string;

export type MemoryUsage = {
    core_id?: string;
    core_name?: string;
    cluster_id: string;
    cluster_name?: string;
    budget: number;
    used: number;
    overflow: number;
    assigned_jobs: string[];
    assigned_tasks?: string[];
    assigned_job_count?: number;
    assigned_task_count?: number;
    memory_accounting?: MemoryAccounting;
};

export type SolverResult = {
    solver: string;
    status: SolverStatus;
    feasible: boolean;
    objective: number;
    makespan: number;
    evaluation?: {
        taskset_id?: string;
        platform_name?: string;
        platform_key?: string;
        source_file?: string;
        seed?: number;
    };
    summary: {
        task_template_count: number;
        job_count: number;
        scheduled_job_count: number;
        task_chain_count: number;
        dependency_template_count: number;
        job_dependency_count: number;
        core_count: number;
        cluster_count: number;
        horizon: number;
    };
    objective_breakdown: Record<string, number>;
    derived_metrics: {
        compute_pressure: number;
        deadline_violation: number;
        total_memory_overflow_kb: number;
        core_memory_overflow_kb: number;
        cluster_memory_overflow_kb: number;
        bottleneck: string;
    };
    resource_usage: {
        memory_accounting?: MemoryAccounting;
        core_memory: MemoryUsage[];
        cluster_memory: MemoryUsage[];
    };
    schedule: ScheduledJob[];
};

export type EnrichedJob = ScheduledJob & {
    duration: number;
    slack: number;
    responseTime: number;
    waitingTime: number;
    missedDeadline: boolean;
};
