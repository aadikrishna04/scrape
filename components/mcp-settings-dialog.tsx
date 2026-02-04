'use client'

import { useState, useEffect } from 'react'
import { Globe, Github, MessageSquare, Folder, Search, Database, Wrench, Wifi, WifiOff, Plus, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { MCPServerStatus } from '@/lib/types/mcp'

const iconMap: Record<string, React.ReactNode> = {
  globe: <Globe className="w-5 h-5" />,
  github: <Github className="w-5 h-5" />,
  slack: <MessageSquare className="w-5 h-5" />,
  folder: <Folder className="w-5 h-5" />,
  search: <Search className="w-5 h-5" />,
  database: <Database className="w-5 h-5" />,
  cloud: <Folder className="w-5 h-5" />,
  default: <Wrench className="w-5 h-5" />,
}

interface ServerCardProps {
  server: MCPServerStatus
  onConnect: () => Promise<void>
  onDisconnect: () => Promise<void>
  onRemove: () => Promise<void>
  isBuiltIn: boolean
}

function ServerCard({ server, onConnect, onDisconnect, onRemove, isBuiltIn }: ServerCardProps) {
  const [isLoading, setIsLoading] = useState(false)

  const icon = iconMap[server.icon || 'default'] || iconMap.default

  const handleConnect = async () => {
    setIsLoading(true)
    try {
      await onConnect()
      toast.success(`Connected to ${server.display_name}`)
    } catch (error) {
      toast.error(`Failed to connect: ${(error as Error).message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDisconnect = async () => {
    setIsLoading(true)
    try {
      await onDisconnect()
      toast.success(`Disconnected from ${server.display_name}`)
    } catch (error) {
      toast.error(`Failed to disconnect: ${(error as Error).message}`)
    } finally {
      setIsLoading(false)
    }
  }

  const handleRemove = async () => {
    setIsLoading(true)
    try {
      await onRemove()
      toast.success(`Removed ${server.display_name}`)
    } catch (error) {
      toast.error(`Failed to remove: ${(error as Error).message}`)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Card className={server.connected ? 'border-green-200 bg-green-50/50' : ''}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${server.connected ? 'bg-green-100 text-green-700' : 'bg-muted text-muted-foreground'}`}>
              {icon}
            </div>
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                {server.display_name}
                {server.connected ? (
                  <Wifi className="w-4 h-4 text-green-500" />
                ) : (
                  <WifiOff className="w-4 h-4 text-muted-foreground" />
                )}
              </CardTitle>
              <CardDescription>
                {server.connected
                  ? `${server.tool_count} tool${server.tool_count !== 1 ? 's' : ''} available`
                  : 'Not connected'}
              </CardDescription>
            </div>
          </div>
          <div className="flex gap-2">
            {server.connected ? (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
                disabled={isLoading || isBuiltIn}
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Disconnect'}
              </Button>
            ) : (
              <Button
                variant="default"
                size="sm"
                onClick={handleConnect}
                disabled={isLoading || isBuiltIn}
              >
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Connect'}
              </Button>
            )}
            {!isBuiltIn && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleRemove}
                disabled={isLoading}
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      {server.error && (
        <CardContent className="pt-0">
          <p className="text-sm text-destructive">{server.error}</p>
        </CardContent>
      )}
    </Card>
  )
}

interface AddServerFormProps {
  onAdd: (name: string, displayName: string, command: string, args: string[]) => Promise<void>
}

function AddServerForm({ onAdd }: AddServerFormProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [name, setName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [command, setCommand] = useState('npx')
  const [args, setArgs] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !displayName || !command) return

    setIsLoading(true)
    try {
      await onAdd(name, displayName, command, args.split(' ').filter(Boolean))
      setName('')
      setDisplayName('')
      setCommand('npx')
      setArgs('')
      setIsOpen(false)
      toast.success('Server added successfully')
    } catch (error) {
      toast.error(`Failed to add server: ${(error as Error).message}`)
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) {
    return (
      <Button
        variant="outline"
        className="w-full"
        onClick={() => setIsOpen(true)}
      >
        <Plus className="w-4 h-4 mr-2" />
        Add Custom Server
      </Button>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Add Custom MCP Server</CardTitle>
        <CardDescription>Connect to a custom MCP server</CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Server ID</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="my-server"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="My Server"
                required
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="command">Command</Label>
            <Input
              id="command"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="npx"
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="args">Arguments (space-separated)</Label>
            <Input
              id="args"
              value={args}
              onChange={(e) => setArgs(e.target.value)}
              placeholder="-y @modelcontextprotocol/server-github"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
              Add Server
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

interface MCPSettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function MCPSettingsDialog({ open, onOpenChange }: MCPSettingsDialogProps) {
  const [servers, setServers] = useState<MCPServerStatus[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const loadServers = async () => {
    setIsLoading(true)
    try {
      const data = await api.mcp.getServers()
      setServers(data)
    } catch (error) {
      console.error('Failed to load servers:', error)
      toast.error('Failed to load MCP servers')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      loadServers()
    }
  }, [open])

  const handleConnect = async (serverName: string) => {
    await api.mcp.connectServer(serverName)
    await loadServers()
  }

  const handleDisconnect = async (serverName: string) => {
    await api.mcp.disconnectServer(serverName)
    await loadServers()
  }

  const handleRemove = async (serverName: string) => {
    await api.mcp.removeServer(serverName)
    await loadServers()
  }

  const handleAdd = async (name: string, displayName: string, command: string, args: string[]) => {
    await api.mcp.addServer({ name, display_name: displayName, command, args })
    await loadServers()
  }

  // Built-in servers that can't be removed
  const builtInServers = new Set(['browser'])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>MCP Server Settings</DialogTitle>
          <DialogDescription>
            Connect to MCP servers to add their tools to your workflows.
            Tools from connected servers will appear in the tool palette.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : servers.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No MCP servers configured. Add a server to get started.
            </p>
          ) : (
            servers.map((server) => (
              <ServerCard
                key={server.name}
                server={server}
                onConnect={() => handleConnect(server.name)}
                onDisconnect={() => handleDisconnect(server.name)}
                onRemove={() => handleRemove(server.name)}
                isBuiltIn={builtInServers.has(server.name)}
              />
            ))
          )}

          <AddServerForm onAdd={handleAdd} />
        </div>
      </DialogContent>
    </Dialog>
  )
}
