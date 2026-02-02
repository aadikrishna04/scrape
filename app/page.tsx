import AuthForm from '@/components/auth-form'
import { Zap } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-white via-slate-50 to-blue-50">
      <div className="container mx-auto px-4 min-h-screen flex flex-col lg:flex-row items-center justify-center gap-12 py-12">
        {/* Hero Section */}
        <div className="flex-1 max-w-xl text-center lg:text-left animate-in fade-in slide-in-from-bottom-4 duration-700">
          <div className="flex items-center justify-center lg:justify-start gap-2 mb-6">
            <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
              <Zap className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-bold text-foreground">PromptFlow</span>
            <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-medium ml-2 border border-green-200">
              Hello
            </span>
          </div>
          
          <h1 className="text-4xl lg:text-5xl font-bold text-foreground leading-tight mb-6">
            Build workflows with words — <span className="text-primary">our engine does the rest</span>
          </h1>
          
          <p className="text-lg text-muted-foreground mb-8 leading-relaxed">
            Describe what you want in natural language. Watch as your ideas transform 
            into automated workflows. No coding required.
          </p>
          
          <div className="flex flex-wrap gap-4 justify-center lg:justify-start text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span>AI-powered</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span>Visual workflows</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-purple-500" />
              <span>Instant execution</span>
            </div>
          </div>
        </div>

        {/* Auth Section */}
        <div className="w-full max-w-md animate-in fade-in slide-in-from-bottom-8 duration-1000">
          <AuthForm />
          
          <p className="text-center text-xs text-muted-foreground mt-6">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  )
}
