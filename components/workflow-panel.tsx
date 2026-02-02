'use client'

import { useCallback, useEffect, useState, memo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  Handle,
  Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Play, Globe, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface WorkflowPanelProps {
  projectId: string
  version?: number
}

// Custom Node Components - defined outside component to prevent recreation
const BrowserAgentNode = memo(({ data }: { data: any }) => (
  <div className="px-4 py-2 shadow-md rounded-md bg-blue-50 border-2 border-blue-200 min-w-[150px]">
    <Handle type="target" position={Position.Left} className="w-2 h-2" />
    <div className="flex items-center gap-2">
      <Globe className="w-4 h-4 text-blue-600" />
      <span className="font-medium text-sm text-blue-900">Browser Agent</span>
    </div>
    <div className="text-xs text-gray-600 mt-1 truncate">{data?.instruction?.substring(0, 30)}...</div>
    <Handle type="source" position={Position.Right} className="w-2 h-2" />
  </div>
))

const AITransformNode = memo(({ data }: { data: any }) => (
  <div className="px-4 py-2 shadow-md rounded-md bg-purple-50 border-2 border-purple-200 min-w-[150px]">
    <Handle type="target" position={Position.Left} className="w-2 h-2" />
    <div className="flex items-center gap-2">
      <Brain className="w-4 h-4 text-purple-600" />
      <span className="font-medium text-sm text-purple-900">AI Transform</span>
    </div>
    <div className="text-xs text-gray-600 mt-1 truncate">{data?.instruction?.substring(0, 30)}...</div>
    <Handle type="source" position={Position.Right} className="w-2 h-2" />
  </div>
))

// Node types defined outside component
const nodeTypes = {
  browser_agent: BrowserAgentNode,
  ai_transform: AITransformNode,
}

interface WorkflowPanelProps {
  projectId: string
  version?: number
}

export default function WorkflowPanel({ projectId, version }: WorkflowPanelProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [isRunning, setIsRunning] = useState(false)

  useEffect(() => {
    loadWorkflow()
  }, [projectId, version])

  const loadWorkflow = async () => {
    try {
      const data = await api.workflows.get(projectId)
      // Ensure edges have unique ids
      const edgesWithIds = (data.edges || []).map((edge: any, index: number) => ({
        ...edge,
        id: edge.id || `e${index}`,
      }))
      setNodes(data.nodes || [])
      setEdges(edgesWithIds)
    } catch (error) {
      console.error('Failed to load workflow:', error)
      toast.error('Failed to load workflow')
    }
  }

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, id: `e${eds.length}` }, eds)),
    [setEdges]
  )

  const handleSave = async () => {
    try {
      await api.workflows.update(projectId, { nodes, edges })
      toast.success('Workflow saved')
    } catch (error) {
      toast.error('Failed to save workflow')
    }
  }

  const handleExecute = async () => {
    setIsRunning(true)
    try {
      await handleSave() // Save before executing
      const result = await api.workflows.execute(projectId)
      toast.success('Workflow executed successfully!')
      console.log('Execution result:', result)
    } catch (error) {
      toast.error('Failed to execute workflow')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="flex-1 h-full relative group">
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <Button 
          onClick={handleExecute} 
          disabled={isRunning}
          className="bg-green-600 hover:bg-green-700 text-white"
        >
          <Play className="w-4 h-4 mr-2" />
          {isRunning ? 'Running...' : 'Run Workflow'}
        </Button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-right"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}
