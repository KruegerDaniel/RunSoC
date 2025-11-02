'use client';

import {useCallback, useState} from 'react';
import type {Runnable} from '@/types/runnable';

export type SortKey = 'id' | 'name' | 'criticality' | 'execution_time'
export type SortDir = 'asc' | 'desc'

const lexical = (a: string, b: string) => a.localeCompare(b);

const numericIdCompare = (a: string, b: string) => {
    const na = Number(a), nb = Number(b);
    const aNum = Number.isFinite(na), bNum = Number.isFinite(nb);
    if (aNum && bNum) return na - nb;
    return lexical(a, b); // fallback if non-numeric
};

const baseComparators: Record<Exclude<SortKey, 'id'>, (a: Runnable, b: Runnable) => number> = {
    name: (a, b) => lexical(a.name, b.name),
    criticality: (a, b) => a.criticality - b.criticality,
    execution_time: (a, b) => a.execution_time - b.execution_time,
};

const getComparator = (key: SortKey) =>
    key === 'id'
        ? (a: Runnable, b: Runnable) => numericIdCompare(a.id, b.id)
        : baseComparators[key];

export function useRunnablesSorting() {
    const [sortKey, setSortKey] = useState<SortKey>('id');
    const [sortDir, setSortDir] = useState<SortDir>('asc');

    const sortWith = useCallback(
        (items: Runnable[], key: SortKey = sortKey, dir: SortDir = sortDir) => {
            const d = dir === 'asc' ? 1 : -1;
            const cmp = getComparator(key);
            return [...items].sort((a, b) => d * cmp(a, b));
        },
        [sortKey, sortDir],
    );

    return {sortKey, sortDir, setSortKey, setSortDir, sortWith};
}
