-- Per-user OAuth/integration tokens (e.g. GitHub).
-- Backend uses service role to read/write; RLS can restrict if needed.
CREATE TABLE IF NOT EXISTS public.user_integration_tokens (
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  expires_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_user_integration_tokens_user_id ON public.user_integration_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_user_integration_tokens_provider ON public.user_integration_tokens(provider);

COMMENT ON TABLE public.user_integration_tokens IS 'OAuth/integration tokens per user (e.g. GitHub). Used by backend only.';
