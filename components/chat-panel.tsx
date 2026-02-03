'use client'

import { useState, useEffect, useRef } from 'react'
import { Send, Bot, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

interface Message {
  role: 'user' | 'assistant'
  content: string
  created_at?: string
}

interface ChatPanelProps {
  projectId: string
  onWorkflowUpdate?: () => void
  version?: number
}

export default function ChatPanel({ projectId, onWorkflowUpdate, version }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

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
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      const response = await api.chat.send(projectId, userMessage)
      setMessages(prev => [...prev, { role: 'assistant', content: response.message }])
      
      if (response.workflow_update) {
        toast.success('Workflow updated')
        onWorkflowUpdate?.()
      }
    } catch (error) {
      toast.error('Failed to send message')
      // Remove user message on failure or show error state
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <h2 className="font-semibold text-foreground flex items-center gap-2">
          <Bot className="w-4 h-4" />
          Chat Assistant
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-center p-4">
            <Bot className="w-12 h-12 mb-4 opacity-20" />
            <p className="mb-2 font-medium">No messages yet</p>
            <p className="text-sm max-w-[240px]">
              Start by describing what you want to build, like "Create a workflow that summarizes news articles".
            </p>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                "flex w-full gap-2 items-start",
                msg.role === 'user' ? "flex-row-reverse" : "flex-row"
              )}
            >
              <div className={cn(
                "w-8 h-8 rounded-full flex items-center justify-center shrink-0",
                msg.role === 'user' ? "bg-primary text-primary-foreground" : "bg-muted"
              )}>
                {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>
              <div
                className={cn(
                  "px-4 py-2 rounded-lg max-w-[80%] text-sm",
                  msg.role === 'user' 
                    ? "bg-primary text-primary-foreground" 
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
                      li: ({ children }) => <li className="ml-1">{children}</li>,
                      h1: ({ children }) => <h1 className="text-base font-bold mb-2">{children}</h1>,
                      h2: ({ children }) => <h2 className="text-sm font-bold mb-2">{children}</h2>,
                      h3: ({ children }) => <h3 className="text-sm font-semibold mb-1">{children}</h3>,
                      code: ({ children }) => <code className="bg-background/50 px-1 py-0.5 rounded text-xs font-mono">{children}</code>,
                      pre: ({ children }) => <pre className="bg-background/50 p-2 rounded my-2 overflow-x-auto text-xs">{children}</pre>,
                      hr: () => <hr className="my-3 border-border" />,
                      blockquote: ({ children }) => <blockquote className="border-l-2 border-primary/50 pl-3 my-2 italic">{children}</blockquote>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="flex w-full gap-2 items-start">
             <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center shrink-0">
               <Bot className="w-4 h-4" />
             </div>
             <div className="bg-muted px-4 py-2 rounded-lg">
               <div className="flex gap-1">
                 <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce" />
                 <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:0.2s]" />
                 <div className="w-2 h-2 bg-foreground/30 rounded-full animate-bounce [animation-delay:0.4s]" />
               </div>
             </div>
          </div>
        )}
      </div>

      <div className="p-4 border-t border-border bg-background">
        <form onSubmit={handleSend} className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isLoading}
            className="flex-1"
          />
          <Button type="submit" disabled={isLoading || !input.trim()}>
            <Send className="w-4 h-4" />
            <span className="sr-only">Send</span>
          </Button>
        </form>
      </div>
    </div>
  )
}
