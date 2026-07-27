// Fix for newer versions of Node.js that expose a broken experimental localStorage implementation.
// This is needed for the instrumentation to work in Node.js environments.
export async function register() {
    // If Node.js is exposing a broken experimental localStorage, we intercept and mock it
    if (typeof globalThis !== 'undefined' && typeof globalThis.localStorage !== 'undefined') {
        const store: Record<string, string> = {};

        Object.defineProperty(globalThis, 'localStorage', {
            configurable: true,
            writable: true,
            value: {
                getItem: (key: string) => store[key] ?? null,
                setItem: (key: string, value: string) => { store[key] = value; },
                removeItem: (key: string) => { delete store[key]; },
                clear: () => { Object.keys(store).forEach((k) => delete store[k]); },
                key: (index: number) => Object.keys(store)[index] ?? null,
                length: 0,
            },
        });
    }
}