import { useEffect, useRef } from 'react';
import ReactFlow, { Background, Controls, Edge, Node, NodeMouseHandler, ReactFlowInstance } from 'reactflow';

interface RunnablePlaygroundProps {
    nodes: Node[];
    edges: Edge[];
    onRunnableClick?: (id: string) => void;
}

const RunnablePlayground = ({
    nodes,
    edges,
    onRunnableClick,
}: RunnablePlaygroundProps) => {
    const wrapperRef = useRef<HTMLDivElement | null>(null);
    const rfRef = useRef<ReactFlowInstance | null>(null);

    useEffect(() => {
        if (!wrapperRef.current) return;

        const ro = new ResizeObserver(() => {
            rfRef.current?.fitView({ padding: 0.2, duration: 150 });
        });

        ro.observe(wrapperRef.current);
        return () => ro.disconnect();
    }, []);

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
