"""
Workflow Generator - Uses Gemini to parse natural language into workflow nodes
"""
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types

SYSTEM_PROMPT = """You are a workflow generation assistant for PromptFlow, an AI-powered workflow builder.
Your job is to analyze user messages and either:
1. Generate a workflow from their description
2. Modify an existing workflow based on their request
3. Answer questions about workflows
4. Have a helpful conversation

WORKFLOW STRUCTURE:
- Workflows consist of nodes connected by edges
- Node types:
  - "browser_agent": For web automation (scraping, navigation, form filling, clicking, etc.)
  - "ai_transform": For AI-based data processing/transformation (summarizing, analyzing, formatting)

RESPONSE FORMAT:
You must respond with valid JSON in this exact format:
{
  "response_type": "workflow_create" | "workflow_modify" | "conversation",
  "message": "Your friendly response to the user explaining what you did or answering their question",
  "workflow": {
    "nodes": [
      {
        "id": "1",
        "type": "browser_agent" | "ai_transform",
        "instruction": "Clear, specific instruction for this step",
        "position": {"x": number, "y": number}
      }
    ],
    "edges": [
      {"id": "e1", "source": "1", "target": "2"}
    ]
  }
}

RULES:
1. For "conversation" type, set workflow to null
2. For "workflow_create", generate a complete new workflow
3. For "workflow_modify", include the full modified workflow (not just changes)
4. Node positions should be spaced horizontally (x increases by 250 for each node)
5. Node IDs should be simple strings like "1", "2", "3"
6. Edge IDs should be like "e1", "e2", etc.
7. Instructions should be specific and actionable
8. Use browser_agent for ANY web interaction (visiting sites, clicking, typing, extracting data)
9. Use ai_transform for processing data between browser steps (summarizing, analyzing, formatting)

EXAMPLES:

User: "Scrape the headlines from CNN"
Response:
{
  "response_type": "workflow_create",
  "message": "I've created a workflow to scrape headlines from CNN. Click 'Run Workflow' to execute it!",
  "workflow": {
    "nodes": [
      {"id": "1", "type": "browser_agent", "instruction": "Go to cnn.com and extract all headline text from the main page", "position": {"x": 100, "y": 200}}
    ],
    "edges": []
  }
}

User: "Get stock prices from Yahoo Finance and summarize them"
Response:
{
  "response_type": "workflow_create",
  "message": "I've built a 2-step workflow: First, I'll scrape stock data from Yahoo Finance, then summarize it with AI. Ready to run!",
  "workflow": {
    "nodes": [
      {"id": "1", "type": "browser_agent", "instruction": "Go to finance.yahoo.com, navigate to the market summary, and extract the major stock indices with their current prices and daily changes", "position": {"x": 100, "y": 200}},
      {"id": "2", "type": "ai_transform", "instruction": "Summarize the stock market data into a brief, readable report highlighting key movements", "position": {"x": 350, "y": 200}}
    ],
    "edges": [{"id": "e1", "source": "1", "target": "2"}]
  }
}

User: "What can you do?"
Response:
{
  "response_type": "conversation",
  "message": "I can help you build automated workflows! Just describe what you want to accomplish, like:\\n\\n• 'Scrape news from BBC and summarize it'\\n• 'Check stock prices on Yahoo Finance'\\n• 'Extract product info from Amazon'\\n\\nI'll create a visual workflow that you can run with one click!",
  "workflow": null
}

User: "Add an email step to send the results"
Response:
{
  "response_type": "workflow_modify",
  "message": "I've added an email step to your workflow. The results will now be sent via email after processing!",
  "workflow": {
    "nodes": [
      {"id": "1", "type": "browser_agent", "instruction": "Previous step instruction here", "position": {"x": 100, "y": 200}},
      {"id": "2", "type": "ai_transform", "instruction": "Previous transform instruction here", "position": {"x": 350, "y": 200}},
      {"id": "3", "type": "browser_agent", "instruction": "Open Gmail, compose a new email, paste the summary in the body, and send it", "position": {"x": 600, "y": 200}}
    ],
    "edges": [{"id": "e1", "source": "1", "target": "2"}, {"id": "e2", "source": "2", "target": "3"}]
  }
}

Always respond with valid JSON only. No markdown, no extra text outside the JSON."""


def get_gemini_client():
    """Get configured Gemini client."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")
    return genai.Client(api_key=api_key)


async def generate_workflow_response(
    user_message: str,
    chat_history: List[Dict[str, str]],
    current_workflow: Optional[Dict[str, Any]] = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Generate a response and optionally a workflow from user message.
    
    Args:
        user_message: The user's message
        chat_history: Previous messages in the conversation
        current_workflow: The current workflow if one exists
        
    Returns:
        Tuple of (response_message, workflow_update or None)
    """
    client = get_gemini_client()
    
    # Build conversation context
    context_parts = [SYSTEM_PROMPT]
    
    # Add current workflow context if exists
    if current_workflow and (current_workflow.get("nodes") or current_workflow.get("edges")):
        context_parts.append(f"\n\nCURRENT WORKFLOW STATE:\n{json.dumps(current_workflow, indent=2)}")
    
    # Add recent chat history (last 10 messages for context)
    if chat_history:
        recent_history = chat_history[-10:]
        history_text = "\n\nRECENT CONVERSATION:\n"
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"
        context_parts.append(history_text)
    
    # Add current user message
    context_parts.append(f"\n\nUser: {user_message}\n\nRespond with valid JSON:")
    
    full_prompt = "\n".join(context_parts)
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                top_p=0.95,
                max_output_tokens=2048,
            )
        )
        response_text = response.text.strip()
        
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith("```"):
            # Remove ```json and ``` markers
            response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
            response_text = re.sub(r'\s*```$', '', response_text)
        
        # Parse JSON response
        parsed = json.loads(response_text)
        
        message = parsed.get("message", "I've processed your request.")
        workflow = parsed.get("workflow")
        
        # Only return workflow if it's a create/modify action
        if parsed.get("response_type") in ["workflow_create", "workflow_modify"] and workflow:
            return message, workflow
        
        return message, None
        
    except json.JSONDecodeError as e:
        # If JSON parsing fails, try to extract useful content
        print(f"JSON parse error: {e}")
        print(f"Raw response: {response_text[:500]}")
        return "I understand your request. Could you provide more details about what you'd like to build?", None
        
    except Exception as e:
        print(f"Gemini error: {e}")
        return "I'm having trouble processing that right now. Could you try rephrasing your request?", None


def validate_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean up a generated workflow."""
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])
    
    # Ensure all nodes have required fields
    validated_nodes = []
    for i, node in enumerate(nodes):
        validated_node = {
            "id": str(node.get("id", str(i + 1))),
            "type": node.get("type", "browser_agent"),
            "instruction": node.get("instruction", ""),
            "position": node.get("position", {"x": 100 + (i * 250), "y": 200}),
            "data": {"instruction": node.get("instruction", "")}
        }
        validated_nodes.append(validated_node)
    
    # Ensure all edges have required fields
    validated_edges = []
    for i, edge in enumerate(edges):
        validated_edge = {
            "id": edge.get("id", f"e{i + 1}"),
            "source": str(edge.get("source", "")),
            "target": str(edge.get("target", "")),
        }
        if validated_edge["source"] and validated_edge["target"]:
            validated_edges.append(validated_edge)
    
    return {
        "nodes": validated_nodes,
        "edges": validated_edges
    }
