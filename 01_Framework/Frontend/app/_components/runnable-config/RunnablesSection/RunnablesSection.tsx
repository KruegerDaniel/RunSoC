'use client';

import {Button, Flex, ScrollArea, Text} from '@radix-ui/themes';
import {useMemo} from 'react';
import type {Runnable} from '@/types/runnable';
import SortControls from '../SortControls';
import RunnableCard from './RunnableCard';
import {type SortKey, useRunnablesSorting} from '../hooks/useRunnablesSorting';

interface Props {
    runnables: Runnable[];
    onAdd: () => void;
    onRemove: (id: string) => void;
}

const RunnablesSection = ({runnables, onAdd, onRemove}: Props) => {
    const {sortKey, sortDir, setSortKey, setSortDir, sortWith} = useRunnablesSorting();

    const sortOptions = useMemo(
        () => [
            {value: 'id', label: 'ID'},
            {value: 'priority', label: 'Priority'},
            {value: 'execution_time', label: 'Execution Time'},
            {value: 'name', label: 'Name'},
        ],
        [],
    );

    const allRunnableNames = useMemo(
        () => runnables.map((r) => ({id: r.id, name: r.name})),
        [runnables],
    );

    const sortedRunnables = useMemo(
        () => sortWith(runnables),
        [runnables, sortWith],
    );

    return (
        <div className="flex flex-col gap-2">
            {/* Header (non-scrollable) */}
            <Flex justify="between" align="center" mb="2">
                <Text as="label" size="3" className="font-medium">
                    Tasks
                </Text>

                <Flex align="center" gap="2">
                    <SortControls
                        sortKey={sortKey}
                        sortDir={sortDir}
                        options={sortOptions}
                        onChangeKey={(k) => {
                            const key = k as SortKey;
                            setSortKey(key);
                        }}
                        onToggleDir={() => {
                            const nextDir = sortDir === 'asc' ? 'desc' : 'asc';
                            setSortDir(nextDir);
                        }}
                    />

                    <Button variant="soft" type="button" onClick={onAdd}>
                        Add Task
                    </Button>
                </Flex>
            </Flex>

            <ScrollArea
                scrollbars="vertical"
                className="border rounded-md"
                style={{maxHeight: '45vh'}}
            >
                <Flex direction="column" gap="4" p="2">
                    {sortedRunnables.map((runnable) => {
                        const originalIndex = runnables.findIndex((r) => r.id === runnable.id);
                        return <RunnableCard
                            key={runnable.id}
                            runnable={runnable}
                            index={originalIndex}
                            allRunnables={allRunnableNames}
                            onRemove={onRemove}
                        />;
                    })},
                </Flex>
            </ScrollArea>
        </div>
    );
};

export default RunnablesSection;
