// MCP Types for PromptFlow

export interface MCPServerConfig {
  name: string
  display_name: string
  command: string
  args: string[]
  env?: Record<string, string>
}

export interface MCPServerStatus {
  name: string
  display_name: string
  connected: boolean
  tool_count: number
  icon?: string
  error?: string
}

export interface MCPTool {
  name: string
  server_name: string
  display_name: string
  description: string
  input_schema: JSONSchema
  category?: string
}

export interface JSONSchema {
  type: string
  properties?: Record<string, JSONSchema>
  required?: string[]
  items?: JSONSchema
  enum?: string[]
  description?: string
  default?: unknown
  additionalProperties?: JSONSchema | boolean
}

export interface NodeConfigUpdate {
  tool_name?: string
  params?: Record<string, unknown>
  prompt?: string
  label?: string
  instruction?: string
}

// Node data types for ReactFlow
export interface MCPToolNodeData {
  tool_name: string
  params: Record<string, unknown>
  label: string
  executionStatus?: 'idle' | 'executing' | 'success' | 'failed'
  icon?: string
}

export interface AITransformNodeData {
  instruction: string
  label: string
  executionStatus?: 'idle' | 'executing' | 'success' | 'failed'
}

export interface BrowserAgentNodeData {
  instruction: string
  label?: string
  executionStatus?: 'idle' | 'executing' | 'success' | 'failed'
}

export type WorkflowNodeData = MCPToolNodeData | AITransformNodeData | BrowserAgentNodeData
