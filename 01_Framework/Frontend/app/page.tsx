'use client';

import { Runnable, SimulationForm } from '@/types/runnable';
import { useMemo } from 'react';
import { FormProvider, useForm, useWatch } from 'react-hook-form';
import { Edge, MarkerType, Node } from 'reactflow';
import 'reactflow/dist/style.css';
import { RunnableConfigPanel, RunnablePlayground } from './_components';

function computeNodeDepths(runnables: Runnable[]) {
    const depths: Record<string, number> = {};
    const byId = Object.fromEntries(runnables.map((r) => [r.id, r]));

    // detect cycles in current DFS path
    const visiting = new Set<string>();

    const getDepth = (id: string): number => {
        if (depths[id] !== undefined) return depths[id];

        const runnable = byId[id];
        if (!runnable) {
            depths[id] = 0;
            return 0;
        }

        const deps = runnable.dependencies ?? [];
        if (deps.length === 0) {
            depths[id] = 0;
            return 0;
        }

        if (visiting.has(id)) {
            // break cycle gracefully
            depths[id] = 0;
            return 0;
        }

        visiting.add(id);
        const childDepths = deps.map((depId) => getDepth(depId));
        visiting.delete(id);

        const d = 1 + Math.max(...childDepths);
        depths[id] = d;
        return d;
    };

    runnables.forEach((r) => getDepth(r.id));
    return depths;
}

export default function Home() {
    const methods = useForm<SimulationForm>({
        defaultValues: {
            numCores: 1,
            runnables: [
                {
                    id: '1',
                    name: 'Task1',
                    priority: 0,
                    affinity: 0,
                    period: 100,
                    execution_time: 5,
                    type: 'periodic',
                    dependencies: [],
                },
            ],
        },
    });

    const runnables = useWatch({
        name: 'runnables',
        control: methods.control,
        defaultValue: [],
    });

    const nodes: Node[] = useMemo(() => {
        const depths = computeNodeDepths(runnables);
        const levels: string[][] = [];

        Object.entries(depths).forEach(([id, depth]) => {
            if (!levels[depth]) levels[depth] = [];
            levels[depth].push(id);
        });

        const nodeMap: Record<string, { x: number; y: number }> = {};
        const verticalSpacing = 120;
        const horizontalSpacing = 120;

        levels.forEach((level, depth) => {
            const y = depth * verticalSpacing;
            const totalWidth = (level.length - 1) * horizontalSpacing;
            level.forEach((id, i) => {
                const x = i * horizontalSpacing - totalWidth / 2;
                nodeMap[id] = { x, y };
            });
        });

        return runnables.map((runnable) => ({
            id: runnable.id,
            data: { label: runnable.name },
            position: nodeMap[runnable.id] || { x: 0, y: 0 },
            type: 'default',
            style: {
                width: 60,
                height: 60,
                borderRadius: 30,
                background: '#fff',
                border: '2px solid #6366f1',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
            },
        }));
    }, [runnables]);

    const edges: Edge[] = useMemo(() => {
        const existingIds = new Set(runnables.map((r) => r.id));

        return runnables.flatMap((runnable) =>
            (runnable.dependencies ?? [])
                .filter((depId) => existingIds.has(depId))
                .map((depId) => ({
                    id: `${depId}->${runnable.id}`,
                    source: depId,
                    target: runnable.id,
                    animated: true,
                    style: { stroke: '#6366f1' },
                    markerEnd: { type: MarkerType.ArrowClosed },
                })),
        );
    }, [runnables]);

    return (
        <div className="flex h-screen w-full flex-col gap-8 overflow-hidden px-4 sm:px-6 lg:px-8 py-8 md:flex-row">
            <RunnablePlayground nodes={nodes} edges={edges} />
            <div className="flex-[0_0_520px] min-w-0 overflow-auto">
                <FormProvider {...methods}>
                    <RunnableConfigPanel />
                </FormProvider>
            </div>
        </div>
    );

}
