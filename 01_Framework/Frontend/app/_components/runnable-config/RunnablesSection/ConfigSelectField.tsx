import { Flex, Select, Text } from '@radix-ui/themes'
import { Controller, useFormContext } from 'react-hook-form'
import { Runnable, SimulationForm } from '@/types/runnable'

interface Props {
    field: keyof Runnable
    options: { value: string; label: string }[]
    name: string
    index: number
}

const ConfigSelectField = ({ field, options, name, index }: Props) => {
    const { control } = useFormContext<SimulationForm>()

    return (
        <Flex direction="column" gap="1">
            <Text size="2">{name}</Text>
            <Controller
                control={control}
                name={`runnables.${index}.${field}` as const}
                render={({ field: f }) => (
                    <Select.Root
                        value={f.value?.toString() ?? ''}
                        onValueChange={(val) =>
                            f.onChange(field === 'type' ? val : Number(val))
                        }
                    >
                        <Select.Trigger className="w-24" />
                        <Select.Content>
                            {options.map((opt) => (
                                <Select.Item key={opt.value} value={opt.value}>
                                    {opt.label}
                                </Select.Item>
                            ))}
                        </Select.Content>
                    </Select.Root>
                )}
            />
        </Flex>
    )
}

export default ConfigSelectField
