// RunnableConfigPanel.tsx
'use client';

import {useRef, useState} from 'react';
import {
    Box,
    Button,
    Flex,
    Heading,
    Text,
    TextField,
    DropdownMenu,
} from '@radix-ui/themes';
import {useFormContext} from 'react-hook-form';
import type {SimulationForm} from '@/types/runnable';
import type {
    Algorithm,
    AllocationPolicy,
    SchedulingPolicy,
} from '@/types/algorithms';

import ImportJsonButton from './ImportJsonButton';
import SimulationDialog from './SimulationDialog';

import RunnablesSection from './RunnablesSection/RunnablesSection';
import {useImportJson} from './hooks/useImportJson';
import {useSimulationRunner} from './hooks/useSimulationRunner';

const RunnableConfigPanel = () => {
    const {watch, register, handleSubmit, setValue, getValues} =
        useFormContext<SimulationForm>();

    const numCores = watch('numCores');
    const runnables = watch('runnables') ?? [];

    const [dialogOpen, setDialogOpen] = useState(false);

    const [selectedAlgorithm, setSelectedAlgorithm] =
        useState<Algorithm>('main');
    const [selectedSchedulingPolicy, setSelectedSchedulingPolicy] =
        useState<SchedulingPolicy>('fcfs');
    const [selectedAllocationPolicy, setSelectedAllocationPolicy] =
        useState<AllocationPolicy>('static');

    const {loading, resultId, runSimulation} = useSimulationRunner(getValues);
    const handleImport = useImportJson(setValue);

    const formRef = useRef<HTMLFormElement>(null);

    const handleAddRunnable = () => {
        const nextId = (
            Math.max(...runnables.map((r) => parseInt(r.id)), 0) + 1
        ).toString();
        const newRunnable = {
            id: nextId,
            name: `Task${nextId}`,
            priority: 0,
            affinity: 0,
            period: 100,
            execution_time: 5,
            type: 'periodic' as const,
            dependencies: [],
        };
        setValue('runnables', [...runnables, newRunnable], {shouldDirty: true});
    };

    const handleRemoveRunnable = (id: string) => {
        setValue(
            'runnables',
            runnables
                .filter((r) => r.id !== id)
                .map((r) => ({
                    ...r,
                    dependencies: r.dependencies.filter((d) => d !== id),
                })),
            {shouldDirty: true},
        );
    };

    const handleResetRunnables = () => {
        setValue('runnables', [], {shouldDirty: true});
    };

    const onSubmit = async () => {
        await runSimulation(
            selectedAlgorithm,
            selectedSchedulingPolicy,
            selectedAllocationPolicy,
        );
    };

    return (
        <div className="w-full md:w-[520px] md:max-w-none">
            <form ref={formRef} onSubmit={handleSubmit(onSubmit)}>
                {/* Header */}
                <Flex justify="between" align="center" mb="6">
                    <Heading className="text-2xl font-bold">Configuration</Heading>

                    <Flex gap="2" align="center">
                        <ImportJsonButton onFile={handleImport} />

                        {/* Download dropdown */}
                        <DropdownMenu.Root>
                            <DropdownMenu.Trigger>
                                <Button type="button" variant="outline">
                                    Download
                                </Button>
                            </DropdownMenu.Trigger>

                            <DropdownMenu.Content>
                                <DropdownMenu.Item asChild>
                                    <a href="/template_json.json" download>
                                        Template JSON
                                    </a>
                                </DropdownMenu.Item>

                                <DropdownMenu.Item asChild>
                                    <a href="/example_balanced.json" download>
                                        Example JSON- balanced
                                    </a>
                                </DropdownMenu.Item>
                                <DropdownMenu.Item asChild>
                                    <a href="/example_long.json" download>
                                        Example JSON - long path
                                    </a>
                                </DropdownMenu.Item>
                            </DropdownMenu.Content>
                        </DropdownMenu.Root>
                    </Flex>
                </Flex>

                {/* Number of cores */}
                <Flex direction="column" gap="2" mb="5">
                    <Text as="label" size="3" className="block mb-2 font-medium">
                        Number of Cores
                    </Text>
                    <TextField.Root
                        type="number"
                        placeholder="1"
                        {...register('numCores')}
                        className="w-32"
                    />
                </Flex>

                {/* Runnables list section */}
                <Box mb="5">
                    <RunnablesSection
                        runnables={runnables}
                        numCores={numCores}
                        onAdd={handleAddRunnable}
                        onRemove={handleRemoveRunnable}
                    />

                    <Flex justify="end" mt="2">
                        <Button
                            type="button"
                            variant="outline"
                            disabled={!runnables.length}
                            onClick={handleResetRunnables}
                        >
                            Reset Tasks
                        </Button>
                    </Flex>
                </Box>

                <div className="flex flex-col gap-2 mt-4">
                    <Button
                        type="button"
                        loading={loading}
                        onClick={() => setDialogOpen(true)}
                    >
                        Run Simulation
                    </Button>
                    {resultId && (
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() =>
                                window.open(`/result/${resultId}`, '_blank')
                            }
                        >
                            View Result
                        </Button>
                    )}
                </div>
            </form>

            {/* Algorithm + policy selection dialog */}
            <SimulationDialog
                open={dialogOpen}
                loading={loading}
                selectedAlgorithm={selectedAlgorithm}
                selectedSchedulingPolicy={selectedSchedulingPolicy}
                selectedAllocationPolicy={selectedAllocationPolicy}
                onOpenChange={setDialogOpen}
                onChangeAlgorithm={setSelectedAlgorithm}
                onChangeSchedulingPolicy={setSelectedSchedulingPolicy}
                onChangeAllocationPolicy={setSelectedAllocationPolicy}
                onConfirm={() => {
                    setDialogOpen(false);
                    formRef.current?.requestSubmit();
                }}
            />
        </div>
    );
};

export default RunnableConfigPanel;
