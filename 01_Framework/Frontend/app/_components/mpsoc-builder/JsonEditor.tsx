'use client';

import { useEffect, useState } from 'react';

type JsonEditorProps<T> = {
    title: string;
    value: T;
    onChange: (value: T) => void;
};

export default function JsonEditor<T>({
    title,
    value,
    onChange,
}: JsonEditorProps<T>) {
    const [text, setText] = useState('');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setText(JSON.stringify(value, null, 2));
    }, [value]);

    function handleApply() {
        try {
            const parsed = JSON.parse(text) as T;
            onChange(parsed);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Invalid JSON');
        }
    }

    return (
        <section>
            <h1>{title}</h1>

            <textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                spellCheck={false}
                style={{
                    width: '100%',
                    minHeight: '500px',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                    padding: '12px',
                }}
            />

            <div style={{ marginTop: '12px' }}>
                <button onClick={handleApply}>Apply changes</button>
            </div>

            {error && (
                <p style={{ color: 'crimson', marginTop: '12px' }}>
                    JSON error: {error}
                </p>
            )}
        </section>
    );
}
