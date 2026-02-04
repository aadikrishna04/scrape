"""
Tool Wrapper - Convert MCP tools to LangChain BaseTool format
"""
from typing import Any, Dict, List, Optional, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
import json


def json_schema_to_pydantic(schema: Dict[str, Any], name: str = "ToolInput") -> Type[BaseModel]:
    """Convert JSON schema to Pydantic model for tool input validation."""
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    fields = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        description = prop_schema.get("description", "")
        default = prop_schema.get("default", ...)

        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_mapping.get(prop_type, str)

        # Handle required vs optional
        if prop_name in required:
            if default is ...:
                fields[prop_name] = (python_type, Field(description=description))
            else:
                fields[prop_name] = (python_type, Field(default=default, description=description))
        else:
            fields[prop_name] = (Optional[python_type], Field(default=None, description=description))

    # Create dynamic Pydantic model
    return create_model(name, **fields)


class MCPToolWrapper(BaseTool):
    """Wraps an MCP tool as a LangChain BaseTool for use with LLM bind_tools()."""

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None

    # Custom attributes
    mcp_tool_name: str = ""
    server_name: str = ""
    user_id: Optional[str] = None
    _mcp_manager: Any = None

    def __init__(
        self,
        mcp_tool_name: str,
        server_name: str,
        display_name: str,
        description: str,
        input_schema: Dict[str, Any],
        mcp_manager: Any,
        user_id: Optional[str] = None,
    ):
        # Create args schema from input_schema
        args_schema = None
        if input_schema and input_schema.get("properties"):
            try:
                schema_name = f"{display_name.replace(' ', '')}Input"
                args_schema = json_schema_to_pydantic(input_schema, schema_name)
            except Exception:
                pass

        super().__init__(
            name=mcp_tool_name,
            description=description or f"Tool: {display_name}",
            args_schema=args_schema,
        )
        self.mcp_tool_name = mcp_tool_name
        self.server_name = server_name
        self.user_id = user_id
        self._mcp_manager = mcp_manager

    def _run(self, **kwargs) -> str:
        """Synchronous run - not supported, use async."""
        raise NotImplementedError("Use async version (_arun)")

    async def _arun(self, **kwargs) -> str:
        """Execute the MCP tool asynchronously."""
        try:
            result = await self._mcp_manager.call_tool(
                self.mcp_tool_name,
                kwargs,
                context=None,
                user_id=self.user_id,
            )

            if result.get("success"):
                return result.get("result", "Success")
            else:
                return f"Error: {result.get('error', 'Unknown error')}"
        except Exception as e:
            return f"Error executing tool: {str(e)}"


def create_langchain_tools_from_mcp(
    mcp_manager: Any,
    user_id: Optional[str] = None,
) -> List[BaseTool]:
    """
    Convert all available MCP tools to LangChain BaseTool instances.

    Args:
        mcp_manager: The MCP manager instance
        user_id: Optional user ID for per-user tools (e.g., GitHub OAuth)

    Returns:
        List of LangChain BaseTool instances
    """
    tools = []
    mcp_tools = mcp_manager.get_all_tools(user_id=user_id)

    for mcp_tool in mcp_tools:
        try:
            wrapper = MCPToolWrapper(
                mcp_tool_name=mcp_tool.name,
                server_name=mcp_tool.server_name,
                display_name=mcp_tool.display_name,
                description=mcp_tool.description,
                input_schema=mcp_tool.input_schema,
                mcp_manager=mcp_manager,
                user_id=user_id,
            )
            tools.append(wrapper)
        except Exception as e:
            print(f"Failed to wrap tool {mcp_tool.name}: {e}")

    return tools


def get_tool_descriptions(tools: List[BaseTool]) -> str:
    """Get formatted descriptions of all tools for the agent prompt."""
    descriptions = []
    for tool in tools:
        desc = f"- **{tool.name}**: {tool.description}"
        if tool.args_schema:
            schema = tool.args_schema.model_json_schema()
            props = schema.get("properties", {})
            required = set(schema.get("required", []))

            params = []
            for name, prop in props.items():
                req_marker = " (required)" if name in required else ""
                param_desc = prop.get("description", "")
                params.append(f"    - `{name}`{req_marker}: {param_desc}")

            if params:
                desc += "\n" + "\n".join(params)

        descriptions.append(desc)

    return "\n".join(descriptions)
