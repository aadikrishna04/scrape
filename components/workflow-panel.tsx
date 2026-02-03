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
import { Play, Globe, Brain, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type NodeStatus = 'idle' | 'executing' | 'success' | 'failed'

// Custom Node Components with status support
const BrowserAgentNode = memo(({ data }: { data: any }) => {
  const status: NodeStatus = data?.executionStatus || 'idle'
  
  return (
    <div className={cn(
      "px-4 py-2 shadow-md rounded-md min-w-[150px] transition-all duration-300",
      status === 'idle' && "bg-blue-50 border-2 border-blue-200",
      status === 'executing' && "bg-yellow-50 border-2 border-yellow-400 animate-pulse shadow-lg shadow-yellow-200",
      status === 'success' && "bg-green-50 border-2 border-green-400",
      status === 'failed' && "bg-red-50 border-2 border-red-400"
    )}>
      <Handle type="target" position={Position.Left} className="w-2 h-2" />
      <div className="flex items-center gap-2">
        {status === 'executing' ? (
          <Loader2 className="w-4 h-4 text-yellow-600 animate-spin" />
        ) : status === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-green-600" />
        ) : status === 'failed' ? (
          <XCircle className="w-4 h-4 text-red-600" />
        ) : (
          <Globe className="w-4 h-4 text-blue-600" />
        )}
        <span className={cn(
          "font-medium text-sm",
          status === 'idle' && "text-blue-900",
          status === 'executing' && "text-yellow-900",
          status === 'success' && "text-green-900",
          status === 'failed' && "text-red-900"
        )}>Browser Agent</span>
      </div>
      <div className="text-xs text-gray-600 mt-1 truncate">{data?.instruction?.substring(0, 30)}...</div>
      <Handle type="source" position={Position.Right} className="w-2 h-2" />
    </div>
  )
})

const AITransformNode = memo(({ data }: { data: any }) => {
  const status: NodeStatus = data?.executionStatus || 'idle'
  
  return (
    <div className={cn(
      "px-4 py-2 shadow-md rounded-md min-w-[150px] transition-all duration-300",
      status === 'idle' && "bg-purple-50 border-2 border-purple-200",
      status === 'executing' && "bg-yellow-50 border-2 border-yellow-400 animate-pulse shadow-lg shadow-yellow-200",
      status === 'success' && "bg-green-50 border-2 border-green-400",
      status === 'failed' && "bg-red-50 border-2 border-red-400"
    )}>
      <Handle type="target" position={Position.Left} className="w-2 h-2" />
      <div className="flex items-center gap-2">
        {status === 'executing' ? (
          <Loader2 className="w-4 h-4 text-yellow-600 animate-spin" />
        ) : status === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-green-600" />
        ) : status === 'failed' ? (
          <XCircle className="w-4 h-4 text-red-600" />
        ) : (
          <Brain className="w-4 h-4 text-purple-600" />
        )}
        <span className={cn(
          "font-medium text-sm",
          status === 'idle' && "text-purple-900",
          status === 'executing' && "text-yellow-900",
          status === 'success' && "text-green-900",
          status === 'failed' && "text-red-900"
        )}>AI Transform</span>
      </div>
      <div className="text-xs text-gray-600 mt-1 truncate">{data?.instruction?.substring(0, 30)}...</div>
      <Handle type="source" position={Position.Right} className="w-2 h-2" />
    </div>
  )
})

// Node types defined outside component
const nodeTypes = {
  browser_agent: BrowserAgentNode,
  ai_transform: AITransformNode,
}

interface WorkflowPanelProps {
  projectId: string
  version?: number
  onChatUpdate?: () => void
}

export default function WorkflowPanel({ projectId, version, onChatUpdate }: WorkflowPanelProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [isRunning, setIsRunning] = useState(false)
  const [executionStatus, setExecutionStatus] = useState<Record<string, NodeStatus>>({})

  useEffect(() => {
    loadWorkflow()
  }, [projectId, version])

  // Update node data with execution status
  useEffect(() => {
    if (Object.keys(executionStatus).length > 0) {
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          data: {
            ...node.data,
            executionStatus: executionStatus[node.id] || 'idle',
          },
        }))
      )
    }
  }, [executionStatus, setNodes])

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
      setExecutionStatus({}) // Reset execution status
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

  const updateNodeStatus = (nodeId: string, status: NodeStatus) => {
    setExecutionStatus((prev) => ({ ...prev, [nodeId]: status }))
  }

  const resetNodeStatuses = () => {
    setExecutionStatus({})
  }

  const handleExecute = async () => {
    if (nodes.length === 0) {
      toast.error('No nodes to execute')
      return
    }

    setIsRunning(true)
    resetNodeStatuses()

    // Get execution order (simple: by node id for now, backend returns actual order)
    const nodeIds = nodes.map((n) => n.id)

    // Set all nodes to pending first, then execute
    nodeIds.forEach((id) => updateNodeStatus(id, 'idle'))

    try {
      await handleSave() // Save before executing

      // Mark first node as executing
      if (nodeIds.length > 0) {
        updateNodeStatus(nodeIds[0], 'executing')
      }

      const result = await api.workflows.execute(projectId)
      console.log('Execution result:', result)

      // Update node statuses based on results
      const executionOrder = result.execution_order || nodeIds
      const results = result.results || []

      // Create a map of node results
      const resultMap: Record<string, string> = {}
      results.forEach((r: any) => {
        resultMap[r.node_id] = r.status === 'success' ? 'success' : 'failed'
      })

      // Update all nodes with their final status
      executionOrder.forEach((nodeId: string) => {
        const status = resultMap[nodeId] || 'failed'
        updateNodeStatus(nodeId, status as NodeStatus)
      })

      if (result.status === 'completed') {
        toast.success('Workflow executed successfully!')
      } else if (result.status === 'partial_failure') {
        toast.warning('Workflow completed with some issues')
      } else {
        toast.error('Workflow execution failed')
      }

      // Refresh chat to show execution results
      onChatUpdate?.()
    } catch (error) {
      console.error('Execution error:', error)
      // Mark all nodes as failed
      nodeIds.forEach((id) => updateNodeStatus(id, 'failed'))
      toast.error('Failed to execute workflow')
      // Still refresh chat to show error message
      onChatUpdate?.()
    } finally {
      setIsRunning(false)
      // Reset statuses after a delay so user can see the final state
      setTimeout(() => {
        resetNodeStatuses()
      }, 5000)
    }
  }

  return (
    <div className="flex-1 h-full relative group">
      <div className="absolute top-4 right-4 z-10 flex gap-2 items-center">
        {isRunning && (
          <div className="flex items-center gap-2 bg-yellow-100 text-yellow-800 px-3 py-1.5 rounded-md text-sm font-medium">
            <Loader2 className="w-4 h-4 animate-spin" />
            Executing workflow...
          </div>
        )}
        <Button 
          onClick={handleExecute} 
          disabled={isRunning}
          className="bg-green-600 hover:bg-green-700 text-white"
        >
          {isRunning ? (
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <Play className="w-4 h-4 mr-2" />
          )}
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
