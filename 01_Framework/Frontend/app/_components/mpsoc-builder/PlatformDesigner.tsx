'use client';

import { useMemo, useState } from 'react';
import ReactFlow, { Background, Controls, Edge, Handle, Node, NodeProps, Position } from 'reactflow';
import 'reactflow/dist/style.css';

import { useJsonModel } from '@/lib/JsonModelContext';
import type { Cluster, Core, Platform } from '@/lib/types/mpsoc';
import ClusterCoreDialog, { ClusterCoreDialogState } from '@/app/_components/mpsoc-builder/ClusterCoreDialog';

type PendingDelete =
    | { kind: 'cluster'; clusterId: string }
    | { kind: 'core'; clusterId: string; coreId: string }
    | null;

type DropdownState =
    | { kind: 'cluster'; id: string }
    | { kind: 'core'; id: string }
    | null;

type ClusterNodeData = {
    cluster: Cluster;
};

type CoreNodeData = {
    core: Core;
};

type CacheNodeData = {
    label: string;
};

function ClusterNode({ data }: NodeProps<ClusterNodeData>) {
    return (
        <div
            style={{
                width: 330,
                minHeight: 250,
                background: '#bebebe',
                border: '1px solid #aaa',
                padding: 16,
                textAlign: 'center',
                fontFamily: 'Arial, sans-serif',
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
                width: 300,
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

const nodeTypes = {
    cluster: ClusterNode,
    core: CoreNode,
    cache: CacheNode,
};

export default function PlatformDesigner() {
    const { model, updatePlatform } = useJsonModel();
    const platform = model.platform;

    const [clusterCoreDialog, setClusterCoreDialog] =
        useState<ClusterCoreDialogState | null>(null);
    const [openDropdown, setOpenDropdown] = useState<DropdownState>(null);
    const [pendingDelete, setPendingDelete] = useState<PendingDelete>(null);

    const { nodes, edges } = useMemo(() => {
        return buildPlatformGraph(platform);
    }, [platform]);

    function setPlatform(nextPlatform: Platform) {
        updatePlatform(nextPlatform);
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

    function saveCluster(cluster: Cluster, previousClusterId?: string) {
        const isEdit = Boolean(previousClusterId);

        const duplicate = platform.clusters.some(
            (item) => item.id === cluster.id && item.id !== previousClusterId,
        );

        if (duplicate) {
            window.alert(`Cluster ID "${cluster.id}" already exists.`);
            return;
        }

        let nextClusters: Cluster[];

        if (isEdit) {
            nextClusters = platform.clusters.map((item) =>
                item.id === previousClusterId
                    ? {
                        ...cluster,
                        cores: item.cores,
                        numCores: item.cores.length,
                    }
                    : item,
            );
        } else {
            nextClusters = [
                ...platform.clusters,
                {
                    ...cluster,
                    cores: [],
                    numCores: 0,
                },
            ];
        }

        setPlatform({
            ...platform,
            clusters: nextClusters,
            numClusters: nextClusters.length,
            numCores: countCores(nextClusters),
        });

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

        setPlatform({
            ...platform,
            clusters: nextClusters,
            numCores: countCores(nextClusters),
        });

        setClusterCoreDialog(null);
    }
    function confirmDelete() {
        if (!pendingDelete) return;

        if (pendingDelete.kind === 'cluster') {
            const nextClusters = platform.clusters.filter(
                (cluster) => cluster.id !== pendingDelete.clusterId,
            );

            setPlatform({
                ...platform,
                clusters: nextClusters,
                numClusters: nextClusters.length,
                numCores: countCores(nextClusters),
            });
        }

        if (pendingDelete.kind === 'core') {
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

            setPlatform({
                ...platform,
                clusters: nextClusters,
                numCores: countCores(nextClusters),
            });
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

                <aside>
                    <Panel
                        title="Clusters"
                        actionLabel="+"
                        onAction={addCluster}
                    >
                        {platform.clusters.map((cluster) => (
                            <ListEntry
                                key={cluster.id}
                                title={cluster.name}
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
                        ))}
                    </Panel>

                    <Panel title="Cores" actionLabel="+" onAction={addCore}>
                        {platform.clusters.flatMap((cluster) =>
                            cluster.cores.map((core) => (
                                <ListEntry
                                    key={`${cluster.id}:${core.id}`}
                                    title={core.name}
                                    subtitle={core.id}
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
                                    onEdit={() =>
                                        editCore(cluster.id, core.id)
                                    }
                                    onDelete={() =>
                                        setPendingDelete({
                                            kind: 'core',
                                            clusterId: cluster.id,
                                            coreId: core.id,
                                        })
                                    }
                                />
                            )),
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
    return (
        <section
            style={{
                border: '1px solid #d5d5d5',
                borderRadius: 6,
                background: '#fff',
                padding: '24px 24px 30px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.15)',
                marginBottom: 0,
            }}
        >
            <div
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: '1px solid #d5d5d5',
                    paddingBottom: 14,
                    marginBottom: 10,
                }}
            >
                <h2 style={{ margin: 0, fontSize: 16 }}>{title}</h2>

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

            {children}
        </section>
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
    pendingDelete: PendingDelete;
    onCancel: () => void;
    onConfirm: () => void;
}) {
    const message =
        pendingDelete?.kind === 'cluster'
            ? 'Delete this cluster? Its cores and cluster memory will also be removed.'
            : 'Delete this core?';

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

function buildPlatformGraph(platform: Platform): {
    nodes: Node[];
    edges: Edge[];
} {
    const nodes: Node[] = [];
    const edges: Edge[] = [];

    const horizontalSpacing = 420;
    const verticalSpacing = 360;

    platform.clusters.forEach((cluster, clusterIndex) => {
        const column = clusterIndex % 2;
        const row = Math.floor(clusterIndex / 2);

        const clusterX = column * horizontalSpacing + 40;
        const clusterY = row * verticalSpacing + 60;

        const clusterNodeId = `cluster:${cluster.id}`;

        nodes.push({
            id: clusterNodeId,
            type: 'cluster',
            position: { x: clusterX, y: clusterY },
            data: { cluster },
            draggable: true,
        });

        cluster.cores.forEach((core, coreIndex) => {
            const coreNodeId = `core:${cluster.id}:${core.id}`;
            const localCacheNodeId = `cache:l1:${cluster.id}:${core.id}`;

            const coreX = clusterX + 24 + (coreIndex % 2) * 170;
            const coreY = clusterY + 84 + Math.floor(coreIndex / 2) * 110;

            nodes.push({
                id: coreNodeId,
                type: 'core',
                position: { x: coreX, y: coreY },
                data: { core },
                draggable: true,
            });

            nodes.push({
                id: localCacheNodeId,
                type: 'cache',
                position: { x: coreX, y: coreY + 70 },
                data: { label: 'L1 cache' },
                draggable: true,
            });

            edges.push({
                id: `edge:${coreNodeId}:${localCacheNodeId}`,
                source: coreNodeId,
                target: localCacheNodeId,
                hidden: true,
            });
        });

        const sharedCache = cluster.memory?.find(
            (memory) => memory.type === 'cache',
        );

        if (sharedCache) {
            nodes.push({
                id: `cache:shared:${cluster.id}`,
                type: 'cache',
                position: {
                    x: clusterX + 14,
                    y: clusterY + 210,
                },
                data: {
                    label: `${sharedCache.level ?? 'L2'} shared cache`,
                },
                draggable: true,
            });
        }
    });

    return { nodes, edges };
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
