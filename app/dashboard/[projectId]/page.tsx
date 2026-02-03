'use client'

import { useState, useEffect } from 'react'
import { ReactFlowProvider } from 'reactflow'
import ChatPanel from '@/components/chat-panel'
import WorkflowPanel from '@/components/workflow-panel'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Folder } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'

export default function ProjectPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.projectId as string
  const [workflowVersion, setWorkflowVersion] = useState(0)
  const [chatVersion, setChatVersion] = useState(0)
  const [projectName, setProjectName] = useState('')

  useEffect(() => {
    loadProjectName()
  }, [projectId])

  const loadProjectName = async () => {
    try {
      const projects = await api.projects.list()
      const project = projects.find((p: any) => p.id === projectId)
      if (project) {
        setProjectName(project.name)
      }
    } catch (error) {
      console.error('Failed to load project name:', error)
    }
  }

  const handleWorkflowUpdate = () => {
    setWorkflowVersion(v => v + 1)
  }

  const handleChatUpdate = () => {
    setChatVersion(v => v + 1)
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="h-14 border-b border-border bg-background flex items-center px-4 gap-4 shrink-0">
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={() => router.push('/dashboard')}
          className="gap-2"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Button>
        <div className="h-6 w-px bg-border" />
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-primary text-primary-foreground flex items-center justify-center text-xs">
            PF
          </div>
          <span className="font-semibold text-primary">PromptFlow</span>
        </div>
        {projectName && (
          <>
            <div className="h-6 w-px bg-border" />
            <div className="flex items-center gap-2 text-foreground">
              <Folder className="w-4 h-4 text-muted-foreground" />
              <span className="font-medium">{projectName}</span>
            </div>
          </>
        )}
      </header>
      <div className="flex-1 flex overflow-hidden">
        <div className="w-1/3 border-r border-border flex flex-col bg-background">
          <ChatPanel projectId={projectId} onWorkflowUpdate={handleWorkflowUpdate} version={chatVersion} />
        </div>
        <div className="w-2/3 flex flex-col bg-muted/5">
          <ReactFlowProvider>
            <WorkflowPanel projectId={projectId} version={workflowVersion} onChatUpdate={handleChatUpdate} />
          </ReactFlowProvider>
        </div>
      </div>
    </div>
  )
}
