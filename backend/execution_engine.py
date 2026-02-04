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
        Also supports dot notation for nested access: ${step_1.name}, ${step_1.university}
        """
        import re

        if isinstance(value, str):
            pattern = r'\$\{\{([^}]+)\}\}|\$\{([^}]+)\}'
            matches = re.findall(pattern, value)

            for match in matches:
                match = match[0] or match[1]
                resolved_value = None
                
                # Check for dot notation (e.g., step_1.name, step_1.university)
                if "." in match:
                    parts = match.split(".", 1)
                    base_ref = parts[0]
                    property_path = parts[1]
                    
                    # Resolve the base reference first
                    base_value = None
                    if base_ref in self.context:
                        base_value = self.context[base_ref]
                    elif base_ref.startswith("step_"):
                        try:
                            step_idx = int(base_ref.split("_")[1])
                            for node_id, idx in self.step_index_map.items():
                                if idx == step_idx and node_id in self.context:
                                    base_value = self.context[node_id]
                                    break
                        except (ValueError, IndexError):
                            pass
                    
                    # Now access the nested property
                    if base_value is not None:
                        resolved_value = self._get_nested_value(base_value, property_path)

                    # Fallback: if the requested step index doesn't contain the field, scan other step outputs.
                    # This helps when templates reference the wrong step number (e.g., professor info is in step_0
                    # but the template uses ${step_1.name}).
                    if resolved_value is None and base_ref.startswith("step_"):
                        found = None
                        for k, v in self.context.items():
                            if not (isinstance(k, str) and k.startswith("step_")):
                                continue
                            candidate = self._get_nested_value(v, property_path)
                            if candidate is None:
                                continue
                            if found is not None and candidate != found:
                                # Ambiguous; don't guess.
                                found = None
                                break
                            found = candidate
                        if found is not None:
                            resolved_value = found
                else:
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
                        value = value.replace("${{" + match + "}}", resolved_value)
                    else:
                        # If the entire value is just the reference, return the resolved value directly
                        if value == f"${{{match}}}" or value == "${{" + match + "}}":
                            value = resolved_value
                        else:
                            # Otherwise, convert to string for interpolation
                            value = value.replace(f"${{{match}}}", str(resolved_value))
                            value = value.replace("${{" + match + "}}", str(resolved_value))

            return value
        elif isinstance(value, dict):
            return {k: self._resolve_references(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_references(v) for v in value]
        return value

    def _get_nested_value(self, obj: Any, property_path: str) -> Any:
        """
        Get a nested value from an object using dot notation.
        E.g., _get_nested_value({"a": {"b": 1}}, "a.b") returns 1
        """
        if obj is None:
            return None
        
        # If obj is a string, try to parse it as JSON first
        if isinstance(obj, str):
            raw = obj.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                if len(parts) >= 3:
                    raw = parts[1]
                    if "\n" in raw:
                        raw = raw.split("\n", 1)[1]
                    raw = raw.strip()

            # Try to extract the most likely JSON payload from a larger string
            candidate = raw
            first_curly = raw.find("{")
            last_curly = raw.rfind("}")
            first_square = raw.find("[")
            last_square = raw.rfind("]")
            if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
                candidate = raw[first_curly : last_curly + 1]
            elif first_square != -1 and last_square != -1 and last_square > first_square:
                candidate = raw[first_square : last_square + 1]

            import json
            try:
                obj = json.loads(candidate)
            except (json.JSONDecodeError, TypeError):
                # Some tools/LLMs return python-literal dicts (single quotes). Try parsing safely.
                try:
                    import ast
                    obj = ast.literal_eval(candidate)
                except (ValueError, SyntaxError):
                    return None
        
        parts = property_path.split(".")
        current = obj
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # Try to access by index
                try:
                    idx = int(part)
                    current = current[idx] if 0 <= idx < len(current) else None
                except (ValueError, IndexError):
                    return None
            else:
                return None
            
            if current is None:
                return None
        
        return current

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
                        print(f"[WorkflowExecutor] Tool {tool_name} failed: {mcp_result.get('error')}")

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

                # Format input data clearly for the LLM
                context_parts = []
                for k, v in inputs.items():
                    # Get step index for this node if available
                    step_label = f"Step {self.step_index_map.get(k, k)}" if k in self.step_index_map else k
                    context_parts.append(f"=== {step_label} Output ===\n{v}")
                context_str = "\n\n".join(context_parts)
                
                print(f"\n{'='*80}")
                print(f"[AI Transform] Context String for Email Generation:")
                print(f"{'='*80}")
                print(context_str)
                print(f"{'='*80}\n")
                
                system_prompt = """You are a helpful AI assistant that transforms and processes data.

CRITICAL RULES - FOLLOW EXACTLY:
1. NEVER use placeholders: [Professor Name], [Time Slot 1], etc.
2. NEVER use template syntax: ${step_1.name}, ${variable}, etc.
3. Extract ACTUAL values from the input data and write them directly
4. For JSON data: Parse it and extract the real field values
5. For calendar times: Convert ISO timestamps to readable format like "Monday, February 3 at 9:00 AM"
6. Output plain text only - no JSON, no markdown, no code blocks, no template variables
7. Output ONLY the email body text. Do NOT add preamble like "Okay, here's a draft".
8. Do NOT include a "Subject:" line in the body. Start directly with the greeting (e.g., "Dear ...").
9. Write from the sender's perspective in first person ("I", "my", "I'd like to").

WRONG EXAMPLES (DO NOT DO THIS):
❌ "${step_1.name}" - NEVER use template syntax
❌ "[Professor Name]" - NEVER use brackets
❌ "2026-02-03T09:00:00-05:00" - NEVER use raw ISO timestamps

CORRECT EXAMPLES:
✅ "Dr. John Smith" - Extract the actual name
✅ "Monday, February 3 at 9:00 AM" - Format the datetime
✅ "Stanford University" - Use the actual university name"""

                prompt = f"""INPUT DATA:
{context_str}

TASK: {instruction}

CRITICAL INSTRUCTIONS:
1. Read the input data above carefully
2. If there is JSON, parse it to extract actual values (names, universities, research topics, dates, etc.)
3. For calendar events in JSON with "start" field like "2026-02-03T09:00:00-05:00":
   - Parse the date and time
   - Format as readable text: "Monday, February 3 at 9:00 AM"
4. Write your response using ONLY the actual extracted values
5. DO NOT output any template variables like ${{...}} or placeholders like [...]
6. Write naturally as if you're a real person composing the message

Extract the actual data from above and complete the task now:"""

                # Retry with exponential backoff for rate limits
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        response = await client.aio.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                temperature=0.7,
                                system_instruction=system_prompt
                            )
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
