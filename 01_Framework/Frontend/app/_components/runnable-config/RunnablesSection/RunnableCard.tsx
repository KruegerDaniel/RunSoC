import {Box, Flex, IconButton, Text, TextField} from '@radix-ui/themes';
import {Cross2Icon} from '@radix-ui/react-icons';
import {Runnable} from '@/types/runnable';
import {Controller, useFormContext} from 'react-hook-form';
import ConfigSelectField from './ConfigSelectField';
import DependencySelector from './DependencySelector';
import {criticalityOptions, typeOptions} from '@/app/constants';

interface Props {
    runnable: Runnable;
    index: number;
    numCores: number;
    allRunnables: { id: string; name: string }[];
    onRemove: (id: string) => void;
}

const RunnableCard = ({runnable, index, numCores, allRunnables, onRemove}: Props) => {
    const {register, control} = useFormContext();

    const affinityOptions = Array.from({length: numCores}, (_, i) => ({
        value: i.toString(),
        label: `Core ${i}`,
    }));

    return (
        <Box className="border rounded-lg p-4 bg-gray-50 relative">
            <div className="absolute top-2 right-2 z-20">
                <IconButton
                    variant="ghost"
                    color="red"
                    onClick={() => onRemove(runnable.id)}
                    aria-label="Remove Runnable"
                >
                    <Cross2Icon/>
                </IconButton>
            </div>

            <Flex direction="column" gap="2">
                <Text size="2">Runnable Name</Text>
                <TextField.Root
                    className="w-32"
                    placeholder={`Runnable ${index + 1}`}
                    {...register(`runnables.${index}.name` as const)}
                />
            </Flex>

            <Flex gap="3" wrap="wrap" mt="3">
                <ConfigSelectField
                    field="criticality"
                    options={criticalityOptions}
                    name="Criticality"
                    index={index}
                />
                <ConfigSelectField
                    field="affinity"
                    options={affinityOptions}
                    name="Affinity"
                    index={index}
                />
                <Flex direction="column" gap="1">
                    <Text size="2">Execution Time (ms)</Text>
                    <TextField.Root
                        type="number"
                        className="w-24"
                        {...register(`runnables.${index}.execution_time` as const)}
                    />
                </Flex>
                <ConfigSelectField
                    field="type"
                    options={typeOptions}
                    name="Type"
                    index={index}
                />
                {runnable.type === 'periodic' && (
                    <Flex direction="column" gap="1">
                        <Text size="2">Period (ms)</Text>
                        <TextField.Root
                            type="number"
                            className="w-24"
                            {...register(`runnables.${index}.period` as const)}
                        />
                    </Flex>
                )}
                <Flex direction="column" gap="1">
                    <Text size="2">Dependencies</Text>
                    <Controller
                        control={control}
                        name={`runnables.${index}.dependencies` as const}
                        render={({field}) => (
                            <DependencySelector
                                allRunnables={allRunnables}
                                selfId={runnable.id}
                                selected={field.value}
                                onChange={field.onChange}
                            />
                        )}
                    />
                </Flex>
            </Flex>
        </Box>
    );
};

export default RunnableCard;
