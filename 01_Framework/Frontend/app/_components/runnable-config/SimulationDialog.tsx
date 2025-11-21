'use client';

import {Button, Dialog, Flex, RadioGroup, Text} from '@radix-ui/themes';
import type {
    Algorithm,
    AllocationPolicy,
    SchedulingPolicy,
} from '@/types/algorithms';

type Props = {
    open: boolean;
    loading?: boolean;

    // Current selections
    selectedAlgorithm: Algorithm;
    selectedSchedulingPolicy: SchedulingPolicy;
    selectedAllocationPolicy: AllocationPolicy;

    // Callbacks
    onOpenChange: (open: boolean) => void;
    onChangeAlgorithm: (alg: Algorithm) => void;
    onChangeSchedulingPolicy: (p: SchedulingPolicy) => void;
    onChangeAllocationPolicy: (p: AllocationPolicy) => void;
    onConfirm: () => void;
};

const SimulationDialog = ({
    open,
    loading = false,
    selectedAlgorithm,
    selectedSchedulingPolicy,
    selectedAllocationPolicy,
    onOpenChange,
    onChangeAlgorithm,
    onChangeSchedulingPolicy,
    onChangeAllocationPolicy,
    onConfirm,
}: Props) => {
    const disablePolicySelection = selectedAlgorithm === 'all';

    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Content>
                <Dialog.Title>Select Simulation</Dialog.Title>

                {/* Algorithm selection */}
                <div className="mt-3">
                    <Text as="div" className="text-sm font-medium mb-1">
                        Algorithm
                    </Text>
                    <RadioGroup.Root
                        value={selectedAlgorithm}
                        onValueChange={(v) => onChangeAlgorithm(v as Algorithm)}
                        className="flex flex-col gap-2"
                    >
                        <RadioGroup.Item value="main">
                            Single configuration (use policies below)
                        </RadioGroup.Item>
                        <RadioGroup.Item value="all">
                            All 4 combinations (FCFS/PAS × Static/Dynamic)
                        </RadioGroup.Item>
                    </RadioGroup.Root>
                </div>

                {/* Scheduling policy selection */}
                <div className="mt-4">
                    <Text as="div" className="text-sm font-medium mb-1">
                        Scheduling Policy
                    </Text>
                    <RadioGroup.Root
                        value={selectedSchedulingPolicy}
                        onValueChange={(v) =>
                            onChangeSchedulingPolicy(v as SchedulingPolicy)
                        }
                        className="flex flex-col gap-2"
                        disabled={disablePolicySelection}
                    >
                        <RadioGroup.Item value="fcfs">
                            FCFS – First-Come, First-Served
                        </RadioGroup.Item>
                        <RadioGroup.Item value="pas">
                            PAS – Priority-Aware Scheduling
                        </RadioGroup.Item>
                        <RadioGroup.Item value="both">
                            Both – compare FCFS & PAS
                        </RadioGroup.Item>
                    </RadioGroup.Root>
                    {disablePolicySelection && (
                        <Text as="div" size="1" className="mt-1 text-gray-500">
                            When “All 4 combinations” is selected, all scheduling policies are run.
                        </Text>
                    )}
                </div>

                {/* Allocation policy selection */}
                <div className="mt-4">
                    <Text as="div" className="text-sm font-medium mb-1">
                        Allocation Policy
                    </Text>
                    <RadioGroup.Root
                        value={selectedAllocationPolicy}
                        onValueChange={(v) =>
                            onChangeAllocationPolicy(v as AllocationPolicy)
                        }
                        className="flex flex-col gap-2"
                        disabled={disablePolicySelection}
                    >
                        <RadioGroup.Item value="static">
                            Static – fixed subset of cores
                        </RadioGroup.Item>
                        <RadioGroup.Item value="dynamic">
                            Dynamic – adapt cores to load
                        </RadioGroup.Item>
                        <RadioGroup.Item value="both">
                            Both – compare static & dynamic
                        </RadioGroup.Item>
                    </RadioGroup.Root>
                    {disablePolicySelection && (
                        <Text as="div" size="1" className="mt-1 text-gray-500">
                            When “All 4 combinations” is selected, both static and dynamic are run.
                        </Text>
                    )}
                </div>

                <Flex gap="3" mt="4" justify="end">
                    <Button variant="soft" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button onClick={onConfirm} loading={loading}>
                        Run
                    </Button>
                </Flex>
            </Dialog.Content>
        </Dialog.Root>
    );
};

export default SimulationDialog;
