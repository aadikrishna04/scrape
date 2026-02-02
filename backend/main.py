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
from workflow_generator import generate_workflow_response, validate_workflow

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
    
    # Get chat history for context
    history_result = supabase_admin.table("chat_history").select("role, content").eq(
        "project_id", request.project_id
    ).order("created_at").execute()
    chat_history = [{"role": m["role"], "content": m["content"]} for m in history_result.data[:-1]]  # Exclude current message
    
    # Get current workflow for context
    workflow_result = supabase_admin.table("workflows").select("nodes, edges").eq(
        "project_id", request.project_id
    ).execute()
    current_workflow = None
    if workflow_result.data:
        current_workflow = {
            "nodes": workflow_result.data[0].get("nodes", []),
            "edges": workflow_result.data[0].get("edges", [])
        }
    
    # Generate response using Gemini
    try:
        response_text, workflow_update = await generate_workflow_response(
            user_message=request.message,
            chat_history=chat_history,
            current_workflow=current_workflow
        )
        
        # If workflow was generated/modified, save it to database
        if workflow_update:
            validated_workflow = validate_workflow(workflow_update)
            
            # Upsert workflow
            existing = supabase_admin.table("workflows").select("id").eq(
                "project_id", request.project_id
            ).execute()
            
            workflow_data = {
                "project_id": request.project_id,
                "nodes": validated_workflow["nodes"],
                "edges": validated_workflow["edges"]
            }
            
            if existing.data:
                supabase_admin.table("workflows").update(workflow_data).eq(
                    "project_id", request.project_id
                ).execute()
            else:
                workflow_data["id"] = str(uuid.uuid4())
                workflow_data["created_at"] = datetime.utcnow().isoformat()
                supabase_admin.table("workflows").insert(workflow_data).execute()
                
    except Exception as e:
        print(f"Workflow generation error: {e}")
        response_text = "I'm having trouble processing that. Could you try rephrasing your request?"
        workflow_update = None
    
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
        workflow_update=workflow_update
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

class ProjectRename(BaseModel):
    name: str

@app.patch("/api/projects/{project_id}")
async def rename_project(project_id: str, data: ProjectRename, request: Request):
    """Rename a project."""
    supabase_admin.table("projects").update({"name": data.name}).eq("id", project_id).execute()
    return {"success": True, "name": data.name}

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
        # Store empty workflow message in chat
        empty_message = "No nodes to execute yet. Describe what you'd like to build and I'll create a workflow for you!"
        supabase_admin.table("chat_history").insert({
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "assistant",
            "content": empty_message,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        return {"status": "empty", "message": empty_message}
    
    try:
        # Execute using agentic engine
        execution_result = await run_workflow_engine(workflow_data)
        
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
            "created_at": datetime.utcnow().isoformat()
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
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
