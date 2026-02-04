"""
PromptFlow Backend - FastAPI Application
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import time
import httpx
import jwt
import json
import asyncio
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from sse_starlette.sse import EventSourceResponse

from execution_engine import execute_workflow as run_workflow_engine, execute_agentic
from workflow_generator import generate_workflow_response, validate_workflow
from mcp_manager import get_mcp_manager, initialize_mcp_manager, MCPServerConfig
from mcp_config import INTEGRATION_REQUIREMENTS
from langgraph_agent import LangGraphAgent, create_agent

_here = os.path.dirname(__file__)
_backend_env = os.path.join(_here, ".env")
_root_env_local = os.path.join(os.path.dirname(_here), ".env.local")

# Load backend env first, then optionally load root .env.local (without overriding existing vars)
load_dotenv(dotenv_path=_backend_env, override=False)
load_dotenv(dotenv_path=_root_env_local, override=False)

# OAuth state signing (use OAUTH_STATE_SECRET or fall back to service key)
OAUTH_STATE_SECRET = os.getenv("OAUTH_STATE_SECRET") or os.getenv("SUPABASE_SERVICE_KEY", "")
GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Google OAuth scopes for different services
GOOGLE_SCOPES = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ],
    "google-calendar": [
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.readonly",
    ],
    "google-drive": [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
}

# Supabase admin client (bypasses RLS)
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_service_key:
    raise ValueError(f"Missing Supabase credentials. URL: {supabase_url is not None}, Key: {supabase_service_key is not None}")

supabase_admin: Client = create_client(supabase_url, supabase_service_key)

# Regular client for user operations
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", supabase_service_key)
supabase: Client = create_client(supabase_url, supabase_anon_key)


def _get_integration_token_from_db(user_id: str, server_name: str) -> Optional[str]:
    """Resolve per-user integration token from DB (e.g. GitHub OAuth). Returns access_token or None."""
    try:
        result = supabase_admin.table("user_integration_tokens").select("access_token").eq("user_id", user_id).eq("provider", server_name).execute()
        if result.data and len(result.data) > 0:
            return result.data[0].get("access_token")
    except Exception:
        pass
    return None


def _update_integration_token_in_db(user_id: str, server_name: str, token_data: str) -> bool:
    """Update the integration token in DB after a refresh."""
    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("user_integration_tokens").upsert(
            {
                "user_id": user_id,
                "provider": server_name,
                "access_token": token_data,
                "updated_at": now,
            },
            on_conflict="user_id,provider",
        ).execute()
        print(f"[TokenUpdater] Updated token for {server_name}, user_id={user_id[:8]}...")
        return True
    except Exception as e:
        print(f"[TokenUpdater] Failed to update token: {e}")
        return False


async def _get_github_login_for_user(user_id: str) -> Optional[str]:
    """Return the GitHub username (login) for the given user if they have GitHub connected. Used to prefill owner in workflows."""
    token = _get_integration_token_from_db(user_id, "github")
    if not token:
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("login")
    except Exception:
        return None


def _inject_github_owner_into_workflow(workflow: Dict[str, Any], github_login: Optional[str]) -> None:
    """Mutate workflow nodes: for any github.* tool missing 'owner' in params, set owner to github_login.
    Injects into both node['data']['params'] and node['params'] so the executor gets owner either way."""
    if not github_login:
        return
    for node in workflow.get("nodes", []):
        data = node.get("data") or {}
        tool_name = (data.get("tool_name") or node.get("tool_name") or "")
        if not tool_name.startswith("github."):
            continue
        # Params may be in node["data"]["params"] or node["params"]; executor uses node.get("params", node.get("data", {}).get("params", {}))
        params = dict(node.get("params") or data.get("params") or {})
        if not params.get("owner") or not str(params.get("owner", "")).strip():
            params["owner"] = github_login
            data["params"] = params
            node["params"] = params


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup: Initialize MCP manager
    print("Initializing MCP Manager...")
    await initialize_mcp_manager()
    get_mcp_manager().set_integration_token_resolver(_get_integration_token_from_db)
    get_mcp_manager().set_integration_token_updater(_update_integration_token_in_db)
    print("MCP Manager initialized")
    yield
    # Shutdown: Clean up MCP connections
    print("Shutting down MCP Manager...")
    manager = get_mcp_manager()
    await manager.shutdown()
    print("MCP Manager shut down")


app = FastAPI(
    title="PromptFlow API",
    description="Backend API for PromptFlow - AI-powered workflow builder",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    project_id: str
    message: str

class ChatResponse(BaseModel):
    message: str
    workflow_update: Optional[Dict[str, Any]] = None


class StreamChatRequest(BaseModel):
    project_id: str
    message: str
    workflow: Optional[Dict[str, Any]] = None


class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    created_at: str


# MCP Request/Response Models
class MCPServerCreate(BaseModel):
    name: str
    display_name: str
    command: str
    args: List[str] = []
    env: Dict[str, str] = {}


class MCPConnectRequest(BaseModel):
    token: Optional[str] = None

class MCPToolResponse(BaseModel):
    name: str
    server_name: str
    display_name: str
    description: str
    input_schema: Dict[str, Any]
    category: Optional[str] = None

class MCPServerStatusResponse(BaseModel):
    name: str
    display_name: str
    connected: bool
    tool_count: int
    icon: Optional[str] = None
    error: Optional[str] = None

class NodeConfigUpdate(BaseModel):
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    prompt: Optional[str] = None
    label: Optional[str] = None
    instruction: Optional[str] = None


class AgenticExecuteRequest(BaseModel):
    goal: str

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "PromptFlow API"}

# Chat Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(chat_request: ChatRequest, request: Request):
    """Process chat message and return AI response with optional workflow update."""
    project_id = chat_request.project_id
    user_message = chat_request.message
    user_id = _get_user_id_from_request(request)

    # Store user message
    user_message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    supabase_admin.table("chat_history").insert({
        "id": user_message_id,
        "project_id": project_id,
        "role": "user",
        "content": user_message,
        "created_at": now
    }).execute()

    # Get chat history for context
    history_result = supabase_admin.table("chat_history").select("role, content").eq(
        "project_id", project_id
    ).order("created_at").execute()
    chat_history = [{"role": m["role"], "content": m["content"]} for m in history_result.data[:-1]]  # Exclude current message

    # Get current workflow for context
    workflow_result = supabase_admin.table("workflows").select("nodes, edges").eq(
        "project_id", project_id
    ).execute()
    current_workflow = None
    if workflow_result.data:
        current_workflow = {
            "nodes": workflow_result.data[0].get("nodes", []),
            "edges": workflow_result.data[0].get("edges", [])
        }

    # Get available tools (include per-user tools when authenticated)
    manager = get_mcp_manager()
    if user_id:
        # Connect all integrations the user has tokens for
        await manager.ensure_all_user_integrations_connected(user_id)
    available_tools = [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in manager.get_all_tools(user_id=user_id)
    ]

    # Generate response using Gemini
    try:
        response_text, workflow_update = await generate_workflow_response(
            user_message=user_message,
            chat_history=chat_history,
            current_workflow=current_workflow,
            available_tools=available_tools
        )

        # If workflow was generated/modified, inject user context (e.g. GitHub owner) and save
        if workflow_update:
            validated_workflow = validate_workflow(workflow_update)
            if user_id:
                github_login = await _get_github_login_for_user(user_id)
                _inject_github_owner_into_workflow(validated_workflow, github_login)

            existing = supabase_admin.table("workflows").select("id").eq(
                "project_id", project_id
            ).execute()
            workflow_data = {
                "project_id": project_id,
                "nodes": validated_workflow["nodes"],
                "edges": validated_workflow["edges"]
            }
            if existing.data:
                supabase_admin.table("workflows").update(workflow_data).eq(
                    "project_id", project_id
                ).execute()
            else:
                workflow_data["id"] = str(uuid.uuid4())
                workflow_data["created_at"] = datetime.now(timezone.utc).isoformat()
                supabase_admin.table("workflows").insert(workflow_data).execute()

    except Exception as e:
        print(f"Workflow generation error: {e}")
        response_text = "I'm having trouble processing that. Could you try rephrasing your request?"
        workflow_update = None

    # Store assistant message
    assistant_message_id = str(uuid.uuid4())
    supabase_admin.table("chat_history").insert({
        "id": assistant_message_id,
        "project_id": project_id,
        "role": "assistant",
        "content": response_text,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    return ChatResponse(
        message=response_text,
        workflow_update=workflow_update
    )

def _validate_project_id(project_id: str) -> None:
    """Raise 404 if project_id is not a valid UUID (e.g. 'settings' from /dashboard/settings)."""
    try:
        uuid.UUID(project_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Project not found")

@app.get("/api/chat/{project_id}")
async def get_chat_history(project_id: str):
    """Get chat history for a project."""
    _validate_project_id(project_id)
    result = supabase_admin.table("chat_history").select("*").eq("project_id", project_id).order("created_at").execute()
    return {"messages": [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in result.data]}


@app.post("/api/chat/stream")
async def stream_chat(chat_request: StreamChatRequest, request: Request):
    """
    Stream chat responses using Server-Sent Events (SSE).

    Event types:
    - agent_thinking: Streaming text from agent
    - workflow_update: Nodes/edges changed
    - node_status_change: Node execution status changed
    - step_started: Tool execution started
    - step_completed: Tool execution completed
    - plan_created: Execution plan created
    - execution_complete: Workflow execution finished
    - error: An error occurred
    - done: Stream completed
    """
    project_id = chat_request.project_id
    user_message = chat_request.message
    workflow = chat_request.workflow
    user_id = _get_user_id_from_request(request)

    _validate_project_id(project_id)

    async def event_generator():
        """Generate SSE events from the LangGraph agent."""
        event_queue = asyncio.Queue()

        async def streaming_callback(event_type: str, data: Any):
            """Callback for agent events."""
            await event_queue.put({"type": event_type, "data": data})

        try:
            # Store user message
            user_message_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            supabase_admin.table("chat_history").insert({
                "id": user_message_id,
                "project_id": project_id,
                "role": "user",
                "content": user_message,
                "created_at": now
            }).execute()

            # Get MCP manager and create agent
            manager = get_mcp_manager()
            if user_id:
                # Connect all integrations the user has tokens for
                await manager.ensure_all_user_integrations_connected(user_id)

            agent = await create_agent(manager, user_id)

            # Get current workflow nodes/edges
            workflow_nodes = []
            workflow_edges = []
            if workflow:
                workflow_nodes = workflow.get("nodes", [])
                workflow_edges = workflow.get("edges", [])
            else:
                workflow_result = supabase_admin.table("workflows").select("nodes, edges").eq(
                    "project_id", project_id
                ).execute()
                if workflow_result.data:
                    workflow_nodes = workflow_result.data[0].get("nodes", [])
                    workflow_edges = workflow_result.data[0].get("edges", [])

            # Run agent in background task
            async def run_agent():
                try:
                    result = await agent.run(
                        message=user_message,
                        project_id=project_id,
                        workflow_nodes=workflow_nodes,
                        workflow_edges=workflow_edges,
                        streaming_callback=streaming_callback,
                    )

                    # If workflow was updated, save to database
                    if result.get("workflow_nodes"):
                        validated_workflow = {
                            "nodes": result["workflow_nodes"],
                            "edges": result.get("workflow_edges", [])
                        }
                        if user_id:
                            github_login = await _get_github_login_for_user(user_id)
                            _inject_github_owner_into_workflow(validated_workflow, github_login)

                        existing = supabase_admin.table("workflows").select("id").eq(
                            "project_id", project_id
                        ).execute()
                        workflow_data = {
                            "project_id": project_id,
                            "nodes": validated_workflow["nodes"],
                            "edges": validated_workflow["edges"]
                        }
                        if existing.data:
                            supabase_admin.table("workflows").update(workflow_data).eq(
                                "project_id", project_id
                            ).execute()
                        else:
                            workflow_data["id"] = str(uuid.uuid4())
                            workflow_data["created_at"] = datetime.now(timezone.utc).isoformat()
                            supabase_admin.table("workflows").insert(workflow_data).execute()

                    # Store assistant message
                    if result.get("message"):
                        assistant_message_id = str(uuid.uuid4())
                        supabase_admin.table("chat_history").insert({
                            "id": assistant_message_id,
                            "project_id": project_id,
                            "role": "assistant",
                            "content": result["message"],
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).execute()

                    await event_queue.put({"type": "done", "data": result})
                except Exception as e:
                    await event_queue.put({"type": "error", "data": str(e)})

            # Start agent task
            agent_task = asyncio.create_task(run_agent())

            # Yield events as they come in
            full_message = ""
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=60.0)
                    event_type = event["type"]
                    event_data = event["data"]

                    if event_type == "agent_thinking":
                        full_message += event_data
                        yield {
                            "event": event_type,
                            "data": json.dumps({"content": event_data})
                        }
                    elif event_type == "workflow_update":
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data)
                        }
                    elif event_type == "node_status_change":
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data)
                        }
                    elif event_type == "step_started":
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data)
                        }
                    elif event_type == "step_completed":
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data)
                        }
                    elif event_type == "plan_created":
                        yield {
                            "event": event_type,
                            "data": json.dumps({"steps": event_data})
                        }
                    elif event_type == "execution_complete":
                        yield {
                            "event": event_type,
                            "data": json.dumps(event_data)
                        }
                    elif event_type == "error":
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": event_data})
                        }
                        break
                    elif event_type == "done":
                        yield {
                            "event": "done",
                            "data": json.dumps({
                                "message": event_data.get("message", ""),
                                "workflow_update": {
                                    "nodes": event_data.get("workflow_nodes", []),
                                    "edges": event_data.get("workflow_edges", []),
                                } if event_data.get("workflow_nodes") else None
                            })
                        }
                        break

                except asyncio.TimeoutError:
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": "Request timed out"})
                    }
                    break

            # Ensure agent task is complete
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())

# Project Endpoints
@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(project: ProjectCreate, request: Request):
    """Create a new project."""
    auth_header = request.headers.get("authorization")
    user_id = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            user = supabase.auth.get_user(token)
            user_id = user.user.id
        except Exception as e:
            print(f"Auth error: {e}")
            pass
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    
    # Ensure user exists in public.users (FK from projects.user_id)
    user_email = getattr(user.user, "email", None) or ""
    existing = supabase_admin.table("users").select("id").eq("id", user_id).execute()
    if not existing.data:
        now_user = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("users").insert(
            {"id": user_id, "email": user_email, "created_at": now_user}
        ).execute()
    
    project_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    data = {
        "id": project_id,
        "name": project.name,
        "user_id": user_id,
        "created_at": now
    }
    
    try:
        result = supabase_admin.table("projects").insert(data).execute()
        return ProjectResponse(
            id=project_id,
            name=project.name,
            created_at=now
        )
    except Exception as e:
        print(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(request: Request):
    """List all projects for the current user."""
    auth_header = request.headers.get("authorization")
    user_id = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        try:
            user = supabase.auth.get_user(token)
            user_id = user.user.id
        except:
            pass
    
    if user_id:
        result = supabase_admin.table("projects").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    else:
        result = supabase_admin.table("projects").select("*").order("created_at", desc=True).execute()
    
    return [ProjectResponse(id=p["id"], name=p["name"], created_at=p["created_at"]) for p in result.data]

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    """Delete a project."""
    supabase_admin.table("projects").delete().eq("id", project_id).execute()
    supabase_admin.table("chat_history").delete().eq("project_id", project_id).execute()
    supabase_admin.table("workflows").delete().eq("project_id", project_id).execute()
    return {"success": True}

class ProjectRename(BaseModel):
    name: str

@app.patch("/api/projects/{project_id}")
async def rename_project(project_id: str, data: ProjectRename, request: Request):
    """Rename a project."""
    supabase_admin.table("projects").update({"name": data.name}).eq("id", project_id).execute()
    return {"success": True, "name": data.name}


def _get_user_id_from_request(request: Request) -> Optional[str]:
    """Extract user_id from Authorization Bearer JWT. Returns None if missing or invalid."""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.replace("Bearer ", "")
    try:
        user = supabase.auth.get_user(token)
        return user.user.id
    except Exception:
        return None


def _create_oauth_state(user_id: str) -> str:
    """Create signed state for OAuth callback (expires in 10 min)."""
    if not OAUTH_STATE_SECRET:
        raise ValueError("OAUTH_STATE_SECRET or SUPABASE_SERVICE_KEY required for OAuth state")
    payload = {"user_id": user_id, "exp": int(time.time()) + 600}
    return jwt.encode(payload, OAUTH_STATE_SECRET, algorithm="HS256")


def _verify_oauth_state(state: str) -> Optional[str]:
    """Verify state and return user_id, or None if invalid/expired."""
    if not OAUTH_STATE_SECRET or not state:
        return None
    try:
        payload = jwt.decode(state, OAUTH_STATE_SECRET, algorithms=["HS256"])
        return payload.get("user_id")
    except Exception:
        return None


# GitHub OAuth / Integrations
# Requires an OAuth App (not a GitHub App): https://github.com/settings/developers → OAuth Apps
@app.get("/api/integrations/github/oauth/start")
async def github_oauth_start(request: Request):
    """Return GitHub authorize URL for the frontend to redirect to. Requires auth (Authorization header)."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    if not GITHUB_OAUTH_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured (GITHUB_OAUTH_CLIENT_ID).")
    state = _create_oauth_state(user_id)
    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/integrations/github/oauth/callback"
    auth_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_OAUTH_CLIENT_ID}"
        f"&redirect_uri={callback_url}"
        "&scope=repo,read:user,read:org,workflow"
        f"&state={state}"
    )
    return {"url": auth_url}


@app.get("/api/integrations/github/oauth/callback")
async def github_oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None):
    """Exchange code for token, store per user, redirect to frontend."""
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    user_id = _verify_oauth_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if not GITHUB_OAUTH_CLIENT_ID or not GITHUB_OAUTH_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured.")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/integrations/github/oauth/callback"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_OAUTH_CLIENT_ID,
                    "client_secret": GITHUB_OAUTH_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
        data = resp.json()

        if data.get("error"):
            err_msg = data.get("error_description", data.get("error", "Unknown GitHub error"))
            raise HTTPException(status_code=400, detail=f"GitHub: {err_msg}")

        access_token = data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="GitHub did not return an access token")

        now = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("user_integration_tokens").upsert(
            {
                "user_id": user_id,
                "provider": "github",
                "access_token": access_token,
                "updated_at": now,
            },
            on_conflict="user_id,provider",
        ).execute()
    except HTTPException:
        raise
    except Exception as e:
        print(f"GitHub OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    redirect_to = f"{FRONTEND_URL.rstrip('/')}/dashboard/settings?github=connected"
    return RedirectResponse(url=redirect_to, status_code=302)


@app.get("/api/integrations/github/status")
async def github_integration_status(request: Request):
    """Return whether the current user has GitHub connected."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    result = supabase_admin.table("user_integration_tokens").select("user_id").eq("user_id", user_id).eq("provider", "github").execute()
    connected = bool(result.data)
    return {"connected": connected}


@app.get("/api/integrations/github/me")
async def github_me(request: Request):
    """Return the connected GitHub user's login (username) for pre-filling 'owner' in repo tools."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    result = supabase_admin.table("user_integration_tokens").select("access_token").eq("user_id", user_id).eq("provider", "github").execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="GitHub not connected. Connect GitHub in Settings.")
    token = result.data[0].get("access_token")
    if not token:
        raise HTTPException(status_code=404, detail="GitHub token missing.")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"},
            )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub API error")
        data = resp.json()
        login = data.get("login")
        if not login:
            raise HTTPException(status_code=502, detail="GitHub did not return login")
        return {"login": login}
    except HTTPException:
        raise
    except Exception as e:
        print(f"GitHub /user error: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user")


@app.delete("/api/integrations/github")
async def github_integration_disconnect(request: Request):
    """Remove GitHub token for current user and disconnect MCP if connected."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    supabase_admin.table("user_integration_tokens").delete().eq("user_id", user_id).eq("provider", "github").execute()
    manager = get_mcp_manager()
    await manager.disconnect_server_for_user("github", user_id)
    return {"success": True}


# ============================================
# Google OAuth Endpoints (Gmail, Calendar, Drive)
# ============================================

@app.get("/api/integrations/google/oauth/start")
async def google_oauth_start(request: Request, service: str = "gmail"):
    """
    Start Google OAuth flow for Gmail, Calendar, or Drive.
    Query param 'service' can be: gmail, google-calendar, google-drive
    """
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
        )

    # Normalize service name
    if service not in GOOGLE_SCOPES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Use: {', '.join(GOOGLE_SCOPES.keys())}")

    # Create state with service info
    state_payload = {"user_id": user_id, "service": service, "exp": int(time.time()) + 600}
    state = jwt.encode(state_payload, OAUTH_STATE_SECRET, algorithm="HS256")

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/integrations/google/oauth/callback"

    # Build Google OAuth URL
    scopes = GOOGLE_SCOPES[service]
    scope_string = " ".join(scopes)

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={callback_url}"
        "&response_type=code"
        f"&scope={scope_string}"
        "&access_type=offline"
        "&prompt=consent"
        f"&state={state}"
    )

    return {"url": auth_url, "service": service}


@app.get("/api/integrations/google/oauth/callback")
async def google_oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    """Exchange Google OAuth code for tokens, store per user, redirect to frontend."""
    if error:
        redirect_to = f"{FRONTEND_URL.rstrip('/')}/settings?google_error={error}"
        return RedirectResponse(url=redirect_to, status_code=302)

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    # Verify state and extract user_id and service
    try:
        payload = jwt.decode(state, OAUTH_STATE_SECRET, algorithms=["HS256"])
        user_id = payload.get("user_id")
        service = payload.get("service", "gmail")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid state: missing user_id")

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Google OAuth not configured.")

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/integrations/google/oauth/callback"

    try:
        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
        data = resp.json()

        if "error" in data:
            err_msg = data.get("error_description", data.get("error", "Unknown Google error"))
            raise HTTPException(status_code=400, detail=f"Google: {err_msg}")

        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")

        if not access_token:
            raise HTTPException(status_code=502, detail="Google did not return an access token")

        # Store both access and refresh tokens
        # For simplicity, we store them as JSON in the access_token field
        token_data = json.dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": data.get("expires_in"),
        })

        now = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("user_integration_tokens").upsert(
            {
                "user_id": user_id,
                "provider": service,
                "access_token": token_data,
                "updated_at": now,
            },
            on_conflict="user_id,provider",
        ).execute()

    except HTTPException:
        raise
    except Exception as e:
        print(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    redirect_to = f"{FRONTEND_URL.rstrip('/')}/settings?google={service}&connected=true"
    return RedirectResponse(url=redirect_to, status_code=302)


@app.get("/api/integrations/google/{service}/status")
async def google_integration_status(service: str, request: Request):
    """Return whether the current user has a Google service connected."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if service not in GOOGLE_SCOPES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Use: {', '.join(GOOGLE_SCOPES.keys())}")

    result = supabase_admin.table("user_integration_tokens").select("user_id").eq("user_id", user_id).eq("provider", service).execute()
    connected = bool(result.data)
    return {"connected": connected, "service": service}


@app.delete("/api/integrations/google/{service}")
async def google_integration_disconnect(service: str, request: Request):
    """Remove Google service token for current user."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if service not in GOOGLE_SCOPES:
        raise HTTPException(status_code=400, detail=f"Invalid service. Use: {', '.join(GOOGLE_SCOPES.keys())}")

    supabase_admin.table("user_integration_tokens").delete().eq("user_id", user_id).eq("provider", service).execute()

    manager = get_mcp_manager()
    await manager.disconnect_server_for_user(service, user_id)

    return {"success": True, "service": service}


# ============================================
# Generic Integration Endpoints (for all MCP servers)
# ============================================

class IntegrationConnectRequest(BaseModel):
    """Request to connect an integration with a token."""
    token: str


@app.get("/api/integrations")
async def list_all_integrations(request: Request):
    """List all available integrations and their connection status for the current user."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    manager = get_mcp_manager()

    # Get all user's connected integrations from DB
    tokens_result = supabase_admin.table("user_integration_tokens").select("provider").eq("user_id", user_id).execute()
    connected_providers = {row["provider"] for row in tokens_result.data}

    # Google services that are internal but need OAuth
    GOOGLE_OAUTH_SERVICES = {"gmail", "google-calendar", "google-drive"}

    integrations = []
    for name, config in manager.configs.items():
        # Get auth requirements
        req = INTEGRATION_REQUIREMENTS.get(name)

        # Handle internal servers
        if config.command == "internal":
            # Google services are internal but need OAuth
            if name in GOOGLE_OAUTH_SERVICES:
                integrations.append({
                    "name": name,
                    "display_name": config.display_name,
                    "connected": name in connected_providers,
                    "auth_type": "oauth",
                    "icon": config.icon,
                    "help_url": req.help_url if req else None,
                    "description": req.description if req else None,
                })
            else:
                # Other internal tools (browser, scrape, ai) - always available
                integrations.append({
                    "name": name,
                    "display_name": config.display_name,
                    "connected": True,
                    "auth_type": "none",
                    "icon": config.icon,
                })
            continue

        # External MCP servers
        auth_type = req.type if req else "none"

        integrations.append({
            "name": name,
            "display_name": config.display_name,
            "connected": name in connected_providers,
            "auth_type": auth_type,
            "icon": config.icon,
            "help_url": req.help_url if req else None,
            "description": req.description if req else None,
        })

    return {"integrations": integrations}


@app.get("/api/integrations/{provider}/status")
async def get_integration_status(provider: str, request: Request):
    """Check if a specific integration is connected for the current user."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    manager = get_mcp_manager()

    # Check if provider exists
    if provider not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Integration '{provider}' not found")

    config = manager.configs[provider]

    # Internal servers are always connected
    if config.command == "internal":
        return {"connected": True, "provider": provider}

    # Check DB for user token
    result = supabase_admin.table("user_integration_tokens").select("user_id").eq("user_id", user_id).eq("provider", provider).execute()
    connected = bool(result.data)

    return {"connected": connected, "provider": provider}


async def _validate_integration_token(provider: str, token: str) -> dict:
    """
    Validate a token by making a test API call.
    Returns {"valid": True/False, "error": "message if invalid", "info": "optional info"}
    """
    req = INTEGRATION_REQUIREMENTS.get(provider)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == "slack":
                # Slack: auth.test endpoint
                resp = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = resp.json()
                if data.get("ok"):
                    return {"valid": True, "info": f"Connected as @{data.get('user', 'unknown')} in {data.get('team', 'unknown')}"}
                return {"valid": False, "error": data.get("error", "Invalid token")}

            elif provider == "notion":
                # Notion: get current user
                resp = await client.get(
                    "https://api.notion.com/v1/users/me",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Notion-Version": "2022-06-28"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "info": f"Connected as {data.get('name', 'unknown')}"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid token. Make sure it starts with 'secret_'"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "linear":
                # Linear: GraphQL query for viewer
                resp = await client.post(
                    "https://api.linear.app/graphql",
                    headers={"Authorization": token},
                    json={"query": "{ viewer { id name email } }"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "errors" not in data:
                        viewer = data.get("data", {}).get("viewer", {})
                        return {"valid": True, "info": f"Connected as {viewer.get('name', 'unknown')}"}
                    return {"valid": False, "error": data["errors"][0].get("message", "Invalid token")}
                return {"valid": False, "error": "Invalid token"}

            elif provider == "airtable":
                # Airtable: whoami endpoint
                resp = await client.get(
                    "https://api.airtable.com/v0/meta/whoami",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "info": f"Connected as {data.get('email', 'unknown')}"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid token"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "stripe":
                # Stripe: get balance (simplest authenticated endpoint)
                resp = await client.get(
                    "https://api.stripe.com/v1/balance",
                    auth=(token, "")
                )
                if resp.status_code == 200:
                    return {"valid": True, "info": "Connected to Stripe"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid API key"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "discord":
                # Discord: get current user
                resp = await client.get(
                    "https://discord.com/api/v10/users/@me",
                    headers={"Authorization": f"Bot {token}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "info": f"Connected as {data.get('username', 'unknown')}#{data.get('discriminator', '0000')}"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid bot token"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "vercel":
                # Vercel: get current user
                resp = await client.get(
                    "https://api.vercel.com/v2/user",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "info": f"Connected as {data.get('user', {}).get('username', 'unknown')}"}
                elif resp.status_code in [401, 403]:
                    return {"valid": False, "error": "Invalid token"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "trello":
                # Trello: expects api_key:token format
                if ":" not in token:
                    return {"valid": False, "error": "Please use format: api_key:token"}
                api_key, user_token = token.split(":", 1)
                resp = await client.get(
                    f"https://api.trello.com/1/members/me?key={api_key}&token={user_token}"
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"valid": True, "info": f"Connected as {data.get('fullName', 'unknown')}"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid API key or token"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "sendgrid":
                # SendGrid: no simple validation endpoint, check format
                if not token.startswith("SG."):
                    return {"valid": False, "error": "SendGrid API keys start with 'SG.'"}
                return {"valid": True, "info": "Token format looks valid (will verify on first use)"}

            elif provider == "twilio":
                # Twilio: expects account_sid:auth_token format
                if ":" not in token:
                    return {"valid": False, "error": "Please use format: account_sid:auth_token"}
                account_sid, auth_token = token.split(":", 1)
                if not account_sid.startswith("AC"):
                    return {"valid": False, "error": "Account SID should start with 'AC'"}
                resp = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}.json",
                    auth=(account_sid, auth_token)
                )
                if resp.status_code == 200:
                    return {"valid": True, "info": f"Connected to Twilio account {account_sid}"}
                elif resp.status_code == 401:
                    return {"valid": False, "error": "Invalid Account SID or Auth Token"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            elif provider == "jira":
                # Jira: expects email:token format (needs JIRA_URL too)
                if ":" not in token:
                    return {"valid": False, "error": "Please use format: email:api_token"}
                return {"valid": True, "info": "Token format looks valid (will verify on first use)"}

            elif provider == "aws":
                # AWS: expects access_key:secret:region format
                parts = token.split(":")
                if len(parts) != 3:
                    return {"valid": False, "error": "Please use format: access_key_id:secret_access_key:region"}
                if not parts[0].startswith("AKIA"):
                    return {"valid": False, "error": "Access Key ID should start with 'AKIA'"}
                return {"valid": True, "info": "Credentials format looks valid (will verify on first use)"}

            elif provider in ["postgres", "mongodb", "redis"]:
                # Database connections: validate format
                if provider == "postgres" and not token.startswith(("postgresql://", "postgres://")):
                    return {"valid": False, "error": "URL should start with postgresql:// or postgres://"}
                if provider == "mongodb" and not token.startswith(("mongodb://", "mongodb+srv://")):
                    return {"valid": False, "error": "URL should start with mongodb:// or mongodb+srv://"}
                if provider == "redis" and not token.startswith("redis://"):
                    return {"valid": False, "error": "URL should start with redis://"}
                return {"valid": True, "info": "Connection string format looks valid (will verify on first use)"}

            elif provider == "brave-search":
                # Brave Search: test with a simple query
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"X-Subscription-Token": token},
                    params={"q": "test", "count": 1}
                )
                if resp.status_code == 200:
                    return {"valid": True, "info": "API key is valid"}
                elif resp.status_code in [401, 403]:
                    return {"valid": False, "error": "Invalid API key"}
                return {"valid": False, "error": f"API error: {resp.status_code}"}

            else:
                # Unknown provider - accept without validation
                return {"valid": True, "info": "Token saved (validation not available for this provider)"}

    except httpx.TimeoutException:
        return {"valid": False, "error": "Validation timed out - token saved anyway"}
    except Exception as e:
        return {"valid": False, "error": f"Validation error: {str(e)}"}


@app.post("/api/integrations/{provider}/connect")
async def connect_integration(provider: str, request: Request, body: IntegrationConnectRequest):
    """Connect an integration by saving the user's token after validation."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    manager = get_mcp_manager()

    # Check if provider exists
    if provider not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Integration '{provider}' not found")

    # GitHub and Google use OAuth only
    if provider == "github":
        raise HTTPException(
            status_code=400,
            detail="GitHub uses OAuth. Use the 'Connect with GitHub' button instead."
        )
    if provider in ["gmail", "google-calendar", "google-drive"]:
        raise HTTPException(
            status_code=400,
            detail="Google services use OAuth. Use the 'Connect with Google' button instead."
        )

    config = manager.configs[provider]

    # Internal servers don't need tokens
    if config.command == "internal":
        return {"success": True, "provider": provider, "message": "This integration doesn't require authentication."}

    # Validate token is provided
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    # Validate the token before saving
    validation = await _validate_integration_token(provider, token)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=validation["error"])

    # Save token to database
    now = datetime.now(timezone.utc).isoformat()
    try:
        supabase_admin.table("user_integration_tokens").upsert(
            {
                "user_id": user_id,
                "provider": provider,
                "access_token": token,
                "updated_at": now,
            },
            on_conflict="user_id,provider",
        ).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save token: {str(e)}")

    # Try to connect the MCP server for this user
    mcp_warning = None
    try:
        success = await manager.connect_server_for_user(provider, user_id, token)
        if not success:
            mcp_warning = "Token validated but MCP server connection failed. Tools may not be available until restart."
    except Exception as e:
        mcp_warning = f"Token validated but MCP server connection failed: {str(e)}"

    result = {
        "success": True,
        "provider": provider,
        "info": validation.get("info")
    }
    if mcp_warning:
        result["warning"] = mcp_warning

    return result


@app.delete("/api/integrations/{provider}")
async def disconnect_integration(provider: str, request: Request):
    """Disconnect an integration by removing the user's token."""
    user_id = _get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")

    manager = get_mcp_manager()

    # Check if provider exists
    if provider not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Integration '{provider}' not found")

    config = manager.configs[provider]

    # Internal servers can't be disconnected
    if config.command == "internal":
        raise HTTPException(status_code=400, detail="This integration cannot be disconnected.")

    # Remove token from database
    supabase_admin.table("user_integration_tokens").delete().eq("user_id", user_id).eq("provider", provider).execute()

    # Disconnect MCP server for this user
    await manager.disconnect_server_for_user(provider, user_id)

    return {"success": True, "provider": provider}


@app.get("/api/integrations/{provider}/requirements")
async def get_integration_requirements(provider: str):
    """Get the authentication requirements for an integration."""
    manager = get_mcp_manager()

    if provider not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Integration '{provider}' not found")

    config = manager.configs[provider]

    # Internal servers don't need auth
    if config.command == "internal":
        return {
            "requires_auth": False,
            "type": "none",
            "name": config.display_name,
            "description": "This integration is built-in and doesn't require authentication.",
            "env_var": None,
            "help_url": None,
            "required_scopes": None,
            "setup_steps": None,
        }

    req = INTEGRATION_REQUIREMENTS.get(provider)
    if req:
        return {
            "requires_auth": True,
            "type": req.type,
            "name": req.name,
            "description": req.description,
            "env_var": req.env_var,
            "help_url": req.help_url,
            "required_scopes": req.required_scopes,
            "setup_steps": req.setup_steps,
        }

    return {
        "requires_auth": False,
        "type": "none",
        "name": config.display_name,
        "description": None,
        "env_var": None,
        "help_url": None,
        "required_scopes": None,
        "setup_steps": None,
    }


# Workflow Endpoints
@app.get("/api/workflows/{project_id}")
async def get_workflow(project_id: str):
    """Get workflow for a project."""
    _validate_project_id(project_id)
    result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    if result.data:
        workflow = result.data[0]
        return {"nodes": workflow.get("nodes", []), "edges": workflow.get("edges", [])}
    return {"nodes": [], "edges": []}

@app.post("/api/workflows/{project_id}")
async def update_workflow(project_id: str, workflow: Dict[str, Any]):
    """Update workflow for a project."""
    _validate_project_id(project_id)
    existing = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    
    data = {
        "project_id": project_id,
        "nodes": workflow.get("nodes", []),
        "edges": workflow.get("edges", [])
    }
    
    if existing.data:
        supabase_admin.table("workflows").update(data).eq("project_id", project_id).execute()
    else:
        data["id"] = str(uuid.uuid4())
        data["created_at"] = datetime.now(timezone.utc).isoformat()
        supabase_admin.table("workflows").insert(data).execute()
    
    return {"success": True}

@app.post("/api/workflows/{project_id}/execute")
async def execute_workflow(project_id: str):
    """Execute a workflow using the agentic browser engine."""
    _validate_project_id(project_id)
    # Fetch workflow and project (for user_id) from database
    workflow_result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    if not workflow_result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    project_result = supabase_admin.table("projects").select("user_id").eq("id", project_id).execute()
    user_id = project_result.data[0].get("user_id") if project_result.data else None

    workflow = workflow_result.data[0]
    workflow_data = {
        "nodes": workflow.get("nodes", []),
        "edges": workflow.get("edges", [])
    }

    # At execution time, ensure GitHub owner is set for any github.* node (covers old workflows or missed injection)
    if user_id:
        github_login = await _get_github_login_for_user(user_id)
        _inject_github_owner_into_workflow(workflow_data, github_login)

    # Check if workflow has any nodes
    if not workflow_data["nodes"]:
        # Store empty workflow message in chat
        empty_message = "No nodes to execute yet. Describe what you'd like to build and I'll create a workflow for you!"
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": empty_message,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return {"status": "empty", "message": empty_message}

    try:
        # Execute using agentic engine (pass user_id for per-user integrations like GitHub)
        execution_result = await run_workflow_engine(workflow_data, user_id=user_id)
        
        # Format results for chat message
        status = execution_result["status"]
        results = execution_result.get("results", [])
        final_context = execution_result.get("final_context", {})
        
        # Get node count for summary
        total_steps = len(results)
        successful_steps = sum(1 for r in results if r.get("status") == "success")
        
        # Build a clean, user-friendly message with proper markdown
        if status == "completed":
            message_parts = [f"## ✅ Workflow Complete\n\n**{successful_steps}/{total_steps}** steps succeeded\n\n---\n\n"]
        elif status == "partial_failure":
            message_parts = [f"## ⚠️ Workflow Finished\n\n**{successful_steps}/{total_steps}** steps succeeded\n\n---\n\n"]
        else:
            message_parts = ["## ❌ Workflow Failed\n\n---\n\n"]
        
        # Only show final result for successful workflows, not step-by-step details
        if status == "completed" and final_context:
            # Get the last node's output as the main result
            last_key = list(final_context.keys())[-1] if final_context else None
            if last_key:
                final_output = final_context[last_key]
                if isinstance(final_output, str):
                    # Clean up and format the output nicely
                    final_output = final_output.strip()
                    if len(final_output) > 1500:
                        final_output = final_output[:1500] + "..."
                    message_parts.append(f"### Results\n\n{final_output}")
        else:
            # For failures, show step summaries in a structured list
            message_parts.append("### Step Details\n\n")
            for i, step_result in enumerate(results):
                node_id = step_result.get("node_id", str(i + 1))
                step_status = step_result.get("status", "unknown")
                node_type = step_result.get("type", "unknown")
                output = step_result.get("output", "No output")
                error = step_result.get("error", "")
                
                status_icon = "✅" if step_status == "success" else "❌"
                type_label = node_type.replace("_", " ").title()
                
                message_parts.append(f"**{i + 1}. {type_label}** {status_icon}\n")
                
                # Get a brief summary of the output
                if step_status == "success":
                    if isinstance(output, str):
                        summary = output[:200].replace("\n", " ").strip()
                        if len(output) > 200:
                            summary += "..."
                        message_parts.append(f"> {summary}\n\n")
                    elif isinstance(output, dict):
                        summary = str(output)[:200]
                        message_parts.append(f"> {summary}\n\n")
                else:
                    # Show error for failed steps
                    error_msg = error if error else (output if isinstance(output, str) else "Unknown error")
                    message_parts.append(f"> *{error_msg[:200]}*\n\n")
        
        chat_message = "".join(message_parts)
        
        # Store execution result as chat message
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": chat_message,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        
        return {
            "status": execution_result["status"],
            "project_id": project_id,
            "execution_order": execution_result.get("execution_order", []),
            "results": execution_result["results"],
            "final_output": execution_result.get("final_context", {}),
            "chat_message": chat_message
        }
        
    except Exception as e:
        # Store error message in chat
        error_message = f"❌ **Execution failed**\n\nSomething went wrong: {str(e)}\n\nPlease try again or modify your workflow."
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": error_message,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@app.post("/api/workflows/{project_id}/execute/stream")
async def execute_workflow_stream(project_id: str, request: Request):
    """
    Execute a workflow with real-time streaming updates via Server-Sent Events.
    Streams node status changes (executing, success, failed) during execution.
    """
    _validate_project_id(project_id)

    # Fetch workflow and project (for user_id) from database
    workflow_result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    if not workflow_result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    project_result = supabase_admin.table("projects").select("user_id").eq("id", project_id).execute()
    user_id = project_result.data[0].get("user_id") if project_result.data else None

    workflow = workflow_result.data[0]
    workflow_data = {
        "nodes": workflow.get("nodes", []),
        "edges": workflow.get("edges", [])
    }

    # At execution time, ensure GitHub owner is set for any github.* node
    if user_id:
        github_login = await _get_github_login_for_user(user_id)
        _inject_github_owner_into_workflow(workflow_data, github_login)

    # Check if workflow has any nodes
    if not workflow_data["nodes"]:
        async def empty_generator():
            yield {
                "event": "error",
                "data": json.dumps({"error": "No nodes to execute. Create a workflow first."})
            }
        return EventSourceResponse(empty_generator())

    async def event_generator():
        """Generate SSE events from workflow execution."""
        event_queue = asyncio.Queue()
        last_event_at = time.time()
        keepalive_interval_seconds = 25.0

        async def stream_callback(event: Dict[str, Any]):
            """Callback for execution events."""
            await event_queue.put(event)

        async def run_workflow():
            """Execute workflow in background."""
            try:
                # Save workflow before execution
                try:
                    existing = supabase_admin.table("workflows").select("id").eq("project_id", project_id).execute()
                    data = {
                        "project_id": project_id,
                        "nodes": workflow_data.get("nodes", []),
                        "edges": workflow_data.get("edges", []),
                    }
                    if existing.data:
                        supabase_admin.table("workflows").update(data).eq("project_id", project_id).execute()
                    else:
                        data["id"] = str(uuid.uuid4())
                        data["created_at"] = datetime.now(timezone.utc).isoformat()
                        supabase_admin.table("workflows").insert(data).execute()
                except Exception as e:
                    # Don't fail execution purely due to a save error
                    print(f"[execute/stream] Failed to save workflow before execution: {e}")

                # Execute with streaming callback
                execution_result = await run_workflow_engine(
                    workflow_data,
                    user_id=user_id,
                    stream_callback=stream_callback
                )

                # Store execution result as chat message
                status = execution_result["status"]
                results = execution_result.get("results", [])
                total_steps = len(results)
                successful_steps = sum(1 for r in results if r.get("status") == "success")

                if status == "completed":
                    message_parts = [f"## ✅ Workflow Complete\n\n**{successful_steps}/{total_steps}** steps succeeded\n\n---\n\n"]
                elif status == "partial_failure":
                    message_parts = [f"## ⚠️ Workflow Finished\n\n**{successful_steps}/{total_steps}** steps succeeded\n\n---\n\n"]
                else:
                    message_parts = ["## ❌ Workflow Failed\n\n---\n\n"]

                # Get final result
                final_context = execution_result.get("final_context", {})
                if status == "completed" and final_context:
                    last_key = list(final_context.keys())[-1] if final_context else None
                    if last_key:
                        final_output = final_context[last_key]
                        if isinstance(final_output, str):
                            final_output = final_output.strip()
                            if len(final_output) > 1500:
                                final_output = final_output[:1500] + "..."
                            message_parts.append(f"### Results\n\n{final_output}")

                chat_message = "".join(message_parts)

                # Store in chat history
                supabase_admin.table("chat_history").insert({
                    "id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "role": "assistant",
                    "content": chat_message,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }).execute()

                await event_queue.put({
                    "type": "execution_complete",
                    "data": {
                        "status": status,
                        "results": results,
                        "chat_message": chat_message
                    }
                })
            except Exception as e:
                await event_queue.put({"type": "error", "data": str(e)})

        # Start workflow execution in background
        workflow_task = asyncio.create_task(run_workflow())

        # Yield events as they come in
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                event_type = event.get("type")
                event_data = event.get("data")
                last_event_at = time.time()

                if event_type == "node_status_change":
                    yield {
                        "event": "node_status_change",
                        "data": json.dumps({
                            "node_id": event.get("node_id"),
                            "status": event.get("status")
                        })
                    }
                elif event_type == "execution_complete":
                    yield {
                        "event": "done",
                        "data": json.dumps(event_data)
                    }
                    break
                elif event_type == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": str(event_data)})
                    }
                    break

            except asyncio.TimeoutError:
                # If the workflow task has finished, return its error (if any) or stop.
                if workflow_task.done():
                    err = None
                    try:
                        workflow_task.result()
                    except Exception as e:
                        err = str(e)

                    yield {
                        "event": "error" if err else "done",
                        "data": json.dumps({"error": err} if err else {"status": "completed", "results": [], "chat_message": ""})
                    }
                    break

                # Otherwise, keep the SSE connection alive during long-running steps.
                now = time.time()
                if now - last_event_at >= keepalive_interval_seconds:
                    last_event_at = now
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"ts": datetime.now(timezone.utc).isoformat()})
                    }
                continue

        # Ensure workflow task is complete
        if not workflow_task.done():
            workflow_task.cancel()
            try:
                await workflow_task
            except asyncio.CancelledError:
                pass

    return EventSourceResponse(event_generator())


@app.post("/api/workflows/{project_id}/execute-agentic")
async def execute_workflow_agentic(project_id: str, body: AgenticExecuteRequest, request: Request):
    """
    Execute a goal using the agentic orchestrator.
    This uses plan-execute-observe-replan loops for intelligent task completion.
    """
    _validate_project_id(project_id)
    goal = body.goal
    user_id = _get_user_id_from_request(request)

    if not goal or not goal.strip():
        raise HTTPException(status_code=400, detail="Goal is required")

    try:
        # Execute using agentic orchestrator (pass user_id for per-user integrations)
        execution_result = await execute_agentic(goal, user_id=user_id)

        status = execution_result.get("status", "unknown")
        result_text = execution_result.get("result", "")
        history = execution_result.get("history", [])
        steps_executed = execution_result.get("steps_executed", 0)
        replans = execution_result.get("replans", 0)
        error = execution_result.get("error")

        # Build chat message
        if status == "completed":
            message_parts = [f"## ✅ Task Complete\n\n**{steps_executed}** steps executed"]
            if replans > 0:
                message_parts.append(f" ({replans} replans)")
            message_parts.append("\n\n---\n\n")

            if result_text:
                message_parts.append(f"### Result\n\n{result_text}")
        else:
            message_parts = [f"## ❌ Task Failed\n\n"]
            if error:
                message_parts.append(f"**Error:** {error}\n\n")

            message_parts.append("### Steps Attempted\n\n")
            for step in history:
                status_icon = "✅" if step.get("status") == "success" else "❌"
                message_parts.append(f"- {step.get('description', 'Unknown step')} {status_icon}\n")

        chat_message = "".join(message_parts)

        # Store execution result as chat message
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": chat_message,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()

        return {
            "status": status,
            "project_id": project_id,
            "goal": goal,
            "result": result_text,
            "steps_executed": steps_executed,
            "replans": replans,
            "history": history,
            "chat_message": chat_message,
            "error": error
        }

    except Exception as e:
        # Store error message in chat
        error_message = f"❌ **Agentic execution failed**\n\nSomething went wrong: {str(e)}\n\nPlease try again."
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": error_message,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        raise HTTPException(status_code=500, detail=f"Agentic execution failed: {str(e)}")


# Node Configuration Endpoint
@app.patch("/api/workflows/{project_id}/nodes/{node_id}")
async def update_node_config(project_id: str, node_id: str, config: NodeConfigUpdate):
    """Update configuration for a specific node."""
    _validate_project_id(project_id)
    # Get current workflow
    result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow = result.data[0]
    nodes = workflow.get("nodes", [])

    # Find and update the node
    updated = False
    for node in nodes:
        if node.get("id") == node_id:
            if config.tool_name is not None:
                node["tool_name"] = config.tool_name
            if config.params is not None:
                node["params"] = config.params
            if config.prompt is not None:
                node["prompt"] = config.prompt
            if config.label is not None:
                node["label"] = config.label
                if "data" not in node:
                    node["data"] = {}
                node["data"]["label"] = config.label
            if config.instruction is not None:
                node["instruction"] = config.instruction
                if "data" not in node:
                    node["data"] = {}
                node["data"]["instruction"] = config.instruction
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Node not found")

    # Save updated workflow
    supabase_admin.table("workflows").update({"nodes": nodes}).eq("project_id", project_id).execute()

    return {"success": True, "node_id": node_id}


# MCP Server Endpoints
@app.get("/api/mcp/servers", response_model=List[MCPServerStatusResponse])
async def list_mcp_servers():
    """List all configured MCP servers and their connection status."""
    manager = get_mcp_manager()
    statuses = manager.get_server_statuses()
    return [
        MCPServerStatusResponse(
            name=s.name,
            display_name=s.display_name,
            connected=s.connected,
            tool_count=s.tool_count,
            icon=s.icon,
            error=s.error
        )
        for s in statuses
    ]


@app.get("/api/mcp/servers/{server_name}/requirements")
async def get_server_requirements(server_name: str):
    """Get the requirements for connecting to a server (e.g., token needed)."""
    if server_name in INTEGRATION_REQUIREMENTS:
        req = INTEGRATION_REQUIREMENTS[server_name]
        return {
            "requires_auth": True,
            "type": req.type,
            "name": req.name,
            "description": req.description,
            "env_var": req.env_var,
            "help_url": req.help_url
        }
    return {
        "requires_auth": False,
        "type": "none",
        "name": None,
        "description": None,
        "env_var": None,
        "help_url": None
    }


@app.post("/api/mcp/servers")
async def add_mcp_server(server: MCPServerCreate):
    """Add a new MCP server configuration."""
    manager = get_mcp_manager()

    config = MCPServerConfig(
        name=server.name,
        display_name=server.display_name,
        command=server.command,
        args=server.args,
        env=server.env,
        enabled=False
    )

    manager.add_server_config(config)

    return {"success": True, "name": server.name}


@app.post("/api/mcp/servers/{server_name}/connect")
async def connect_mcp_server(server_name: str, request: Optional[MCPConnectRequest] = None):
    """Connect to an MCP server with optional token. GitHub uses OAuth only (no PAT)."""
    manager = get_mcp_manager()

    if server_name not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    # GitHub is OAuth-only; do not accept PAT
    if server_name == "github":
        raise HTTPException(
            status_code=400,
            detail="Use Settings → Integrations → Connect with GitHub to authorize via OAuth."
        )

    # Check if this server requires a token
    if server_name in INTEGRATION_REQUIREMENTS:
        req = INTEGRATION_REQUIREMENTS[server_name]
        if req.type == "token" and (not request or not request.token):
            if not manager.get_user_token(server_name):
                raise HTTPException(
                    status_code=400,
                    detail=f"This integration requires a {req.name}. Please provide a token."
                )

    token = request.token if request else None
    success = await manager.connect_server(server_name, token=token)

    if not success:
        conn = manager.connections.get(server_name)
        error = conn.error if conn else "Unknown error"
        raise HTTPException(status_code=500, detail=f"Failed to connect: {error}")

    return {"success": True, "name": server_name}


@app.post("/api/mcp/servers/{server_name}/disconnect")
async def disconnect_mcp_server(server_name: str):
    """Disconnect from an MCP server."""
    manager = get_mcp_manager()

    if server_name not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    await manager.disconnect_server(server_name)

    return {"success": True, "name": server_name}


@app.delete("/api/mcp/servers/{server_name}")
async def remove_mcp_server(server_name: str):
    """Remove an MCP server configuration."""
    manager = get_mcp_manager()

    if server_name not in manager.configs:
        raise HTTPException(status_code=404, detail=f"Server '{server_name}' not found")

    # Disconnect first if connected
    await manager.disconnect_server(server_name)

    # Remove config
    del manager.configs[server_name]

    return {"success": True, "name": server_name}


@app.get("/api/mcp/tools", response_model=List[MCPToolResponse])
async def list_available_tools(request: Request):
    """List all available tools. When authenticated, includes per-user tools for connected integrations."""
    manager = get_mcp_manager()
    user_id = _get_user_id_from_request(request)
    if user_id:
        # Connect all integrations the user has tokens for
        await manager.ensure_all_user_integrations_connected(user_id)
    tools = manager.get_all_tools(user_id=user_id)

    return [
        MCPToolResponse(
            name=t.name,
            server_name=t.server_name,
            display_name=t.display_name,
            description=t.description,
            input_schema=t.input_schema,
            category=t.category
        )
        for t in tools
    ]


@app.get("/api/mcp/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str, request: Request):
    """Get the full JSON schema for a tool's parameters. Pass auth for per-user (e.g. GitHub) tools."""
    manager = get_mcp_manager()
    user_id = _get_user_id_from_request(request)
    schema = manager.get_tool_schema(tool_name, user_id=user_id)

    if schema is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return schema


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
