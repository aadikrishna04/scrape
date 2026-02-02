import { supabase } from '@/lib/supabase'

const API_URL = 'http://localhost:8000/api'

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`
  }
  return headers
}

export const api = {
  projects: {
    create: async (name: string, description?: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ name, description }),
      })
      if (!res.ok) throw new Error('Failed to create project')
      return res.json()
    },
    list: async () => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to list projects')
      return res.json()
    },
    delete: async (id: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/projects/${id}`, {
        method: 'DELETE',
        headers,
      })
      if (!res.ok) throw new Error('Failed to delete project')
      return res.json()
    },
  },
  chat: {
    send: async (projectId: string, message: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ project_id: projectId, message }),
      })
      if (!res.ok) throw new Error('Failed to send message')
      return res.json()
    },
    getHistory: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/chat/${projectId}`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to get chat history')
      return res.json()
    },
  },
  workflows: {
    get: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}`, {
        headers,
      })
      if (!res.ok) throw new Error('Failed to get workflow')
      return res.json()
    },
    update: async (projectId: string, workflow: { nodes: any[], edges: any[] }) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(workflow),
      })
      if (!res.ok) throw new Error('Failed to update workflow')
      return res.json()
    },
    execute: async (projectId: string) => {
      const headers = await getAuthHeader()
      const res = await fetch(`${API_URL}/workflows/${projectId}/execute`, {
        method: 'POST',
        headers,
      })
      if (!res.ok) throw new Error('Failed to execute workflow')
      return res.json()
    },
  },
}
