// RunnablesSection.tsx
'use client';

import {Button, Flex, Text, ScrollArea} from '@radix-ui/themes';
import {useMemo} from 'react';
import {useFormContext} from 'react-hook-form';
import type {Runnable, SimulationForm} from '@/types/runnable';
import SortControls from '../SortControls';
import RunnableCard from './RunnableCard';
import {type SortKey, useRunnablesSorting} from '../hooks/useRunnablesSorting';

interface Props {
    runnables: Runnable[];
    numCores: number;
    onAdd: () => void;
    onRemove: (id: string) => void;
}

const RunnablesSection = ({runnables, numCores, onAdd, onRemove}: Props) => {
    const {setValue} = useFormContext<SimulationForm>();
    const {sortKey, sortDir, setSortKey, setSortDir, sortWith} = useRunnablesSorting();

    const sortOptions = useMemo(
        () => [
            {value: 'id', label: 'ID'},
            {value: 'criticality', label: 'Criticality'},
            {value: 'execution_time', label: 'Execution Time'},
            {value: 'name', label: 'Name'},
        ],
        [],
    );

    const allRunnableNames = useMemo(
        () => runnables.map((r) => ({id: r.id, name: r.name})),
        [runnables],
    );

    return (
        <div className="flex flex-col gap-2">
            {/* Header (non-scrollable) */}
            <Flex justify="between" align="center" mb="2">
                <Text as="label" size="3" className="font-medium">
                    Runnables
                </Text>

                <Flex align="center" gap="2">
                    <SortControls
                        sortKey={sortKey}
                        sortDir={sortDir}
                        options={sortOptions}
                        onChangeKey={(k) => {
                            const key = k as SortKey;
                            setValue('runnables', sortWith(runnables, key, sortDir), {
                                shouldDirty: true,
                            });
                            setSortKey(key);
                        }}
                        onToggleDir={() => {
                            const nextDir = sortDir === 'asc' ? 'desc' : 'asc';
                            setValue('runnables', sortWith(runnables, sortKey, nextDir), {
                                shouldDirty: true,
                            });
                            setSortDir(nextDir);
                        }}
                    />

                    <Button variant="soft" type="button" onClick={onAdd}>
                        Add Runnable
                    </Button>
                </Flex>
            </Flex>

            <ScrollArea
                scrollbars="vertical"
                className="border rounded-md"
                style={{maxHeight: '50vh'}}
            >
                <Flex direction="column" gap="4" p="2">
                    {runnables.map((runnable, idx) => (
                        <RunnableCard
                            key={runnable.id}
                            runnable={runnable}
                            index={idx}
                            numCores={numCores}
                            allRunnables={allRunnableNames}
                            onRemove={onRemove}
                        />
                    ))}
                </Flex>
            </ScrollArea>
        </div>
    );
};

export default RunnablesSection;
