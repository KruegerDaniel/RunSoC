import { useEffect, useRef } from 'react';
import ReactFlow, { Background, Controls, Edge, Node, NodeMouseHandler, ReactFlowInstance } from 'reactflow';

interface RunnableSelection {
    id: string;
    source: 'playground' | 'panel';
    nonce: number;
}

interface RunnablePlaygroundProps {
    nodes: Node[];
    edges: Edge[];
    selection?: RunnableSelection | null;
    onRunnableClick?: (id: string) => void;
}

const RunnablePlayground = ({
    nodes,
    edges,
    selection,
    onRunnableClick,
}: RunnablePlaygroundProps) => {
    const wrapperRef = useRef<HTMLDivElement | null>(null);
    const rfRef = useRef<ReactFlowInstance | null>(null);

    useEffect(() => {
        if (!selection) return;
        if (selection.source !== 'panel') return;
        if (!rfRef.current) return;

        const selectedNode = nodes.find((node) => node.id === selection.id);
        if (!selectedNode) return;

        const width =
            typeof selectedNode.width === 'number'
                ? selectedNode.width
                : typeof selectedNode.style?.width === 'number'
                    ? selectedNode.style.width
                    : 60;

        const height =
            typeof selectedNode.height === 'number'
                ? selectedNode.height
                : typeof selectedNode.style?.height === 'number'
                    ? selectedNode.style.height
                    : 60;

        const centerX = selectedNode.position.x + width / 2;
        const centerY = selectedNode.position.y + height / 2;

        rfRef.current.setCenter(centerX, centerY, {
            zoom: 1.5,
            duration: 400,
        });
    }, [selection, nodes]);

    useEffect(() => {
        if (!selection) return;
        if (selection.source !== 'panel') return;
        if (!rfRef.current) return;

        const nodeExists = nodes.some((node) => node.id === selection.id);
        if (!nodeExists) return;

        rfRef.current.fitView({
            nodes: [{ id: selection.id }],
            padding: 1.2,
            minZoom: 1.2,
            maxZoom: 1.8,
            duration: 400,
        });
    }, [selection, nodes]);

    const handleNodeClick: NodeMouseHandler = (_event, node) => {
        onRunnableClick?.(String(node.id));
    };

    return (
        <div className="flex-1 bg-white rounded-lg shadow-md p-4 min-w-0">
            <div
                ref={wrapperRef}
                className="
                    w-full
                    h-[60vh]
                    min-h-[320px]
                    md:h-[calc(100vh-5rem)]
                "
            >
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    fitView
                    onInit={(instance) => {
                        rfRef.current = instance;
                        instance.fitView({ padding: 0.2 });
                    }}
                    onNodeClick={handleNodeClick}
                    nodesDraggable={false}
                    nodesConnectable={false}
                    elementsSelectable={false}
                    zoomOnScroll={true}
                >
                    <Background />
                    <Controls />
                </ReactFlow>
            </div>
        </div>
    );
};

export default RunnablePlayground;
