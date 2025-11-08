'use client';

import {Button, Dialog, Flex, RadioGroup} from '@radix-ui/themes';
import type {Algorithm, AllocationPolicy} from '@/types/algorithms';

type Props = {
    open: boolean;
    loading?: boolean;
    selected: Algorithm;
    selectedAllocationPolicy: AllocationPolicy;
    onOpenChange: (open: boolean) => void;
    onChangeAlgorithm: (alg: Algorithm) => void;
    onChangeAllocationPolicy: (p: AllocationPolicy) => void;
    onConfirm: () => void;
};


const SimulationDialog = ({
    open,
    loading = false,
    selected,
    selectedAllocationPolicy,
    onOpenChange,
    onChangeAlgorithm,
    onChangeAllocationPolicy,
    onConfirm,
}: Props) => {
    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Content>
                <Dialog.Title>Select Simulation</Dialog.Title>

                {/* Algorithm selection */}
                <RadioGroup.Root
                    value={selected}
                    onValueChange={(v) => onChangeAlgorithm(v as Algorithm)}
                    className="mt-3 flex flex-col gap-2"
                >
                    <RadioGroup.Item value="all">All Algorithms</RadioGroup.Item>
                    <RadioGroup.Item value="fcfs">First Come – First Serve</RadioGroup.Item>
                    <RadioGroup.Item value="criticality">Priority-aware</RadioGroup.Item>
                    <RadioGroup.Item value="main">Main (DAG & core allocation)</RadioGroup.Item>
                </RadioGroup.Root>

                <div className="mt-4">
                    <div className="text-sm font-medium mb-1">
                        Allocation Policy (for Main Scheduler)
                    </div>
                    <RadioGroup.Root
                        value={selectedAllocationPolicy}
                        onValueChange={(v) =>
                            onChangeAllocationPolicy(v as AllocationPolicy)
                        }
                        className="flex flex-col gap-2"
                    >
                        <RadioGroup.Item value="all">
                            Both – compare static & dynamic
                        </RadioGroup.Item>
                        <RadioGroup.Item value="static">
                            Static – fixed subset of cores
                        </RadioGroup.Item>
                        <RadioGroup.Item value="dynamic">
                            Dynamic – adapt cores to load
                        </RadioGroup.Item>
                    </RadioGroup.Root>
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
