"""
PromptFlow Backend - FastAPI Application
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid
from datetime import datetime
from execution_engine import execute_workflow as run_workflow_engine

load_dotenv()

# Supabase admin client (bypasses RLS)
supabase_url = os.getenv("SUPABASE_URL")
supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

if not supabase_url or not supabase_service_key:
    raise ValueError(f"Missing Supabase credentials. URL: {supabase_url is not None}, Key: {supabase_service_key is not None}")

supabase_admin: Client = create_client(supabase_url, supabase_service_key)

# Regular client for user operations
supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", supabase_service_key)
supabase: Client = create_client(supabase_url, supabase_anon_key)

app = FastAPI(
    title="PromptFlow API",
    description="Backend API for PromptFlow - AI-powered workflow builder",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],
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

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: str
    name: str
    created_at: str

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "PromptFlow API"}

# Chat Endpoints
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat message and return AI response with optional workflow update."""
    # Store user message
    user_message_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    supabase_admin.table("chat_history").insert({
        "id": user_message_id,
        "project_id": request.project_id,
        "role": "user",
        "content": request.message,
        "created_at": now
    }).execute()
    
    # TODO: Implement Gemini integration for real responses
    response_text = "Hello! I'm your workflow assistant. What would you like to build today?"
    
    # Store assistant message
    assistant_message_id = str(uuid.uuid4())
    supabase_admin.table("chat_history").insert({
        "id": assistant_message_id,
        "project_id": request.project_id,
        "role": "assistant",
        "content": response_text,
        "created_at": datetime.utcnow().isoformat()
    }).execute()
    
    return ChatResponse(
        message=response_text,
        workflow_update=None
    )

@app.get("/api/chat/{project_id}")
async def get_chat_history(project_id: str):
    """Get chat history for a project."""
    result = supabase_admin.table("chat_history").select("*").eq("project_id", project_id).order("created_at").execute()
    return {"messages": [{"role": m["role"], "content": m["content"], "created_at": m["created_at"]} for m in result.data]}

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
    
    project_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    
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

# Workflow Endpoints
@app.get("/api/workflows/{project_id}")
async def get_workflow(project_id: str):
    """Get workflow for a project."""
    result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    if result.data:
        workflow = result.data[0]
        return {"nodes": workflow.get("nodes", []), "edges": workflow.get("edges", [])}
    return {"nodes": [], "edges": []}

@app.post("/api/workflows/{project_id}")
async def update_workflow(project_id: str, workflow: Dict[str, Any]):
    """Update workflow for a project."""
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
        data["created_at"] = datetime.utcnow().isoformat()
        supabase_admin.table("workflows").insert(data).execute()
    
    return {"success": True}

@app.post("/api/workflows/{project_id}/execute")
async def execute_workflow(project_id: str):
    """Execute a workflow using the agentic browser engine."""
    # Fetch workflow from database
    result = supabase_admin.table("workflows").select("*").eq("project_id", project_id).execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    workflow = result.data[0]
    workflow_data = {
        "nodes": workflow.get("nodes", []),
        "edges": workflow.get("edges", [])
    }
    
    # Check if workflow has any nodes
    if not workflow_data["nodes"]:
        return {"status": "empty", "message": "No nodes to execute. Chat with me to build a workflow first!"}
    
    try:
        # Execute using agentic engine
        execution_result = await run_workflow_engine(workflow_data)
        
        # Store execution log (optional - could add executions table later)
        return {
            "status": execution_result["status"],
            "project_id": project_id,
            "execution_order": execution_result.get("execution_order", []),
            "results": execution_result["results"],
            "final_output": execution_result.get("final_context", {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
