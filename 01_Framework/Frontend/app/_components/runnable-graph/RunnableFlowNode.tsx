'use client';

import { memo } from 'react';
import { ClockIcon, LightningBoltIcon } from '@radix-ui/react-icons';
import { Handle, type NodeProps, Position } from 'reactflow';

type RunnableNodeData = {
    label: string;
    runnableType: 'periodic' | 'event';
};

const RunnableFlowNode = ({ data, selected }: NodeProps<RunnableNodeData>) => {
    const Icon =
        data.runnableType === 'periodic' ? ClockIcon : LightningBoltIcon;

    return (
        <>
            <Handle
                type="target"
                position={Position.Top}
                style={{ opacity: 0 }}
                isConnectable={false}
            />

            <div
                className={[
                    'relative flex h-[60px] w-[60px] items-center justify-center rounded-full border-2 bg-white text-xs font-medium',
                    selected ? 'border-indigo-600' : 'border-indigo-500',
                ].join(' ')}
            >
                <span className="max-w-[40px] truncate text-center leading-tight">
                    {data.label}
                </span>

                <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border border-gray-200 bg-white shadow-sm">
                    <Icon width={12} height={12} />
                </div>
            </div>

            <Handle
                type="source"
                position={Position.Bottom}
                style={{ opacity: 0 }}
                isConnectable={false}
            />
        </>
    );
};

export default memo(RunnableFlowNode);
