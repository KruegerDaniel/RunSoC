'use client';

import { useEffect, useMemo, useState } from 'react';
import { SolverResultExplorer } from '@/app/_components';
import type { SolverResult } from '@/app/_components';
import { useJsonModel } from '@/lib/JsonModelContext';

const SOLVER = 'cpsat';
const RESULT_STORAGE_KEY = 'runsoc:v2:last-cpsat-result';

function getBackendUrl() {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

    if (!backendUrl) {
        throw new Error(
            'NEXT_PUBLIC_BACKEND_URL is not configured. Add it to .env.local, for example NEXT_PUBLIC_BACKEND_URL=http://localhost:8000',
        );
    }

    return backendUrl.replace(/\/$/, '');
}

function isSolverResult(value: unknown): value is SolverResult {
    if (!value || typeof value !== 'object') return false;

    const candidate = value as Partial<SolverResult>;

    return (
        typeof candidate.status === 'string' &&
        typeof candidate.feasible === 'boolean' &&
        typeof candidate.objective === 'number' &&
        typeof candidate.makespan === 'number' &&
        Array.isArray(candidate.schedule)
    );
}

function readStoredResult(): SolverResult | null {
    if (typeof window === 'undefined') return null;

    try {
        const raw = window.localStorage.getItem(RESULT_STORAGE_KEY);
        if (!raw) return null;

        const parsed = JSON.parse(raw);
        return isSolverResult(parsed) ? parsed : null;
    } catch {
        return null;
    }
}

function writeStoredResult(result: SolverResult) {
    if (typeof window === 'undefined') return;

    try {
        window.localStorage.setItem(RESULT_STORAGE_KEY, JSON.stringify(result));
    } catch {
        // Ignore quota/private-mode failures.
    }
}

function clearStoredResult() {
    if (typeof window === 'undefined') return;

    try {
        window.localStorage.removeItem(RESULT_STORAGE_KEY);
    } catch {
        // Ignore storage failures.
    }
}

export default function SolvePanel() {
    const { model } = useJsonModel();

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [result, setResult] = useState<SolverResult | null>(null);
    const [rawResponse, setRawResponse] = useState<unknown>(null);
    const [error, setError] = useState<string | null>(null);

    const endpoint = useMemo(() => {
        try {
            return `${getBackendUrl()}/api/solve/${SOLVER}`;
        } catch {
            return null;
        }
    }, []);

    useEffect(() => {
        setResult(readStoredResult());
    }, []);

    async function handleSolve() {
        setIsSubmitting(true);
        setError(null);
        setRawResponse(null);

        try {
            const backendUrl = getBackendUrl();
            const url = `${backendUrl}/api/solve/${SOLVER}`;

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Accept: 'application/json',
                },
                body: JSON.stringify(model),
            });

            const contentType = response.headers.get('content-type') ?? '';
            const payload = contentType.includes('application/json')
                ? await response.json()
                : await response.text();

            if (!response.ok) {
                throw new Error(
                    typeof payload === 'string'
                        ? payload
                        : JSON.stringify(payload, null, 2),
                );
            }

            setRawResponse(payload);

            if (!isSolverResult(payload)) {
                throw new Error(
                    'Backend response is not a valid SolverResult. Expected fields: status, feasible, objective, makespan, schedule.',
                );
            }

            setResult(payload);
            writeStoredResult(payload);
        } catch (err) {
            setResult(null);
            setError(err instanceof Error ? err.message : 'Unknown solve error');
        } finally {
            setIsSubmitting(false);
        }
    }

    function handleClearResult() {
        setResult(null);
        setRawResponse(null);
        setError(null);
        clearStoredResult();
    }

    return (
        <section style={{ maxWidth: 1400 }}>
            <header
                style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    gap: 24,
                    marginBottom: 24,
                }}
            >
                <div>
                    <h1 style={{ margin: 0, fontSize: 32 }}>
                        Finalize and solve
                    </h1>

                    <p
                        style={{
                            margin: '8px 0 0',
                            color: '#666',
                            maxWidth: 820,
                            lineHeight: 1.5,
                        }}
                    >
                        Submit the current V2 JSON model to the CPSAT backend and
                        inspect the resulting allocation, schedule, memory
                        pressure, objective breakdown, and task chains.
                    </p>

                    <div
                        style={{
                            marginTop: 12,
                            fontFamily: 'monospace',
                            fontSize: 13,
                            color: endpoint ? '#333' : 'crimson',
                            background: '#f6f6f6',
                            border: '1px solid #e3e3e3',
                            borderRadius: 8,
                            padding: '10px 12px',
                            display: 'inline-block',
                        }}
                    >
                        POST {endpoint ?? '{backend}/api/solve/cpsat'}
                    </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                    <button
                        type="button"
                        onClick={handleSolve}
                        disabled={isSubmitting}
                        style={{
                            border: 'none',
                            background: isSubmitting ? '#9fcfff' : '#0d8cff',
                            color: '#fff',
                            borderRadius: 8,
                            padding: '12px 18px',
                            fontSize: 15,
                            fontWeight: 700,
                            cursor: isSubmitting ? 'not-allowed' : 'pointer',
                        }}
                    >
                        {isSubmitting ? 'Solving…' : 'Solve with CPSAT'}
                    </button>

                    <button
                        type="button"
                        onClick={handleClearResult}
                        disabled={isSubmitting && !result && !rawResponse}
                        style={{
                            border: '1px solid #ccc',
                            background: '#fff',
                            color: '#333',
                            borderRadius: 8,
                            padding: '12px 18px',
                            fontSize: 15,
                            cursor: 'pointer',
                        }}
                    >
                        Clear result
                    </button>
                </div>
            </header>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                    gap: 12,
                    marginBottom: 24,
                }}
            >
                <SummaryCard label="Platform" value={model.platform.name} />
                <SummaryCard label="Clusters" value={model.platform.clusters.length} />
                <SummaryCard
                    label="Cores"
                    value={model.platform.clusters.reduce(
                        (sum, cluster) => sum + cluster.cores.length,
                        0,
                    )}
                />
                <SummaryCard label="Tasks" value={model.tasks.length} />
            </div>

            {error && (
                <div
                    style={{
                        border: '1px solid #f0b4b4',
                        background: '#fff1f1',
                        color: '#9f1d1d',
                        borderRadius: 10,
                        padding: 16,
                        marginBottom: 24,
                        whiteSpace: 'pre-wrap',
                    }}
                >
                    <strong>Solve failed</strong>
                    <div style={{ marginTop: 8 }}>{error}</div>
                </div>
            )}

            {!result && !error && (
                <div
                    style={{
                        border: '1px solid #ddd',
                        background: '#fafafa',
                        borderRadius: 12,
                        padding: 18,
                        marginBottom: 24,
                        color: '#555',
                    }}
                >
                    No solver result yet. Click <strong>Solve with CPSAT</strong>{' '}
                    to send the current JSON model to the backend.
                </div>
            )}

            {result && <SolverResultExplorer result={result} />}

            {!!rawResponse && !result && (
                <details style={{ marginTop: 24 }}>
                    <summary>Raw backend response</summary>
                    <pre
                        style={{
                            marginTop: 12,
                            padding: 16,
                            background: '#f5f5f5',
                            overflow: 'auto',
                            maxHeight: 520,
                            borderRadius: 8,
                        }}
                    >
                        {typeof rawResponse === 'string'
                            ? rawResponse
                            : JSON.stringify(rawResponse, null, 2)}
                    </pre>
                </details>
            )}
        </section>
    );
}

function SummaryCard({
    label,
    value,
}: {
    label: string;
    value: string | number;
}) {
    return (
        <div
            style={{
                border: '1px solid #e0e0e0',
                borderRadius: 12,
                padding: 16,
                background: '#fff',
                boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
            }}
        >
            <div
                style={{
                    color: '#777',
                    fontSize: 12,
                    textTransform: 'uppercase',
                    letterSpacing: 0.6,
                    marginBottom: 6,
                }}
            >
                {label}
            </div>

            <div
                style={{
                    color: '#111',
                    fontSize: 20,
                    fontWeight: 700,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                }}
                title={String(value)}
            >
                {value}
            </div>
        </div>
    );
}