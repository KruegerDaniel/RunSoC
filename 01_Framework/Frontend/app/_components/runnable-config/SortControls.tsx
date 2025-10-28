'use client';

import {Button, Flex, Select, Text} from '@radix-ui/themes';

type SortDir = 'asc' | 'desc'

export type SortOption = { value: string; label: string }

type Props = {
    sortKey: string
    sortDir: SortDir
    options: SortOption[]
    onChangeKey: (key: string) => void
    onToggleDir: () => void
}

const SortControls = ({
                          sortKey,
                          sortDir,
                          options,
                          onChangeKey,
                          onToggleDir,
                      }: Props) => {
    return (
        <Flex align="center" gap="2">
            <Text size="2">Sort by</Text>
            <Select.Root value={sortKey} onValueChange={onChangeKey}>
                <Select.Trigger className="w-[160px]"/>
                <Select.Content>
                    {options.map((opt) => (
                        <Select.Item key={opt.value} value={opt.value}>
                            {opt.label}
                        </Select.Item>
                    ))}
                </Select.Content>
            </Select.Root>

            <Button variant="ghost" type="button" onClick={onToggleDir}>
                {sortDir === 'asc' ? '↑ Asc' : '↓ Desc'}
            </Button>
        </Flex>
    );
};

export default SortControls;
