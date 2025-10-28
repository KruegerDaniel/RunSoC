'use client'

import { Button, Dialog, Flex, RadioGroup } from '@radix-ui/themes'
import type { Algorithm } from '@/types/algorithms'

type Props = {
    open: boolean
    loading?: boolean
    selected: Algorithm
    onOpenChange: (open: boolean) => void
    onChangeAlgorithm: (alg: Algorithm) => void
    onConfirm: () => void
}

const SimulationDialog = ({
                              open,
                              loading = false,
                              selected,
                              onOpenChange,
                              onChangeAlgorithm,
                              onConfirm,
                          }: Props) => {
    return (
        <Dialog.Root open={open} onOpenChange={onOpenChange}>
            <Dialog.Content>
                <Dialog.Title>Select Simulation Algorithm</Dialog.Title>

                <RadioGroup.Root
                    value={selected}
                    onValueChange={(v) => onChangeAlgorithm(v as Algorithm)}
                    className="mt-3"
                >
                    <RadioGroup.Item value="all">All</RadioGroup.Item>
                    <RadioGroup.Item value="fcfs">First Come – First Serve</RadioGroup.Item>
                    <RadioGroup.Item value="criticality">Criticality</RadioGroup.Item>
                </RadioGroup.Root>

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
    )
}

export default SimulationDialog
