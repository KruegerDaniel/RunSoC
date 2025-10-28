import ReactFlow, { Background, Controls, Edge, Node } from 'reactflow'

interface RunnablePlaygroundProps {
  nodes: Node[]
  edges: Edge[]
}

const RunnablePlayground = ({ nodes, edges }: RunnablePlaygroundProps) => {
  return (
    <div className="flex-1 bg-white rounded-lg shadow-md p-4 min-h-[500px] flex items-center justify-center">
      <div style={{ width: '100%', height: 500 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          zoomOnScroll={false}
          panOnScroll
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>
    </div>
  )
}

export default RunnablePlayground
