'use client'

import DashboardLayout from '@/components/dashboard-layout'
import { Sparkles } from 'lucide-react'

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="max-w-md text-center">
          <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-6">
            <Sparkles className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold text-foreground mb-2">
            Welcome to PromptFlow
          </h1>
          <p className="text-muted-foreground mb-6">
            Build powerful automated workflows using natural language. 
            Select a project from the sidebar or create a new one to get started.
          </p>
          <div className="text-sm text-muted-foreground/70">
            <p className="mb-1">💡 Try creating a workflow like:</p>
            <p className="italic">"Scrape headlines from CNN and summarize them"</p>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
