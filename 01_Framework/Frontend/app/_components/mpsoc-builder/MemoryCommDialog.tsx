'use client';

import { useEffect, useState } from 'react';
import HintIcon from '@/app/_components/runnable-config/HintIcon';

// Assuming these types are exported from your types file:
import type { MemoryNode, Communication } from '@/lib/types/mpsoc';

type DialogMode = 'add' | 'edit';

export type MemoryDialogState = {
    kind: 'memory';
    mode: DialogMode;
    memory?: MemoryNode;
};

export type CommDialogState = {
    kind: 'comm';
    mode: DialogMode;
    comm?: Communication;
    // We pass a composite ID string (e.g. "source-target-index") 
    // to track edits since Communication lacks a native ID field.
    commId?: string;
};

export type MemoryCommDialogState = MemoryDialogState | CommDialogState;

type MemoryCommDialogProps = {
    state: MemoryCommDialogState;
    onCancel: () => void;
    onSaveMemory: (memory: MemoryNode, previousMemoryId?: string) => void;
    onSaveComm: (comm: Communication, previousCommId?: string) => void;
};

const defaultMemory: MemoryNode = {
    id: '',
    name: '',
    type: 'dram',
    scope: 'system',
    accessibleBy: [],
    capacityGB: 0,
    coherent: false,
};

const defaultComm: Communication = {
    source: '',
    target: '',
    penalty: 0,
};

export default function MemoryCommDialog({
    state,
    onCancel,
    onSaveMemory,
    onSaveComm,
}: MemoryCommDialogProps) {
    if (state.kind === 'memory') {
        return (
            <MemoryDialog
                state={state}
                onCancel={onCancel}
                onSave={onSaveMemory}
            />
        );
    }

    return (
        <CommDialog
            state={state}
            onCancel={onCancel}
            onSave={onSaveComm}
        />
    );
}

function MemoryDialog({
    state,
    onCancel,
    onSave,
}: {
    state: MemoryDialogState;
    onCancel: () => void;
    onSave: (memory: MemoryNode, previousMemoryId?: string) => void;
}) {
    const [memory, setMemory] = useState<MemoryNode>(defaultMemory);
    const previousMemoryId = state.memory?.id;

    useEffect(() => {
        setMemory({
            ...defaultMemory,
            ...state.memory,
            accessibleBy: state.memory?.accessibleBy ?? [],
        });
    }, [state.memory]);

    function updateField<K extends keyof MemoryNode>(key: K, value: MemoryNode[K]) {
        setMemory((current) => ({
            ...current,
            [key]: value,
        }));
    }

    function handleDone() {
        if (!memory.id.trim()) {
            window.alert('Memory ID is required.');
            return;
        }

        if (!memory.name.trim()) {
            window.alert('Memory name is required.');
            return;
        }

        if (memory.capacityGB < 0) {
            window.alert('Capacity must be a positive number.');
            return;
        }

        onSave(
            {
                ...memory,
                id: memory.id.trim(),
                name: memory.name.trim(),
            },
            previousMemoryId,
        );
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Memory Node' : 'Edit Memory Node'}
            onCancel={onCancel}
            onDone={handleDone}
        >
            <DialogField
                label="ID"
                hint="Unique memory identifier used by solvers and platform configuration."
            >
                <input
                    value={memory.id}
                    placeholder="mn_00"
                    onChange={(event) => updateField('id', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Name"
                hint="Human-readable memory node name."
            >
                <input
                    value={memory.name}
                    placeholder="main_dram"
                    onChange={(event) => updateField('name', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Type"
                hint="Hardware type of this memory (e.g., dram, sram, flash)."
            >
                <input
                    value={memory.type}
                    placeholder="dram"
                    onChange={(event) => updateField('type', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Scope"
                hint="Logical scope of the memory, such as 'system' or 'cluster'."
            >
                <input
                    value={memory.scope}
                    placeholder="system"
                    onChange={(event) => updateField('scope', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Technology"
                hint="Optional underlying hardware tech (e.g., LPDDR5)."
            >
                <input
                    value={memory.technology ?? ''}
                    placeholder="LPDDR5"
                    onChange={(event) =>
                        updateField('technology', event.target.value || undefined)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Capacity GB"
                hint="Memory capacity in Gigabytes."
            >
                <input
                    type="number"
                    step="0.1"
                    value={memory.capacityGB === 0 ? '' : memory.capacityGB}
                    placeholder="64"
                    onChange={(event) =>
                        updateField(
                            'capacityGB',
                            event.target.value === '' ? 0 : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Accessible By"
                hint="Comma-separated list of cluster or core IDs that can access this memory."
            >
                <input
                    value={memory.accessibleBy.join(', ')}
                    placeholder="app_cluster_0, comms_cluster_0"
                    onChange={(event) =>
                        updateField(
                            'accessibleBy',
                            event.target.value
                                .split(',')
                                .map((item) => item.trim())
                                .filter(Boolean),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <label style={{ ...fieldStyle, flexDirection: 'row', alignItems: 'center' }}>
                <input
                    type="checkbox"
                    checked={memory.coherent}
                    onChange={(event) => updateField('coherent', event.target.checked)}
                    style={{ width: 18, height: 18, cursor: 'pointer' }}
                />
                <span style={{ fontSize: 16, color: '#333' }}>
                    Coherent
                    <HintIcon hint="Is this memory domain cache-coherent?" side="right" />
                </span>
            </label>

            <DialogField
                label="Contention Domain"
                hint="Optional domain defining shared contention limits (e.g., mm_ddr)."
            >
                <input
                    value={memory.contentionDomain ?? ''}
                    placeholder="mm_ddr"
                    onChange={(event) =>
                        updateField('contentionDomain', event.target.value || undefined)
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Notes"
                hint="Optional notes about this memory node."
            >
                <input
                    value={memory.notes ?? ''}
                    placeholder="64 GB 256-bit LPDDR5 DRAM..."
                    onChange={(event) =>
                        updateField('notes', event.target.value || undefined)
                    }
                    style={inputStyle}
                />
            </DialogField>
        </DialogShell>
    );
}

function CommDialog({
    state,
    onCancel,
    onSave,
}: {
    state: CommDialogState;
    onCancel: () => void;
    onSave: (comm: Communication, previousCommId?: string) => void;
}) {
    const [comm, setComm] = useState<Communication>(defaultComm);
    const previousCommId = state.commId;

    useEffect(() => {
        setComm({
            ...defaultComm,
            ...state.comm,
        });
    }, [state.comm]);

    function updateField<K extends keyof Communication>(key: K, value: Communication[K]) {
        setComm((current) => ({
            ...current,
            [key]: value,
        }));
    }

    function handleDone() {
        if (!comm.source.trim()) {
            window.alert('Source ID is required.');
            return;
        }

        if (!comm.target.trim()) {
            window.alert('Target ID is required.');
            return;
        }

        onSave(
            {
                ...comm,
                source: comm.source.trim(),
                target: comm.target.trim(),
            },
            previousCommId,
        );
    }

    return (
        <DialogShell
            title={state.mode === 'add' ? 'Add Communication Path' : 'Edit Communication Path'}
            onCancel={onCancel}
            onDone={handleDone}
        >
            <DialogField
                label="Source"
                hint="Source cluster or core ID."
            >
                <input
                    value={comm.source}
                    placeholder="core_0"
                    onChange={(event) => updateField('source', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Target"
                hint="Target cluster or core ID."
            >
                <input
                    value={comm.target}
                    placeholder="core_1"
                    onChange={(event) => updateField('target', event.target.value)}
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Penalty"
                hint="Cost or latency penalty of communicating between source and target."
            >
                <input
                    type="number"
                    value={comm.penalty === 0 && state.mode === 'add' ? '' : comm.penalty}
                    placeholder="15"
                    onChange={(event) =>
                        updateField(
                            'penalty',
                            event.target.value === '' ? 0 : Number(event.target.value),
                        )
                    }
                    style={inputStyle}
                />
            </DialogField>

            <DialogField
                label="Notes"
                hint="Optional notes about this communication link."
            >
                <input
                    value={comm.notes ?? ''}
                    placeholder="Inter-cluster mesh routing penalty"
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

// -----------------------------------------------------------------------------
// Styles
// -----------------------------------------------------------------------------

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