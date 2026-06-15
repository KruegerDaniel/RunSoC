'use client';

import { useMemo, useState } from 'react';
import ReactFlow, {
    Background,
    Controls,
    Edge,
    Handle,
    Node,
    NodeProps,
    Position,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { useJsonModel } from '@/lib/JsonModelContext';
import type {
    Cluster,
    Communication,
    Core,
    MemoryNode,
    Platform,
} from '@/lib/types/mpsoc';
import ClusterCoreDialog, {
    ClusterCoreDialogState,
} from '@/app/_components/mpsoc-builder/ClusterCoreDialog';
import MemoryCommDialog, {
    MemoryCommDialogState,
} from '@/app/_components/mpsoc-builder/MemoryCommDialog';

type JsonModel = ReturnType<typeof useJsonModel>['model'];

type JsonModelController = ReturnType<typeof useJsonModel> & {
    updateModel?: (nextModel: JsonModel) => void;
    setModel?: (nextModel: JsonModel) => void;
    updateCommunications?: (communications: Communication[]) => void;
};

type PendingDelete =
    | { kind: 'cluster'; clusterId: string }
    | { kind: 'core'; clusterId: string; coreId: string }
    | { kind: 'memory'; memoryId: string }
    | { kind: 'comm'; commId: string }
    | null;

type DropdownState =
    | { kind: 'cluster'; id: string }
    | { kind: 'core'; id: string }
    | { kind: 'memory'; id: string }
    | { kind: 'comm'; id: string }
    | null;

type ClusterNodeData = {
    cluster: Cluster;
    height: number;
};

type CoreNodeData = {
    core: Core;
};

type CacheNodeData = {
    label: string;
    width?: number;
};

type MemoryNodeData = {
    memory: MemoryNode;
};

function ClusterNode({ data }: NodeProps<ClusterNodeData>) {
    return (
        <div
            style={{
                width: 330,
                height: data.height,
                background: '#bebebe',
                border: '1px solid #aaa',
                padding: 16,
                textAlign: 'center',
                fontFamily: 'Arial, sans-serif',
                boxSizing: 'border-box',
            }}
        >
            <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
            <strong style={{ fontSize: 20 }}>{data.cluster.id}</strong>
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
        </div>
    );
}

function CoreNode({ data }: NodeProps<CoreNodeData>) {
    return (
        <div
            style={{
                width: 114,
                height: 64,
                background: '#dedede',
                border: '1px solid #111',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                textAlign: 'center',
                fontSize: 14,
                lineHeight: 1.1,
                fontFamily: 'Arial, sans-serif',
                whiteSpace: 'pre-line',
            }}
        >
            <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
            {data.core.id}
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
        </div>
    );
}

function CacheNode({ data }: NodeProps<CacheNodeData>) {
    return (
        <div
            style={{
                width: data.width ?? 300,
                height: 28,
                background: '#dedede',
                border: '1px solid #111',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 15,
                fontFamily: 'Arial, sans-serif',
            }}
        >
            {data.label}
        </div>
    );
}

function MemoryGraphNode({ data }: NodeProps<MemoryNodeData>) {
    return (
        <div
            style={{
                width: 190,
                minHeight: 72,
                background: '#f5f0ff',
                border: '1px solid #7f65b8',
                borderRadius: 8,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                gap: 6,
                padding: '10px 14px',
                fontFamily: 'Arial, sans-serif',
                boxShadow: '0 2px 5px rgba(0,0,0,0.16)',
            }}
        >
            <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
            <strong style={{ fontSize: 15 }}>{data.memory.id}</strong>
            <span style={{ fontSize: 13, color: '#555' }}>
                {data.memory.type.toUpperCase()} · {data.memory.capacityGB}GB
            </span>
            <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
        </div>
    );
}

const nodeTypes = {
    cluster: ClusterNode,
    core: CoreNode,
    cache: CacheNode,
    memory: MemoryGraphNode,
};

export default function PlatformDesigner() {
    const jsonModel = useJsonModel() as JsonModelController;
    const { model, updatePlatform } = jsonModel;
    const platform = model.platform;
    const communications = useMemo(
        () => model.communications ?? [],
        [model.communications],
    );

    const [clusterCoreDialog, setClusterCoreDialog] =
        useState<ClusterCoreDialogState | null>(null);
    const [memoryCommDialog, setMemoryCommDialog] =
        useState<MemoryCommDialogState | null>(null);
    const [openDropdown, setOpenDropdown] = useState<DropdownState>(null);
    const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);

    const { nodes, edges } = useMemo(() => {
        return buildPlatformGraph(platform, communications);
    }, [platform, communications]);

    function commitModel(nextModel: JsonModel) {
        if (jsonModel.updateModel) {
            jsonModel.updateModel(nextModel);
            return true;
        }

        if (jsonModel.setModel) {
            jsonModel.setModel(nextModel);
            return true;
        }

        return false;
    }

    function setPlatform(
        nextPlatform: Platform,
        nextCommunications?: Communication[],
    ) {
        if (nextCommunications && commitModel({
            ...model,
            platform: nextPlatform,
            communications: nextCommunications,
        })) {
            return;
        }

        updatePlatform(nextPlatform);

        if (nextCommunications) {
            setCommunications(nextCommunications);
        }
    }

    function setCommunications(nextCommunications: Communication[]) {
        if (jsonModel.updateCommunications) {
            jsonModel.updateCommunications(nextCommunications);
            return;
        }

        if (commitModel({
            ...model,
            communications: nextCommunications,
        })) {
            return;
        }

        window.alert(
            'Communication paths cannot be saved because JsonModelContext does not expose a root-model updater.',
        );
    }

    function addCluster() {
        setClusterCoreDialog({
            kind: 'cluster',
            mode: 'add',
            cluster: {
                id: `cluster_${platform.clusters.length}`,
                name: '',
                type: 'application',
                executionDomain: 'general_purpose',
                numCores: 0,
                cores: [],
                memory: [],
            },
        });
    }

    function addCore() {
        if (platform.clusters.length === 0) {
            window.alert('Create a cluster before adding a core.');
            return;
        }

        const clusterId =
            platform.clusters.length === 1
                ? platform.clusters[0].id
                : window.prompt('Add core to which cluster ID?');

        if (!clusterId) return;

        const cluster = platform.clusters.find((item) => item.id === clusterId);

        if (!cluster) {
            window.alert(`Cluster "${clusterId}" does not exist.`);
            return;
        }

        setClusterCoreDialog({
            kind: 'core',
            mode: 'add',
            clusterId,
            core: {
                id: `core_${Date.now()}`,
                name: '',
                executionDomain: cluster.executionDomain ?? 'general_purpose',
                wcetScale: 1,
                supportedTaskTypes: ['event', 'periodic'],
            },
        });
    }

    function addMemory() {
        setMemoryCommDialog({
            kind: 'memory',
            mode: 'add',
            memory: {
                id: `memory_${platform.memoryNodes?.length ?? 0}`,
                name: '',
                type: 'dram',
                scope: 'system',
                accessibleBy: [],
                capacityGB: 0,
                coherent: false,
            },
        });
    }

    function addCommunication() {
        const entityIds = getEntityIds(platform);

        if (entityIds.length < 2) {
            window.alert(
                'Create at least two clusters, cores, or memory nodes before adding a communication path.',
            );
            return;
        }

        setMemoryCommDialog({
            kind: 'comm',
            mode: 'add',
            comm: {
                source: entityIds[0],
                target: entityIds[1],
                penalty: 0,
            },
        });
    }

    function editCluster(clusterId: string) {
        const cluster = platform.clusters.find((item) => item.id === clusterId);
        if (!cluster) return;

        setClusterCoreDialog({
            kind: 'cluster',
            mode: 'edit',
            cluster,
        });

        setOpenDropdown(null);
    }

    function editCore(clusterId: string, coreId: string) {
        const cluster = platform.clusters.find((item) => item.id === clusterId);
        const core = cluster?.cores.find((item) => item.id === coreId);

        if (!cluster || !core) return;

        setClusterCoreDialog({
            kind: 'core',
            mode: 'edit',
            clusterId,
            core,
        });

        setOpenDropdown(null);
    }

    function editMemory(memoryId: string) {
        const memory = (platform.memoryNodes ?? []).find(
            (item) => item.id === memoryId,
        );

        if (!memory) return;

        setMemoryCommDialog({
            kind: 'memory',
            mode: 'edit',
            memory,
        });

        setOpenDropdown(null);
    }

    function editCommunication(commId: string) {
        const comm = communications.find(
            (item, index) => getCommunicationId(item, index) === commId,
        );

        if (!comm) return;

        setMemoryCommDialog({
            kind: 'comm',
            mode: 'edit',
            comm,
            commId,
        });

        setOpenDropdown(null);
    }

    function saveCluster(cluster: Cluster, previousClusterId?: string) {
        const isEdit = Boolean(previousClusterId);
        const clusterIdChanged = Boolean(
            previousClusterId && previousClusterId !== cluster.id,
        );

        const duplicate = platform.clusters.some(
            (item) => item.id === cluster.id && item.id !== previousClusterId,
        );

        if (duplicate) {
            window.alert(`Cluster ID "${cluster.id}" already exists.`);
            return;
        }

        const nextClusters = isEdit
            ? platform.clusters.map((item) =>
                item.id === previousClusterId
                    ? {
                        ...cluster,
                        cores: item.cores,
                        numCores: item.cores.length,
                    }
                    : item,
            )
            : [
                ...platform.clusters,
                {
                    ...cluster,
                    cores: [],
                    numCores: 0,
                },
            ];

        const nextPlatform: Platform = {
            ...platform,
            clusters: nextClusters,
            memoryNodes: clusterIdChanged
                ? replaceAccessibleBy(
                    platform.memoryNodes,
                    previousClusterId as string,
                    cluster.id,
                )
                : platform.memoryNodes,
            numClusters: nextClusters.length,
            numCores: countCores(nextClusters),
        };

        const nextCommunications = clusterIdChanged
            ? replaceCommunicationEndpoint(
                communications,
                previousClusterId as string,
                cluster.id,
            )
            : undefined;

        setPlatform(nextPlatform, nextCommunications);
        setClusterCoreDialog(null);
    }

    function saveCore(
        clusterId: string,
        core: Core,
        previousCoreId?: string,
    ) {
        const cluster = platform.clusters.find((item) => item.id === clusterId);

        if (!cluster) {
            window.alert(`Cluster "${clusterId}" does not exist.`);
            return;
        }

        const duplicate = cluster.cores.some(
            (item) => item.id === core.id && item.id !== previousCoreId,
        );

        if (duplicate) {
            window.alert(`Core ID "${core.id}" already exists in this cluster.`);
            return;
        }

        const coreIdChanged = Boolean(previousCoreId && previousCoreId !== core.id);

        const nextClusters = platform.clusters.map((item) => {
            if (item.id !== clusterId) return item;

            const nextCores = previousCoreId
                ? item.cores.map((existingCore) =>
                    existingCore.id === previousCoreId ? core : existingCore,
                )
                : [...item.cores, core];

            return {
                ...item,
                cores: nextCores,
                numCores: nextCores.length,
            };
        });

        const nextPlatform: Platform = {
            ...platform,
            clusters: nextClusters,
            memoryNodes: coreIdChanged
                ? replaceAccessibleBy(
                    platform.memoryNodes,
                    previousCoreId as string,
                    core.id,
                )
                : platform.memoryNodes,
            numCores: countCores(nextClusters),
        };

        const nextCommunications = coreIdChanged
            ? replaceCommunicationEndpoint(
                communications,
                previousCoreId as string,
                core.id,
            )
            : undefined;

        setPlatform(nextPlatform, nextCommunications);
        setClusterCoreDialog(null);
    }

    function saveMemory(memory: MemoryNode, previousMemoryId?: string) {
        const memoryNodes = platform.memoryNodes ?? [];
        const memoryIdChanged = Boolean(
            previousMemoryId && previousMemoryId !== memory.id,
        );

        const duplicate = memoryNodes.some(
            (item) => item.id === memory.id && item.id !== previousMemoryId,
        );

        if (duplicate) {
            window.alert(`Memory ID "${memory.id}" already exists.`);
            return;
        }

        const nextMemoryNodes = previousMemoryId
            ? memoryNodes.map((item) =>
                item.id === previousMemoryId ? memory : item,
            )
            : [...memoryNodes, memory];

        const nextCommunications = memoryIdChanged
            ? replaceCommunicationEndpoint(
                communications,
                previousMemoryId as string,
                memory.id,
            )
            : undefined;

        setPlatform(
            {
                ...platform,
                memoryNodes: nextMemoryNodes,
            },
            nextCommunications,
        );
        setMemoryCommDialog(null);
    }

    function saveCommunication(
        comm: Communication,
        previousCommId?: string,
    ) {
        const normalizedComm: Communication = {
            ...comm,
            source: comm.source.trim(),
            target: comm.target.trim(),
        };

        if (normalizedComm.source === normalizedComm.target) {
            window.alert('Source and target must be different.');
            return;
        }

        if (!entityExists(platform, normalizedComm.source)) {
            window.alert(`Source "${normalizedComm.source}" does not exist.`);
            return;
        }

        if (!entityExists(platform, normalizedComm.target)) {
            window.alert(`Target "${normalizedComm.target}" does not exist.`);
            return;
        }

        const duplicate = communications.some((item, index) => {
            const commId = getCommunicationId(item, index);
            return (
                item.source === normalizedComm.source &&
                item.target === normalizedComm.target &&
                commId !== previousCommId
            );
        });

        if (duplicate) {
            window.alert(
                `Communication path "${normalizedComm.source}" ➔ "${normalizedComm.target}" already exists.`,
            );
            return;
        }

        let wasReplaced = false;
        const nextCommunications = previousCommId
            ? communications.map((item, index) => {
                if (getCommunicationId(item, index) !== previousCommId) {
                    return item;
                }

                wasReplaced = true;
                return normalizedComm;
            })
            : [...communications, normalizedComm];

        setCommunications(
            previousCommId && !wasReplaced
                ? [...communications, normalizedComm]
                : nextCommunications,
        );
        setMemoryCommDialog(null);
    }

    function confirmDelete() {
        if (!pendingDelete) return;

        if (pendingDelete.kind === 'cluster') {
            const cluster = platform.clusters.find(
                (item) => item.id === pendingDelete.clusterId,
            );
            const references = new Set([
                pendingDelete.clusterId,
                ...(cluster?.cores.map((core) => core.id) ?? []),
            ]);
            const nextClusters = platform.clusters.filter(
                (item) => item.id !== pendingDelete.clusterId,
            );

            setPlatform(
                {
                    ...platform,
                    clusters: nextClusters,
                    memoryNodes: removeAccessibleBy(platform.memoryNodes, references),
                    numClusters: nextClusters.length,
                    numCores: countCores(nextClusters),
                },
                removeCommunicationReferences(communications, references),
            );
        }

        if (pendingDelete.kind === 'core') {
            const references = new Set([pendingDelete.coreId]);
            const nextClusters = platform.clusters.map((cluster) => {
                if (cluster.id !== pendingDelete.clusterId) return cluster;

                const nextCores = cluster.cores.filter(
                    (core) => core.id !== pendingDelete.coreId,
                );

                return {
                    ...cluster,
                    cores: nextCores,
                    numCores: nextCores.length,
                };
            });

            setPlatform(
                {
                    ...platform,
                    clusters: nextClusters,
                    memoryNodes: removeAccessibleBy(platform.memoryNodes, references),
                    numCores: countCores(nextClusters),
                },
                removeCommunicationReferences(communications, references),
            );
        }

        if (pendingDelete.kind === 'memory') {
            const references = new Set([pendingDelete.memoryId]);

            setPlatform(
                {
                    ...platform,
                    memoryNodes: (platform.memoryNodes ?? []).filter(
                        (memory) => memory.id !== pendingDelete.memoryId,
                    ),
                },
                removeCommunicationReferences(communications, references),
            );
        }

        if (pendingDelete.kind === 'comm') {
            setCommunications(
                communications.filter(
                    (comm, index) =>
                        getCommunicationId(comm, index) !== pendingDelete.commId,
                ),
            );
        }

        setPendingDelete(null);
        setOpenDropdown(null);
    }

    return (
        <div>
            <header
                style={{
                    height: 80,
                    border: '1px solid #111',
                    borderRadius: 7,
                    background: '#dedede',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0 22px 0 96px',
                    boxShadow: '0 4px 6px rgba(0,0,0,0.25)',
                    marginBottom: 38,
                }}
            >
                <h1
                    style={{
                        margin: 0,
                        fontSize: 36,
                        letterSpacing: 1,
                    }}
                >
                    {platform.name}
                </h1>

                <div
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 22,
                        borderRadius: 999,
                        background: '#f8f2ff',
                        padding: '18px 28px',
                        boxShadow: '0 1px 4px rgba(0,0,0,0.2)',
                    }}
                >
                    <button style={iconButtonStyle} title="Import">
                        ⤴
                    </button>
                    <button style={iconButtonStyle} title="Comments">
                        ▣
                    </button>
                    <button style={iconButtonStyle} title="Download">
                        ⇩
                    </button>
                </div>
            </header>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(650px, 1fr) 408px',
                    gap: 28,
                }}
            >
                <section
                    style={{
                        height: 838,
                        border: '1px solid #111',
                        background: '#e7e7e7',
                    }}
                >
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        nodeTypes={nodeTypes}
                        fitView
                        nodesDraggable
                        nodesConnectable={false}
                        elementsSelectable
                        proOptions={{ hideAttribution: true }}
                    >
                        <Background />
                        <Controls />
                    </ReactFlow>
                </section>

                <aside
                    style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 18,
                    }}
                >
                    <Panel
                        title="Clusters"
                        actionLabel="+"
                        onAction={addCluster}
                    >
                        {platform.clusters.length === 0 ? (
                            <EmptyState label="No clusters yet." />
                        ) : (
                            platform.clusters.map((cluster) => (
                                <ListEntry
                                    key={cluster.id}
                                    title={cluster.name || cluster.id}
                                    subtitle={cluster.id}
                                    dropdownOpen={
                                        openDropdown?.kind === 'cluster' &&
                                        openDropdown.id === cluster.id
                                    }
                                    onToggleDropdown={() =>
                                        setOpenDropdown(
                                            openDropdown?.kind === 'cluster' &&
                                            openDropdown.id === cluster.id
                                                ? null
                                                : { kind: 'cluster', id: cluster.id },
                                        )
                                    }
                                    onEdit={() => editCluster(cluster.id)}
                                    onDelete={() =>
                                        setPendingDelete({
                                            kind: 'cluster',
                                            clusterId: cluster.id,
                                        })
                                    }
                                />
                            ))
                        )}
                    </Panel>

                    <Panel title="Cores" actionLabel="+" onAction={addCore}>
                        {countCores(platform.clusters) === 0 ? (
                            <EmptyState label="No cores yet." />
                        ) : (
                            platform.clusters.flatMap((cluster) =>
                                cluster.cores.map((core) => (
                                    <ListEntry
                                        key={`${cluster.id}:${core.id}`}
                                        title={core.name || core.id}
                                        subtitle={`${core.id} · ${cluster.id}`}
                                        dropdownOpen={
                                            openDropdown?.kind === 'core' &&
                                            openDropdown.id ===
                                            `${cluster.id}:${core.id}`
                                        }
                                        onToggleDropdown={() =>
                                            setOpenDropdown(
                                                openDropdown?.kind === 'core' &&
                                                openDropdown.id ===
                                                `${cluster.id}:${core.id}`
                                                    ? null
                                                    : {
                                                        kind: 'core',
                                                        id: `${cluster.id}:${core.id}`,
                                                    },
                                            )
                                        }
                                        onEdit={() => editCore(cluster.id, core.id)}
                                        onDelete={() =>
                                            setPendingDelete({
                                                kind: 'core',
                                                clusterId: cluster.id,
                                                coreId: core.id,
                                            })
                                        }
                                    />
                                )),
                            )
                        )}
                    </Panel>

                    <Panel
                        title="Memory Nodes"
                        actionLabel="+"
                        onAction={addMemory}
                    >
                        {(platform.memoryNodes ?? []).length === 0 ? (
                            <EmptyState label="No memory nodes yet." />
                        ) : (
                            (platform.memoryNodes ?? []).map((memory) => (
                                <ListEntry
                                    key={memory.id}
                                    title={memory.name || memory.id}
                                    subtitle={`${memory.type.toUpperCase()} · ${memory.capacityGB}GB`}
                                    dropdownOpen={
                                        openDropdown?.kind === 'memory' &&
                                        openDropdown.id === memory.id
                                    }
                                    onToggleDropdown={() =>
                                        setOpenDropdown(
                                            openDropdown?.kind === 'memory' &&
                                            openDropdown.id === memory.id
                                                ? null
                                                : { kind: 'memory', id: memory.id },
                                        )
                                    }
                                    onEdit={() => editMemory(memory.id)}
                                    onDelete={() =>
                                        setPendingDelete({
                                            kind: 'memory',
                                            memoryId: memory.id,
                                        })
                                    }
                                />
                            ))
                        )}
                    </Panel>

                    <Panel
                        title="Communication Paths"
                        actionLabel="+"
                        onAction={addCommunication}
                    >
                        {communications.length === 0 ? (
                            <EmptyState label="No communication paths yet." />
                        ) : (
                            communications.map((comm, index) => {
                                const commId = getCommunicationId(comm, index);
                                return (
                                    <ListEntry
                                        key={commId}
                                        title={`${comm.source} ➔ ${comm.target}`}
                                        subtitle={`Penalty: ${comm.penalty}`}
                                        dropdownOpen={
                                            openDropdown?.kind === 'comm' &&
                                            openDropdown.id === commId
                                        }
                                        onToggleDropdown={() =>
                                            setOpenDropdown(
                                                openDropdown?.kind === 'comm' &&
                                                openDropdown.id === commId
                                                    ? null
                                                    : { kind: 'comm', id: commId },
                                            )
                                        }
                                        onEdit={() => editCommunication(commId)}
                                        onDelete={() =>
                                            setPendingDelete({
                                                kind: 'comm',
                                                commId,
                                            })
                                        }
                                    />
                                );
                            })
                        )}
                    </Panel>
                </aside>
            </div>

            {pendingDelete && (
                <ConfirmDialog
                    pendingDelete={pendingDelete}
                    onCancel={() => setPendingDelete(null)}
                    onConfirm={confirmDelete}
                />
            )}

            {clusterCoreDialog && (
                <ClusterCoreDialog
                    state={clusterCoreDialog}
                    onCancel={() => setClusterCoreDialog(null)}
                    onSaveCluster={saveCluster}
                    onSaveCore={saveCore}
                />
            )}

            {memoryCommDialog && (
                <MemoryCommDialog
                    state={memoryCommDialog}
                    onCancel={() => setMemoryCommDialog(null)}
                    onSaveMemory={saveMemory}
                    onSaveComm={saveCommunication}
                />
            )}
        </div>
    );
}

function Panel({
    title,
    actionLabel,
    onAction,
    children,
}: {
    title: string;
    actionLabel: string;
    onAction: () => void;
    children: React.ReactNode;
}) {
    const [isExpanded, setIsExpanded] = useState(true);

    return (
        <section
            style={{
                border: '1px solid #d5d5d5',
                borderRadius: 6,
                background: '#fff',
                padding: isExpanded ? '24px 24px 30px' : '24px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.15)',
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: isExpanded ? '1px solid #d5d5d5' : 'none',
                    paddingBottom: isExpanded ? 14 : 0,
                    marginBottom: isExpanded ? 10 : 0,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        style={{
                            background: 'transparent',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: 14,
                            padding: 0,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#555',
                        }}
                        title={isExpanded ? 'Collapse panel' : 'Expand panel'}
                    >
                        {isExpanded ? '▼' : '▶'}
                    </button>
                    <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>
                </div>

                <button
                    onClick={onAction}
                    style={{
                        border: '1px solid #ccc',
                        background: '#fafafa',
                        borderRadius: 6,
                        cursor: 'pointer',
                        width: 28,
                        height: 28,
                        fontSize: 18,
                    }}
                >
                    {actionLabel}
                </button>
            </div>

            {isExpanded && children}
        </section>
    );
}

function EmptyState({ label }: { label: string }) {
    return (
        <div
            style={{
                padding: '16px 0 2px',
                color: '#777',
                fontSize: 14,
            }}
        >
            {label}
        </div>
    );
}

function ListEntry({
    title,
    subtitle,
    dropdownOpen,
    onToggleDropdown,
    onEdit,
    onDelete,
}: {
    title: string;
    subtitle: string;
    dropdownOpen: boolean;
    onToggleDropdown: () => void;
    onEdit: () => void;
    onDelete: () => void;
}) {
    return (
        <div
            style={{
                position: 'relative',
                display: 'grid',
                gridTemplateColumns: '24px 1fr 32px',
                alignItems: 'center',
                gap: 8,
                padding: '14px 0',
            }}
        >
            <span style={{ fontSize: 24 }}>☆</span>

            <div>
                <div style={{ fontSize: 16 }}>{title}</div>
                <div style={{ fontSize: 14, color: '#777', marginTop: 6 }}>
                    {subtitle}
                </div>
            </div>

            <button
                onClick={onToggleDropdown}
                style={{
                    border: 'none',
                    background: 'transparent',
                    cursor: 'pointer',
                    fontSize: 18,
                }}
            >
                ...
            </button>

            {dropdownOpen && (
                <div
                    style={{
                        position: 'absolute',
                        top: 42,
                        right: 0,
                        zIndex: 20,
                        width: 140,
                        background: '#fff',
                        border: '1px solid #ccc',
                        borderRadius: 6,
                        boxShadow: '0 3px 10px rgba(0,0,0,0.18)',
                        overflow: 'hidden',
                    }}
                >
                    <button onClick={onEdit} style={menuButtonStyle}>
                        Edit
                    </button>
                    <button
                        onClick={onDelete}
                        style={{
                            ...menuButtonStyle,
                            color: 'crimson',
                        }}
                    >
                        Delete
                    </button>
                </div>
            )}
        </div>
    );
}

function ConfirmDialog({
    pendingDelete,
    onCancel,
    onConfirm,
}: {
    pendingDelete: Exclude<PendingDelete, null>;
    onCancel: () => void;
    onConfirm: () => void;
}) {
    const message = getDeleteMessage(pendingDelete);

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                zIndex: 100,
                background: 'rgba(0,0,0,0.35)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}
        >
            <div
                style={{
                    width: 420,
                    background: '#fff',
                    borderRadius: 8,
                    padding: 24,
                    boxShadow: '0 8px 30px rgba(0,0,0,0.25)',
                }}
            >
                <h2 style={{ marginTop: 0 }}>Confirm deletion</h2>
                <p>{message}</p>

                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 12,
                        marginTop: 24,
                    }}
                >
                    <button onClick={onCancel}>Cancel</button>
                    <button
                        onClick={onConfirm}
                        style={{
                            background: 'crimson',
                            color: '#fff',
                            border: 'none',
                            padding: '8px 14px',
                            borderRadius: 4,
                            cursor: 'pointer',
                        }}
                    >
                        Delete
                    </button>
                </div>
            </div>
        </div>
    );
}

function getDeleteMessage(pendingDelete: Exclude<PendingDelete, null>) {
    if (pendingDelete.kind === 'cluster') {
        return 'Delete this cluster? Its cores, cluster memory, and related communication paths will also be removed.';
    }

    if (pendingDelete.kind === 'core') {
        return 'Delete this core? Related communication paths will also be removed.';
    }

    if (pendingDelete.kind === 'memory') {
        return 'Delete this memory node? Related communication paths will also be removed.';
    }

    return 'Delete this communication path?';
}

function buildPlatformGraph(
    platform: Platform,
    communications: Communication[],
): {
    nodes: Node[];
    edges: Edge[];
} {
    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const nodeIdByReference = new Map<string, string>();

    const horizontalSpacing = 420;
    const verticalSpacing = 480;

    platform.clusters.forEach((cluster, clusterIndex) => {
        const column = clusterIndex % 2;
        const row = Math.floor(clusterIndex / 2);

        const clusterX = column * horizontalSpacing + 40;
        const clusterY = row * verticalSpacing + 60;
        const clusterNodeId = `cluster:${cluster.id}`;

        const coreRows = Math.max(1, Math.ceil(cluster.cores.length / 2));
        const sharedCache = cluster.memory?.find((memory) => memory.type === 'cache');
        const clusterHeight = 84 + (coreRows * 110) + (sharedCache ? 60 : 20);

        nodeIdByReference.set(cluster.id, clusterNodeId);

        nodes.push({
            id: clusterNodeId,
            type: 'cluster',
            position: { x: clusterX, y: clusterY },
            data: { cluster, height: clusterHeight },
            draggable: true,
        });

        cluster.cores.forEach((core, coreIndex) => {
            const coreNodeId = `core:${cluster.id}:${core.id}`;
            const localCacheNodeId = `cache:l1:${cluster.id}:${core.id}`;

            const relX = 24 + (coreIndex % 2) * 170;
            const relY = 84 + Math.floor(coreIndex / 2) * 110;

            nodeIdByReference.set(core.id, coreNodeId);
            nodeIdByReference.set(`${cluster.id}:${core.id}`, coreNodeId);

            nodes.push({
                id: coreNodeId,
                type: 'core',
                position: { x: relX, y: relY },
                data: { core },
                draggable: true,
                parentNode: clusterNodeId,
                extent: 'parent',
            });

            nodes.push({
                id: localCacheNodeId,
                type: 'cache',
                position: { x: relX, y: relY + 70 },
                data: { label: 'L1 cache', width: 114 },
                draggable: true,
                parentNode: clusterNodeId,
                extent: 'parent',
            });

            edges.push({
                id: `edge:${coreNodeId}:${localCacheNodeId}`,
                source: coreNodeId,
                target: localCacheNodeId,
                hidden: true,
            });
        });

        if (sharedCache) {
            nodes.push({
                id: `cache:shared:${cluster.id}`,
                type: 'cache',
                position: {
                    x: 14,
                    y: 84 + (coreRows * 110),
                },
                data: {
                    label: `${sharedCache.level ?? 'L2'} shared cache`,
                    width: 300,
                },
                draggable: true,
                parentNode: clusterNodeId,
                extent: 'parent',
            });
        }
    });

    const clusterRows = Math.ceil(platform.clusters.length / 2);
    const memoryStartY = clusterRows > 0 ? clusterRows * verticalSpacing + 40 : 60;

    (platform.memoryNodes ?? []).forEach((memory, memoryIndex) => {
        const memoryNodeId = `memory:${memory.id}`;
        const column = memoryIndex % 3;
        const row = Math.floor(memoryIndex / 3);

        nodeIdByReference.set(memory.id, memoryNodeId);

        nodes.push({
            id: memoryNodeId,
            type: 'memory',
            position: {
                x: 40 + column * 240,
                y: memoryStartY + row * 130,
            },
            data: { memory },
            draggable: true,
        });
    });

    communications.forEach((comm, index) => {
        const source = nodeIdByReference.get(comm.source);
        const target = nodeIdByReference.get(comm.target);

        if (!source || !target) return;

        edges.push({
            id: getCommunicationId(comm, index),
            source,
            target,
            label: `Penalty ${comm.penalty}`,
            type: 'smoothstep',
            animated: true,
            style: { strokeWidth: 2 },
            labelBgStyle: {
                fill: '#fff',
                fillOpacity: 0.85,
            },
            labelStyle: {
                fontSize: 12,
            },
        });
    });

    return { nodes, edges };
}

function getEntityIds(platform: Platform) {
    return [
        ...platform.clusters.flatMap((cluster) => [
            cluster.id,
            ...cluster.cores.map((core) => core.id),
        ]),
        ...(platform.memoryNodes ?? []).map((memory) => memory.id),
    ];
}

function entityExists(platform: Platform, id: string) {
    return getEntityIds(platform).includes(id);
}

function getCommunicationId(comm: Communication, index: number) {
    return `comm:${index}:${comm.source}->${comm.target}`;
}

function replaceCommunicationEndpoint(
    communications: Communication[],
    previousId: string,
    nextId: string,
) {
    return communications.map((comm) => ({
        ...comm,
        source: comm.source === previousId ? nextId : comm.source,
        target: comm.target === previousId ? nextId : comm.target,
    }));
}

function removeCommunicationReferences(
    communications: Communication[],
    references: Set<string>,
) {
    return communications.filter(
        (comm) => !references.has(comm.source) && !references.has(comm.target),
    );
}

function replaceAccessibleBy(
    memoryNodes: MemoryNode[] | undefined,
    previousId: string,
    nextId: string,
) {
    return memoryNodes?.map((memory) => ({
        ...memory,
        accessibleBy: (memory.accessibleBy ?? []).map((id) =>
            id === previousId ? nextId : id,
        ),
    }));
}

function removeAccessibleBy(
    memoryNodes: MemoryNode[] | undefined,
    references: Set<string>,
) {
    return memoryNodes?.map((memory) => ({
        ...memory,
        accessibleBy: (memory.accessibleBy ?? []).filter(
            (id) => !references.has(id),
        ),
    }));
}

function countCores(clusters: Cluster[]) {
    return clusters.reduce((sum, cluster) => sum + cluster.cores.length, 0);
}

const iconButtonStyle: React.CSSProperties = {
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: 24,
};

const menuButtonStyle: React.CSSProperties = {
    width: '100%',
    border: 'none',
    background: '#fff',
    padding: '10px 12px',
    textAlign: 'left',
    cursor: 'pointer',
};
