'use client'

import { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { cn } from '@/lib/utils'
import { Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { integrationLogos, DefaultLogo } from '@/components/icons/integration-logos'

type NodeStatus = 'idle' | 'executing' | 'success' | 'failed'

interface MCPToolNodeProps {
  data: {
    tool_name?: string
    label?: string
    params?: Record<string, unknown>
    executionStatus?: NodeStatus
    icon?: string
  }
  selected?: boolean
}

function getServerFromToolName(toolName: string): string {
  // Tool names are typically "server.action" format
  const parts = toolName.split('.')
  if (parts.length > 1) {
    return parts[0]
  }
  return toolName
}

function getIconForTool(toolName: string): React.ReactNode {
  const serverName = getServerFromToolName(toolName)
  const LogoComponent = integrationLogos[serverName] || DefaultLogo
  return <LogoComponent className="w-4 h-4" />
}

function getStatusIcon(status: NodeStatus) {
  switch (status) {
    case 'executing':
      return <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />
    case 'success':
      return <CheckCircle2 className="w-4 h-4 text-emerald-600" />
    case 'failed':
      return <XCircle className="w-4 h-4 text-red-500" />
    default:
      return null
  }
}

const MCPToolNode = memo(({ data, selected }: MCPToolNodeProps) => {
  const status: NodeStatus = data?.executionStatus || 'idle'
  const toolName = data?.tool_name || 'unknown'
  const label = data?.label || toolName.split('.').pop()?.replace(/_/g, ' ') || 'Tool'

  const toolIcon = getIconForTool(toolName)
  const statusIcon = getStatusIcon(status)

  return (
    <div
      className={cn(
        "px-4 py-3 rounded-xl min-w-[180px] max-w-[220px] transition-all duration-200 border-2",
        selected && "ring-2 ring-foreground ring-offset-2 ring-offset-background",
        status === 'idle' && "bg-card border-border shadow-sm",
        status === 'executing' && "bg-amber-50 border-amber-300 shadow-md",
        status === 'success' && "bg-emerald-50 border-emerald-300",
        status === 'failed' && "bg-red-50 border-red-300"
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
      />

      <div className="flex items-center gap-2.5">
        <div className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
          status === 'idle' && "bg-muted/50",
          status === 'executing' && "bg-amber-100 text-amber-700",
          status === 'success' && "bg-emerald-100 text-emerald-700",
          status === 'failed' && "bg-red-100 text-red-600"
        )}>
          {statusIcon || toolIcon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm text-foreground truncate">
            {label}
          </p>
          <p className="text-xs text-muted-foreground truncate">
            {toolName}
          </p>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Right}
        className="!w-3 !h-3 !bg-muted-foreground !border-2 !border-background"
      />
    </div>
  )
})

MCPToolNode.displayName = 'MCPToolNode'

export default MCPToolNode
