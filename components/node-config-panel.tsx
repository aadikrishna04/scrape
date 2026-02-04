'use client'

import { useState, useEffect } from 'react'
import { X, Trash2, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ScrollArea } from '@/components/ui/scroll-area'
import DynamicParamsForm from '@/components/dynamic-params-form'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import type { MCPTool, NodeConfigUpdate, JSONSchema } from '@/lib/types/mcp'
import type { Node } from 'reactflow'

function _hasOwnerAndRepo(schema: JSONSchema): boolean {
  const props = schema.properties ?? {}
  return 'owner' in props && ('repo' in props || 'repository' in props)
}

function parseGitHubRepoUrl(input: string): { owner: string; repo: string } | null {
  const s = input.trim()
  if (!s) return null
  if (!s.includes('://') && !s.includes('.')) {
    const parts = s.split('/').filter(Boolean)
    if (parts.length >= 2) return { owner: parts[0], repo: parts[1].replace(/\.git$/, '') }
    if (parts.length === 1) return null
  }
  try {
    let url = s
    if (!url.startsWith('http')) url = `https://${url}`
    const u = new URL(url)
    if (!u.hostname?.toLowerCase().includes('github')) return null
    const path = u.pathname.replace(/^\/+/, '').split('/')
    const owner = path[0]
    const repo = path[1]?.replace(/\.git$/, '') ?? ''
    if (owner && repo) return { owner, repo }
  } catch {
    // ignore
  }
  return null
}

function GitHubRepoUrlInput({
  params,
  schema,
  onApply,
}: {
  params: Record<string, unknown>
  schema: JSONSchema
  onApply: (params: Record<string, unknown>) => void
}) {
  const [urlInput, setUrlInput] = useState('')
  const props = schema.properties ?? {}
  const repoKey = 'repo' in props ? 'repo' : 'repository'

  const handleApply = () => {
    const parsed = parseGitHubRepoUrl(urlInput)
    if (parsed) {
      onApply({ ...params, owner: parsed.owner, [repoKey]: parsed.repo })
      toast.success(`Set to ${parsed.owner}/${parsed.repo}`)
      setUrlInput('')
    } else if (urlInput.trim()) {
      toast.error('Enter a valid GitHub repo URL or owner/repo')
    }
  }

  const currentOwner = params.owner as string | undefined
  const currentRepo = (params[repoKey] as string | undefined) ?? (params.repo as string | undefined)
  const placeholder =
    currentOwner && currentRepo
      ? `Current: ${currentOwner}/${currentRepo}`
      : 'https://github.com/owner/repo'

  return (
    <div className="space-y-2 p-3 rounded-lg bg-muted/50 border border-border">
      <Label className="text-xs font-medium">Quick Fill Repository</Label>
      <div className="flex gap-2">
        <Input
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleApply()}
          placeholder={placeholder}
          className="font-mono text-sm flex-1 h-9"
        />
        <Button type="button" variant="secondary" size="sm" onClick={handleApply} className="h-9">
          Fill
        </Button>
      </div>
    </div>
  )
}

interface NodeConfigPanelProps {
  node: Node | null
  tools: MCPTool[]
  onUpdate: (nodeId: string, config: NodeConfigUpdate) => void
  onDelete: (nodeId: string) => void
  onClose: () => void
}

export default function NodeConfigPanel({
  node,
  tools,
  onUpdate,
  onDelete,
  onClose,
}: NodeConfigPanelProps) {
  const [label, setLabel] = useState('')
  const [params, setParams] = useState<Record<string, unknown>>({})
  const [instruction, setInstruction] = useState('')

  const toolName = node?.data?.tool_name as string | undefined
  const tool = tools.find((t) => t.name === toolName)

  useEffect(() => {
    if (node) {
      setLabel(node.data?.label as string || '')
      setParams((node.data?.params as Record<string, unknown>) || {})
      setInstruction(node.data?.instruction as string || '')
    }
  }, [node?.id, node?.data])

  if (!node) return null

  const nodeType = node.type

  const handleLabelChange = (newLabel: string) => {
    setLabel(newLabel)
    onUpdate(node.id, { label: newLabel })
  }

  const handleParamsChange = (newParams: Record<string, unknown>) => {
    setParams(newParams)
    onUpdate(node.id, { params: newParams })
  }

  const handleInstructionChange = (newInstruction: string) => {
    setInstruction(newInstruction)
    onUpdate(node.id, { instruction: newInstruction })
  }

  const handleDelete = () => {
    onDelete(node.id)
    onClose()
  }

  return (
    <div className="w-80 border-l border-border bg-card flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-4 border-b border-border flex justify-between items-start">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm text-foreground">Configure Node</h3>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {nodeType === 'mcp_tool' ? toolName : nodeType?.replace(/_/g, ' ')}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 shrink-0 -mr-2">
          <X className="w-4 h-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4 space-y-5">
          {/* Label */}
          <div className="space-y-2">
            <Label htmlFor="node-label" className="text-sm font-medium">
              Label
            </Label>
            <Input
              id="node-label"
              value={label}
              onChange={(e) => handleLabelChange(e.target.value)}
              placeholder="Node label"
              className="h-10"
            />
          </div>

          {/* MCP Tool Parameters */}
          {nodeType === 'mcp_tool' && tool && (
            <div className="space-y-4">
              {tool.server_name === 'github' && _hasOwnerAndRepo(tool.input_schema) && (
                <GitHubRepoUrlInput
                  params={params}
                  schema={tool.input_schema}
                  onApply={handleParamsChange}
                />
              )}

              <div>
                <Label className="text-sm font-medium">Parameters</Label>
                <p className="text-xs text-muted-foreground mt-0.5 mb-3">
                  Configure the tool inputs
                </p>
                <DynamicParamsForm
                  schema={tool.input_schema}
                  values={params}
                  onChange={handleParamsChange}
                  onFetchGithubLogin={
                    tool.server_name === 'github'
                      ? async () => {
                          try {
                            const { login } = await api.integrations.getGithubMe()
                            if (login) toast.success(`Owner set to ${login}`)
                            return login ?? null
                          } catch {
                            toast.error('Connect GitHub in Settings first')
                            return null
                          }
                        }
                      : undefined
                  }
                />
              </div>
            </div>
          )}

          {/* MCP Tool without schema */}
          {nodeType === 'mcp_tool' && !tool && (
            <div className="space-y-2">
              <Label>Parameters (JSON)</Label>
              <Textarea
                value={JSON.stringify(params, null, 2)}
                onChange={(e) => {
                  try {
                    handleParamsChange(JSON.parse(e.target.value))
                  } catch {
                    // Invalid JSON
                  }
                }}
                placeholder="{}"
                rows={6}
                className="font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground">
                Tool schema not available
              </p>
            </div>
          )}

          {/* AI Transform */}
          {nodeType === 'ai_transform' && (
            <div className="space-y-2">
              <Label htmlFor="ai-instruction" className="text-sm font-medium">
                Instruction
              </Label>
              <Textarea
                id="ai-instruction"
                value={instruction}
                onChange={(e) => handleInstructionChange(e.target.value)}
                placeholder="Describe how to transform the data..."
                rows={5}
              />
              <p className="text-xs text-muted-foreground">
                How the AI should process the input
              </p>
            </div>
          )}

          {/* Browser Agent */}
          {nodeType === 'browser_agent' && (
            <div className="space-y-2">
              <Label htmlFor="browser-instruction" className="text-sm font-medium">
                Instruction
              </Label>
              <Textarea
                id="browser-instruction"
                value={instruction}
                onChange={(e) => handleInstructionChange(e.target.value)}
                placeholder="Describe what the browser should do..."
                rows={5}
              />
              <p className="text-xs text-muted-foreground">
                Natural language browser instruction
              </p>
            </div>
          )}

          {/* Tool Info */}
          {tool && (
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-2">
                <Info className="w-3.5 h-3.5 text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">Tool Info</span>
              </div>
              <div className="text-xs text-muted-foreground space-y-1">
                <p><span className="font-medium">Name:</span> {tool.name}</p>
                <p><span className="font-medium">Server:</span> {tool.server_name}</p>
                {tool.description && (
                  <p className="mt-2 leading-relaxed">{tool.description}</p>
                )}
              </div>
            </div>
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-4 border-t border-border">
        <Button
          variant="outline"
          size="sm"
          className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
          onClick={handleDelete}
        >
          <Trash2 className="w-4 h-4 mr-2" />
          Delete Node
        </Button>
      </div>
    </div>
  )
}
