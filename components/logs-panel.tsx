'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import {
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  ChevronRight,
  ChevronDown,
  Play,
  AlertCircle,
  Activity,
  FileText,
  Sparkles,
  AlertTriangle,
  Info,
  Shield,
  Zap,
  Bug,
  Database,
  Settings,
  RefreshCw
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { Button } from '@/components/ui/button'

interface Run {
  id: string
  name: string | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  start_time: string
  end_time: string | null
  metadata: Record<string, any>
  created_at: string
}

interface RunEvent {
  id: string
  run_id: string
  type: 'action' | 'reasoning' | 'node_start' | 'node_complete'
  payload: Record<string, any>
  timestamp: string
  step_number: number | null
}

interface RunDetail extends Run {
  events: RunEvent[]
}

interface AnalysisFinding {
  id?: string
  severity: 'low' | 'medium' | 'high'
  category: string
  description: string
  evidence: string[]
  created_at?: string
}

interface LogsPanelProps {
  projectId: string
}

export default function LogsPanel({ projectId }: LogsPanelProps) {
  const [runs, setRuns] = useState<Run[]>([])
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'analysis'>('timeline')
  const [isLoadingRuns, setIsLoadingRuns] = useState(true)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)
  const [page, setPage] = useState(1)
  const [totalRuns, setTotalRuns] = useState(0)
  const [runsError, setRunsError] = useState<string | null>(null)

  // Analysis state
  const [findings, setFindings] = useState<AnalysisFinding[]>([])
  const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set())

  useEffect(() => {
    loadRuns()
  }, [projectId, page])

  // Load analysis when tab changes or run is selected
  useEffect(() => {
    if (selectedRun && activeTab === 'analysis') {
      loadAnalysis(selectedRun.id)
    }
  }, [selectedRun, activeTab])

  const loadRuns = async () => {
    try {
      setIsLoadingRuns(true)
      setRunsError(null)
      const data = await api.runs.list(projectId, page)
      setRuns(data.runs ?? [])
      setTotalRuns(data.total ?? 0)
    } catch (error) {
      console.error('Failed to load runs:', error)
      setRuns([])
      setTotalRuns(0)
      setRunsError('Couldn\'t load runs. Make sure the backend is running and the runs migration is applied.')
    } finally {
      setIsLoadingRuns(false)
    }
  }

  const loadRunDetail = async (runId: string) => {
    try {
      setIsLoadingDetail(true)
      const data = await api.runs.get(runId)
      setSelectedRun(data)
      setFindings([]) // Reset findings when selecting a new run
    } catch (error) {
      console.error('Failed to load run detail:', error)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const loadAnalysis = async (runId: string) => {
    try {
      setIsLoadingAnalysis(true)
      const data = await api.runs.getAnalysis(runId)
      setFindings(data.findings ?? [])
    } catch (error) {
      console.error('Failed to load analysis:', error)
      setFindings([])
    } finally {
      setIsLoadingAnalysis(false)
    }
  }

  const triggerAnalysis = async () => {
    if (!selectedRun) return
    try {
      setIsAnalyzing(true)
      const data = await api.runs.analyze(selectedRun.id)
      setFindings(data.findings ?? [])
    } catch (error) {
      console.error('Failed to analyze run:', error)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleSelectRun = (run: Run) => {
    loadRunDetail(run.id)
  }

  const toggleFindingExpanded = (index: number) => {
    setExpandedFindings(prev => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  const getStatusIcon = (status: Run['status']) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-400" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />
      case 'pending':
        return <Clock className="w-4 h-4 text-muted-foreground" />
      default:
        return <Clock className="w-4 h-4 text-muted-foreground" />
    }
  }

  const getStatusBadge = (status: Run['status']) => {
    const baseClasses = "px-2 py-0.5 rounded-full text-xs font-medium"
    switch (status) {
      case 'running':
        return (
          <span className={cn(baseClasses, "bg-blue-500/20 text-blue-400")}>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-400 mr-1.5 animate-pulse" />
            Running
          </span>
        )
      case 'completed':
        return <span className={cn(baseClasses, "bg-green-500/20 text-green-400")}>Completed</span>
      case 'failed':
        return <span className={cn(baseClasses, "bg-red-500/20 text-red-400")}>Failed</span>
      case 'pending':
        return <span className={cn(baseClasses, "bg-gray-500/20 text-gray-400")}>Pending</span>
      default:
        return <span className={cn(baseClasses, "bg-gray-500/20 text-gray-400")}>{status}</span>
    }
  }

  const getEventIcon = (type: RunEvent['type']) => {
    switch (type) {
      case 'node_start':
        return <Play className="w-3.5 h-3.5 text-blue-400" />
      case 'node_complete':
        return <CheckCircle2 className="w-3.5 h-3.5 text-green-400" />
      case 'action':
        return <Activity className="w-3.5 h-3.5 text-accent" />
      case 'reasoning':
        return <FileText className="w-3.5 h-3.5 text-muted-foreground" />
      default:
        return <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
    }
  }

  const getSeverityConfig = (severity: AnalysisFinding['severity']) => {
    switch (severity) {
      case 'high':
        return {
          icon: <AlertCircle className="w-4 h-4" />,
          bgColor: 'bg-red-500/10',
          borderColor: 'border-red-500/30',
          textColor: 'text-red-400',
          badgeBg: 'bg-red-500/20',
          label: 'High'
        }
      case 'medium':
        return {
          icon: <AlertTriangle className="w-4 h-4" />,
          bgColor: 'bg-amber-500/10',
          borderColor: 'border-amber-500/30',
          textColor: 'text-amber-400',
          badgeBg: 'bg-amber-500/20',
          label: 'Medium'
        }
      case 'low':
      default:
        return {
          icon: <Info className="w-4 h-4" />,
          bgColor: 'bg-blue-500/10',
          borderColor: 'border-blue-500/30',
          textColor: 'text-blue-400',
          badgeBg: 'bg-blue-500/20',
          label: 'Low'
        }
    }
  }

  const getCategoryIcon = (category: string) => {
    const cat = category.toLowerCase()
    if (cat.includes('performance')) return <Zap className="w-3.5 h-3.5" />
    if (cat.includes('error')) return <Bug className="w-3.5 h-3.5" />
    if (cat.includes('security')) return <Shield className="w-3.5 h-3.5" />
    if (cat.includes('data')) return <Database className="w-3.5 h-3.5" />
    return <Settings className="w-3.5 h-3.5" />
  }

  const formatDuration = (start: string, end: string | null) => {
    if (!end) return 'In progress...'
    const startDate = new Date(start)
    const endDate = new Date(end)
    const diffMs = endDate.getTime() - startDate.getTime()
    if (diffMs < 1000) return `${diffMs}ms`
    if (diffMs < 60000) return `${(diffMs / 1000).toFixed(1)}s`
    return `${Math.floor(diffMs / 60000)}m ${Math.floor((diffMs % 60000) / 1000)}s`
  }

  // Count findings by severity
  const severityCounts = findings.reduce((acc, f) => {
    acc[f.severity] = (acc[f.severity] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="flex h-full">
      {/* Left Panel - Run List */}
      <div className="w-80 border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">Execution History</h2>
            <button
              onClick={loadRuns}
              disabled={isLoadingRuns}
              className="p-1.5 rounded-md hover:bg-muted transition-colors disabled:opacity-50"
              title="Refresh runs"
            >
              <RefreshCw className={cn("w-3.5 h-3.5 text-muted-foreground", isLoadingRuns && "animate-spin")} />
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            {totalRuns} total run{totalRuns !== 1 ? 's' : ''}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          {isLoadingRuns ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
            </div>
          ) : runs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <AlertCircle className="w-8 h-8 text-muted-foreground mb-3" />
              <p className="text-sm text-muted-foreground">
                {runsError ?? 'No runs yet'}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {runsError
                  ? 'Start the backend and apply the runs migration, then refresh.'
                  : 'Execute a workflow to see logs here'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {runs.map((run) => (
                <button
                  key={run.id}
                  onClick={() => handleSelectRun(run)}
                  className={cn(
                    "w-full px-4 py-3 text-left hover:bg-muted/50 transition-colors",
                    selectedRun?.id === run.id && "bg-muted"
                  )}
                >
                  <div className="flex items-start gap-3">
                    {getStatusIcon(run.status)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {run.name || `Run ${run.id.slice(0, 8)}`}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {formatDistanceToNow(new Date(run.start_time), { addSuffix: true })}
                      </p>
                      <div className="mt-1.5">
                        {getStatusBadge(run.status)}
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalRuns > 20 && (
          <div className="p-3 border-t border-border flex items-center justify-between">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-muted text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-xs text-muted-foreground">
              Page {page}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={runs.length < 20}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-muted text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Right Panel - Run Details */}
      <div className="flex-1 flex flex-col bg-background">
        {selectedRun ? (
          <>
            {/* Run Header */}
            <div className="p-4 border-b border-border">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-medium text-foreground">
                    {selectedRun.name || `Run ${selectedRun.id.slice(0, 8)}`}
                  </h2>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Started {formatDistanceToNow(new Date(selectedRun.start_time), { addSuffix: true })}
                    {selectedRun.end_time && (
                      <> · Duration: {formatDuration(selectedRun.start_time, selectedRun.end_time)}</>
                    )}
                  </p>
                </div>
                {getStatusBadge(selectedRun.status)}
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-border px-4">
              <button
                className={cn(
                  "px-4 py-2.5 text-sm font-medium transition-colors",
                  activeTab === "timeline"
                    ? "border-b-2 border-accent text-white"
                    : "text-muted-foreground hover:text-white"
                )}
                onClick={() => setActiveTab("timeline")}
              >
                Timeline
              </button>
              <button
                className={cn(
                  "px-4 py-2.5 text-sm font-medium transition-colors flex items-center gap-2",
                  activeTab === "analysis"
                    ? "border-b-2 border-accent text-white"
                    : "text-muted-foreground hover:text-white"
                )}
                onClick={() => setActiveTab("analysis")}
              >
                <Sparkles className="w-3.5 h-3.5" />
                Analysis
                {findings.length > 0 && (
                  <span className="px-1.5 py-0.5 text-xs rounded-full bg-accent/20 text-accent">
                    {findings.length}
                  </span>
                )}
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {isLoadingDetail ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
              ) : activeTab === 'timeline' ? (
                <div className="space-y-4">
                  {selectedRun.events.length === 0 ? (
                    <div className="text-center py-12">
                      <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">No events recorded</p>
                    </div>
                  ) : (
                    <div className="relative">
                      {/* Timeline line */}
                      <div className="absolute left-4 top-2 bottom-2 w-px bg-border" />

                      {selectedRun.events.map((event, index) => (
                        <div key={event.id} className="relative pl-10 pb-6 last:pb-0">
                          {/* Timeline dot */}
                          <div className="absolute left-2.5 w-3 h-3 rounded-full bg-card border-2 border-border flex items-center justify-center">
                            <div className={cn(
                              "w-1.5 h-1.5 rounded-full",
                              event.type === 'node_complete' ? "bg-green-400" :
                              event.type === 'node_start' ? "bg-blue-400" :
                              "bg-accent"
                            )} />
                          </div>

                          {/* Event card */}
                          <div className="bg-card rounded-lg border border-border p-3">
                            <div className="flex items-start gap-2">
                              {getEventIcon(event.type)}
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2">
                                  <p className="text-sm font-medium text-foreground">
                                    {event.type === 'node_start' ? 'Node Started' :
                                     event.type === 'node_complete' ? 'Node Completed' :
                                     event.type === 'action' ? 'Action Executed' :
                                     event.type === 'reasoning' ? 'Reasoning' :
                                     event.type}
                                  </p>
                                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                                    {new Date(event.timestamp).toLocaleTimeString()}
                                  </span>
                                </div>

                                {/* Event payload */}
                                {event.payload && Object.keys(event.payload).length > 0 && (
                                  <div className="mt-2 p-2 bg-muted/50 rounded text-xs font-mono text-muted-foreground overflow-x-auto">
                                    {event.payload.tool_name && (
                                      <p><span className="text-accent">Tool:</span> {event.payload.tool_name}</p>
                                    )}
                                    {event.payload.label && (
                                      <p><span className="text-accent">Label:</span> {event.payload.label}</p>
                                    )}
                                    {event.payload.node_id && (
                                      <p><span className="text-accent">Node:</span> {event.payload.node_id}</p>
                                    )}
                                    {event.payload.params && (
                                      <details className="mt-1">
                                        <summary className="cursor-pointer text-accent hover:underline">Parameters</summary>
                                        <pre className="mt-1 whitespace-pre-wrap">
                                          {JSON.stringify(event.payload.params, null, 2)}
                                        </pre>
                                      </details>
                                    )}
                                    {event.payload.result && (
                                      <details className="mt-1">
                                        <summary className="cursor-pointer text-accent hover:underline">Result</summary>
                                        <pre className="mt-1 whitespace-pre-wrap max-h-40 overflow-y-auto">
                                          {typeof event.payload.result === 'string'
                                            ? event.payload.result
                                            : JSON.stringify(event.payload.result, null, 2)}
                                        </pre>
                                      </details>
                                    )}
                                    {event.payload.error && (
                                      <p className="text-red-400 mt-1">
                                        <span className="font-semibold">Error:</span> {event.payload.error}
                                      </p>
                                    )}
                                    {event.payload.duration_ms && (
                                      <p className="mt-1">
                                        <span className="text-accent">Duration:</span> {event.payload.duration_ms}ms
                                      </p>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                /* Analysis Tab */
                <div className="space-y-4">
                  {/* Analysis Header */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-medium text-foreground">AI Analysis</h3>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Automated insights about this workflow execution
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={triggerAnalysis}
                      disabled={isAnalyzing || selectedRun.status === 'running'}
                      className="gap-2"
                    >
                      {isAnalyzing ? (
                        <>
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          Analyzing...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-3.5 h-3.5" />
                          {findings.length > 0 ? 'Re-analyze' : 'Run Analysis'}
                        </>
                      )}
                    </Button>
                  </div>

                  {/* Severity Summary */}
                  {findings.length > 0 && (
                    <div className="flex gap-3">
                      {severityCounts.high && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-red-500/10 border border-red-500/20">
                          <AlertCircle className="w-3.5 h-3.5 text-red-400" />
                          <span className="text-xs font-medium text-red-400">{severityCounts.high} High</span>
                        </div>
                      )}
                      {severityCounts.medium && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-500/10 border border-amber-500/20">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span className="text-xs font-medium text-amber-400">{severityCounts.medium} Medium</span>
                        </div>
                      )}
                      {severityCounts.low && (
                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-blue-500/10 border border-blue-500/20">
                          <Info className="w-3.5 h-3.5 text-blue-400" />
                          <span className="text-xs font-medium text-blue-400">{severityCounts.low} Low</span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Loading State */}
                  {isLoadingAnalysis && (
                    <div className="flex items-center justify-center py-12">
                      <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                    </div>
                  )}

                  {/* No Findings */}
                  {!isLoadingAnalysis && findings.length === 0 && (
                    <div className="text-center py-12 border border-dashed border-border rounded-lg">
                      <Sparkles className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                      <p className="text-sm font-medium text-foreground">No analysis yet</p>
                      <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
                        Click "Run Analysis" to generate AI-powered insights about this workflow execution
                      </p>
                    </div>
                  )}

                  {/* Findings List */}
                  {!isLoadingAnalysis && findings.length > 0 && (
                    <div className="space-y-3">
                      {findings.map((finding, index) => {
                        const config = getSeverityConfig(finding.severity)
                        const isExpanded = expandedFindings.has(index)

                        return (
                          <div
                            key={finding.id || index}
                            className={cn(
                              "rounded-lg border p-4 transition-colors",
                              config.bgColor,
                              config.borderColor
                            )}
                          >
                            <div className="flex items-start gap-3">
                              <div className={cn("mt-0.5", config.textColor)}>
                                {config.icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={cn(
                                    "px-2 py-0.5 rounded text-xs font-medium",
                                    config.badgeBg,
                                    config.textColor
                                  )}>
                                    {config.label}
                                  </span>
                                  <span className="flex items-center gap-1 px-2 py-0.5 rounded bg-muted/50 text-xs text-muted-foreground">
                                    {getCategoryIcon(finding.category)}
                                    {finding.category}
                                  </span>
                                </div>
                                <p className="text-sm text-foreground mt-2">
                                  {finding.description}
                                </p>

                                {/* Evidence */}
                                {finding.evidence && finding.evidence.length > 0 && (
                                  <div className="mt-3">
                                    <button
                                      onClick={() => toggleFindingExpanded(index)}
                                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                      {isExpanded ? (
                                        <ChevronDown className="w-3.5 h-3.5" />
                                      ) : (
                                        <ChevronRight className="w-3.5 h-3.5" />
                                      )}
                                      {finding.evidence.length} supporting detail{finding.evidence.length !== 1 ? 's' : ''}
                                    </button>

                                    {isExpanded && (
                                      <ul className="mt-2 space-y-1.5 pl-5">
                                        {finding.evidence.map((item, i) => (
                                          <li
                                            key={i}
                                            className="text-xs text-muted-foreground list-disc"
                                          >
                                            {item}
                                          </li>
                                        ))}
                                      </ul>
                                    )}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Activity className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-medium text-foreground">Select a run</p>
              <p className="text-sm text-muted-foreground mt-1">
                Choose a run from the list to view details
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
