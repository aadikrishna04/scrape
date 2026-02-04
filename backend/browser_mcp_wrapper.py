"""
Browser MCP Wrapper - Exposes browser automation as MCP-compatible tools
"""
from typing import Dict, Any, Optional

from mcp_manager import MCPManager, MCPTool
from browser_agent import execute_browser_instruction


def get_browser_tools() -> list[MCPTool]:
    """Return browser tools in MCP format."""
    return [
        MCPTool(
            name="browser.execute_instruction",
            server_name="browser",
            original_name="execute_instruction",
            display_name="Browser Automation",
            description="Execute natural language browser instructions. Use this for web scraping, form filling, clicking, navigation, and any browser interaction.",
            input_schema={
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Natural language instruction for the browser agent (e.g., 'Go to google.com and search for AI news')"
                    }
                },
                "required": ["instruction"]
            },
            category="browser"
        ),
        MCPTool(
            name="browser.extract_data",
            server_name="browser",
            original_name="extract_data",
            display_name="Extract Web Data",
            description="Navigate to a URL and extract specific data from the page.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to"
                    },
                    "data_description": {
                        "type": "string",
                        "description": "Description of what data to extract (e.g., 'all product prices and names')"
                    }
                },
                "required": ["url", "data_description"]
            },
            category="browser"
        ),
        MCPTool(
            name="browser.fill_form",
            server_name="browser",
            original_name="fill_form",
            display_name="Fill Web Form",
            description="Navigate to a URL and fill out a form with provided data.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL containing the form"
                    },
                    "form_data": {
                        "type": "object",
                        "description": "Key-value pairs of form fields to fill",
                        "additionalProperties": {"type": "string"}
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "Whether to submit the form after filling",
                        "default": True
                    }
                },
                "required": ["url", "form_data"]
            },
            category="browser"
        ),
    ]


async def handle_browser_tool(
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle browser tool calls by delegating to the browser agent.

    This is a unified handler for all browser.* tools that constructs
    the appropriate instruction for the underlying browser agent.
    """
    # Get the instruction based on params
    instruction = params.get("instruction")

    # If not a direct instruction, construct one from other params
    if not instruction:
        url = params.get("url", "")
        data_desc = params.get("data_description", "")
        form_data = params.get("form_data", {})
        submit = params.get("submit", True)

        if data_desc:
            instruction = f"Go to {url} and extract {data_desc}"
        elif form_data:
            fields = ", ".join([f"{k}: {v}" for k, v in form_data.items()])
            instruction = f"Go to {url}, fill the form with these values: {fields}"
            if submit:
                instruction += ", then submit the form"
        else:
            instruction = f"Go to {url}"

    # Execute via the existing browser agent
    result = await execute_browser_instruction(instruction, context)

    return result


def register_browser_tools(manager: MCPManager) -> None:
    """Register all browser tools with the MCP manager."""
    tools = get_browser_tools()

    for tool in tools:
        manager.register_internal_tool(tool, handle_browser_tool)
