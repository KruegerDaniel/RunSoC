'use client';

import { useJsonModel } from '@/lib/JsonModelContext';

export default function HomePage() {
    const { model, resetModel } = useJsonModel();

    return (
        <section>
            <h1>Solver JSON Builder</h1>

            <p>
                Edit the platform, taskset, and config on separate pages. The complete
                JSON model is persisted in localStorage.
            </p>

            <button onClick={resetModel}>Reset to default model</button>

            <h2>Current JSON</h2>

            <pre
                style={{
                    padding: '16px',
                    background: '#f5f5f5',
                    overflow: 'auto',
                    maxHeight: '600px',
                }}
            >
                {JSON.stringify(model, null, 2)}
            </pre>
        </section>
    );
}
