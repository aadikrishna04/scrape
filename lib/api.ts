import { supabase } from '@/lib/supabase'
import type { MCPServerStatus, MCPTool, MCPServerConfig, NodeConfigUpdate } from '@/lib/types/mcp'

const RAW_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const API_URL = RAW_API_URL.endsWith('/api') ? RAW_API_URL : `${RAW_API_URL}/api`

// SSE Event Types for streaming chat
export type AgentEvent =
  | { type: 'agent_thinking'; content: string }
  | { type: 'workflow_update'; nodes: any[]; edges: any[] }
  | { type: 'node_status_change'; nodeId: string; status: 'executing' | 'success' | 'failed' }
  | { type: 'step_started'; tool: string; params: Record<string, unknown> }
  | { type: 'step_completed'; tool: string; output: string }
  | { type: 'plan_created'; steps: PlanStep[] }
  | { type: 'execution_complete'; success: boolean }
  | { type: 'error'; error: string }
  | { type: 'done'; message: string; workflow_update?: { nodes: any[]; edges: any[] } | null }

export interface PlanStep {
  tool_name: string
  params: Record<string, unknown>
  description: string
}

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  }
  return headers
}

export const api = {
  projects: {
    create: async (name: string, description?: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name, description }),
      })
      if (!res.ok) throw new Error('Failed to create project')
      return res.json()
    },
    list: async () => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to list projects')
      return res.json()
    },
    delete: async (id: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects/${id}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) throw new Error('Failed to delete project')
      return res.json()
    },
    rename: async (id: string, name: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects/${id}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ name }),
      })
      if (!res.ok) throw new Error('Failed to rename project')
      return res.json()
    },
  },
  chat: {
    send: async (projectId: string, message: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ project_id: projectId, message }),
      })
      if (!res.ok) throw new Error('Failed to send message')
      return res.json()
    },
    getHistory: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/chat/${projectId}`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to get chat history')
      return res.json()
    },
    /**
     * Stream chat responses via Server-Sent Events (SSE)
     * @param projectId - The project ID
     * @param message - User message
     * @param workflow - Optional current workflow state
     * @param onEvent - Callback for SSE events
     */
    streamChat: async (
      projectId: string,
      message: string,
      workflow: { nodes: any[], edges: any[] } | null,
      onEvent: (event: AgentEvent) => void
    ): Promise<void> => {
      const headers = await getAuthHeader()

      const response = await fetch(`${API_URL}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ project_id: projectId, message, workflow }),
      })

      if (!response.ok) {
        throw new Error('Failed to start streaming')
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event:')) {
              const eventType = line.slice(6).trim()
              continue
            }
            if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr)
                  // Determine event type from the data structure
                  if (data.content !== undefined) {
                    onEvent({ type: 'agent_thinking', content: data.content })
                  } else if (data.nodes !== undefined) {
                    onEvent({ type: 'workflow_update', nodes: data.nodes, edges: data.edges || [] })
                  } else if (data.nodeId !== undefined && data.status !== undefined) {
                    onEvent({ type: 'node_status_change', nodeId: data.nodeId, status: data.status })
                  } else if (data.tool !== undefined && data.params !== undefined) {
                    onEvent({ type: 'step_started', tool: data.tool, params: data.params })
                  } else if (data.tool !== undefined && data.output !== undefined) {
                    onEvent({ type: 'step_completed', tool: data.tool, output: data.output })
                  } else if (data.steps !== undefined) {
                    onEvent({ type: 'plan_created', steps: data.steps })
                  } else if (data.success !== undefined && data.message === undefined) {
                    onEvent({ type: 'execution_complete', success: data.success })
                  } else if (data.error !== undefined) {
                    onEvent({ type: 'error', error: data.error })
                  } else if (data.message !== undefined) {
                    onEvent({ type: 'done', message: data.message, workflow_update: data.workflow_update })
                  }
                } catch (e) {
                  console.error('Failed to parse SSE data:', e)
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    },
  },
  workflows: {
    get: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to get workflow')
      return res.json()
    },
    update: async (projectId: string, workflow: { nodes: any[], edges: any[] }) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(workflow),
      })
      if (!res.ok) throw new Error('Failed to update workflow')
      return res.json()
    },
    execute: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}/execute`, {
        method: 'POST',
        headers,
      })
      if (!res.ok) throw new Error('Failed to execute workflow')
      return res.json()
    },
    /**
     * Stream workflow execution with real-time node status updates via SSE
     * @param projectId - The project ID
     * @param onEvent - Callback for SSE events (node_status_change, done, error)
     */
    executeStream: async (
      projectId: string,
      onEvent: (event: { type: string; node_id?: string; status?: string; data?: any }) => void
    ): Promise<void> => {
      const headers = await getAuthHeader()

      const response = await fetch(`${API_URL}/workflows/${projectId}/execute/stream`, {
        method: 'POST',
        headers,
      })

      if (!response.ok) {
        const detail = await response.text().catch(() => '')
        throw new Error(
          `Failed to start workflow execution stream (HTTP ${response.status})${detail ? `: ${detail}` : ''}`
        )
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let currentEventType: string | null = null

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('event:')) {
              currentEventType = line.slice(6).trim() || null
              continue
            }
            if (line.startsWith('data:')) {
              const dataStr = line.slice(5).trim()
              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr)
                  if (currentEventType === 'node_status_change') {
                    if (data.node_id !== undefined && data.status !== undefined) {
                      onEvent({ type: 'node_status_change', node_id: data.node_id, status: data.status })
                    }
                  } else if (currentEventType === 'done') {
                    onEvent({ type: 'done', data })
                  } else if (currentEventType === 'error') {
                    onEvent({ type: 'error', data })
                  } else {
                    if (data.node_id !== undefined && data.status !== undefined) {
                      onEvent({ type: 'node_status_change', node_id: data.node_id, status: data.status })
                    } else if (data.status !== undefined && data.results !== undefined) {
                      onEvent({ type: 'done', data })
                    } else if (data.error !== undefined) {
                      onEvent({ type: 'error', data })
                    }
                  }

                  currentEventType = null
                } catch (e) {
                  console.error('Failed to parse SSE data:', e)
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    },
    executeAgentic: async (projectId: string, goal: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}/execute-agentic`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ goal }),
      })
      if (!res.ok) throw new Error('Failed to execute agentic workflow')
      return res.json()
    },
    updateNode: async (projectId: string, nodeId: string, config: NodeConfigUpdate) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}/nodes/${nodeId}`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify(config),
      })
      if (!res.ok) throw new Error('Failed to update node')
      return res.json()
    },
  },
  mcp: {
    getServers: async (): Promise<MCPServerStatus[]> => {
      try {
        const headers = await getAuthHeader()
        const res = await fetch(`${API_URL}/mcp/servers`, { headers })
        if (!res.ok) return []
        return res.json()
      } catch {
        return []
      }
    },
    addServer: async (config: Omit<MCPServerConfig, 'enabled'>): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/servers`, {
        method: 'POST',
        headers,
        body: JSON.stringify(config),
      })
      if (!res.ok) throw new Error('Failed to add MCP server')
    },
    connectServer: async (serverName: string, token?: string): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/servers/${serverName}/connect`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ token }),
      })
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: 'Failed to connect MCP server' }))
        throw new Error(error.detail || 'Failed to connect MCP server')
      }
    },
    getServerRequirements: async (serverName: string): Promise<{
      requires_auth: boolean
      type: string
      name: string | null
      description: string | null
      env_var: string | null
      help_url: string | null
    }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/servers/${serverName}/requirements`, { headers })
      if (!res.ok) throw new Error('Failed to get server requirements')
      return res.json()
    },
    disconnectServer: async (serverName: string): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/servers/${serverName}/disconnect`, {
        method: 'POST',
        headers,
      })
      if (!res.ok) throw new Error('Failed to disconnect MCP server')
    },
    removeServer: async (serverName: string): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/servers/${serverName}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) throw new Error('Failed to remove MCP server')
    },
    getTools: async (): Promise<MCPTool[]> => {
      try {
        const headers = await getAuthHeader()
        const res = await fetch(`${API_URL}/mcp/tools`, { headers })
        if (!res.ok) return []
        return res.json()
      } catch {
        return []
      }
    },
    getToolSchema: async (toolName: string): Promise<Record<string, unknown>> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/mcp/tools/${encodeURIComponent(toolName)}/schema`, { headers })
      if (!res.ok) throw new Error('Failed to get tool schema')
      return res.json()
    },
  },
  runs: {
    list: async (projectId: string, page: number = 1): Promise<{ runs: Run[]; total: number }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects/${projectId}/runs?page=${page}`, { headers })
      if (!res.ok) return { runs: [], total: 0 }
      return res.json()
    },
    get: async (runId: string): Promise<RunDetail> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/runs/${runId}`, { headers })
      if (!res.ok) throw new Error('Failed to get run')
      return res.json()
    },
    getAnalysis: async (runId: string): Promise<{ findings: AnalysisFinding[] }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/runs/${runId}/analysis`, { headers })
      if (!res.ok) return { findings: [] }
      return res.json()
    },
    analyze: async (runId: string): Promise<{ findings: AnalysisFinding[] }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/runs/${runId}/analyze`, {
        method: 'POST',
        headers
      })
      if (!res.ok) throw new Error('Failed to analyze run')
      return res.json()
    },
  },
  integrations: {
    // Get all integrations with their connection status
    list: async (): Promise<{ integrations: IntegrationStatus[] }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations`, { headers })
      if (!res.ok) throw new Error('Failed to list integrations')
      return res.json()
    },

    // Get status for a specific integration
    getStatus: async (provider: string): Promise<{ connected: boolean; provider: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/${provider}/status`, { headers })
      if (!res.ok) throw new Error(`Failed to get ${provider} status`)
      return res.json()
    },

    // Connect an integration with a token
    connect: async (provider: string, token: string): Promise<{ success: boolean; provider: string; warning?: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/${provider}/connect`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ token }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Failed to connect ${provider}`)
      }
      return res.json()
    },

    // Disconnect an integration
    disconnect: async (provider: string): Promise<{ success: boolean }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/${provider}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Failed to disconnect ${provider}`)
      }
      return res.json()
    },

    // Get requirements for an integration
    getRequirements: async (provider: string): Promise<IntegrationRequirements> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/${provider}/requirements`, { headers })
      if (!res.ok) throw new Error(`Failed to get ${provider} requirements`)
      return res.json()
    },

    // GitHub-specific endpoints (OAuth flow)
    getGithubStatus: async (): Promise<{ connected: boolean }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/github/status`, { headers })
      if (!res.ok) throw new Error('Failed to get GitHub status')
      return res.json()
    },
    getGithubMe: async (): Promise<{ login: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/github/me`, { headers })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to get GitHub username')
      }
      return res.json()
    },
    getGithubOAuthStart: async (): Promise<{ url: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/github/oauth/start`, { headers })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to start GitHub OAuth')
      }
      return res.json()
    },
    disconnectGithub: async (): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/github`, { method: 'DELETE', headers })
      if (!res.ok) throw new Error('Failed to disconnect GitHub')
    },

    // Google OAuth endpoints (Gmail, Calendar, Drive)
    getGoogleOAuthStart: async (service: 'gmail' | 'google-calendar' | 'google-drive'): Promise<{ url: string; service: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/google/oauth/start?service=${service}`, { headers })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || 'Failed to start Google OAuth')
      }
      return res.json()
    },
    getGoogleStatus: async (service: string): Promise<{ connected: boolean; service: string }> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/google/${service}/status`, { headers })
      if (!res.ok) throw new Error(`Failed to get ${service} status`)
      return res.json()
    },
    disconnectGoogle: async (service: string): Promise<void> => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/integrations/google/${service}`, { method: 'DELETE', headers })
      if (!res.ok) throw new Error(`Failed to disconnect ${service}`)
    },
  },
}

// Run types
export interface Run {
  id: string
  project_id: string
  name: string | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  start_time: string
  end_time: string | null
  metadata: Record<string, any>
  created_at: string
}

export interface RunEvent {
  id: string
  run_id: string
  type: 'action' | 'reasoning' | 'node_start' | 'node_complete'
  payload: Record<string, any>
  timestamp: string
  step_number: number | null
}

export interface RunDetail extends Run {
  events: RunEvent[]
}

export interface AnalysisFinding {
  id?: string
  severity: 'low' | 'medium' | 'high'
  category: string
  description: string
  evidence: string[]
  created_at?: string
}

// Integration types
export interface IntegrationStatus {
  name: string
  display_name: string
  connected: boolean
  auth_type: 'oauth' | 'token' | 'none'
  icon?: string
  help_url?: string
  description?: string
}

export interface IntegrationRequirements {
  requires_auth: boolean
  type: 'oauth' | 'token' | 'none'
  name: string
  description: string | null
  env_var: string | null
  help_url: string | null
  required_scopes: string[] | null
  setup_steps: string[] | null
}
