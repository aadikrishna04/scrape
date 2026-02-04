-- Track workflow executions
CREATE TABLE IF NOT EXISTS runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT,
  status TEXT DEFAULT 'pending', -- pending, running, completed, failed
  start_time TIMESTAMPTZ DEFAULT NOW(),
  end_time TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Track individual actions during execution
CREATE TABLE IF NOT EXISTS run_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
  type TEXT NOT NULL, -- action, reasoning, node_start, node_complete
  payload JSONB DEFAULT '{}',
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  step_number INTEGER
);
CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);

-- Analysis findings (for future LLM analysis)
CREATE TABLE IF NOT EXISTS analysis_findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
  severity TEXT, -- low, medium, high
  category TEXT,
  description TEXT,
  evidence JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
