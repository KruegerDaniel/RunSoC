'use client';

import { useState } from 'react';
import { useJsonModel } from '@/lib/JsonModelContext';

export default function SolvePanel() {
    const { model } = useJsonModel();

    const [solverName, setSolverName] = useState('default_solver');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [responseJson, setResponseJson] = useState<unknown>(null);
    const [error, setError] = useState<string | null>(null);

    async function handleSolve() {
        setIsSubmitting(true);
        setError(null);
        setResponseJson(null);

        try {
            const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;

            if (!backendUrl) {
                throw new Error('NEXT_PUBLIC_BACKEND_URL is not configured');
            }

            const response = await fetch(
                `${backendUrl}/api/solve/${encodeURIComponent(solverName)}`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(model),
                },
            );

            const contentType = response.headers.get('content-type');
            const payload = contentType?.includes('application/json')
                ? await response.json()
                : await response.text();

            if (!response.ok) {
                throw new Error(
                    typeof payload === 'string'
                        ? payload
                        : JSON.stringify(payload, null, 2),
                );
            }

            setResponseJson(payload);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown request error');
        } finally {
            setIsSubmitting(false);
        }
    }

    return (
        <section>
            <h1>Solve</h1>

            <label>
                Solver name
                <input
                    value={solverName}
                    onChange={(event) => setSolverName(event.target.value)}
                    style={{
                        display: 'block',
                        marginTop: '8px',
                        padding: '8px',
                        width: '300px',
                    }}
                />
            </label>

            <button
                onClick={handleSolve}
                disabled={isSubmitting || !solverName.trim()}
                style={{ marginTop: '16px', display: 'block' }}
            >
                {isSubmitting ? 'Solving...' : 'Send to solver'}
            </button>

            {error && (
                <>
                    <h2>Error</h2>
                    <pre style={{ color: 'crimson', whiteSpace: 'pre-wrap' }}>
                        {error}
                    </pre>
                </>
            )}

            {responseJson !== null && (
                <>
                    <h2>Backend response</h2>
                    <pre
                        style={{
                            padding: '16px',
                            background: '#f5f5f5',
                            overflow: 'auto',
                        }}
                    >
                        {typeof responseJson === 'string'
                            ? responseJson
                            : JSON.stringify(responseJson, null, 2)}
                    </pre>
                </>
            )}

            <h2>Payload preview</h2>

            <pre
                style={{
                    padding: '16px',
                    background: '#f5f5f5',
                    overflow: 'auto',
                    maxHeight: '500px',
                }}
            >
                {JSON.stringify(model, null, 2)}
            </pre>
        </section>
    );
}
