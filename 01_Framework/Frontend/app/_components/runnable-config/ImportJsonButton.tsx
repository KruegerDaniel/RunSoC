'use client'

import { Button } from '@radix-ui/themes'
import { ChangeEvent } from 'react'

type Props = {
    onFile: (file: File) => void
    label?: string
    accept?: string
    disabled?: boolean
}

const ImportJsonButton = ({
                              onFile,
                              label = 'Import JSON',
                              accept = 'application/json',
                              disabled,
                          }: Props) => {
    const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) onFile(file)
        // reset input so the same file can be re-selected if needed
        e.target.value = ''
    }

    return (
        <label className="relative inline-block">
            <input
                type="file"
                accept={accept}
                onChange={handleChange}
                className="absolute inset-0 opacity-0 cursor-pointer"
                aria-label={label}
                disabled={disabled}
            />
            <Button variant="soft" type="button" disabled={disabled}>
                {label}
            </Button>
        </label>
    )
}

export default ImportJsonButton
