'use client';

import { useState } from 'react';
import type { SimulationForm } from '@/types/runnable';
import type { Algorithm } from '@/types/algorithms';

export function useSimulationRunner(getValues: () => SimulationForm) {
    const [loading, setLoading] = useState(false);
    const [resultId, setResultId] = useState<string | null>(null);

    const runSimulation = async (algorithm: Algorithm) => {
        const values = getValues(); // always latest
        setLoading(true);

        try {
            const res = await fetch('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...values,
                    algorithm,
                }),
            });

            if (!res.ok) throw new Error('Simulation failed');

            const data = await res.json();
            // we expect { resultId: 'abc123', ... }
            setResultId(data.resultId ?? null);
        } catch (err) {
            console.error(err);
            alert('Simulation failed!');
        } finally {
            setLoading(false);
        }
    };

    return { loading, resultId, runSimulation };
}
