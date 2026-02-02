'use client'

import { useState, useEffect } from 'react'
import { Sidebar, SidebarHeader, SidebarContent, SidebarFooter, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar'
import { Plus, Folder, LogOut, Loader2, MoreVertical, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'

interface Project {
  id: string
  name: string
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoadingProjects, setIsLoadingProjects] = useState(true)
  const [newProjectName, setNewProjectName] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [projectToRename, setProjectToRename] = useState<Project | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [isRenaming, setIsRenaming] = useState(false)

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = async () => {
    try {
      const data = await api.projects.list()
      setProjects(data)
    } catch (error) {
      console.error('Failed to load projects:', error)
    } finally {
      setIsLoadingProjects(false)
    }
  }

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push('/')
    router.refresh()
  }

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) return
    
    setIsCreating(true)
    try {
      const project = await api.projects.create(newProjectName.trim())
      setProjects(prev => [...prev, project])
      setNewProjectName('')
      setIsDialogOpen(false)
      toast.success(`Project "${project.name}" created!`)
      router.push(`/dashboard/${project.id}`)
    } catch (error) {
      toast.error('Failed to create project')
      console.error(error)
    } finally {
      setIsCreating(false)
    }
  }

  const handleRenameProject = async () => {
    if (!projectToRename || !renameValue.trim()) return
    
    setIsRenaming(true)
    try {
      await api.projects.rename(projectToRename.id, renameValue.trim())
      setProjects(prev => prev.map(p => 
        p.id === projectToRename.id ? { ...p, name: renameValue.trim() } : p
      ))
      setRenameDialogOpen(false)
      setProjectToRename(null)
      setRenameValue('')
      toast.success('Project renamed!')
    } catch (error) {
      toast.error('Failed to rename project')
      console.error(error)
    } finally {
      setIsRenaming(false)
    }
  }

  const handleDeleteProject = async (project: Project) => {
    if (!confirm(`Delete "${project.name}"? This cannot be undone.`)) return
    
    try {
      await api.projects.delete(project.id)
      setProjects(prev => prev.filter(p => p.id !== project.id))
      toast.success('Project deleted')
    } catch (error) {
      toast.error('Failed to delete project')
      console.error(error)
    }
  }

  const openRenameDialog = (project: Project) => {
    setProjectToRename(project)
    setRenameValue(project.name)
    setRenameDialogOpen(true)
  }

  return (
    <div className="flex h-screen w-full bg-background">
      <Sidebar className="w-64 border-r border-border bg-card">
        <SidebarHeader className="p-4 border-b border-border">
          <button 
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-2 font-bold text-xl text-primary hover:opacity-80 transition-opacity"
          >
            <div className="w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center">
              PF
            </div>
            PromptFlow
          </button>
        </SidebarHeader>
        <SidebarContent className="p-4 space-y-4">
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="w-full justify-start gap-2" variant="default">
                <Plus className="w-4 h-4" />
                New Project
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Project</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  placeholder="Project name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                />
                <Button 
                  onClick={handleCreateProject} 
                  disabled={isCreating || !newProjectName.trim()}
                  className="w-full"
                >
                  {isCreating ? 'Creating...' : 'Create Project'}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
          
          <div className="space-y-1">
            <h3 className="text-sm font-medium text-muted-foreground px-2 pb-2">Projects</h3>
            {isLoadingProjects ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : projects.length === 0 ? (
              <p className="text-sm text-muted-foreground px-2">No projects yet</p>
            ) : (
              <SidebarMenu>
                {projects.map(project => (
                  <SidebarMenuItem key={project.id} className="group">
                    <div className="flex items-center w-full">
                      <SidebarMenuButton 
                        onClick={() => router.push(`/dashboard/${project.id}`)}
                        className="flex-1"
                      >
                        <Folder className="w-4 h-4" />
                        <span className="truncate">{project.name}</span>
                      </SidebarMenuButton>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button 
                            className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-muted transition-opacity"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <MoreVertical className="w-4 h-4 text-muted-foreground" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          <DropdownMenuItem onClick={() => openRenameDialog(project)}>
                            <Pencil className="w-4 h-4 mr-2" />
                            Rename
                          </DropdownMenuItem>
                          <DropdownMenuItem 
                            onClick={() => handleDeleteProject(project)}
                            className="text-destructive focus:text-destructive"
                          >
                            <Trash2 className="w-4 h-4 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            )}
          </div>
        </SidebarContent>
        <SidebarFooter className="p-4 border-t border-border">
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={handleLogout}>
                <LogOut className="w-4 h-4" />
                <span>Log out</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {children}
      </main>

      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <Input
              placeholder="Project name"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRenameProject()}
            />
            <Button 
              onClick={handleRenameProject} 
              disabled={isRenaming || !renameValue.trim()}
              className="w-full"
            >
              {isRenaming ? 'Renaming...' : 'Rename'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
