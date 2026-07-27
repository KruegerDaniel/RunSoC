'use client';

import { useEffect, useState } from 'react';
import HintIcon from '@/app/_components/runnable-config/HintIcon';
import type { Cluster, ClusterMemory, Core } from '@/lib/types/mpsoc';

type DialogMode = 'add' | 'edit';

export type ClusterDialogState = {
    kind: 'cluster';
    mode: DialogMode;
    cluster?: Cluster;
};

export type CoreDialogState = {
    kind: 'core';
    mode: DialogMode;
    clusterId: string;
    core?: Core;
};

export type ClusterCoreDialogState = ClusterDialogState | CoreDialogState;

type ClusterCoreDialogProps = {
    state: ClusterCoreDialogState;
    onCancel: () => void;
    onSaveCluster: (cluster: Cluster, previousClusterId?: string) => void;
    onSaveCore: (clusterId: string, core: Core, previousCoreId?: string) => void;
};

const defaultCluster: Cluster = {
    id: '',
    name: '',
    type: 'application',
    executionDomain: 'general_purpose',
    numCores: 0,
    cores: [],
    memory: [],
};

const defaultCore: Core = {
    id: '',
    name: '',
    executionDomain: 'general_purpose',
    wcetScale: 1,
    supportedTaskTypes: ['event', 'periodic'],
};

export default function ClusterCoreDialog({
    state,
    onCancel,
    onSaveCluster,
    onSaveCore,
}: ClusterCoreDialogProps) {
    if (state.kind === 'cluster') {
        return (
            <ClusterDialog
                state={state}
                onCancel={onCancel}
                onSave={onSaveCluster}
            />
        );
    }

    return (
        <CoreDialog
            state={state}
            onCancel={onCancel}
            onSave={onSaveCore}
        />
    );
}

function ClusterDialog({
    state,
    onCancel,
    onSave,
}: {
    state: ClusterDialogState;
    onCancel: () => void;
    onSave: (cluster: Cluster, previousClusterId?: string) => void;
}) {
    const [cluster, setCluster] = useState<Cluster>(defaultCluster);
    const previousClusterId = state.cluster?.id;

    useEffect(() => {
        setCluster({
            ...defaultCluster,
            ...state.cluster,
            memory: state.cluster?.memory ?? [],
            cores: state.cluster?.cores ?? [],
        });
    }, [state.cluster]);

    function updateField<K extends keyof Cluster>(key: K, value: Cluster[K]) {
        setCluster((current) => ({
            ...current,
            [key]: value,
        }));
    }

    function addMemory() {
        setCluster((current) => ({
            ...current,
            memory: [
                ...(current.memory ?? []),
                {
                    type: 'cache',
                    level: 'L2',
                    sizeKB: 0,
                    notes: '',
                },
            ],
        }));
    }

    function updateMemory<K extends keyof ClusterMemory>(
        index: number,
        key: K,
        value: ClusterMemory[K],
    ) {
        setCluster((current) => ({
            ...current,
            memory: (current.memory ?? []).map((memory, memoryIndex) =>
                memoryIndex === index
                    ? {
                        ...memory,
                        [key]: value,
                    }
                    : memory,
            ),
        }));
    }

    function removeMemory(index: number) {
        setCluster((current) => ({
            ...current,
            memory: (current.memory ?? []).filter(
                (_, memoryIndex) => memoryIndex !== index,
            ),
        }));
    }

    function handleDone() {
        if (!cluster.id.trim()) {
            window.alert('Cluster ID is required.');
            return;
        }

        if (!cluster.name.trim()) {
            window.alert('Cluster name is required.');
            return;
        }

        onSave(
            {
                ...cluster,
                id: cluster.id.trim(),
                name: cluster.name.trim(),
                numCores: cluster.cores.length,
                memory: cluster.memory ?? [],
            },
            previousClusterId,
        );
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Cluster' : 'Edit Cluster'}
            onCancel={onCancel}
            onDone={handleDone}
        >
            <DialogField
                label="ID"
                hint="Unique cluster identifier used by cores, memory accessibility, and solver input."
            >
                <input
                    value={cluster.id}
                    placeholder="app_cluster_0"
                    onChange={(event) => updateField('id', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Name"
                hint="Human-readable cluster name shown in the sidebar."
            >
                <input
                    value={cluster.name}
                    placeholder="General Purpose"
                    onChange={(event) =>
                        updateField('name', event.target.value)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Execution Domain"
                hint="Logical execution domain, for example general_purpose, safety, audio, or always_on."
            >
                <input
                    value={cluster.executionDomain ?? ''}
                    placeholder="general_purpose"
                    onChange={(event) =>
                        updateField(
                            'executionDomain',
                            event.target.value || undefined,
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Type"
                hint="Cluster category used by the solver and UI."
            >
                <input
                    value={cluster.type}
                    placeholder="application"
                    onChange={(event) =>
                        updateField('type', event.target.value)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Count"
                hint="Optional multiplicity of this cluster definition."
            >
                <input
                    type="number"
                    value={cluster.count ?? ''}
                    placeholder="1"
                    onChange={(event) =>
                        updateField(
                            'count',
                            event.target.value === ''
                                ? undefined
                                : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <div style={sectionHeaderStyle}>
                <span>
                    Memory
                    <HintIcon
                        hint="Cluster-local memory entries. Use this for shared cache or local cluster memory."
                        side="right"
                    />
                </span>

                <button onClick={addMemory} type="button" style={plusButtonStyle}>
                    +
                </button>
            </div>

            {(cluster.memory ?? []).map((memory, index) => (
                <div key={index} style={memoryCardStyle}>
                    <div style={memoryHeaderStyle}>
                        <strong>Memory {index + 1}</strong>
                        <button
                            type="button"
                            onClick={() => removeMemory(index)}
                            style={removeButtonStyle}
                        >
                            Remove
                        </button>
                    </div>

                    <DialogField
                        label="Type"
                        hint="Memory type, for example cache, scratchpad, tcm, or sram."
                    >
                        <input
                            value={memory.type}
                            placeholder="cache"
                            onChange={(event) =>
                                updateMemory(index, 'type', event.target.value)
                            }
                            style={inputStyle}
                        />
                    </DialogField>

                    <DialogField
                        label="Level"
                        hint="Optional cache level, for example L1, L2, or L3."
                    >
                        <input
                            value={memory.level ?? ''}
                            placeholder="L2"
                            onChange={(event) =>
                                updateMemory(
                                    index,
                                    'level',
                                    event.target.value || undefined,
                                )
                            }
                            style={inputStyle}
                        />
                    </DialogField>

                    <DialogField
                        label="Size KB"
                        hint="Memory capacity in kilobytes."
                    >
                        <input
                            type="number"
                            value={memory.sizeKB}
                            placeholder="2048"
                            onChange={(event) =>
                                updateMemory(
                                    index,
                                    'sizeKB',
                                    Number(event.target.value),
                                )
                            }
                            style={inputStyle}
                        />
                    </DialogField>

                    <DialogField
                        label="Notes"
                        hint="Optional descriptive notes."
                    >
                        <input
                            value={memory.notes ?? ''}
                            placeholder="2MB shared cache"
                            onChange={(event) =>
                                updateMemory(
                                    index,
                                    'notes',
                                    event.target.value || undefined,
                                )
                            }
                            style={inputStyle}
                        />
                    </DialogField>
                </div>
            ))}

            <DialogField
                label="Notes"
                hint="Optional notes about this cluster."
            >
                <input
                    value={cluster.notes ?? ''}
                    placeholder="Arm Cortex-A cluster"
                    onChange={(event) =>
                        updateField('notes', event.target.value || undefined)
                    }
                    style={inputStyle}
                />
            </DialogField>
        </DialogShell>
    );
}

function CoreDialog({
    state,
    onCancel,
    onSave,
}: {
    state: CoreDialogState;
    onCancel: () => void;
    onSave: (clusterId: string, core: Core, previousCoreId?: string) => void;
}) {
    const [core, setCore] = useState<Core>(defaultCore);
    const previousCoreId = state.core?.id;

    useEffect(() => {
        setCore({
            ...defaultCore,
            ...state.core,
            supportedTaskTypes:
                state.core?.supportedTaskTypes ?? ['event', 'periodic'],
        });
    }, [state.core]);

    function updateField<K extends keyof Core>(key: K, value: Core[K]) {
        setCore((current) => ({
            ...current,
            [key]: value,
        }));
    }

    function handleDone() {
        if (!core.id.trim()) {
            window.alert('Core ID is required.');
            return;
        }

        if (!core.name.trim()) {
            window.alert('Core name is required.');
            return;
        }

        onSave(
            state.clusterId,
            {
                ...core,
                id: core.id.trim(),
                name: core.name.trim(),
                supportedTaskTypes: core.supportedTaskTypes.length
                    ? core.supportedTaskTypes
                    : ['event', 'periodic'],
            },
            previousCoreId,
        );
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Core' : 'Edit Core'}
            onCancel={onCancel}
            onDone={handleDone}
        >
            <DialogField
                label="ID"
                hint="Unique core identifier used by task mappings and solver input."
            >
                <input
                    value={core.id}
                    placeholder="core_00"
                    onChange={(event) => updateField('id', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Name"
                hint="Human-readable core name."
            >
                <input
                    value={core.name}
                    placeholder="arm_cortex_a78ae"
                    onChange={(event) =>
                        updateField('name', event.target.value)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Execution Domain"
                hint="Execution domain supported by this core."
            >
                <input
                    value={core.executionDomain}
                    placeholder="general_purpose"
                    onChange={(event) =>
                        updateField('executionDomain', event.target.value)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Frequency GHz"
                hint="Optional operating frequency in GHz."
            >
                <input
                    type="number"
                    step="0.1"
                    value={core.frequencyGhz ?? ''}
                    placeholder="2.2"
                    onChange={(event) =>
                        updateField(
                            'frequencyGhz',
                            event.target.value === ''
                                ? undefined
                                : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="WCET Scale"
                hint="Multiplier applied to task WCET when executed on this core."
            >
                <input
                    type="number"
                    step="0.1"
                    value={core.wcetScale}
                    placeholder="1.0"
                    onChange={(event) =>
                        updateField('wcetScale', Number(event.target.value))
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Local Memory KB"
                hint="Optional core-local memory size in kilobytes."
            >
                <input
                    type="number"
                    value={core.localMemoryKB ?? ''}
                    placeholder="384"
                    onChange={(event) =>
                        updateField(
                            'localMemoryKB',
                            event.target.value === ''
                                ? undefined
                                : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Supported Task Types"
                hint="Comma-separated task types supported by this core."
            >
                <input
                    value={core.supportedTaskTypes.join(', ')}
                    placeholder="event, periodic"
                    onChange={(event) =>
                        updateField(
                            'supportedTaskTypes',
                            event.target.value
                                .split(',')
                                .map((item) => item.trim())
                                .filter(Boolean),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Count"
                hint="Optional multiplicity of this core definition."
            >
                <input
                    type="number"
                    value={core.count ?? ''}
                    placeholder="1"
                    onChange={(event) =>
                        updateField(
                            'count',
                            event.target.value === ''
                                ? undefined
                                : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Notes"
                hint="Optional notes about this core."
            >
                <input
                    value={core.notes ?? ''}
                    placeholder="64KB L1 I-cache + 64KB L1 D-cache"
                    onChange={(event) =>
                        updateField('notes', event.target.value || undefined)
                    }
                    style={inputStyle}
                />
            </DialogField>
        </DialogShell>
    );
}

function DialogShell({
    title,
    children,
    onCancel,
    onDone,
}: {
    title: string;
    children: React.ReactNode;
    onCancel: () => void;
    onDone: () => void;
}) {
    return (
        <div style={overlayStyle}>
            <div style={dialogStyle}>
                <h2 style={dialogTitleStyle}>{title}</h2>

                <div style={dialogContentStyle}>{children}</div>

                <div style={dialogActionsStyle}>
                    <button onClick={onDone} style={doneButtonStyle}>
                        Done
                    </button>
                    <button onClick={onCancel} style={cancelButtonStyle}>
                        Cancel
                    </button>
                </div>
            </div>
        </div>
    );
}

function DialogField({
    label,
    hint,
    children,
}: {
    label: string;
    hint: string;
    children: React.ReactNode;
}) {
    return (
        <label style={fieldStyle}>
            <span style={labelStyle}>
                {label}
                <HintIcon hint={hint} side="right" />
            </span>
            {children}
        </label>
    );
}

const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 100,
    background: 'rgba(0, 0, 0, 0.28)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
};

const dialogStyle: React.CSSProperties = {
    width: 484,
    maxHeight: '86vh',
    background: '#fff',
    padding: '0 48px 12px',
    boxShadow: '0 8px 28px rgba(0, 0, 0, 0.2)',
    overflowY: 'auto',
};

const dialogTitleStyle: React.CSSProperties = {
    margin: '0 0 14px',
    paddingTop: 4,
    fontSize: 16,
    fontWeight: 700,
};

const dialogContentStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
};

const fieldStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
};

const labelStyle: React.CSSProperties = {
    fontSize: 16,
    color: '#333',
};

const inputStyle: React.CSSProperties = {
    height: 40,
    border: '1px solid #ddd',
    borderRadius: 8,
    padding: '0 14px',
    fontSize: 16,
    outline: 'none',
};

const sectionHeaderStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: 16,
    color: '#333',
};

const plusButtonStyle: React.CSSProperties = {
    width: 30,
    height: 30,
    borderRadius: 6,
    border: '1px solid #ccc',
    background: '#fafafa',
    cursor: 'pointer',
    fontSize: 20,
    lineHeight: 1,
};

const memoryCardStyle: React.CSSProperties = {
    border: '1px solid #e0e0e0',
    borderRadius: 8,
    padding: 14,
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
};

const memoryHeaderStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
};

const removeButtonStyle: React.CSSProperties = {
    border: 'none',
    background: 'transparent',
    color: 'crimson',
    cursor: 'pointer',
};

const dialogActionsStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 80,
    paddingBottom: 0,
};

const doneButtonStyle: React.CSSProperties = {
    border: 'none',
    background: '#0d8cff',
    color: '#fff',
    borderRadius: 6,
    padding: '10px 18px',
    fontSize: 15,
    cursor: 'pointer',
};

const cancelButtonStyle: React.CSSProperties = {
    border: 'none',
    background: '#e51e25',
    color: '#fff',
    borderRadius: 6,
    padding: '10px 18px',
    fontSize: 15,
    cursor: 'pointer',
};
