'use client'

import { useState, useMemo } from 'react'

export interface DependencySelectorProps {
    allRunnables: { id: string; name: string }[]
    selfId: string
    selected: string[]
    onChange: (deps: string[]) => void
}

const DependencySelector = ({
                                allRunnables,
                                selfId,
                                selected,
                                onChange,
                            }: DependencySelectorProps) => {
    const [search, setSearch] = useState('')
    const [focused, setFocused] = useState(false)

    const filtered = useMemo(
        () =>
            allRunnables.filter(
                (r) =>
                    r.id !== selfId &&
                    !selected.includes(r.id) &&
                    r.name.toLowerCase().includes(search.toLowerCase())
            ),
        [allRunnables, selfId, selected, search]
    )

    const handleAdd = (id: string) => {
        onChange([...selected, id])
        setSearch('')
    }

    const handleRemove = (id: string) => {
        onChange(selected.filter((d) => d !== id))
    }

    return (
        <div className="relative">
            {/* Selected chips */}
            <div className="flex flex-wrap gap-1 mb-1">
                {selected.map((depId) => {
                    const dep = allRunnables.find((r) => r.id === depId)
                    return (
                        <span
                            key={depId}
                            className="inline-flex items-center bg-indigo-100 text-indigo-800 rounded px-2 py-0.5 text-xs"
                        >
              {dep?.name ?? depId}
                            <button
                                type="button"
                                className="ml-1 text-indigo-500 hover:text-red-500"
                                onClick={() => handleRemove(depId)}
                                aria-label={`Remove ${dep?.name ?? depId}`}
                            >
                ×
              </button>
            </span>
                    )
                })}
            </div>

            {/* Search input */}
            <input
                type="text"
                className="w-full border rounded px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                placeholder="Search and add dependencies..."
                value={search}
                onFocus={() => setFocused(true)}
                onBlur={() => setTimeout(() => setFocused(false), 100)} // delay to allow click
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' && filtered.length > 0) {
                        handleAdd(filtered[0].id)
                        e.preventDefault()
                    }
                }}
            />

            {/* Dropdown */}
            {focused && filtered.length > 0 && (
                <div className="absolute left-0 right-0 border rounded bg-white shadow mt-1 max-h-32 overflow-y-auto z-10">
                    {filtered.map((r) => (
                        <div
                            key={r.id}
                            className="px-2 py-1 cursor-pointer hover:bg-indigo-100"
                            onMouseDown={() => handleAdd(r.id)}
                        >
                            {r.name}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default DependencySelector
