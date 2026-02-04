"use client";

import DashboardLayout from "@/components/dashboard-layout";
import { Workflow, Zap, Globe, Brain, ArrowRight } from "lucide-react";

export default function DashboardPage() {
  return (
    <DashboardLayout>
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="max-w-lg text-center">
          <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-6">
            <Workflow className="w-7 h-7 text-foreground" />
          </div>

          <h1 className="text-2xl font-semibold text-foreground mb-3">
            Welcome to Sentric
          </h1>

          <p className="text-muted-foreground mb-10 leading-relaxed">
            Build automated workflows using natural language. Select a project
            from the sidebar or create a new one.
          </p>

          <div className="grid gap-4 text-left max-w-md mx-auto">
            <div className="flex items-start gap-4 p-4 rounded-xl bg-card border border-border">
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                <Zap className="w-5 h-5 text-foreground" />
              </div>
              <div>
                <h3 className="font-medium text-foreground mb-1">
                  Fast Scraping
                </h3>
                <p className="text-sm text-muted-foreground">
                  HTTP-based scraping for static sites. 10x faster than browser
                  automation.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-xl bg-card border border-border">
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                <Globe className="w-5 h-5 text-foreground" />
              </div>
              <div>
                <h3 className="font-medium text-foreground mb-1">
                  Browser Automation
                </h3>
                <p className="text-sm text-muted-foreground">
                  Full browser control for dynamic sites that require
                  JavaScript.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 rounded-xl bg-card border border-border">
              <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                <Brain className="w-5 h-5 text-foreground" />
              </div>
              <div>
                <h3 className="font-medium text-foreground mb-1">
                  AI Transform
                </h3>
                <p className="text-sm text-muted-foreground">
                  Process and transform data with AI. Summarize, analyze, or
                  format.
                </p>
              </div>
            </div>
          </div>

          <p className="mt-10 text-sm text-muted-foreground">
            Try: &quot;Scrape headlines from CNN and summarize them&quot;
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
