'use client'

import DashboardLayout from '@/components/dashboard-layout'

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="flex-1 flex">
        {/* Chat Panel */}
        <div className="w-1/2 border-r border-border flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-foreground">Chat</h2>
          </div>
          <div className="flex-1 p-4 flex items-center justify-center">
            <div className="text-center text-muted-foreground">
              <p className="mb-2">Start a conversation to build your workflow</p>
              <p className="text-sm">Try: "Create a new project called Earnings Bot"</p>
            </div>
          </div>
          <div className="p-4 border-t border-border">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Type your message..."
                className="flex-1 px-4 py-2 rounded-md border border-input bg-background"
              />
              <button className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90">
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Graph Panel */}
        <div className="w-1/2 flex flex-col">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-foreground">Workflow</h2>
          </div>
          <div className="flex-1 flex items-center justify-center bg-muted/30">
            <div className="text-center text-muted-foreground">
              <p className="mb-2">Chat on the left to build!</p>
              <p className="text-sm">Your workflow will appear here</p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
