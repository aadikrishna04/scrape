'use client'

import { useState, useEffect, useRef } from 'react'
import { Send, Bot, User, MessageSquare, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api, AgentEvent } from '@/lib/api'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
  isStreaming?: boolean
}

interface ChatPanelProps {
  projectId: string
  onWorkflowUpdate?: (nodes?: any[], edges?: any[]) => void
  onNodeStatusChange?: (nodeId: string, status: 'executing' | 'success' | 'failed') => void
  version?: number
  workflow?: { nodes: any[], edges: any[] } | null
}

export default function ChatPanel({ projectId, onWorkflowUpdate, onNodeStatusChange, version, workflow }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [agentStatus, setAgentStatus] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    loadHistory()
  }, [projectId, version])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  const loadHistory = async () => {
    try {
      const data = await api.chat.getHistory(projectId)
      setMessages(data.messages)
    } catch (error) {
      console.error('Failed to load chat history:', error)
    }
  }

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isLoading || isStreaming) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)
    setIsStreaming(true)
    setStreamingContent('')
    setAgentStatus(null)

    // Reset textarea height
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
    }

    try {
      // Use streaming API
      await api.chat.streamChat(
        projectId,
        userMessage,
        workflow || null,
        (event: AgentEvent) => {
          switch (event.type) {
            case 'agent_thinking':
              setStreamingContent(prev => prev + event.content)
              break

            case 'workflow_update':
              onWorkflowUpdate?.(event.nodes, event.edges)
              break

            case 'node_status_change':
              onNodeStatusChange?.(event.nodeId, event.status)
              break

            case 'step_started':
              setAgentStatus(`Running ${event.tool}...`)
              break

            case 'step_completed':
              setAgentStatus(null)
              break

            case 'plan_created':
              setAgentStatus(`Planning: ${event.steps.length} steps`)
              break

            case 'execution_complete':
              setAgentStatus(null)
              if (event.success) {
                toast.success('Workflow executed successfully')
              }
              break

            case 'error':
              toast.error(event.error)
              setAgentStatus(null)
              break

            case 'done':
              // Add the final message
              setMessages(prev => [...prev, { role: 'assistant', content: event.message }])
              setStreamingContent('')
              setAgentStatus(null)

              if (event.workflow_update) {
                toast.success('Workflow updated')
                onWorkflowUpdate?.(event.workflow_update.nodes, event.workflow_update.edges)
              }
              break
          }
        }
      )
    } catch (error) {
      // Fallback to non-streaming API
      try {
        const response = await api.chat.send(projectId, userMessage)
        setMessages(prev => [...prev, { role: 'assistant', content: response.message }])

        if (response.workflow_update) {
          toast.success('Workflow updated')
          onWorkflowUpdate?.()
        }
      } catch (fallbackError) {
        toast.error('Failed to send message')
      }
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
      setStreamingContent('')
      setAgentStatus(null)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    // Auto-resize textarea
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center">
            <MessageSquare className="w-4 h-4 text-foreground" />
          </div>
          <div>
            <h2 className="font-medium text-foreground text-sm">Chat Assistant</h2>
            <p className="text-xs text-muted-foreground">Describe your workflow</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-8">
            <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
              <Bot className="w-6 h-6 text-muted-foreground" />
            </div>
            <p className="font-medium text-foreground mb-2">Start a conversation</p>
            <p className="text-sm text-muted-foreground max-w-[260px]">
              Describe what you want to build, like &quot;Scrape news from BBC and summarize it&quot;
            </p>
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={cn(
                  "flex gap-3",
                  msg.role === 'user' ? "flex-row-reverse" : "flex-row"
                )}
              >
                <div className={cn(
                  "w-7 h-7 rounded-lg flex items-center justify-center shrink-0",
                  msg.role === 'user' ? "bg-foreground" : "bg-muted"
                )}>
                  {msg.role === 'user' ? (
                    <User className="w-3.5 h-3.5 text-background" />
                  ) : (
                    <Bot className="w-3.5 h-3.5 text-foreground" />
                  )}
                </div>
                <div
                  className={cn(
                    "px-4 py-3 rounded-xl max-w-[85%] text-sm leading-relaxed",
                    msg.role === 'user'
                      ? "bg-foreground text-background"
                      : "bg-muted text-foreground"
                  )}
                >
                  {msg.role === 'assistant' ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        h1: ({ children }) => <h1 className="text-base font-semibold mb-2">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-sm font-semibold mb-2">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-sm font-medium mb-1">{children}</h3>,
                        code: ({ children }) => (
                          <code className="bg-background/20 px-1.5 py-0.5 rounded text-xs font-mono">
                            {children}
                          </code>
                        ),
                        pre: ({ children }) => (
                          <pre className="bg-background/20 p-3 rounded-lg my-2 overflow-x-auto text-xs font-mono">
                            {children}
                          </pre>
                        ),
                        hr: () => <hr className="my-3 border-border" />,
                        blockquote: ({ children }) => (
                          <blockquote className="border-l-2 border-foreground/30 pl-3 my-2 italic">
                            {children}
                          </blockquote>
                        ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}

            {/* Streaming message */}
            {isStreaming && streamingContent && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center shrink-0">
                  <Sparkles className="w-3.5 h-3.5 text-foreground animate-pulse" />
                </div>
                <div className="bg-muted px-4 py-3 rounded-xl max-w-[85%]">
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0 text-sm">{children}</p>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    }}
                  >
                    {streamingContent}
                  </ReactMarkdown>
                  <span className="inline-block w-2 h-4 bg-foreground/50 animate-pulse ml-0.5" />
                </div>
              </div>
            )}

            {/* Agent status indicator */}
            {agentStatus && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-amber-100 flex items-center justify-center shrink-0">
                  <Sparkles className="w-3.5 h-3.5 text-amber-600 animate-spin" />
                </div>
                <div className="bg-amber-50 text-amber-800 px-4 py-2 rounded-xl text-sm">
                  {agentStatus}
                </div>
              </div>
            )}

            {/* Loading indicator (when not streaming yet) */}
            {isLoading && !isStreaming && !streamingContent && !agentStatus && (
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-muted flex items-center justify-center shrink-0">
                  <Bot className="w-3.5 h-3.5 text-foreground" />
                </div>
                <div className="bg-muted px-4 py-3 rounded-xl">
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:0.15s]" />
                    <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:0.3s]" />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border">
        <form onSubmit={handleSend} className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="Describe your workflow..."
            disabled={isLoading}
            rows={1}
            className="flex-1 resize-none rounded-xl border border-border bg-muted/50 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50"
          />
          <Button
            type="submit"
            disabled={isLoading || isStreaming || !input.trim()}
            size="icon"
            className="h-11 w-11 rounded-xl shrink-0"
          >
            {isStreaming ? (
              <Sparkles className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </div>
  )
}
