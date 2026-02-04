"""
Agentic Execution Engine - Executes workflows using MCP tools
Supports both traditional workflow execution and agentic orchestration.
"""
from typing import Dict, Any, List, Optional, Callable
import os
import json

from mcp_manager import get_mcp_manager


def fill_github_defaults_at_runtime(tool_name: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fill in sensible defaults for GitHub tool parameters at runtime.
    This is a fallback to ensure required params are always present.

    Args:
        tool_name: The MCP tool name (e.g., "github.create_or_update_file")
        params: The current parameters
        context: Execution context with outputs from previous nodes

    Returns:
        Updated parameters with defaults filled in
    """
    if not tool_name.startswith("github."):
        return params

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

        # Try to infer repo from context (previous node outputs)
        if "repo" not in params or not params["repo"]:
            # Look for repo info in context from previous create_repository calls
            for node_output in context.values():
                if isinstance(node_output, str):
                    # Check if it contains repo creation info
                    if "created" in node_output.lower() and "repository" in node_output.lower():
                        # Try to extract repo name from output
                        import re
                        match = re.search(r"'([^']+)'|\"([^\"]+)\"", node_output)
                        if match:
                            params["repo"] = match.group(1) or match.group(2)
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


class WorkflowExecutor:
    """Executes agentic workflows with sequential node processing."""

    def __init__(self, workflow: Dict[str, Any], user_id: Optional[str] = None, stream_callback: Optional[Callable] = None):
        self.workflow = workflow
        self.nodes = {node["id"]: node for node in workflow.get("nodes", [])}
        self.edges = workflow.get("edges", [])
        self.context = {}  # Stores outputs from each node
        self.step_index_map = {}  # Maps node_id to step_N for reference resolution
        self.execution_log = []
        self.mcp_manager = get_mcp_manager()
        self.user_id = user_id
        self.stream_callback = stream_callback

    async def _notify_status(self, node_id: str, status: str):
        """Notify stream callback of node status change."""
        print(f"[WorkflowExecutor] Notifying status: node_id={node_id}, status={status}")
        if self.stream_callback:
            await self.stream_callback({
                "type": "node_status_change",
                "node_id": node_id,
                "status": status
            })

    def _resolve_references(self, value: Any) -> Any:
        """
        Recursively resolve ${step_N} and ${node_id} references in values.
        Supports both step-based references (${step_0}) and node_id references (${node-1}).
        """
        import re

        if isinstance(value, str):
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)

            for match in matches:
                resolved_value = None

                # First, try direct lookup by node_id
                if match in self.context:
                    resolved_value = self.context[match]
                # Then, try step_N format
                elif match.startswith("step_"):
                    try:
                        step_idx = int(match.split("_")[1])
                        # Find the node_id for this step index
                        for node_id, idx in self.step_index_map.items():
                            if idx == step_idx and node_id in self.context:
                                resolved_value = self.context[node_id]
                                break
                    except (ValueError, IndexError):
                        pass

                if resolved_value is not None:
                    if isinstance(resolved_value, str):
                        value = value.replace(f"${{{match}}}", resolved_value)
                    else:
                        # If the entire value is just the reference, return the resolved value directly
                        if value == f"${{{match}}}":
                            value = resolved_value
                        else:
                            # Otherwise, convert to string for interpolation
                            value = value.replace(f"${{{match}}}", str(resolved_value))

            return value
        elif isinstance(value, dict):
            return {k: self._resolve_references(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_references(v) for v in value]
        return value

    def topological_sort(self) -> List[str]:
        """
        Topologically sort nodes based on edges.
        Returns ordered list of node IDs.
        """
        # Build adjacency list
        graph = {node_id: [] for node_id in self.nodes}
        in_degree = {node_id: 0 for node_id in self.nodes}

        for edge in self.edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in graph and target in graph:
                graph[source].append(target)
                in_degree[target] += 1

        # Kahn's algorithm
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_nodes = []

        while queue:
            current = queue.pop(0)
            sorted_nodes.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_nodes) != len(self.nodes):
            raise ValueError("Workflow contains a cycle - cannot execute")

        return sorted_nodes

    async def execute_node(self, node_id: str) -> Dict[str, Any]:
        """
        Execute a single node based on its type.

        Returns:
            Dict with execution result
        """
        node = self.nodes[node_id]
        node_type = node.get("type", "mcp_tool")

        # Gather inputs from predecessor nodes
        inputs = self._get_node_inputs(node_id)

        result = {
            "node_id": node_id,
            "type": node_type,
            "status": "pending",
            "label": node.get("label", node.get("data", {}).get("label", node_id))
        }

        # Notify that this node is now executing
        await self._notify_status(node_id, "executing")

        try:
            if node_type == "mcp_tool":
                # Execute via MCP Manager
                tool_name = node.get("tool_name", node.get("data", {}).get("tool_name"))
                params = node.get("params", node.get("data", {}).get("params", {}))

                if not tool_name:
                    result["status"] = "error"
                    result["error"] = "No tool_name specified"
                else:
                    # Resolve ${step_N} and ${node_id} references in params
                    params = self._resolve_references(params)
                    print(f"[WorkflowExecutor] Resolved params for {tool_name}: {str(params)[:500]}")

                    # Fill in smart defaults for GitHub tools at runtime
                    params = fill_github_defaults_at_runtime(tool_name, params, self.context)
                    mcp_result = await self.mcp_manager.call_tool(tool_name, params, inputs, user_id=self.user_id)
                    result["status"] = "success" if mcp_result.get("success") else "failed"
                    result["output"] = mcp_result.get("result", mcp_result.get("error", "No output"))

                    if mcp_result.get("success"):
                        self.context[node_id] = mcp_result.get("result")
                    else:
                        result["error"] = mcp_result.get("error")

            elif node_type == "browser_agent":
                # Legacy browser_agent support - convert to mcp_tool call
                instruction = node.get("instruction", node.get("data", {}).get("instruction", ""))
                # Resolve references in instruction
                instruction = self._resolve_references(instruction)

                mcp_result = await self.mcp_manager.call_tool(
                    "browser.execute_instruction",
                    {"instruction": instruction},
                    inputs,
                    user_id=self.user_id
                )

                result["status"] = "success" if mcp_result.get("success") else "failed"
                result["output"] = mcp_result.get("result", mcp_result.get("error", "No output"))

                if mcp_result.get("success"):
                    self.context[node_id] = mcp_result.get("result")
                else:
                    result["error"] = mcp_result.get("error")

            elif node_type == "ai_transform":
                # AI transformation using Gemini with retry logic
                from google import genai
                from google.genai import types
                import asyncio

                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

                instruction = node.get("instruction", node.get("data", {}).get("instruction", ""))
                # Resolve references in instruction
                instruction = self._resolve_references(instruction)

                context_str = "\n".join([f"{k}: {v}" for k, v in inputs.items()])
                prompt = f"Context:\n{context_str}\n\nTransform/Process according to: {instruction}"

                # Retry with exponential backoff for rate limits
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.aio.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=prompt,
                            config=types.GenerateContentConfig(temperature=0.7)
                        )
                        result["status"] = "success"
                        result["output"] = response.text
                        self.context[node_id] = response.text
                        break
                    except Exception as e:
                        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                                await asyncio.sleep(wait_time)
                                continue
                        raise

            elif node_type == "conditional":
                # LLM-based conditional routing
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

                instruction = node.get("instruction", node.get("data", {}).get("instruction", ""))
                # Resolve references in instruction
                instruction = self._resolve_references(instruction)

                context_str = "\n".join([f"{k}: {v}" for k, v in inputs.items()])
                prompt = f"Context:\n{context_str}\n\nDecision: {instruction}\n\nRespond with ONLY 'true' or 'false'."

                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3)
                )
                decision = "true" in response.text.lower()

                result["status"] = "success"
                result["output"] = {"decision": decision}
                self.context[node_id] = {"decision": decision}

            else:
                result["status"] = "error"
                result["error"] = f"Unknown node type: {node_type}"

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)

        # Notify that this node has completed
        final_status = "success" if result["status"] == "success" else "failed"
        await self._notify_status(node_id, final_status)

        self.execution_log.append(result)
        return result

    def _get_node_inputs(self, node_id: str) -> Dict[str, Any]:
        """Get outputs from all predecessor nodes."""
        inputs = {}

        for edge in self.edges:
            if edge.get("target") == node_id:
                source_id = edge.get("source")
                if source_id in self.context:
                    inputs[source_id] = self.context[source_id]

        return inputs

    async def execute(self) -> Dict[str, Any]:
        """
        Execute entire workflow.

        Returns:
            Execution results and logs
        """
        try:
            # Get execution order
            execution_order = self.topological_sort()

            # Build step_index_map for reference resolution
            # Maps node_id -> step index (0, 1, 2, ...)
            for idx, node_id in enumerate(execution_order):
                self.step_index_map[node_id] = idx
                # Also store as step_N for direct lookup
                self.context[f"step_{idx}"] = None  # Will be populated during execution
            print(f"[WorkflowExecutor] Step index map: {self.step_index_map}")

            # Execute each node
            for node_id in execution_order:
                await self.execute_node(node_id)
                # Also update step_N reference after execution
                step_idx = self.step_index_map.get(node_id)
                if step_idx is not None and node_id in self.context:
                    self.context[f"step_{step_idx}"] = self.context[node_id]

            # Check for failures
            failed_nodes = [log for log in self.execution_log if log["status"] in ["failed", "error"]]

            return {
                "status": "completed" if not failed_nodes else "partial_failure",
                "execution_order": execution_order,
                "results": self.execution_log,
                "final_context": self.context,
                "failed_count": len(failed_nodes)
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "results": self.execution_log
            }


async def execute_workflow(workflow: Dict[str, Any], user_id: Optional[str] = None, stream_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Convenience function to execute a workflow.

    Args:
        workflow: Dict with 'nodes' and 'edges' keys
        user_id: Optional user ID for per-user integrations (e.g. GitHub OAuth)
        stream_callback: Optional callback for real-time node status updates

    Returns:
        Execution results
    """
    executor = WorkflowExecutor(workflow, user_id=user_id, stream_callback=stream_callback)
    return await executor.execute()


class AgenticWorkflowExecutor:
    """
    Agentic workflow executor that uses the agent orchestrator
    for intelligent plan-execute-observe-replan loops.
    """

    def __init__(self, goal: str, stream_callback: Optional[Callable] = None, user_id: Optional[str] = None):
        self.goal = goal
        self.stream_callback = stream_callback
        self.user_id = user_id
        self.events = []

    async def _notify_status(self, node_id: str, status: str):
        """Notify stream callback of node status change."""
        print(f"[WorkflowExecutor] Notifying status: node_id={node_id}, status={status}")
        if self.stream_callback:
            await self.stream_callback({
                "type": "node_status_change",
                "node_id": node_id,
                "status": status
            })

    async def _event_handler(self, event: Dict[str, Any]):
        """Handle events from the orchestrator."""
        self.events.append(event)
        if self.stream_callback:
            await self.stream_callback(event)

    async def execute(self) -> Dict[str, Any]:
        """
        Execute the goal using agentic orchestration.

        Returns:
            Execution results including steps, context, and final output
        """
        from agent_orchestrator import run_agent

        result = await run_agent(
            goal=self.goal,
            stream_callback=self._event_handler,
            user_id=self.user_id
        )

        return {
            "status": "completed" if result.get("success") else "failed",
            "goal": self.goal,
            "result": result.get("result"),
            "steps_executed": result.get("steps_executed", 0),
            "replans": result.get("replans", 0),
            "history": result.get("history", []),
            "context": result.get("context", {}),
            "error": result.get("error"),
            "events": self.events
        }


async def execute_agentic(
    goal: str,
    stream_callback: Optional[Callable] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute a goal using agentic orchestration.

    Args:
        goal: The user's goal to achieve
        stream_callback: Optional callback for real-time event updates
        user_id: Optional user ID for per-user integrations (Gmail, etc.)

    Returns:
        Execution results
    """
    executor = AgenticWorkflowExecutor(goal, stream_callback, user_id=user_id)
    return await executor.execute()
