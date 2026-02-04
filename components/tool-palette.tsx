'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import type { MCPTool, MCPServerStatus } from '@/lib/types/mcp'
import { Globe, Github, MessageSquare, Folder, Search, Database, Wrench, ChevronDown, ChevronRight, Zap, Circle } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'

interface ToolPaletteProps {
  tools: MCPTool[]
  servers: MCPServerStatus[]
  onDragStart: (tool: MCPTool) => void
}

const iconMap: Record<string, React.ReactNode> = {
  globe: <Globe className="w-4 h-4" />,
  browser: <Globe className="w-4 h-4" />,
  github: <Github className="w-4 h-4" />,
  slack: <MessageSquare className="w-4 h-4" />,
  folder: <Folder className="w-4 h-4" />,
  filesystem: <Folder className="w-4 h-4" />,
  search: <Search className="w-4 h-4" />,
  database: <Database className="w-4 h-4" />,
  scrape: <Zap className="w-4 h-4" />,
  default: <Wrench className="w-4 h-4" />,
}

function groupToolsByServer(tools: MCPTool[]): Record<string, MCPTool[]> {
  return tools.reduce((acc, tool) => {
    const server = tool.server_name
    if (!acc[server]) {
      acc[server] = []
    }
    acc[server].push(tool)
    return acc
  }, {} as Record<string, MCPTool[]>)
}

interface ToolItemProps {
  tool: MCPTool
  onDragStart: (tool: MCPTool) => void
}

function ToolItem({ tool, onDragStart }: ToolItemProps) {
  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData('application/json', JSON.stringify(tool))
    e.dataTransfer.effectAllowed = 'copy'
    onDragStart(tool)
  }

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="mx-3 my-1 px-3 py-2.5 rounded-lg bg-card border border-border hover:border-foreground/20 cursor-grab active:cursor-grabbing transition-all hover:shadow-sm"
    >
      <p className="font-medium text-sm text-foreground truncate">{tool.display_name}</p>
      <p className="text-xs text-muted-foreground truncate mt-0.5">
        {tool.description.length > 50 ? tool.description.slice(0, 50) + '...' : tool.description}
      </p>
    </div>
  )
}

interface ServerSectionProps {
  server: MCPServerStatus
  tools: MCPTool[]
  onDragStart: (tool: MCPTool) => void
}

function ServerSection({ server, tools, onDragStart }: ServerSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const icon = iconMap[server.icon || server.name] || iconMap.default

  return (
    <div className="border-b border-border last:border-b-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-3 w-full px-4 py-3 hover:bg-muted/50 transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0" />
        )}
        <div className="w-7 h-7 rounded-md bg-muted flex items-center justify-center shrink-0">
          {icon}
        </div>
        <span className="font-medium text-sm flex-1 text-left text-foreground truncate">
          {server.display_name}
        </span>
        <Circle className={cn(
          "w-2 h-2 shrink-0",
          server.connected ? "fill-emerald-500 text-emerald-500" : "fill-muted-foreground/30 text-muted-foreground/30"
        )} />
        <span className="text-xs text-muted-foreground tabular-nums">{tools.length}</span>
      </button>

      {isExpanded && tools.length > 0 && (
        <div className="pb-2">
          {tools.map((tool) => (
            <ToolItem key={tool.name} tool={tool} onDragStart={onDragStart} />
          ))}
        </div>
      )}

      {isExpanded && tools.length === 0 && (
        <p className="px-4 pb-3 text-xs text-muted-foreground">
          {server.connected ? 'No tools available' : 'Not connected'}
        </p>
      )}
    </div>
  )
}

export default function ToolPalette({ tools, servers, onDragStart }: ToolPaletteProps) {
  const toolsByServer = groupToolsByServer(tools)

  const sortedServers = [...servers].sort((a, b) => {
    if (a.connected && !b.connected) return -1
    if (!a.connected && b.connected) return 1
    return a.display_name.localeCompare(b.display_name)
  })

  return (
    <div className="w-96 border-r border-border bg-card flex flex-col h-full shrink-0">
      <div className="px-4 py-4 border-b border-border">
        <h3 className="font-semibold text-sm text-foreground">Tools</h3>
        <p className="text-xs text-muted-foreground mt-1">
          Drag onto canvas to add
        </p>
      </div>

      <ScrollArea className="flex-1">
        {sortedServers.map((server) => (
          <ServerSection
            key={server.name}
            server={server}
            tools={toolsByServer[server.name] || []}
            onDragStart={onDragStart}
          />
        ))}

        {servers.length === 0 && (
          <div className="p-6 text-center">
            <p className="text-sm text-muted-foreground">
              No servers configured.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Add integrations in Settings.
            </p>
          </div>
        )}
      </ScrollArea>
    </div>
  )
}
