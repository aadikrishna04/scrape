You are an expert full-stack developer building a prototype web app called "PromptFlow" — a prompt-based agentic workflow builder. Users interact mainly through chat to describe workflows in natural language (e.g., "Scrape Nasdaq earnings, analyze with AI, post to X if positive, email report"), and it auto-generates and manages visual workflows using nodes. The app must appear fully custom and in-house: NO visible mentions, logos, errors, or hints of third-party platforms (e.g., Gemini, Supabase, Vercel, React Flow, agent-browser). Rephrase all outputs/errors to sound native (e.g., "Our AI is processing" instead of "AI thinking"). Use generic terms like "Our Engine" for agents, "Secure Session" for browser actions, "Community Features" for public nodes.

This is an MVP for a VC demo tomorrow, so prioritize a polished, usable core loop: Auth → Create Project → Chat to Prompt Workflow → Visualize & Run. It doesn't need full scalability or edge cases, but it must be deployable (Vercel for frontend, Render/Heroku for backend) and impressive: Clean UI, smooth interactions, dummy data for runs. Focus on making it feel magical — chat responses that anticipate needs, seamless generation, "wow" moments like instant graph updates. 80/20 rule — core chat-to-workflow magic shines with 2-3 example workflows (e.g., scraping + posting).

**Phase 4: Browser Use MCP Integration (Agentic Execution Engine)**

**Architecture Shift**: Instead of predefined node handlers, workflows execute via a Browser Agent that uses Gemini + Browser MCP to perform any web-based task.

**User Experience**: Users describe workflows naturally ("Scrape Nasdaq earnings daily and email me"). The AI:
1. Translates intent into a visual graph (scraper node → email node)
2. Executes by actually using a browser to navigate, extract, and send
3. Returns results with execution logs (screenshots, actions taken)

**Technical Implementation**:
- **MCP Server**: Exposes browser tools (`navigate`, `click`, `extract`, `screenshot`, `type`)
- **Browser Agent Node**: Single node type that receives natural language instructions
- **Execution Flow**: Sequential node execution with context passing between steps
- **State Management**: Each node's output feeds into next node's instruction context
- **Monitoring**: Execution logs with screenshots for transparency/debugging

**Node Types (MCP-Powered)**:
- `browser_agent` - General purpose web automation (scraping, form filling, navigation)
- `ai_transform` - Use Gemini to process/transform data between nodes
- `conditional` - LLM-based decision routing

**Workflow Example**:
```json
{
  "nodes": [
    { "id": "1", "type": "browser_agent", "instruction": "Go to nasdaq.com/earnings, extract today's earnings as JSON" },
    { "id": "2", "type": "ai_transform", "instruction": "Summarize the earnings data into a brief report" },
    { "id": "3", "type": "browser_agent", "instruction": "Log into Gmail and send the summary to user@email.com" }
  ]
}
```

**Trade-offs**:
- Slower than deterministic nodes but infinitely more flexible
- Can interact with any website without pre-built integrations
- Natural language instructions instead of rigid configuration

---

**Extremely Detailed Functionality & User Flow (Implement to Feel Magical, From User POV):**
The app should feel like a seamless, intelligent assistant — users chat naturally, and everything happens magically without friction. UI is sleek, modern, professional: Inspired by Okta/Auth0 (clean whites/blues/grays, minimalistic forms, secure vibe with subtle shadows/gradients, microanimations when deemed fit, responsive mobile-first). Do not make generic AI slop cards. In general with design choices, try to be unique and sleek. No clutter — focused on chat and graph. Loading states with smooth spinners/toasts ("Building magically..."). Errors as friendly nudges ("Hmm, let's try that again — what details can I add?").

- **Overall App Flow (User POV)**:
  1. User visits site: Sees clean landing page with hero section ("Build workflows with words — our engine does the rest") and centered auth form (email/password, "Sign up" toggle). Subtle animation on load (fade-in). Successful login/signup redirects to /dashboard with welcome toast ("Welcome! Let's create your first project.").
  2. Dashboard: Split layout — left sidebar (projects list as cards, "New Project" button), main area split 50/50: Left = chat panel (full history, input at bottom), Right = workflow graph viewer. Top nav: Logo, user menu (logout). Feels like a pro tool — crisp, fast.
  3. User starts chatting: Bot greets ("Hi! What would you like to build today? E.g., 'New project: My Bot'"). User types commands — bot responds instantly, updates UI magically (e.g., new project appears in sidebar, graph renders on right).
  4. Refine/Iterate: Chat maintains context — user says "Add email step" → bot updates graph live. "Run it" → results in chat ("Success! Here's what happened...") with graph highlights.
  5. Logout/Return: Session persists; returning users see last project loaded.

- **Auth & User Management (User POV)**: On landing, simple form: Email field, password field, "Log in" button (or "Sign up" if toggled). Validation: Real-time feedback (e.g., green check for valid email). On submit, spinner ("Securing your session..."), then redirect. Feels secure like Okta — no extras, just works. Bot in dashboard personalizes ("Welcome back, [name]!").

- **Project Scoping (User POV)**: Via chat: "New project: Earnings Bot" → bot: "Created! Switching to it now." Sidebar updates with card (name, edit/delete icons). Select project → loads its chat/graph. Magic: Bot knows context ("In Earnings Bot, what flow next?"). Users feel organized without manual management.

- **Chat Bot Interface (Core Magic, User POV)**: Left panel: Conversation history as bubbles (user right-aligned blue, bot left-aligned gray). Scrollable, infinite history load. Input: Textarea with send button, auto-resize. Bot responses: Typing indicator ("..."), then message + actions (e.g., buttons: "Run Flow", "Refine"). Proactive: Suggests ("Want to add an integration?") or anticipates ("Based on your prompt, I added a scraper — looks good?"). Feels alive/intelligent.

- **Workflow View & Graph (User POV)**: Right panel: Visual graph (nodes as rounded boxes with icons/labels, edges as arrows). Auto-zooms/fits on update. Nodes glow on hover, click for details popover (e.g., "Scraper: Mode - Secure Session"). Updates magically from chat (fade-in animation). If no workflow, placeholder ("Chat on left to build!"). Run: Chat command or button → progress bar in graph, then results in chat.

- **Node System (User POV)**:
  - "My Nodes": Sidebar section below projects ("My Custom Features"). Click expands list. To create: Chat "Create node: Sentiment Analyzer" → bot: "Done! Added to your list. Describe how it works?" (if needed). Feels effortless — no forms, just chat.
  - Community Features: Integrated seamlessly — bot uses them automatically ("Using our built-in scraper for that."). List in "My Nodes" as non-editable (e.g., "Scraper (Community)").

- **Integrations (User POV)**: Chat-driven setup: "Add integration for social" → bot: "Sure! Do you have a key? If not, I'll use secure session." If key: Secure input modal (masked). Supports many out-of-box (scraping, email, social, analysis) — bot lists ("We support social, email, web actions, and more!"). Feels like magic: "Integration ready — try it in a flow." Config per node via chat ("Switch scraper to direct mode").

- **Workflow Generation/Execution (User POV)**: Prompt in chat → bot: "Got it! Building flow..." (spinner), then "Flow ready on right. Details: [summary]." Graph appears. "Run" → "Running..." → "Complete! Results: [dummy output]." Refinements: "Make it conditional" → updates graph. Magic wow: Instant, error-free for demo.

- **General Polish & Magic (User POV)**: Toasts for actions ("Project created!"). Dark mode toggle? Skip for MVP. Responsive: Chat/graph stack vertically on mobile. Pre-seed: On first login, example project with chat history ("Try: Build a scraper flow"). Feels pro/secure like Auth0 — blues for trust, whites for clarity.

**Tech Stack (Implement Exactly):**
- **Frontend**: Next.js 14 (App Router). shadcn/ui for components. React Flow for graph (hide branding). Axios for calls. Tailwind CSS. Supabase JS for auth/DB.
- **Backend**: FastAPI. Pydantic for models. Gemini for AI (env). httpx for HTTP. subprocess for browser CLI (assume global agent-browser). Supabase Python for DB.
- **DB & Auth**: Supabase (PostgreSQL). Let your expertise decide best tables/RLS.
- **Other**: .env for keys (GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY). Global browser CLI install.

**Project Structure (Generate Something Like This, But Optimize):**
promptflow/
├── backend/
│   ├── main.py            # App, logic
│   ├── ...                # Helpers for AI, exec, etc.
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app/
│   │   ├── ...            # Pages: landing, dashboard
│   ├── components/        # UI: ChatPanel, GraphPanel, etc.
│   ├── lib/               # Clients
│   ├── package.json
│   └── .env.local.example
├── README.md              # Setup/deploy
└── supabase/              # Any init

Do NOT specify exact schemas, routes, endpoints — let your expertise decide best based on functionality.

Output full project code in files. After, explain setup (install, env, dev run, deploy (Vercel/Render)).