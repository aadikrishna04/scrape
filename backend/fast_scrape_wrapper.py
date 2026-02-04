"""
Fast Scrape MCP Wrapper - Exposes fast HTTP scraping as MCP-compatible tool
"""
from typing import Dict, Any, Optional

from mcp_manager import MCPManager, MCPTool
from fast_scrape import fast_scrape


def get_fast_scrape_tools() -> list[MCPTool]:
    """Return fast scrape tool in MCP format."""
    return [
        MCPTool(
            name="scrape.fast",
            server_name="scrape",
            original_name="fast",
            display_name="Fast Web Scrape",
            description="Fast HTTP-based web scraping with AI extraction. 10x faster than browser automation. Use for static websites that don't require JavaScript rendering or authentication. Supports pagination.",
            input_schema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape"
                    },
                    "extract": {
                        "type": "string",
                        "description": "What information to extract from the page"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum pages to scrape if pagination is detected (default: 1, max: 10)",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["url", "extract"]
            },
            category="scrape"
        ),
    ]


async def handle_fast_scrape_tool(
    params: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Handle fast scrape tool calls.
    """
    url = params.get("url", "")
    extract_prompt = params.get("extract", "")
    max_pages = min(params.get("max_pages", 1), 10)

    if not url:
        return {
            "success": False,
            "error": "No URL provided. Please provide a URL to scrape."
        }

    if not extract_prompt:
        return {
            "success": False,
            "error": "No extraction prompt provided. Please specify what to extract."
        }

    result = await fast_scrape(url, extract_prompt, max_pages=max_pages)

    if result.get("success"):
        return {
            "success": True,
            "result": result.get("data", ""),
            "pages_scraped": result.get("pages_scraped", 1),
            "url": url
        }
    else:
        return {
            "success": False,
            "error": result.get("error", "Scraping failed")
        }


def register_fast_scrape_tools(manager: MCPManager) -> None:
    """Register fast scrape tool with the MCP manager."""
    tools = get_fast_scrape_tools()

    for tool in tools:
        manager.register_internal_tool(tool, handle_fast_scrape_tool)
