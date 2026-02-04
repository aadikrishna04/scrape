'use client'

import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import { Loader2, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export default function AuthForm() {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const router = useRouter()

  const handleLogin = async () => {
    setIsLoading(true)
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      toast.error(error.message)
    } else if (data.session) {
      toast.success('Welcome back!')
      await router.push('/dashboard')
      router.refresh()
    } else {
      toast.error('Login failed')
    }
    setIsLoading(false)
  }

  const handleSignup = async () => {
    setIsLoading(true)
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) {
      toast.error(error.message)
    } else if (data.session) {
      toast.success('Account created!')
      await router.push('/dashboard')
      router.refresh()
    } else {
      toast.error('Signup failed')
    }
    setIsLoading(false)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (mode === 'login') {
      handleLogin()
    } else {
      handleSignup()
    }
  }

  const isValid = email.includes('@') && password.length >= 6

  return (
    <Card className="border border-border shadow-sm">
      <CardContent className="p-8">
        {/* Tab Switcher */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg mb-8">
          <button
            type="button"
            onClick={() => setMode('login')}
            className={cn(
              "flex-1 py-2.5 text-sm font-medium rounded-md transition-all",
              mode === 'login'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Log In
          </button>
          <button
            type="button"
            onClick={() => setMode('signup')}
            className={cn(
              "flex-1 py-2.5 text-sm font-medium rounded-md transition-all",
              mode === 'signup'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-sm font-medium">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="h-11"
              autoComplete="email"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password" className="text-sm font-medium">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              placeholder="At least 6 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="h-11"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
          </div>

          <Button
            type="submit"
            disabled={isLoading || !isValid}
            className="w-full h-11 text-sm font-medium"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {mode === 'login' ? 'Signing in...' : 'Creating account...'}
              </>
            ) : (
              <>
                {mode === 'login' ? 'Sign in' : 'Create account'}
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-muted-foreground">
          {mode === 'login' ? (
            <>
              Don&apos;t have an account?{' '}
              <button
                type="button"
                onClick={() => setMode('signup')}
                className="text-foreground font-medium hover:underline"
              >
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                type="button"
                onClick={() => setMode('login')}
                className="text-foreground font-medium hover:underline"
              >
                Log in
              </button>
            </>
          )}
        </p>
      </CardContent>
    </Card>
  )
}
