import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

export type Database = {
  public: {
    tables: {
      users: {
        Row: {
          id: string
          email: string
          created_at: string
        }
      }
      projects: {
        Row: {
          id: string
          user_id: string
          name: string
          created_at: string
        }
      }
      workflows: {
        Row: {
          id: string
          project_id: string
          nodes: any
          edges: any
          version: number
          created_at: string
        }
      }
      chat_history: {
        Row: {
          id: string
          project_id: string
          role: string
          content: string
          created_at: string
        }
      }
      user_nodes: {
        Row: {
          id: string
          user_id: string
          name: string
          config: any
          is_community: boolean
          created_at: string
        }
      }
    }
  }
}
