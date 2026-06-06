'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { defaultModel } from './defaultModel';
import type { SolverJson } from './types/mpsoc';

type JsonModelContextValue = {
    model: SolverJson;
    setModel: React.Dispatch<React.SetStateAction<SolverJson>>;
    updateConfig: (config: SolverJson['config']) => void;
    updatePlatform: (platform: SolverJson['platform']) => void;
    updateTasks: (tasks: SolverJson['tasks']) => void;
    updateCommunications: (communications: SolverJson['communications']) => void;
    resetModel: () => void;
};

const STORAGE_KEY = 'solver-json-model';

const JsonModelContext = createContext<JsonModelContextValue | null>(null);

export function JsonModelProvider({
    children,
}: {
    children: React.ReactNode;
}) {
    const [model, setModel] = useState<SolverJson>(defaultModel);
    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        const stored = window.localStorage.getItem(STORAGE_KEY);

        if (stored) {
            try {
                setModel(JSON.parse(stored));
            } catch {
                window.localStorage.removeItem(STORAGE_KEY);
                setModel(defaultModel);
            }
        }

        setIsLoaded(true);
    }, []);

    useEffect(() => {
        if (!isLoaded) return;

        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(model));
    }, [model, isLoaded]);

    const value = useMemo<JsonModelContextValue>(
        () => ({
            model,
            setModel,

            updateConfig: (config) =>
                setModel((current) => ({
                    ...current,
                    config,
                })),

            updatePlatform: (platform) =>
                setModel((current) => ({
                    ...current,
                    platform,
                })),

            updateTasks: (tasks) =>
                setModel((current) => ({
                    ...current,
                    tasks,
                })),

            updateCommunications: (communications) =>
                setModel((current) => ({
                    ...current,
                    communications,
                })),

            resetModel: () => {
                setModel(defaultModel);
                window.localStorage.removeItem(STORAGE_KEY);
            },
        }),
        [model],
    );

    return (
        <JsonModelContext.Provider value={value}>
            {children}
        </JsonModelContext.Provider>
    );
}

export function useJsonModel() {
    const context = useContext(JsonModelContext);

    if (!context) {
        throw new Error('useJsonModel must be used inside JsonModelProvider');
    }

    return context;
}
