export type SolverJson = {
    config: Config;
    platform: Platform;
    tasks: Task[];
    communications: Communication[];
};

export type Config = {
    generateComms: boolean;
    commsPenaltyWeight: {
        intraCoreWeight: number;
        interCoreWeight: number;
        interClusterWeight: number;
    };
    memoryPenaltyScale: {
        coreOverflowScale: number;
        clusterOverflowScale: number;
    };
};

export type Platform = {
    name: string;
    numCores: number;
    numClusters: number;
    timeUnit: string;
    clusters: Cluster[];
    memoryNodes: MemoryNode[];
};

export type Cluster = {
    name: string;
    id: string;
    type?: string;
    executionDomain?: string;
    numCores: number;
    count?: number;
    notes?: string;
    cores: Core[];
    memory?: ClusterMemory[];
};

export type Core = {
    name: string;
    id: string;
    frequencyGhz?: number;
    executionDomain: string;
    wcetScale: number;
    localMemoryKB?: number;
    supportedTaskTypes: string[];
    count?: number;
    notes?: string;
};

export type ClusterMemory = {
    type: string;
    level?: string;
    sizeKB: number;
    notes?: string;
};

export type MemoryNode = {
    id: string;
    name: string;
    type: string;
    scope: string;
    accessibleBy: string[];
    technology?: string;
    capacityGB: number;
    coherent: boolean;
    contentionDomain?: string;
    notes?: string;
};

export type Task = {
    id: string;
    name: string;
    type?: 'event' | 'periodic';
    taskType?: 'event' | 'periodic';
    wcet: number;
    duration?: number;
    period?: number;
    deadline?: number;
    minStart?: number;
    memoryUsageKB?: number;
    memory?: number;
    requiredDomain?: string;
    eligibleCores?: string[];
    dependencies?: string[];
    criticality?: number;
    priority?: number;
    notes?: string;
};

export type Communication = {
    source: string;
    target: string;
    penalty: number;
    notes?: string;
};
