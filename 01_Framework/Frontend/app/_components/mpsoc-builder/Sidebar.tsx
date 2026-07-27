'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useRef, useState } from 'react';
import { useJsonModel } from '@/lib/JsonModelContext';
import type { SolverJson } from '@/lib/types/mpsoc';

const WARNING_STORAGE_KEY = 'runsoc:v2:skip-import-overwrite-warning';

const items = [
    { href: '/v2/platform', label: 'SoC Design', icon: '✦' },
    { href: '/v2/taskset', label: 'Tasks', icon: '✩' },
    { href: '/v2/config', label: 'Config', icon: '✩' },
    { href: '/v2/solve', label: 'Finalize', icon: '✓' },
];

const presets = [
    {
        label: 'Nvidia Jetson AGX Orin 64',
        fileName: 'nvidia-jetson-agx-orin64.json',
        href: '/nvidia-jetson-agx-orin64.json',
    },
    {
        label: 'Renesas R-car VH4',
        fileName: 'renesas-rcar-vh4.json',
        href: '/renesas-rcar-vh4.json',
    },
    {
        label: 'TI TDA4VM',
        fileName: 'ti-tda4vm.json',
        href: '/ti-tda4vm.json',
    },
];

type PendingImportAction =
    | { kind: 'file' }
    | { kind: 'preset'; preset: (typeof presets)[number] }
    | null;

function shouldSkipOverwriteWarning() {
    if (typeof window === 'undefined') return false;

    try {
        return window.localStorage.getItem(WARNING_STORAGE_KEY) === 'true';
    } catch {
        return false;
    }
}

function setSkipOverwriteWarning(value: boolean) {
    if (typeof window === 'undefined') return;

    try {
        if (value) {
            window.localStorage.setItem(WARNING_STORAGE_KEY, 'true');
        } else {
            window.localStorage.removeItem(WARNING_STORAGE_KEY);
        }
    } catch {
        // Ignore storage failures.
    }
}

function assertSolverJson(value: unknown): SolverJson {
    if (!value || typeof value !== 'object') {
        throw new Error('Imported JSON must be an object.');
    }

    const candidate = value as Partial<SolverJson>;

    if (!candidate.config || typeof candidate.config !== 'object') {
        throw new Error('Imported JSON is missing "config".');
    }

    if (!candidate.platform || typeof candidate.platform !== 'object') {
        throw new Error('Imported JSON is missing "platform".');
    }

    if (!Array.isArray(candidate.tasks)) {
        throw new Error('Imported JSON is missing "tasks" array.');
    }

    return {
        ...candidate,
        communications: candidate.communications ?? [],
    } as SolverJson;
}

export default function Sidebar() {
    const pathname = usePathname();
    const { model, setModel } = useJsonModel();

    const fileInputRef = useRef<HTMLInputElement | null>(null);

    const [presetOpen, setPresetOpen] = useState(false);
    const [pendingAction, setPendingAction] =
        useState<PendingImportAction>(null);
    const [doNotShowAgain, setDoNotShowAgain] = useState(false);
    const [error, setError] = useState<string | null>(null);

    function requestImportFile() {
        setError(null);

        if (shouldSkipOverwriteWarning()) {
            fileInputRef.current?.click();
            return;
        }

        setPendingAction({ kind: 'file' });
    }

    function requestPresetImport(preset: (typeof presets)[number]) {
        setError(null);
        setPresetOpen(false);

        if (shouldSkipOverwriteWarning()) {
            void loadPreset(preset);
            return;
        }

        setPendingAction({ kind: 'preset', preset });
    }

    function confirmPendingAction() {
        setSkipOverwriteWarning(doNotShowAgain);

        const action = pendingAction;
        setPendingAction(null);
        setDoNotShowAgain(false);

        if (!action) return;

        if (action.kind === 'file') {
            fileInputRef.current?.click();
            return;
        }

        void loadPreset(action.preset);
    }

    function cancelPendingAction() {
        setPendingAction(null);
        setDoNotShowAgain(false);
    }

    async function handleImportFile(file: File | undefined) {
        if (!file) return;

        setError(null);

        try {
            const text = await file.text();
            const parsed = JSON.parse(text);
            setModel(assertSolverJson(parsed));
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : 'Could not import JSON file.',
            );
        } finally {
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    }

    async function loadPreset(preset: (typeof presets)[number]) {
        setError(null);

        try {
            const response = await fetch(preset.href, {
                headers: {
                    Accept: 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(
                    `Could not load ${preset.fileName}. HTTP ${response.status}`,
                );
            }

            const parsed = await response.json();
            setModel(assertSolverJson(parsed));
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : `Could not load preset ${preset.fileName}.`,
            );
        }
    }

    function exportJson() {
        const blob = new Blob([JSON.stringify(model, null, 2)], {
            type: 'application/json',
        });

        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');

        const platformName =
            model.platform?.name
                ?.trim()
                .toLowerCase()
                .replace(/[^a-z0-9-_]+/gi, '_') || 'solver_model';

        anchor.href = url;
        anchor.download = `${platformName}.json`;
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        URL.revokeObjectURL(url);
    }

    return (
        <aside
            style={{
                width: 94,
                minHeight: '100vh',
                background: '#f2f2f7',
                borderRight: '1px solid #e5e5e5',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                paddingTop: 48,
                paddingBottom: 18,
                gap: 28,
                position: 'fixed',
                left: 0,
                top: 0,
                zIndex: 50,
            }}
        >
            <div style={{ fontSize: 22, marginBottom: 20 }}>☰</div>

            {items.map((item) => {
                const active = pathname === item.href;

                return (
                    <Link
                        key={item.href}
                        href={item.href}
                        style={{
                            textDecoration: 'none',
                            color: '#333',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 6,
                            fontSize: 13,
                            width: '100%',
                        }}
                    >
                        <div
                            style={{
                                width: 54,
                                height: 28,
                                borderRadius: 999,
                                background: active ? '#e7ddff' : 'transparent',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: 20,
                            }}
                        >
                            {item.icon}
                        </div>
                        <span>{item.label}</span>
                    </Link>
                );
            })}

            <div style={{ flex: 1 }} />

            <div
                style={{
                    position: 'relative',
                    width: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 10,
                }}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="application/json,.json"
                    style={{ display: 'none' }}
                    onChange={(event) =>
                        void handleImportFile(event.target.files?.[0])
                    }
                />

                <SidebarActionButton
                    icon="⤴"
                    label="Import JSON"
                    title="Import JSON"
                    onClick={requestImportFile}
                />

                <div style={{ position: 'relative' }}>
                    <SidebarActionButton
                        icon="▣"
                        label="Preset SoC"
                        title="Use preset SoC"
                        onClick={() => setPresetOpen((current) => !current)}
                    />

                    {presetOpen && (
                        <div
                            style={{
                                position: 'absolute',
                                left: 82,
                                bottom: 0,
                                width: 260,
                                background: '#fff',
                                border: '1px solid #d0d0d0',
                                borderRadius: 10,
                                boxShadow: '0 8px 28px rgba(0,0,0,0.18)',
                                overflow: 'hidden',
                                zIndex: 90,
                            }}
                        >
                            <div
                                style={{
                                    padding: '10px 12px',
                                    fontSize: 12,
                                    fontWeight: 700,
                                    color: '#666',
                                    background: '#f7f7f7',
                                    borderBottom: '1px solid #e5e5e5',
                                }}
                            >
                                Use preset SoC
                            </div>

                            {presets.map((preset) => (
                                <button
                                    key={preset.fileName}
                                    type="button"
                                    onClick={() =>
                                        requestPresetImport(preset)
                                    }
                                    style={{
                                        width: '100%',
                                        border: 'none',
                                        background: '#fff',
                                        padding: '12px 14px',
                                        textAlign: 'left',
                                        cursor: 'pointer',
                                        fontSize: 14,
                                        color: '#222',
                                    }}
                                >
                                    <div>{preset.label}</div>
                                    <div
                                        style={{
                                            marginTop: 3,
                                            color: '#777',
                                            fontSize: 12,
                                            fontFamily: 'monospace',
                                        }}
                                    >
                                        {preset.fileName}
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                <SidebarActionButton
                    icon="⇩"
                    label="Export JSON"
                    title="Export JSON"
                    onClick={exportJson}
                />
            </div>

            {error && (
                <div
                    style={{
                        position: 'fixed',
                        left: 110,
                        bottom: 18,
                        width: 360,
                        border: '1px solid #f0b4b4',
                        background: '#fff1f1',
                        color: '#9f1d1d',
                        borderRadius: 10,
                        padding: 12,
                        fontSize: 13,
                        zIndex: 100,
                        boxShadow: '0 8px 28px rgba(0,0,0,0.16)',
                    }}
                >
                    <strong>JSON action failed</strong>
                    <div style={{ marginTop: 6 }}>{error}</div>
                    <button
                        type="button"
                        onClick={() => setError(null)}
                        style={{
                            marginTop: 10,
                            border: '1px solid #e0a0a0',
                            background: '#fff',
                            borderRadius: 6,
                            padding: '5px 9px',
                            cursor: 'pointer',
                        }}
                    >
                        Dismiss
                    </button>
                </div>
            )}

            {pendingAction && (
                <OverwriteWarningDialog
                    doNotShowAgain={doNotShowAgain}
                    setDoNotShowAgain={setDoNotShowAgain}
                    onCancel={cancelPendingAction}
                    onConfirm={confirmPendingAction}
                />
            )}
        </aside>
    );
}

function SidebarActionButton({
    icon,
    label,
    title,
    onClick,
}: {
    icon: string;
    label: string;
    title: string;
    onClick: () => void;
}) {
    return (
        <button
            type="button"
            title={title}
            aria-label={label}
            onClick={onClick}
            style={{
                width: 68,
                border: '1px solid #d6d6d6',
                borderRadius: 10,
                background: '#fff',
                color: '#333',
                cursor: 'pointer',
                padding: '7px 4px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 4,
                boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            }}
        >
            <span style={{ fontSize: 18, lineHeight: 1 }}>{icon}</span>
            <span style={{ fontSize: 10, lineHeight: 1.1 }}>{label}</span>
        </button>
    );
}

function OverwriteWarningDialog({
    doNotShowAgain,
    setDoNotShowAgain,
    onCancel,
    onConfirm,
}: {
    doNotShowAgain: boolean;
    setDoNotShowAgain: (value: boolean) => void;
    onCancel: () => void;
    onConfirm: () => void;
}) {
    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.32)',
                zIndex: 120,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            }}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-labelledby="overwrite-warning-title"
                style={{
                    width: 430,
                    background: '#fff',
                    borderRadius: 12,
                    padding: 24,
                    boxShadow: '0 14px 44px rgba(0,0,0,0.28)',
                }}
            >
                <h2
                    id="overwrite-warning-title"
                    style={{
                        margin: 0,
                        fontSize: 20,
                        color: '#111',
                    }}
                >
                    Overwrite current JSON?
                </h2>

                <p
                    style={{
                        margin: '12px 0 0',
                        color: '#555',
                        lineHeight: 1.5,
                        fontSize: 14,
                    }}
                >
                    Importing a JSON file or loading a preset SoC will replace
                    the current platform, taskset, communications, and config.
                    Export your current JSON first if you want to keep it.
                </p>

                <label
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginTop: 16,
                        fontSize: 14,
                        color: '#333',
                        cursor: 'pointer',
                    }}
                >
                    <input
                        type="checkbox"
                        checked={doNotShowAgain}
                        onChange={(event) =>
                            setDoNotShowAgain(event.target.checked)
                        }
                    />
                    Do not show me this again
                </label>

                <div
                    style={{
                        display: 'flex',
                        justifyContent: 'flex-end',
                        gap: 10,
                        marginTop: 24,
                    }}
                >
                    <button
                        type="button"
                        onClick={onCancel}
                        style={{
                            border: '1px solid #ccc',
                            background: '#fff',
                            color: '#333',
                            borderRadius: 7,
                            padding: '9px 13px',
                            cursor: 'pointer',
                        }}
                    >
                        Cancel
                    </button>

                    <button
                        type="button"
                        onClick={onConfirm}
                        style={{
                            border: 'none',
                            background: '#0d8cff',
                            color: '#fff',
                            borderRadius: 7,
                            padding: '9px 13px',
                            cursor: 'pointer',
                            fontWeight: 700,
                        }}
                    >
                        Continue
                    </button>
                </div>
            </div>
        </div>
    );
}