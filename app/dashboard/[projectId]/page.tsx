"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import ChatPanel from "@/components/chat-panel";
import WorkflowPanel from "@/components/workflow-panel";
import { useParams, useRouter } from "next/navigation";
import {
  ChevronLeft,
  Folder,
  Settings,
  PanelLeftClose,
  PanelLeft,
  Workflow,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.projectId as string;
  const [workflowVersion, setWorkflowVersion] = useState(0);
  const [chatVersion, setChatVersion] = useState(0);
  const [projectName, setProjectName] = useState("");
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [currentWorkflow, setCurrentWorkflow] = useState<{ nodes: any[]; edges: any[] } | null>(null);
  const workflowPanelRef = useRef<{ updateNodeStatus: (nodeId: string, status: string) => void; updateWorkflow: (nodes: any[], edges: any[]) => void } | null>(null);

  useEffect(() => {
    if (projectId === "settings") {
      router.replace("/settings");
    }
  }, [projectId, router]);

  useEffect(() => {
    if (projectId === "settings") return;
    loadProjectName();
  }, [projectId]);

  if (projectId === "settings") {
    return null;
  }

  const loadProjectName = async () => {
    try {
      const projects = await api.projects.list();
      const project = projects.find((p: any) => p.id === projectId);
      if (project) {
        setProjectName(project.name);
      }
    } catch (error) {
      console.error("Failed to load project name:", error);
    }
  };

  const handleWorkflowUpdate = useCallback((nodes?: any[], edges?: any[]) => {
    if (nodes && edges) {
      // Update from streaming - apply immediately to canvas
      setCurrentWorkflow({ nodes, edges });
      workflowPanelRef.current?.updateWorkflow(nodes, edges);
    }
    // Trigger version bump to refetch if needed
    setWorkflowVersion((v) => v + 1);
  }, []);

  const handleNodeStatusChange = useCallback((nodeId: string, status: 'executing' | 'success' | 'failed') => {
    workflowPanelRef.current?.updateNodeStatus(nodeId, status);
  }, []);

  const handleChatUpdate = useCallback(() => {
    setChatVersion((v) => v + 1);
  }, []);

  const handleWorkflowChange = useCallback((nodes: any[], edges: any[]) => {
    setCurrentWorkflow({ nodes, edges });
  }, []);

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
      <header className="h-14 border-b border-border bg-card flex items-center px-4 gap-3 shrink-0">
        {/* Back Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/dashboard")}
          className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
        >
          <ChevronLeft className="w-4 h-4" />
          <span className="hidden sm:inline">Back</span>
        </Button>

        <div className="h-5 w-px bg-border" />

        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-foreground flex items-center justify-center">
            <Workflow className="w-3.5 h-3.5 text-background" />
          </div>
          <span className="font-semibold text-foreground hidden sm:inline">PromptFlow</span>
        </div>

        {/* Project Name */}
        {projectName && (
          <>
            <div className="h-5 w-px bg-border" />
            <div className="flex items-center gap-2 text-foreground min-w-0">
              <Folder className="w-4 h-4 text-muted-foreground shrink-0" />
              <span className="font-medium truncate">{projectName}</span>
            </div>
          </>
        )}

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setChatCollapsed(!chatCollapsed)}
            className="gap-2 text-muted-foreground"
          >
            {chatCollapsed ? (
              <PanelLeft className="w-4 h-4" />
            ) : (
              <PanelLeftClose className="w-4 h-4" />
            )}
            <span className="hidden sm:inline">
              {chatCollapsed ? "Show Chat" : "Hide Chat"}
            </span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push("/settings")}
            className="gap-2 text-muted-foreground"
          >
            <Settings className="w-4 h-4" />
            <span className="hidden sm:inline">Settings</span>
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Chat Panel */}
        <div
          className={cn(
            "border-r border-border flex flex-col bg-card transition-all duration-300 ease-in-out overflow-hidden",
            chatCollapsed ? "w-0" : "w-full sm:w-[380px] lg:w-[420px]"
          )}
        >
          {!chatCollapsed && (
            <ChatPanel
              projectId={projectId}
              onWorkflowUpdate={handleWorkflowUpdate}
              onNodeStatusChange={handleNodeStatusChange}
              version={chatVersion}
              workflow={currentWorkflow}
            />
          )}
        </div>

        {/* Workflow Canvas */}
        <div className="flex-1 flex flex-col bg-muted/30 min-w-0 min-h-0">
          <div className="flex-1 min-h-0 h-full">
            <WorkflowPanel
              ref={workflowPanelRef}
              projectId={projectId}
              version={workflowVersion}
              onChatUpdate={handleChatUpdate}
              onWorkflowChange={handleWorkflowChange}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
