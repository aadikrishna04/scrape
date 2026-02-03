'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { supabase } from '@/lib/supabase'
import { useRouter } from 'next/navigation'
import { Loader2, Check } from 'lucide-react'
import { toast } from 'sonner'

export default function AuthForm() {
  const [isLoading, setIsLoading] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [isValidEmail, setIsValidEmail] = useState(false)
  const router = useRouter()

  const validateEmail = (value: string) => {
    const isValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
    setIsValidEmail(isValid)
    setEmail(value)
  }

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
      toast.error('Login failed - no session')
    }
    setIsLoading(false)
  }

  const handleSignup = async () => {
    setIsLoading(true)
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) {
      toast.error(error.message)
    } else if (data.session) {
      toast.success('Account created! Welcome aboard.')
      await router.push('/dashboard')
      router.refresh()
    } else {
      toast.error('Signup succeeded but no session created.')
    }
    setIsLoading(false)
  }

  return (
    <Card className="w-full max-w-md shadow-xl border-0">
      <CardHeader className="text-center pb-2">
        <h2 className="text-2xl font-semibold text-foreground">Welcome</h2>
        <p className="text-muted-foreground text-sm">Build workflows with words</p>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="login" className="w-full">
          <TabsList className="grid w-full grid-cols-2 mb-6">
            <TabsTrigger value="login">Log In</TabsTrigger>
            <TabsTrigger value="signup">Sign Up</TabsTrigger>
          </TabsList>
          
          <TabsContent value="login" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="login-email">Email</Label>
              <div className="relative">
                <Input
                  id="login-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => validateEmail(e.target.value)}
                  className="pr-10"
                />
                {isValidEmail && <Check className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-green-500" />}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button 
              onClick={handleLogin} 
              disabled={isLoading || !isValidEmail || !password}
              className="w-full"
            >
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {isLoading ? 'Securing...' : 'Log In'}
            </Button>
          </TabsContent>

          <TabsContent value="signup" className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="signup-email">Email</Label>
              <div className="relative">
                <Input
                  id="signup-email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => validateEmail(e.target.value)}
                  className="pr-10"
                />
                {isValidEmail && <Check className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-green-500" />}
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="signup-password">Password</Label>
              <Input
                id="signup-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button 
              onClick={handleSignup} 
              disabled={isLoading || !isValidEmail || !password}
              className="w-full"
            >
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {isLoading ? 'Creating...' : 'Create account'}
            </Button>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
