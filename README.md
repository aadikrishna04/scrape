# Sentric

A natural language interface for building, visualizing, and executing automated workflows using AI agents and browser automation.

## Tech Stack

- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4, ReactFlow
- **Backend**: FastAPI, Python, Pydantic
- **Database & Auth**: Supabase (PostgreSQL + Auth)
- **AI**: Google Gemini 2.0 Flash
- **Browser Automation**: browser-use + Playwright

## Prerequisites

- Node.js 18+
- Python 3.9+
- Supabase account
- Google AI Studio API key (Gemini)

## Setup

### 1. Install dependencies

```bash
# Frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
cd ..
```

### 2. Environment variables

```bash
# Copy templates
cp env.example .env.local
cp backend/env.example backend/.env
```

Fill in:

- `NEXT_PUBLIC_SUPABASE_URL` - Your Supabase project URL
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` - Your Supabase anon key
- `SUPABASE_SERVICE_KEY` - Your Supabase service key (backend)
- `GEMINI_API_KEY` - From https://aistudio.google.com

### 3. Supabase setup

Create these tables in your Supabase project:

- `projects` (id, user_id, name, created_at)
- `workflows` (id, project_id, nodes, edges, version, created_at)
- `chat_history` (id, project_id, role, content, created_at)

## Running

**Terminal 1 - Frontend:**

```bash
npm run dev
# Runs on http://localhost:3000
```

**Terminal 2 - Backend:**

```bash
cd backend
python main.py
# Runs on http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Usage

1. Open http://localhost:3000
2. Sign up with email/password
3. Create a new project
4. Describe your workflow in natural language (e.g., "Scrape headlines from CNN")
5. View the generated workflow graph
6. Click "Run Workflow" to execute

## Project Structure

```
├── app/                    # Next.js App Router pages
├── components/             # React components
│   └── ui/                 # shadcn/ui components
├── lib/                    # Utilities & API clients
├── backend/
│   ├── main.py             # FastAPI app
│   ├── workflow_generator.py  # AI workflow generation
│   ├── browser_agent.py    # Browser automation
│   └── execution_engine.py # Workflow orchestration
└── public/                 # Static assets
```
