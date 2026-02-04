import AuthForm from '@/components/auth-form'
import { Workflow, Sparkles, Zap, ArrowRight } from 'lucide-react'

export default function Home() {
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-primary flex items-center justify-center">
                <Workflow className="w-5 h-5 text-primary-foreground" />
              </div>
              <span className="font-logo text-xl tracking-tight">Sentric</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="min-h-[calc(100vh-4rem)] flex flex-col lg:flex-row items-center justify-center gap-12 lg:gap-24 py-12 lg:py-0">

            {/* Left - Hero */}
            <div className="flex-1 max-w-xl text-center lg:text-left">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted text-sm text-muted-foreground mb-8">
                <Sparkles className="w-4 h-4" />
                <span>AI-Powered Automation</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-foreground leading-[1.1] mb-6">
                Build workflows with natural language
              </h1>

              <p className="text-lg sm:text-xl text-muted-foreground mb-10 leading-relaxed max-w-lg mx-auto lg:mx-0">
                Describe what you want to automate. Watch as your ideas transform into powerful workflows.
              </p>

              <div className="flex flex-col sm:flex-row gap-6 justify-center lg:justify-start text-sm">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                    <Zap className="w-5 h-5 text-foreground" />
                  </div>
                  <div className="text-left">
                    <p className="font-medium text-foreground">Fast Execution</p>
                    <p className="text-muted-foreground">HTTP & browser automation</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                    <Workflow className="w-5 h-5 text-foreground" />
                  </div>
                  <div className="text-left">
                    <p className="font-medium text-foreground">Visual Editor</p>
                    <p className="text-muted-foreground">Drag and drop interface</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right - Auth */}
            <div className="w-full max-w-md">
              <AuthForm />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 right-0 py-4 text-center text-xs text-muted-foreground bg-background/80 backdrop-blur-sm border-t border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </div>
      </footer>
    </div>
  )
}
