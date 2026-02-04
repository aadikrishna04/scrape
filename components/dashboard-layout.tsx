'use client'

import { useState, useEffect } from 'react'
import { Plus, Folder, LogOut, Loader2, MoreHorizontal, Pencil, Trash2, Settings, Workflow, ChevronRight, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from '@/components/ui/dropdown-menu'
import { supabase } from '@/lib/supabase'
import { api } from '@/lib/api'
import { useRouter, usePathname } from 'next/navigation'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

interface Project {
  id: string
  name: string
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoadingProjects, setIsLoadingProjects] = useState(true)
  const [newProjectName, setNewProjectName] = useState('')
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [isCreating, setIsCreating] = useState(false)
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [projectToRename, setProjectToRename] = useState<Project | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [isRenaming, setIsRenaming] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

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
      toast.success(`Project created`)
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
      toast.success('Project renamed')
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
      if (pathname.includes(project.id)) {
        router.push('/dashboard')
      }
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

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const isProjectActive = (projectId: string) => pathname.includes(projectId)

  return (
    <div className="flex h-screen w-full bg-background">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card flex flex-col shrink-0">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-border">
          <button
            onClick={() => router.push('/dashboard')}
            className="flex items-center gap-3 hover:opacity-80 transition-opacity"
          >
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Workflow className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-logo text-lg text-foreground tracking-tight">Sentric</span>
          </button>
        </div>

        {/* Search & New Project */}
        <div className="p-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 bg-muted/50 border-0"
            />
          </div>

          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button className="w-full justify-start gap-2 h-9" variant="default">
                <Plus className="w-4 h-4" />
                New Project
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Create Project</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  placeholder="Project name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreateProject()}
                  className="h-11"
                  autoFocus
                />
                <div className="flex gap-3 justify-end">
                  <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateProject}
                    disabled={isCreating || !newProjectName.trim()}
                  >
                    {isCreating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      'Create'
                    )}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Projects List */}
        <div className="flex-1 overflow-y-auto px-3">
          <div className="py-2">
            <p className="px-2 mb-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Projects
            </p>

            {isLoadingProjects ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              </div>
            ) : filteredProjects.length === 0 ? (
              <p className="text-sm text-muted-foreground px-2 py-4">
                {searchQuery ? 'No matching projects' : 'No projects yet'}
              </p>
            ) : (
              <div className="space-y-1">
                {filteredProjects.map(project => (
                  <div
                    key={project.id}
                    className={cn(
                      "group flex items-center rounded-lg transition-colors",
                      isProjectActive(project.id)
                        ? "bg-muted"
                        : "hover:bg-muted/50"
                    )}
                  >
                    <button
                      onClick={() => router.push(`/dashboard/${project.id}`)}
                      className="flex-1 flex items-center gap-3 px-3 py-2.5 text-left min-w-0"
                    >
                      <Folder className={cn(
                        "w-4 h-4 shrink-0",
                        isProjectActive(project.id)
                          ? "text-foreground"
                          : "text-muted-foreground"
                      )} />
                      <span className={cn(
                        "text-sm truncate",
                        isProjectActive(project.id)
                          ? "font-medium text-foreground"
                          : "text-muted-foreground"
                      )}>
                        {project.name}
                      </span>
                    </button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button
                          className="p-1.5 mr-1 rounded opacity-0 group-hover:opacity-100 hover:bg-background transition-all"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem onClick={() => openRenameDialog(project)}>
                          <Pencil className="w-4 h-4 mr-2" />
                          Rename
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
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
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border space-y-1">
          <button
            onClick={() => router.push('/settings')}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors",
              pathname === '/settings'
                ? "bg-muted font-medium text-foreground"
                : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
            )}
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Log out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {children}
      </main>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Rename Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-4">
            <Input
              placeholder="Project name"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleRenameProject()}
              className="h-11"
              autoFocus
            />
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setRenameDialogOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleRenameProject}
                disabled={isRenaming || !renameValue.trim()}
              >
                {isRenaming ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save'
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
