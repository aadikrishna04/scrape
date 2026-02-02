'use client'

import { useState } from 'react'
import { ReactFlowProvider } from 'reactflow'
import ChatPanel from '@/components/chat-panel'
import WorkflowPanel from '@/components/workflow-panel'
import { useParams } from 'next/navigation'

export default function ProjectPage() {
  const params = useParams()
  const projectId = params.projectId as string
  const [workflowVersion, setWorkflowVersion] = useState(0)

  const handleWorkflowUpdate = () => {
    setWorkflowVersion(v => v + 1)
  }

  return (
    <div className="flex-1 flex h-full">
      <div className="w-1/3 border-r border-border flex flex-col bg-background">
        <ChatPanel projectId={projectId} onWorkflowUpdate={handleWorkflowUpdate} />
      </div>
      <div className="w-2/3 flex flex-col bg-muted/5">
        <ReactFlowProvider>
          <WorkflowPanel projectId={projectId} version={workflowVersion} />
        </ReactFlowProvider>
      </div>
    </div>
  )
}
