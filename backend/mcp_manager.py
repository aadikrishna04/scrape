"""
MCP Manager - Manages connections to multiple MCP servers and aggregates tools
"""
import os
import asyncio
import json
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Google OAuth services that need special credentials file handling
# Note: gmail and google-calendar use @presto-ai/google-workspace-mcp which has its own OAuth flow
# Only google-drive uses our OAuth token handling
GOOGLE_SERVICES = {"google-drive"}


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    display_name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    icon: Optional[str] = None


@dataclass
class MCPTool:
    """Unified tool representation from any MCP server."""
    name: str  # Full namespaced name (e.g., "github.create_issue")
    server_name: str
    original_name: str  # Original name from server
    display_name: str
    description: str
    input_schema: Dict[str, Any]
    category: Optional[str] = None


@dataclass
class MCPServerStatus:
    """Status of an MCP server connection."""
    name: str
    display_name: str
    connected: bool
    tool_count: int
    icon: Optional[str] = None
    error: Optional[str] = None


class MCPConnection:
    """Represents a connection to a single MCP server."""

    def __init__(self, config: MCPServerConfig, user_token: Optional[str] = None):
        self.config = config
        self.user_token = user_token
        self.session: Optional[ClientSession] = None
        self.tools: List[MCPTool] = []
        self.connected = False
        self.error: Optional[str] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._temp_credentials_file: Optional[str] = None  # For Google OAuth credentials

    async def connect(self) -> bool:
        """Establish connection to the MCP server."""
        if self.config.command == "internal":
            # Internal tools (like browser) are handled separately
            self.connected = True
            return True

        try:
            # Start with current environment and add/override with config
            env = dict(os.environ)

            # Handle Google OAuth services specially - they need credentials files
            if self.config.name in GOOGLE_SERVICES and self.user_token:
                try:
                    # Parse the stored token JSON
                    token_data = json.loads(self.user_token)

                    # Create a temp directory for credentials
                    temp_dir = tempfile.mkdtemp(prefix=f'google_mcp_{self.config.name}_')
                    self._temp_credentials_file = temp_dir  # Store dir path for cleanup

                    # Write OAuth client credentials file (gcp-oauth.keys.json format)
                    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
                    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")

                    credentials = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "redirect_uris": ["http://localhost"]
                        }
                    }

                    creds_path = os.path.join(temp_dir, "gcp-oauth.keys.json")
                    with open(creds_path, 'w') as f:
                        json.dump(credentials, f)

                    # Write the token file (credentials.json format expected by Google libraries)
                    token_file_data = {
                        "token": token_data.get("access_token"),
                        "refresh_token": token_data.get("refresh_token"),
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scopes": token_data.get("scopes", []),
                        "expiry": token_data.get("expiry", "")
                    }

                    token_path = os.path.join(temp_dir, "credentials.json")
                    with open(token_path, 'w') as f:
                        json.dump(token_file_data, f)

                    # Set various env vars that different MCP servers might use
                    env["GOOGLE_OAUTH_CREDENTIALS"] = creds_path
                    env["GDRIVE_CREDENTIALS_PATH"] = creds_path
                    env["GOOGLE_CREDENTIALS_PATH"] = temp_dir
                    env["GOOGLE_TOKEN_PATH"] = token_path

                    # Also set individual token values for servers that use them directly
                    env["GOOGLE_ACCESS_TOKEN"] = token_data.get("access_token", "")
                    env["GOOGLE_REFRESH_TOKEN"] = token_data.get("refresh_token", "")

                    print(f"[MCP] Created Google credentials for {self.config.name} in {temp_dir}")

                except (json.JSONDecodeError, KeyError) as e:
                    self.error = f"Invalid Google OAuth token format: {e}"
                    return False

            # Resolve and add config environment variables
            for key, value in self.config.env.items():
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    # Skip if already set (e.g., by Google OAuth handling above)
                    if key in env and env[key]:
                        continue
                    # First check if we have a user-provided token
                    # Apply user_token to ANY token-based env var (not just specific ones)
                    if self.user_token:
                        env[key] = self.user_token
                    else:
                        env[key] = os.getenv(env_var, "")
                else:
                    env[key] = value

            # Create server parameters
            server_params = StdioServerParameters(
                command=self.config.command,
                args=self.config.args,
                env=env
            )

            # Create exit stack for cleanup
            self._exit_stack = AsyncExitStack()

            # Connect via stdio
            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport

            # Create session
            self.session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Initialize the session
            await self.session.initialize()

            # Load available tools
            await self._load_tools()

            self.connected = True
            self.error = None
            return True

        except Exception as e:
            self.error = str(e)
            self.connected = False
            print(f"[MCP] Failed to connect to {self.config.name}: {e}")
            # Clean up exit stack on failure
            if self._exit_stack:
                try:
                    await self._exit_stack.aclose()
                except Exception:
                    pass  # Ignore cleanup errors
                self._exit_stack = None
            # Clean up temp credentials dir/file on failure
            if self._temp_credentials_file:
                try:
                    if os.path.isdir(self._temp_credentials_file):
                        shutil.rmtree(self._temp_credentials_file)
                    else:
                        os.unlink(self._temp_credentials_file)
                except OSError:
                    pass
                self._temp_credentials_file = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self.session = None
        self.tools = []
        self.connected = False

        # Clean up temp credentials dir/file for Google services
        if self._temp_credentials_file:
            try:
                if os.path.isdir(self._temp_credentials_file):
                    shutil.rmtree(self._temp_credentials_file)
                else:
                    os.unlink(self._temp_credentials_file)
            except OSError:
                pass
            self._temp_credentials_file = None

    async def _load_tools(self) -> None:
        """Load available tools from the server."""
        if not self.session:
            return

        try:
            result = await self.session.list_tools()
            self.tools = []

            for tool in result.tools:
                mcp_tool = MCPTool(
                    name=f"{self.config.name}.{tool.name}",
                    server_name=self.config.name,
                    original_name=tool.name,
                    display_name=tool.name.replace("_", " ").title(),
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                )
                self.tools.append(mcp_tool)

        except Exception as e:
            print(f"Error loading tools from {self.config.name}: {e}")

    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on this server."""
        if not self.session or not self.connected:
            return {"success": False, "error": "Not connected"}

        try:
            result = await self.session.call_tool(tool_name, params)

            # Extract content from result
            content = ""
            if hasattr(result, 'content') and result.content:
                for item in result.content:
                    if hasattr(item, 'text'):
                        content += item.text

            return {
                "success": True,
                "result": content,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class MCPManager:
    """Manages multiple MCP server connections."""

    def __init__(self):
        self.connections: Dict[str, MCPConnection] = {}  # server_name -> connection (global)
        self._user_connections: Dict[Tuple[str, str], MCPConnection] = {}  # (server_name, user_id) -> connection
        self.configs: Dict[str, MCPServerConfig] = {}
        self._internal_tools: List[MCPTool] = []
        self._internal_handlers: Dict[str, Any] = {}
        self._user_tokens: Dict[str, str] = {}  # Store user-provided tokens (legacy)
        # Resolver: (user_id, server_name) -> access_token or None (e.g. from DB for GitHub OAuth)
        self._integration_token_resolver: Optional[Callable[[str, str], Optional[str]]] = None
        # Updater: (user_id, server_name, token_data) -> bool (to save refreshed tokens)
        self._integration_token_updater: Optional[Callable[[str, str, str], bool]] = None

    def set_integration_token_resolver(self, resolver: Callable[[str, str], Optional[str]]) -> None:
        """Set a callable to resolve per-user tokens for integrations (e.g. GitHub OAuth from DB)."""
        self._integration_token_resolver = resolver

    def set_integration_token_updater(self, updater: Callable[[str, str, str], bool]) -> None:
        """Set a callable to update per-user tokens after refresh."""
        self._integration_token_updater = updater

    def register_internal_tool(
        self,
        tool: MCPTool,
        handler: Any
    ) -> None:
        """Register an internal tool (like browser) that doesn't use MCP protocol."""
        self._internal_tools.append(tool)
        self._internal_handlers[tool.name] = handler

    def add_server_config(self, config: MCPServerConfig) -> None:
        """Add a server configuration."""
        self.configs[config.name] = config

    def set_user_token(self, server_name: str, token: str) -> None:
        """Store a user-provided token for a server."""
        self._user_tokens[server_name] = token

    def get_user_token(self, server_name: str) -> Optional[str]:
        """Get a stored user token for a server."""
        return self._user_tokens.get(server_name)

    def clear_user_token(self, server_name: str) -> None:
        """Clear a stored user token."""
        if server_name in self._user_tokens:
            del self._user_tokens[server_name]

    async def connect_server(self, name: str, token: Optional[str] = None) -> bool:
        """Connect to a specific MCP server."""
        if name not in self.configs:
            return False

        config = self.configs[name]

        # Skip internal servers
        if config.command == "internal":
            return True

        # Store token if provided
        if token:
            self.set_user_token(name, token)

        # Get stored token
        stored_token = self.get_user_token(name)

        connection = MCPConnection(config, user_token=stored_token)
        success = await connection.connect()

        if success:
            self.connections[name] = connection

        return success

    async def disconnect_server(self, name: str) -> None:
        """Disconnect from a specific MCP server (global connection only)."""
        if name in self.connections:
            await self.connections[name].disconnect()
            del self.connections[name]

    async def disconnect_server_for_user(self, name: str, user_id: str) -> None:
        """Disconnect a per-user MCP server connection (e.g. GitHub for a user)."""
        key = (name, user_id)
        if key in self._user_connections:
            await self._user_connections[key].disconnect()
            del self._user_connections[key]

    async def connect_all_enabled(self) -> Dict[str, bool]:
        """Connect to all enabled servers."""
        results = {}
        for name, config in self.configs.items():
            if config.enabled:
                results[name] = await self.connect_server(name)
        return results

    async def ensure_user_github_connected(self, user_id: str) -> None:
        """If the user has GitHub OAuth connected, ensure the GitHub MCP server is connected for them so tools show up."""
        await self.ensure_user_integration_connected(user_id, "github")

    async def ensure_user_integration_connected(self, user_id: str, server_name: str) -> bool:
        """
        If the user has an integration token, ensure the MCP server is connected for them.
        Returns True if connected successfully, False otherwise.
        """
        if not self._integration_token_resolver:
            return False
        token = self._integration_token_resolver(user_id, server_name)
        if not token or server_name not in self.configs:
            return False
        key = (server_name, user_id)
        if key in self._user_connections and self._user_connections[key].connected:
            return True
        config = self.configs[server_name]
        conn = MCPConnection(config, user_token=token)
        success = await conn.connect()
        if success:
            self._user_connections[key] = conn
            print(f"[MCP] Connected {server_name} for user {user_id[:8]}... ({len(conn.tools)} tools)")
        else:
            print(f"[MCP] Failed to connect {server_name} for user {user_id[:8]}...: {conn.error}")
        return success

    async def ensure_all_user_integrations_connected(self, user_id: str) -> Dict[str, bool]:
        """
        Connect all integrations that the user has tokens for.
        Returns dict of server_name -> success.
        """
        if not self._integration_token_resolver:
            return {}

        results = {}
        for server_name in self.configs.keys():
            # Skip internal servers
            if self.configs[server_name].command == "internal":
                continue
            # Check if user has a token for this server
            token = self._integration_token_resolver(user_id, server_name)
            if token:
                results[server_name] = await self.ensure_user_integration_connected(user_id, server_name)
        return results

    async def connect_server_for_user(self, server_name: str, user_id: str, token: str) -> bool:
        """
        Connect an MCP server for a specific user with the given token.
        This is used when a user connects an integration via the UI.
        """
        if server_name not in self.configs:
            return False

        config = self.configs[server_name]
        if config.command == "internal":
            return True

        key = (server_name, user_id)

        # Disconnect existing connection if any
        if key in self._user_connections:
            await self._user_connections[key].disconnect()
            del self._user_connections[key]

        # Create new connection with the provided token
        conn = MCPConnection(config, user_token=token)
        success = await conn.connect()
        if success:
            self._user_connections[key] = conn
        return success

    def get_all_tools(self, user_id: Optional[str] = None) -> List[MCPTool]:
        """Get all available tools. If user_id is set, include per-user tools for that user only."""
        tools = list(self._internal_tools)

        # Add tools from global connections
        for connection in self.connections.values():
            if connection.connected:
                tools.extend(connection.tools)

        # Add tools from per-user connections
        if user_id:
            seen_servers = set()
            for (server_name, uid), connection in self._user_connections.items():
                if uid == user_id and connection.connected:
                    # Avoid duplicates if server is also in global connections
                    if server_name not in seen_servers:
                        tools.extend(connection.tools)
                        seen_servers.add(server_name)

        # When user_id is None, do not include per-user connections (avoid mixing users / leaking tool names)
        return tools

    def get_tools_by_server(self, server_name: str, user_id: Optional[str] = None) -> List[MCPTool]:
        """Get tools from a specific server (optionally per-user for GitHub)."""
        if server_name == "internal":
            return list(self._internal_tools)

        if user_id and (server_name, user_id) in self._user_connections:
            return self._user_connections[(server_name, user_id)].tools
        if server_name in self.connections:
            return self.connections[server_name].tools

        return []

    def get_server_statuses(self, user_id: Optional[str] = None) -> List[MCPServerStatus]:
        """Get status of all configured servers. Pass user_id to include user-specific connections."""
        statuses = []

        for name, config in self.configs.items():
            if config.command == "internal":
                # Internal tools are always "connected"
                internal_count = len([t for t in self._internal_tools if t.server_name == name])
                statuses.append(MCPServerStatus(
                    name=name,
                    display_name=config.display_name,
                    connected=True,
                    tool_count=internal_count,
                    icon=config.icon,
                ))
            elif name in self.connections:
                conn = self.connections[name]
                statuses.append(MCPServerStatus(
                    name=name,
                    display_name=config.display_name,
                    connected=conn.connected,
                    tool_count=len(conn.tools),
                    icon=config.icon,
                    error=conn.error,
                ))
            elif user_id and (name, user_id) in self._user_connections:
                # Check user-specific connections
                conn = self._user_connections[(name, user_id)]
                statuses.append(MCPServerStatus(
                    name=name,
                    display_name=config.display_name,
                    connected=conn.connected,
                    tool_count=len(conn.tools),
                    icon=config.icon,
                    error=conn.error,
                ))
            else:
                statuses.append(MCPServerStatus(
                    name=name,
                    display_name=config.display_name,
                    connected=False,
                    tool_count=0,
                    icon=config.icon,
                ))

        return statuses

    def get_tool_schema(self, tool_name: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get the input schema for a specific tool. Pass user_id to resolve per-user (e.g. GitHub) tools."""
        for tool in self.get_all_tools(user_id=user_id):
            if tool.name == tool_name:
                return tool.input_schema
        return None

    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call a tool by its full namespaced name. Pass user_id to use per-user tokens."""
        # Check if it's an internal tool
        if tool_name in self._internal_handlers:
            handler = self._internal_handlers[tool_name]
            # Inject user_id and token resolver into context for internal tools
            enriched_context = dict(context or {})
            if user_id:
                enriched_context["user_id"] = user_id
            if self._integration_token_resolver:
                enriched_context["_token_resolver"] = self._integration_token_resolver
            if self._integration_token_updater:
                enriched_context["_token_updater"] = self._integration_token_updater
            return await handler(params, enriched_context)

        # Parse server name from tool name
        if "." not in tool_name:
            return {"success": False, "error": f"Invalid tool name: {tool_name}"}

        server_name, original_tool_name = tool_name.split(".", 1)

        # Per-user connection: resolve token and get or create connection
        if user_id and self._integration_token_resolver:
            token = self._integration_token_resolver(user_id, server_name)
            if token:
                key = (server_name, user_id)
                if key not in self._user_connections:
                    if server_name not in self.configs:
                        return {"success": False, "error": f"Server '{server_name}' not configured"}
                    config = self.configs[server_name]
                    conn = MCPConnection(config, user_token=token)
                    success = await conn.connect()
                    if not success:
                        return {"success": False, "error": conn.error or f"Failed to connect to {server_name}"}
                    self._user_connections[key] = conn
                return await self._user_connections[key].call_tool(original_tool_name, params)
            else:
                # User doesn't have this integration connected
                display_name = self.configs.get(server_name, {})
                if hasattr(display_name, 'display_name'):
                    display_name = display_name.display_name
                else:
                    display_name = server_name.replace("-", " ").title()
                return {"success": False, "error": f"Connect {display_name} in Settings to use this tool."}

        # Global connection (fallback for non-authenticated requests)
        if server_name in self.connections:
            return await self.connections[server_name].call_tool(original_tool_name, params)

        return {"success": False, "error": f"Server not connected: {server_name}. Connect it in Settings."}

    async def shutdown(self) -> None:
        """Disconnect from all servers (global and per-user)."""
        for name in list(self.connections.keys()):
            await self.disconnect_server(name)
        for key in list(self._user_connections.keys()):
            await self._user_connections[key].disconnect()
        self._user_connections.clear()


# Global instance
_mcp_manager: Optional[MCPManager] = None


def get_mcp_manager() -> MCPManager:
    """Get the global MCP manager instance."""
    global _mcp_manager
    if _mcp_manager is None:
        _mcp_manager = MCPManager()
    return _mcp_manager


async def initialize_mcp_manager() -> MCPManager:
    """Initialize the MCP manager with default configs and internal tools."""
    from mcp_config import get_default_configs
    from browser_mcp_wrapper import register_browser_tools
    from fast_scrape_wrapper import register_fast_scrape_tools
    from google_workspace_tools import register_google_workspace_tools
    from ai_tools import register_ai_tools

    manager = get_mcp_manager()

    # Add default server configs
    for config in get_default_configs():
        manager.add_server_config(config)

    # Register internal tools (browser)
    register_browser_tools(manager)

    # Register internal tools (fast scrape)
    register_fast_scrape_tools(manager)

    # Register internal tools (Google Workspace: Gmail, Calendar, Drive)
    register_google_workspace_tools(manager)

    # Register internal tools (AI processing)
    register_ai_tools(manager)

    # Connect to enabled servers
    await manager.connect_all_enabled()

    return manager
