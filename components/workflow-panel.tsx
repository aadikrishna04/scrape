'use client'

import { useCallback, useEffect, useState, memo, useMemo, forwardRef, useImperativeHandle } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Node,
  Handle,
  Position,
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { Play, Globe, Brain, Loader2, CheckCircle2, XCircle, PanelLeftClose, PanelLeft, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { MCPTool, MCPServerStatus, NodeConfigUpdate } from '@/lib/types/mcp'
import ToolPalette from '@/components/tool-palette'
import NodeConfigPanel from '@/components/node-config-panel'
import MCPToolNode from '@/components/nodes/mcp-tool-node'

export interface WorkflowPanelHandle {
  updateNodeStatus: (nodeId: string, status: string) => void
  updateWorkflow: (nodes: any[], edges: any[]) => void
}

type NodeStatus = 'idle' | 'executing' | 'success' | 'failed'

// Browser Agent Node
const BrowserAgentNode = memo(({ data }: { data: Record<string, unknown> }) => {
  const status: NodeStatus = (data?.executionStatus as NodeStatus) || 'idle'
  const label = (data?.label as string) || 'Browser Agent'
  const instruction = data?.instruction as string

  return (
    <div className={cn(
      "px-4 py-3 rounded-xl min-w-[180px] transition-all duration-200 border-2",
      status === 'idle' && "bg-card border-border shadow-sm",
      status === 'executing' && "bg-amber-50 border-amber-300 shadow-md",
      status === 'success' && "bg-emerald-50 border-emerald-300",
      status === 'failed' && "bg-red-50 border-red-300"
    )}>
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background" />
      <div className="flex items-center gap-2.5">
        {status === 'executing' ? (
          <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
        ) : status === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
        ) : status === 'failed' ? (
          <XCircle className="w-4 h-4 text-red-600" />
        ) : (
          <Globe className="w-4 h-4 text-muted-foreground" />
        )}
        <span className="font-medium text-sm text-foreground">{label}</span>
      </div>
      {instruction && (
        <p className="text-xs text-muted-foreground mt-1.5 truncate max-w-[200px]">
          {instruction}
        </p>
      )}
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background" />
    </div>
  )
})
BrowserAgentNode.displayName = 'BrowserAgentNode'

// AI Transform Node
const AITransformNode = memo(({ data }: { data: Record<string, unknown> }) => {
  const status: NodeStatus = (data?.executionStatus as NodeStatus) || 'idle'
  const label = (data?.label as string) || 'AI Transform'
  const instruction = data?.instruction as string

  return (
    <div className={cn(
      "px-4 py-3 rounded-xl min-w-[180px] transition-all duration-200 border-2",
      status === 'idle' && "bg-card border-border shadow-sm",
      status === 'executing' && "bg-amber-50 border-amber-300 shadow-md",
      status === 'success' && "bg-emerald-50 border-emerald-300",
      status === 'failed' && "bg-red-50 border-red-300"
    )}>
      <Handle type="target" position={Position.Left} className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background" />
      <div className="flex items-center gap-2.5">
        {status === 'executing' ? (
          <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
        ) : status === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
        ) : status === 'failed' ? (
          <XCircle className="w-4 h-4 text-red-600" />
        ) : (
          <Brain className="w-4 h-4 text-muted-foreground" />
        )}
        <span className="font-medium text-sm text-foreground">{label}</span>
      </div>
      {instruction && (
        <p className="text-xs text-muted-foreground mt-1.5 truncate max-w-[200px]">
          {instruction}
        </p>
      )}
      <Handle type="source" position={Position.Right} className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background" />
    </div>
  )
})
AITransformNode.displayName = 'AITransformNode'

interface WorkflowPanelProps {
  projectId: string
  version?: number
  onChatUpdate?: () => void
  onWorkflowChange?: (nodes: any[], edges: any[]) => void
}

interface WorkflowPanelInnerProps extends WorkflowPanelProps {
  innerRef?: React.Ref<WorkflowPanelHandle>
}

function WorkflowPanelInner({ projectId, version, onChatUpdate, onWorkflowChange, innerRef }: WorkflowPanelInnerProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [isRunning, setIsRunning] = useState(false)
  const [executionStatus, setExecutionStatus] = useState<Record<string, NodeStatus>>({})
  const [tools, setTools] = useState<MCPTool[]>([])
  const [servers, setServers] = useState<MCPServerStatus[]>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [showPalette, setShowPalette] = useState(true)

  const { screenToFlowPosition } = useReactFlow()

  // Expose methods to parent via ref
  useImperativeHandle(innerRef, () => ({
    updateNodeStatus: (nodeId: string, status: string) => {
      setExecutionStatus((prev) => ({ ...prev, [nodeId]: status as NodeStatus }))
    },
    updateWorkflow: (newNodes: any[], newEdges: any[]) => {
      const edgesWithIds = newEdges.map((edge: any, index: number) => ({
        ...edge,
        id: edge.id || `e${index}`,
      }))
      setNodes(newNodes)
      setEdges(edgesWithIds)
    },
  }), [setNodes, setEdges])

  const nodeTypes = useMemo(() => ({
    browser_agent: BrowserAgentNode,
    ai_transform: AITransformNode,
    mcp_tool: MCPToolNode,
  }), [])

  useEffect(() => {
    loadToolsAndServers()
  }, [])

  useEffect(() => {
    loadWorkflow()
  }, [projectId, version])

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

  // Notify parent when workflow changes
  useEffect(() => {
    if (nodes.length > 0 || edges.length > 0) {
      onWorkflowChange?.(nodes, edges)
    }
  }, [nodes, edges, onWorkflowChange])

  const loadToolsAndServers = async () => {
    try {
      const [toolsData, serversData] = await Promise.all([
        api.mcp.getTools(),
        api.mcp.getServers(),
      ])
      setTools(toolsData)
      setServers(serversData)
    } catch (error) {
      console.error('Failed to load MCP data:', error)
    }
  }

  const loadWorkflow = async () => {
    try {
      const data = await api.workflows.get(projectId)
      const edgesWithIds = (data.edges || []).map((edge: Record<string, unknown>, index: number) => ({
        ...edge,
        id: edge.id || `e${index}`,
      }))
      setNodes(data.nodes || [])
      setEdges(edgesWithIds)
      setExecutionStatus({})
      setSelectedNode(null)
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

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      try {
        const toolData = JSON.parse(event.dataTransfer.getData('application/json')) as MCPTool

        const position = screenToFlowPosition({
          x: event.clientX,
          y: event.clientY,
        })

        const newNode: Node = {
          id: `${Date.now()}`,
          type: 'mcp_tool',
          position,
          data: {
            tool_name: toolData.name,
            label: toolData.display_name,
            params: {},
            icon: toolData.server_name,
          },
        }

        setNodes((nds) => [...nds, newNode])
        toast.success(`Added ${toolData.display_name}`)
      } catch (error) {
        console.error('Failed to add node:', error)
      }
    },
    [screenToFlowPosition, setNodes]
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleNodeUpdate = useCallback(
    async (nodeId: string, config: NodeConfigUpdate) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? {
                ...n,
                data: {
                  ...n.data,
                  ...(config.label && { label: config.label }),
                  ...(config.params && { params: config.params }),
                  ...(config.instruction && { instruction: config.instruction }),
                },
              }
            : n
        )
      )

      if (selectedNode?.id === nodeId) {
        setSelectedNode((prev) =>
          prev
            ? {
                ...prev,
                data: {
                  ...prev.data,
                  ...(config.label && { label: config.label }),
                  ...(config.params && { params: config.params }),
                  ...(config.instruction && { instruction: config.instruction }),
                },
              }
            : null
        )
      }

      try {
        await api.workflows.updateNode(projectId, nodeId, config)
      } catch (error) {
        console.error('Failed to update node:', error)
      }
    },
    [projectId, selectedNode, setNodes]
  )

  const handleNodeDelete = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNode(null)
      toast.success('Node deleted')
    },
    [setNodes, setEdges]
  )

  const handleExecute = async () => {
    if (nodes.length === 0) {
      toast.error('No nodes to execute')
      return
    }

    setIsRunning(true)
    setSelectedNode(null)
    resetNodeStatuses()

    const nodeIds = nodes.map((n) => n.id)
    nodeIds.forEach((id) => updateNodeStatus(id, 'idle'))

    try {
      await handleSave()

      if (nodeIds.length > 0) {
        updateNodeStatus(nodeIds[0], 'executing')
      }

      const result = await api.workflows.execute(projectId)

      const executionOrder = result.execution_order || nodeIds
      const results = result.results || []

      const resultMap: Record<string, string> = {}
      results.forEach((r: Record<string, unknown>) => {
        resultMap[r.node_id as string] = r.status === 'success' ? 'success' : 'failed'
      })

      executionOrder.forEach((nodeId: string) => {
        const status = resultMap[nodeId] || 'failed'
        updateNodeStatus(nodeId, status as NodeStatus)
      })

      if (result.status === 'completed') {
        toast.success('Workflow executed successfully')
      } else if (result.status === 'partial_failure') {
        toast.warning('Workflow completed with issues')
      } else {
        toast.error('Workflow execution failed')
      }

      onChatUpdate?.()
    } catch (error) {
      console.error('Execution error:', error)
      nodeIds.forEach((id) => updateNodeStatus(id, 'failed'))
      toast.error('Failed to execute workflow')
      onChatUpdate?.()
    } finally {
      setIsRunning(false)
      setTimeout(() => {
        resetNodeStatuses()
      }, 5000)
    }
  }

  return (
    <div className="flex h-full">
      {/* Tool Palette */}
      {showPalette && (
        <ToolPalette
          tools={tools}
          servers={servers}
          onDragStart={() => {}}
        />
      )}

      {/* Canvas */}
      <div className="flex-1 h-full relative">
        {/* Top Left Controls */}
        <div className="absolute top-4 left-4 z-10 flex gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => setShowPalette(!showPalette)}
            className="bg-card shadow-sm h-9 w-9"
          >
            {showPalette ? (
              <PanelLeftClose className="w-4 h-4" />
            ) : (
              <PanelLeft className="w-4 h-4" />
            )}
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={loadToolsAndServers}
            className="bg-card shadow-sm h-9 w-9"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>

        {/* Top Right Controls */}
        <div className="absolute top-4 right-4 z-10 flex gap-3 items-center">
          {isRunning && (
            <div className="flex items-center gap-2 bg-amber-100 text-amber-800 px-3 py-2 rounded-lg text-sm font-medium">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="hidden sm:inline">Running...</span>
            </div>
          )}
          <Button
            onClick={handleExecute}
            disabled={isRunning || nodes.length === 0}
            className="bg-foreground hover:bg-foreground/90 text-background shadow-sm"
          >
            {isRunning ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Play className="w-4 h-4 mr-2" />
            )}
            <span className="hidden sm:inline">
              {isRunning ? 'Running...' : 'Run Workflow'}
            </span>
            <span className="sm:hidden">Run</span>
          </Button>
        </div>

        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          onDrop={onDrop}
          onDragOver={onDragOver}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#e5e5e5" gap={20} />
          <Controls className="!rounded-lg !border !border-border !shadow-sm" />
          <MiniMap
            className="!rounded-lg !border !border-border !shadow-sm"
            nodeColor="#d4d4d4"
            maskColor="rgba(0, 0, 0, 0.1)"
          />
        </ReactFlow>
      </div>

      {/* Config Panel */}
      {selectedNode && (
        <NodeConfigPanel
          node={selectedNode}
          tools={tools}
          onUpdate={handleNodeUpdate}
          onDelete={handleNodeDelete}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  )
}

const WorkflowPanel = forwardRef<WorkflowPanelHandle, WorkflowPanelProps>((props, ref) => {
  return (
    <ReactFlowProvider>
      <WorkflowPanelInner {...props} innerRef={ref} />
    </ReactFlowProvider>
  )
})

WorkflowPanel.displayName = 'WorkflowPanel'

export default WorkflowPanel
