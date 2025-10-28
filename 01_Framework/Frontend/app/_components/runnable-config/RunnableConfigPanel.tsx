'use client';

import {ChangeEvent, useRef, useState} from 'react';
import {Box, Button, Dialog, Flex, Heading, RadioGroup, ScrollArea, Text, TextField,} from '@radix-ui/themes';
import {useFormContext} from 'react-hook-form';
import type {SimulationForm} from '@/types/runnable';
import type {Algorithm} from '@/types/algorithms';

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
    const [selectedAlgorithm, setSelectedAlgorithm] = useState<Algorithm>('all');

    const {loading, resultId, runSimulation} = useSimulationRunner(getValues);
    const handleImport = useImportJson(setValue);

    const formRef = useRef<HTMLFormElement>(null);

    const handleImportJSON = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) handleImport(file);
        e.target.value = '';
    };

    const handleAddRunnable = () => {
        const nextId = (
            Math.max(...runnables.map((r) => parseInt(r.id)), 0) + 1
        ).toString();
        const newRunnable = {
            id: nextId,
            name: `Runnable${nextId}`,
            criticality: 0,
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
            {shouldDirty: true}
        );
    };

    const onSubmit = async (values: SimulationForm) => {
        await runSimulation(values, selectedAlgorithm);
    };

    return (
        <div className="w-full md:min-w-[480px] md:max-w-[640px]">
            <ScrollArea scrollbars="vertical">
                <form ref={formRef} onSubmit={handleSubmit(onSubmit)}>
                    {/* Header */}
                    <Flex justify="between" align="center" mb="6">
                        <Heading className="text-2xl font-bold">Configuration</Heading>

                        {/* Import JSON */}
                        <ImportJsonButton onFile={handleImport}/>
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
                    </Box>

                    {/* Simulation buttons */}
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
                                onClick={() => window.open(`/result/${resultId}`, '_blank')}
                            >
                                View Result
                            </Button>
                        )}
                    </div>
                </form>
            </ScrollArea>

            {/* Algorithm selection dialog */}
            <SimulationDialog
                open={dialogOpen}
                loading={loading}
                selected={selectedAlgorithm}
                onOpenChange={setDialogOpen}
                onChangeAlgorithm={setSelectedAlgorithm}
                onConfirm={() => {
                    setDialogOpen(false)
                    formRef.current?.requestSubmit()
                }}
            />

        </div>
    );
};

export default RunnableConfigPanel;
