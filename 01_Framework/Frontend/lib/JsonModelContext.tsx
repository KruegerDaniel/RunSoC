'use client';

import {
    createContext,
    useContext,
    useEffect,
    useMemo,
    useState,
} from 'react';
import { defaultModel } from './defaultModel';
import type { SolverJson } from './types/mpsoc';

type JsonModelContextValue = {
    model: SolverJson;
    setModel: React.Dispatch<React.SetStateAction<SolverJson>>;
    updateConfig: (config: SolverJson['config']) => void;
    updatePlatform: (platform: SolverJson['platform']) => void;
    updateTasks: (tasks: SolverJson['tasks']) => void;
    updateCommunications: (
        communications: SolverJson['communications'],
    ) => void;
    resetModel: () => void;
};

const STORAGE_KEY = 'solver-json-model';

const JsonModelContext = createContext<JsonModelContextValue | null>(null);

function getSafeLocalStorage(): Storage | null {
    if (typeof window === 'undefined') return null;

    try {
        const storage = window.localStorage;

        if (
            !storage ||
            typeof storage.getItem !== 'function' ||
            typeof storage.setItem !== 'function' ||
            typeof storage.removeItem !== 'function'
        ) {
            return null;
        }

        return storage;
    } catch {
        return null;
    }
}

function loadStoredModel(): SolverJson {
    const storage = getSafeLocalStorage();

    if (!storage) {
        return defaultModel;
    }

    const stored = storage.getItem(STORAGE_KEY);

    if (!stored) {
        return defaultModel;
    }

    try {
        return JSON.parse(stored) as SolverJson;
    } catch {
        storage.removeItem(STORAGE_KEY);
        return defaultModel;
    }
}

export function JsonModelProvider({
    children,
}: {
    children: React.ReactNode;
}) {
    const [model, setModel] = useState<SolverJson>(defaultModel);
    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        setModel(loadStoredModel());
        setIsLoaded(true);
    }, []);

    useEffect(() => {
        if (!isLoaded) return;

        const storage = getSafeLocalStorage();

        if (!storage) {
            return;
        }

        try {
            storage.setItem(STORAGE_KEY, JSON.stringify(model));
        } catch {
            // Ignore quota/private-mode/storage failures.
        }
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

                const storage = getSafeLocalStorage();
                storage?.removeItem(STORAGE_KEY);
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