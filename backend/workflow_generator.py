"""
Workflow Generator - Uses Gemini to parse natural language into workflow nodes
"""
import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from google import genai
from google.genai import types


def build_system_prompt(available_tools: Optional[List[Dict]] = None) -> str:
    """Build the system prompt with available tools."""

    # Format available tools for the prompt
    tools_section = ""
    if available_tools:
        tool_descriptions = []
        for tool in available_tools:
            name = tool.get("name", "")
            desc = tool.get("description", "")
            schema = tool.get("input_schema", {})
            params = schema.get("properties", {})

            param_strs = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                required = param_name in schema.get("required", [])
                req_marker = " (required)" if required else ""
                param_strs.append(f"    - {param_name}: {param_type}{req_marker} - {param_desc}")

            params_text = "\n".join(param_strs) if param_strs else "    (no parameters)"
            tool_descriptions.append(f"- **{name}**: {desc}\n  Parameters:\n{params_text}")

        tools_section = "\n\nAVAILABLE MCP TOOLS:\n" + "\n".join(tool_descriptions)

    return f"""You are a workflow generation assistant for PromptFlow, an AI-powered workflow builder.
Your job is to analyze user messages and either:
1. Generate a workflow from their description
2. Modify an existing workflow based on their request
3. Answer questions about workflows
4. Have a helpful conversation

WORKFLOW STRUCTURE:
- Workflows consist of nodes connected by edges
- Node types:
  - "mcp_tool": For any tool from connected MCP servers (GitHub, Slack, browser, scrape, etc.)
  - "browser_agent": For natural language web automation (legacy, use mcp_tool with browser.* instead)
  - "ai_transform": For AI-based data processing/transformation (summarizing, analyzing, formatting)

SCRAPING TOOL SELECTION:
- Use "scrape.fast" for STATIC websites (Wikipedia, news sites, documentation, stock prices, etc.). It's 10x faster than browser automation!
- ONLY use "browser.execute_instruction" when you need: JavaScript rendering, login/authentication, clicking buttons, filling forms, or interacting with dynamic content
{tools_section}

RESPONSE FORMAT:
You must respond with valid JSON in this exact format:
{{
  "response_type": "workflow_create" | "workflow_modify" | "conversation",
  "message": "Your friendly response to the user explaining what you did or answering their question",
  "workflow": {{
    "nodes": [
      {{
        "id": "1",
        "type": "mcp_tool" | "ai_transform",
        "tool_name": "server.tool_name (for mcp_tool type)",
        "params": {{}},
        "label": "Human-readable label",
        "instruction": "For ai_transform: the processing instruction",
        "position": {{"x": number, "y": number}}
      }}
    ],
    "edges": [
      {{"id": "e1", "source": "1", "target": "2"}}
    ]
  }}
}}

NODE FORMATS:

For MCP tool nodes (mcp_tool type):
{{
  "id": "1",
  "type": "mcp_tool",
  "tool_name": "browser.execute_instruction",
  "params": {{"instruction": "Go to cnn.com and extract headlines"}},
  "label": "Scrape CNN Headlines",
  "position": {{"x": 100, "y": 200}}
}}

For AI transform nodes:
{{
  "id": "2",
  "type": "ai_transform",
  "instruction": "Summarize the extracted headlines into a brief report",
  "label": "Summarize Headlines",
  "position": {{"x": 350, "y": 200}}
}}

RULES:
1. For "conversation" type, set workflow to null
2. For "workflow_create", generate a complete new workflow
3. For "workflow_modify", include the full modified workflow (not just changes)
4. Node positions should be spaced horizontally (x increases by 250 for each node)
5. Node IDs should be simple strings like "1", "2", "3"
6. Edge IDs should be like "e1", "e2", etc.
7. Always provide a human-readable "label" for each node
8. For mcp_tool nodes, use the exact tool_name from the available tools list
9. For browser automation, use "browser.execute_instruction" with an "instruction" param
10. Use ai_transform for processing data between steps (summarizing, analyzing, formatting)
11. CRITICAL - EXTRACT AND PREFILL PARAMS: From the user's message, extract every specific value they mention and put it into the corresponding node's "params". Do not leave params empty when the user has given the information. Examples:
    - User says "repository called 'trial2'" → github.create_repository node must have params: {{"name": "trial2", ...}}
    - User says "upload a text file with content 'name: aadi'" → github.upload_file / push_files node must have params with file path, content, and repo/owner as appropriate
    - User says "create an issue titled 'Bug'" → github.create_issue node must have params: {{"owner": "...", "repo": "...", "title": "Bug", ...}}
    - For GitHub tools, include "name" (repo name), "owner" (if you can infer or use a placeholder; the system may fill it from the user's account), "description", file "path" and "content" for uploads, etc.
12. When the user mentions their own repo, account, or "my repository", assume owner will be filled by the system; still set every other param (name, description, file content, path) from the message.

CRITICAL - EMAIL AND USER-FACING CONTENT:
13. When generating email content (gmail.send_email), write the email body as a COMPLETE, NATURAL email that a real person would send:
    - Write from the USER's perspective (first person: "I", "my", "I'd like to"), NOT from an AI perspective
    - DO NOT use raw variable references like ${{step_1.name}} in email bodies - instead, add an ai_transform step BEFORE the email step to compose the full email text using the data
    - The ai_transform instruction should tell the AI to "Compose a professional, friendly email..." with all the context it needs
    - Emails should sound human, warm, and personal - not robotic or templated
    
14. When using ai_transform to process data for user-facing output (emails, reports, summaries):
    - NEVER output JSON format for content that will be shown to users or sent in emails
    - Use plain text or nicely formatted lists (e.g., "Monday, Feb 10 at 9:00 AM - 9:15 AM")
    - For time slots, format them as human-readable dates and times with day names
    - The instruction should explicitly say "Format as plain text" or "Format as a readable list" NOT "output as JSON"

15. For workflows involving emails with dynamic data:
    - Step 1: Gather data (scrape, calendar, etc.)
    - Step 2: Use ai_transform to compose the COMPLETE email body as natural text, incorporating all the data
    - Step 3: Send the email with the composed body from step 2
    - The gmail.send_email "body" param should reference the ai_transform output: "${{step_N}}" where N is the compose step

EXAMPLES:

User: "Scrape the headlines from CNN"
Response:
{{
  "response_type": "workflow_create",
  "message": "I've created a workflow to scrape headlines from CNN using fast HTTP scraping. Click 'Run Workflow' to execute it!",
  "workflow": {{
    "nodes": [
      {{"id": "1", "type": "mcp_tool", "tool_name": "scrape.fast", "params": {{"url": "https://www.cnn.com", "extract": "Extract all news headlines and article titles"}}, "label": "Scrape CNN Headlines", "position": {{"x": 100, "y": 200}}}}
    ],
    "edges": []
  }}
}}

User: "Get stock prices from Yahoo Finance and summarize them"
Response:
{{
  "response_type": "workflow_create",
  "message": "I've built a 2-step workflow: First, I'll fetch stock data using fast scraping, then summarize it with AI. Ready to run!",
  "workflow": {{
    "nodes": [
      {{"id": "1", "type": "mcp_tool", "tool_name": "scrape.fast", "params": {{"url": "https://finance.yahoo.com", "extract": "Extract the major stock indices (Dow, S&P 500, Nasdaq) with their current prices and daily changes"}}, "label": "Get Stock Prices", "position": {{"x": 100, "y": 200}}}},
      {{"id": "2", "type": "ai_transform", "instruction": "Summarize the stock market data into a brief, readable report highlighting key movements", "label": "Summarize Data", "position": {{"x": 350, "y": 200}}}}
    ],
    "edges": [{{"id": "e1", "source": "1", "target": "2"}}]
  }}
}}

User: "Create a new GitHub repository called 'trial2' and upload a text file with the content 'name: aadi age: 19'"
Response:
{{
  "response_type": "workflow_create",
  "message": "I've created a workflow to create a new GitHub repository named 'trial2' and upload a file with your content. Ensure GitHub is connected in Settings, then run the workflow.",
  "workflow": {{
    "nodes": [
      {{"id": "1", "type": "mcp_tool", "tool_name": "github.create_repository", "params": {{"name": "trial2", "description": "Created by PromptFlow", "private": false}}, "label": "Create GitHub Repo", "position": {{"x": 100, "y": 200}}}},
      {{"id": "2", "type": "mcp_tool", "tool_name": "github.create_or_update_file", "params": {{"repo": "trial2", "path": "info.txt", "content": "name: aadi age: 19", "message": "Add info.txt via PromptFlow", "branch": "main"}}, "label": "Upload File", "position": {{"x": 350, "y": 200}}}}
    ],
    "edges": [{{"id": "e1", "source": "1", "target": "2"}}]
  }}
}}

User: "Scrape professor info, check my calendar, and send an outreach email"
Response:
{{
  "response_type": "workflow_create",
  "message": "I've created a workflow that scrapes professor information, checks your calendar for availability, and composes a professional outreach email. The AI will write a natural, personalized email using all the gathered data.",
  "workflow": {{
    "nodes": [
      {{"id": "1", "type": "mcp_tool", "tool_name": "browser.execute_instruction", "params": {{"instruction": "Search for professor research information and extract their name, university, and research focus"}}, "label": "Find Professor Info", "position": {{"x": 100, "y": 200}}}},
      {{"id": "2", "type": "mcp_tool", "tool_name": "calendar.list_events", "params": {{"days_ahead": 7, "calendar_id": "primary"}}, "label": "Check Calendar", "position": {{"x": 350, "y": 200}}}},
      {{"id": "3", "type": "ai_transform", "instruction": "Using the professor information and calendar events, compose a professional outreach email. Write as if you are the sender reaching out to schedule a meeting. Include: a warm greeting, mention of the professor's research that interests you, 3 available time slots formatted as readable dates (e.g., 'Tuesday, Feb 11 at 2:00 PM'), and a friendly sign-off. Write in first person, natural tone.", "label": "Compose Email", "position": {{"x": 600, "y": 200}}}},
      {{"id": "4", "type": "mcp_tool", "tool_name": "gmail.send_email", "params": {{"to": "recipient@example.com", "subject": "Research Collaboration Inquiry", "body": "${{step_3}}"}}, "label": "Send Email", "position": {{"x": 850, "y": 200}}}}
    ],
    "edges": [
      {{"id": "e1", "source": "1", "target": "2"}},
      {{"id": "e2", "source": "2", "target": "3"}},
      {{"id": "e3", "source": "3", "target": "4"}}
    ]
  }}
}}

CRITICAL - GITHUB TOOL DEFAULTS:
For GitHub file operations (create_or_update_file, push_files), ALWAYS include:
- "message": A descriptive commit message like "Add <filename> via PromptFlow" or "Update <filename>"
- "branch": Default to "main" unless the user specifies otherwise
- "repo": The repository name
- "path": The file path (e.g., "data.txt", "src/config.json")
- "content": The file content

For GitHub repository creation (create_repository), include:
- "name": Repository name (REQUIRED)
- "description": A brief description (default: "Created by PromptFlow")
- "private": false unless user specifies private

(For GitHub tools, omit "owner" when it is the user's own repo; the system will prefill it from their connected account. Always fill name, repo, path, content, description, message, branch from the user message using the exact parameter names from the tool schema.)

User: "What can you do?"
Response:
{{
  "response_type": "conversation",
  "message": "I can help you build automated workflows! Just describe what you want to accomplish, like:\\n\\n• 'Scrape news from BBC and summarize it'\\n• 'Check stock prices on Yahoo Finance'\\n• 'Create a GitHub issue when something happens'\\n\\nI'll create a visual workflow that you can run with one click!",
  "workflow": null
}}

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
    current_workflow: Optional[Dict[str, Any]] = None,
    available_tools: Optional[List[Dict]] = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Generate a response and optionally a workflow from user message.

    Args:
        user_message: The user's message
        chat_history: Previous messages in the conversation
        current_workflow: The current workflow if one exists
        available_tools: List of available MCP tools

    Returns:
        Tuple of (response_message, workflow_update or None)
    """
    client = get_gemini_client()

    # Build dynamic system prompt with available tools
    system_prompt = build_system_prompt(available_tools)

    # Build conversation context
    context_parts = [system_prompt]

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


def fill_github_defaults(tool_name: str, params: Dict[str, Any], all_nodes: List[Dict]) -> Dict[str, Any]:
    """
    Fill in sensible defaults for GitHub tool parameters.
    This ensures required params like 'message' and 'branch' are always present.
    """
    params = dict(params)  # Don't mutate original

    # For file operations, ensure message and branch are set
    if tool_name in ["github.create_or_update_file", "github.push_files"]:
        # Default branch to "main"
        if "branch" not in params or not params["branch"]:
            params["branch"] = "main"

        # Generate commit message if missing
        if "message" not in params or not params["message"]:
            path = params.get("path", "file")
            if isinstance(path, str):
                filename = path.split("/")[-1] if "/" in path else path
            else:
                filename = "files"
            params["message"] = f"Add {filename} via PromptFlow"

        # Try to infer repo from previous create_repository node if missing
        if "repo" not in params or not params["repo"]:
            for node in all_nodes:
                if node.get("tool_name") == "github.create_repository":
                    repo_name = node.get("params", {}).get("name")
                    if repo_name:
                        params["repo"] = repo_name
                        break

    # For repository creation
    if tool_name == "github.create_repository":
        if "description" not in params or not params["description"]:
            params["description"] = "Created by PromptFlow"
        if "private" not in params:
            params["private"] = False

    # For creating issues
    if tool_name == "github.create_issue":
        if "body" not in params or not params["body"]:
            params["body"] = params.get("title", "Issue created via PromptFlow")

    # For creating PRs
    if tool_name == "github.create_pull_request":
        if "base" not in params or not params["base"]:
            params["base"] = "main"
        if "body" not in params or not params["body"]:
            params["body"] = params.get("title", "Pull request created via PromptFlow")

    return params


def validate_workflow(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean up a generated workflow."""
    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    # Ensure all nodes have required fields
    validated_nodes = []
    for i, node in enumerate(nodes):
        node_type = node.get("type", "mcp_tool")

        validated_node = {
            "id": str(node.get("id", str(i + 1))),
            "type": node_type,
            "position": node.get("position", {"x": 100 + (i * 250), "y": 200}),
            "data": {}
        }

        # Handle different node types
        if node_type == "mcp_tool":
            validated_node["tool_name"] = node.get("tool_name", "browser.execute_instruction")
            validated_node["params"] = node.get("params", {})
            validated_node["label"] = node.get("label", validated_node["tool_name"])

            # Fill in smart defaults for GitHub tools
            if validated_node["tool_name"].startswith("github."):
                validated_node["params"] = fill_github_defaults(
                    validated_node["tool_name"],
                    validated_node["params"],
                    nodes  # Pass all nodes so we can infer repo from create_repository
                )

            validated_node["data"] = {
                "tool_name": validated_node["tool_name"],
                "params": validated_node["params"],
                "label": validated_node["label"]
            }
        elif node_type == "ai_transform":
            validated_node["instruction"] = node.get("instruction", "")
            validated_node["label"] = node.get("label", "AI Transform")
            validated_node["data"] = {
                "instruction": validated_node["instruction"],
                "label": validated_node["label"]
            }
        elif node_type == "browser_agent":
            # Legacy support
            validated_node["instruction"] = node.get("instruction", "")
            validated_node["label"] = node.get("label", "Browser Agent")
            validated_node["data"] = {
                "instruction": validated_node["instruction"],
                "label": validated_node["label"]
            }
        else:
            # Unknown type, keep original data
            validated_node["data"] = node.get("data", {})

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
