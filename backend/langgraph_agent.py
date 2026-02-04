"""
LangGraph Agent - Core agentic system for Sentric
"""
import os
import json
import uuid
from typing import Any, Dict, List, Optional, Annotated, Literal, TypedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from tool_wrapper import create_langchain_tools_from_mcp, get_tool_descriptions


# Type definitions
class AgentState(TypedDict, total=False):
    """State for the LangGraph agent."""
    messages: Annotated[List[BaseMessage], add_messages]
    workflow_nodes: List[Dict]
    workflow_edges: List[Dict]
    execution_context: Dict[str, Any]
    current_plan: Optional[Dict]
    plan_step_index: int
    replan_count: int
    user_id: Optional[str]
    project_id: str
    intent: Optional[str]
    streaming_callback: Any


@dataclass
class PlanStep:
    """A single step in the execution plan."""
    tool_name: str
    params: Dict[str, Any]
    description: str
    depends_on: List[int] = field(default_factory=list)


@dataclass
class AgentPlan:
    """The agent's execution plan."""
    goal: str
    steps: List[PlanStep]
    reasoning: str


# Intent classification
INTENT_CONVERSATION = "conversation"
INTENT_WORKFLOW_CREATE = "workflow_create"
INTENT_WORKFLOW_MODIFY = "workflow_modify"
INTENT_EXECUTE = "execute"
INTENT_QUESTION = "question"


def create_llm(temperature: float = 0.1) -> ChatGoogleGenerativeAI:
    """Create a Gemini LLM instance. Uses GOOGLE_API_KEY or GEMINI_API_KEY."""
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=api_key,
        temperature=temperature,
        convert_system_message_to_human=True,
    )


class LangGraphAgent:
    """
    LangGraph-based agent for Sentric.

    Nodes:
    - router: Classify user intent
    - respond: Handle conversation/questions
    - plan: Create execution plan
    - build_workflow: Generate workflow nodes/edges
    - execute: Execute current plan step
    - observe: Check execution results
    - replan: Adjust plan based on observations
    """

    def __init__(self, mcp_manager: Any, user_id: Optional[str] = None):
        self.mcp_manager = mcp_manager
        self.user_id = user_id
        self.llm = create_llm()
        self.tools = create_langchain_tools_from_mcp(mcp_manager, user_id)
        self.tool_descriptions = get_tool_descriptions(self.tools)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        # Create graph with state schema
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("router", self._router_node)
        graph.add_node("respond", self._respond_node)
        graph.add_node("plan", self._plan_node)
        graph.add_node("build_workflow", self._build_workflow_node)
        graph.add_node("execute", self._execute_node)
        graph.add_node("observe", self._observe_node)
        graph.add_node("replan", self._replan_node)

        # Set entry point
        graph.set_entry_point("router")

        # Add conditional edges from router
        graph.add_conditional_edges(
            "router",
            self._route_intent,
            {
                INTENT_CONVERSATION: "respond",
                INTENT_QUESTION: "respond",
                INTENT_WORKFLOW_CREATE: "plan",
                INTENT_WORKFLOW_MODIFY: "plan",
                INTENT_EXECUTE: "plan",  # Execute also needs planning first
            }
        )

        # respond -> END
        graph.add_edge("respond", END)

        # plan -> build_workflow (always build the visual workflow)
        graph.add_edge("plan", "build_workflow")

        # build_workflow -> conditional (END or execute based on intent)
        graph.add_conditional_edges(
            "build_workflow",
            self._route_after_build,
            {
                "execute": "execute",
                "end": END,
            }
        )

        # execute -> observe
        graph.add_edge("execute", "observe")

        # observe -> conditional (END or replan)
        graph.add_conditional_edges(
            "observe",
            self._should_continue_or_replan,
            {
                "continue": "execute",
                "replan": "replan",
                "end": END,
            }
        )

        # replan -> execute
        graph.add_edge("replan", "execute")

        return graph.compile()

    def _route_intent(self, state: AgentState) -> str:
        """Route based on classified intent."""
        return state.get("intent", INTENT_CONVERSATION)

    def _route_after_build(self, state: AgentState) -> Literal["execute", "end"]:
        """After building workflow, always end here - user must manually click Run Workflow."""
        # Never auto-execute from chat - let user review and click Run Workflow manually
        return "end"

    def _should_continue_or_replan(self, state: AgentState) -> Literal["continue", "replan", "end"]:
        """Decide whether to continue, replan, or end execution."""
        plan = state.get("current_plan")
        step_index = state.get("plan_step_index", 0)
        replan_count = state.get("replan_count", 0)
        context = state.get("execution_context", {})

        # Check if we're done
        if plan is None:
            return "end"

        plan_steps = plan.get("steps", [])
        if step_index >= len(plan_steps):
            return "end"

        # Check for failures that need replanning
        last_result = context.get("last_result", {})
        if not last_result.get("success", True) and replan_count < 3:
            return "replan"

        # Continue to next step
        return "continue"

    async def _router_node(self, state: AgentState) -> Dict[str, Any]:
        """Classify user intent from messages."""
        messages = state.get("messages", [])
        if not messages:
            return {"intent": INTENT_CONVERSATION}

        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return {"intent": INTENT_CONVERSATION}

        user_text = last_message.content.lower()

        # IMPORTANT: Check for workflow creation/modification FIRST
        # These should NOT trigger auto-execution
        workflow_create_keywords = [
            "create workflow", "build workflow", "make workflow", "new workflow", 
            "set up workflow", "create a workflow", "build a workflow", "make a workflow",
            "workflow to", "workflow that", "workflow for",
        ]
        if any(kw in user_text for kw in workflow_create_keywords):
            print(f"[Agent] Classified as WORKFLOW_CREATE: {user_text[:50]}...")
            return {"intent": INTENT_WORKFLOW_CREATE}

        workflow_modify_keywords = [
            "modify workflow", "change workflow", "update workflow", 
            "edit workflow", "add to workflow"
        ]
        if any(kw in user_text for kw in workflow_modify_keywords):
            return {"intent": INTENT_WORKFLOW_MODIFY}

        # Execute intent: ONLY for explicit execution commands
        # User must explicitly want to run something NOW
        execute_keywords = [
            "run", "execute", "start", "do it", "go ahead", "run it", "execute it",
        ]
        if any(kw in user_text for kw in execute_keywords):
            print(f"[Agent] Classified as EXECUTE: {user_text[:50]}...")
            return {"intent": INTENT_EXECUTE}

        # For action-oriented requests without explicit workflow/execute keywords,
        # treat them as workflow creation (user can then run manually)
        action_keywords = [
            # Email actions
            "send email", "send an email", "email to", "list email", "list my email",
            "get email", "read email", "check email", "reply to", "emails",
            "inbox", "recent email", "my email",
            # Calendar actions
            "schedule", "create event", "list event", "my calendar", "upcoming event",
            "calendar", "events",
            # Drive actions
            "upload file", "download file", "list file", "search file", "my drive",
            "drive", "files",
            # GitHub actions
            "create issue", "create pr", "pull request", "commit", "push",
            "github", "repo",
            # General action verbs - these create workflows, NOT execute
            "scrape", "fetch", "get the", "show me", "find", "search for", "look up",
            "send", "post", "delete", "remove",
        ]
        if any(kw in user_text for kw in action_keywords):
            print(f"[Agent] Classified as WORKFLOW_CREATE (action request): {user_text[:50]}...")
            return {"intent": INTENT_WORKFLOW_CREATE}

        if any(kw in user_text for kw in ["what is", "how does", "why", "can you explain", "explain", "tell me about"]):
            return {"intent": INTENT_QUESTION}

        # Use LLM for ambiguous cases
        classification_prompt = f"""Classify the user's intent. User said: "{last_message.content}"

Available tools:
{self.tool_descriptions[:1000]}...

Respond with ONLY one of: conversation, workflow_create, workflow_modify, execute, question"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are an intent classifier. Respond with only the intent category."),
                HumanMessage(content=classification_prompt)
            ])
            intent = response.content.strip().lower()

            if intent in [INTENT_CONVERSATION, INTENT_WORKFLOW_CREATE, INTENT_WORKFLOW_MODIFY, INTENT_EXECUTE, INTENT_QUESTION]:
                return {"intent": intent}
        except Exception:
            pass

        return {"intent": INTENT_CONVERSATION}

    async def _respond_node(self, state: AgentState) -> Dict[str, Any]:
        """Handle conversational responses and questions."""
        messages = state.get("messages", [])
        streaming_callback = state.get("streaming_callback")

        system_prompt = f"""You are Sentric, an AI assistant that helps users build and execute automated workflows.

You have access to these tools:
{self.tool_descriptions}

When users ask questions, provide helpful, concise answers. If they want to create a workflow,
explain what you can do and ask clarifying questions if needed.

Be friendly but professional. Keep responses focused and actionable."""

        llm_messages = [SystemMessage(content=system_prompt)] + list(messages)

        try:
            if streaming_callback:
                response_text = ""
                async for chunk in self.llm.astream(llm_messages):
                    if chunk.content:
                        response_text += chunk.content
                        await streaming_callback("agent_thinking", chunk.content)
                response = AIMessage(content=response_text)
            else:
                response = await self.llm.ainvoke(llm_messages)

            return {"messages": [response]}
        except Exception as e:
            return {"messages": [AIMessage(content=f"I encountered an error: {str(e)}")]}

    async def _plan_node(self, state: AgentState) -> Dict[str, Any]:
        """Create an execution plan for the user's request."""
        messages = state.get("messages", [])
        workflow_nodes = state.get("workflow_nodes", [])
        streaming_callback = state.get("streaming_callback")

        user_request = messages[-1].content if messages else ""
        print(f"[Agent] Planning for request: {user_request[:100]}...")

        planning_prompt = f"""Create a workflow plan for this request: "{user_request}"

Current workflow has {len(workflow_nodes)} nodes.

Available tools:
{self.tool_descriptions}

IMPORTANT - Context References:
- Each step's output is stored as ${{step_0}}, ${{step_1}}, etc.
- When a step needs data from a previous step, use these references in params
- Example: If step 0 scrapes articles, step 1 can use input_data: "${{step_0}}"
- NEVER use placeholder text like "PLACEHOLDER" or made-up values
- If you don't know a value (like an email ID), you must get it from a previous step's output

Respond with a JSON object:
{{
    "goal": "Brief description of the goal",
    "reasoning": "Why this approach",
    "steps": [
        {{
            "tool_name": "tool.name",
            "params": {{"param": "value or ${{step_N}} reference"}},
            "description": "What this step does"
        }}
    ]
}}

Examples of proper context usage:
- Scrape then process: step 0 scrapes, step 1 uses {{"input_data": "${{step_0}}", "instruction": "summarize"}}
- List then read: step 0 lists emails (returns IDs), step 1 can reference the ID from output
- Process then email: step 0 generates content, step 1 uses {{"body": "${{step_0}}"}}

Only include steps that use available tools. Be specific with parameters."""

        try:
            if streaming_callback:
                await streaming_callback("agent_thinking", "Planning workflow...")

            response = await self.llm.ainvoke([
                SystemMessage(content="You are a workflow planner. Output valid JSON only."),
                HumanMessage(content=planning_prompt)
            ])

            # Parse JSON from response
            content = response.content
            # Extract JSON if wrapped in markdown
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            plan = json.loads(content.strip())
            print(f"\n[Agent] ========== PLAN CREATED ==========")
            print(f"[Agent] Goal: {plan.get('goal', 'N/A')}")
            print(f"[Agent] Steps ({len(plan.get('steps', []))}):")
            for i, step in enumerate(plan.get("steps", [])):
                print(f"[Agent]   Step {i}: {step.get('tool_name')} - {step.get('description', '')[:50]}")
                print(f"[Agent]          Params: {step.get('params', {})}")

            if streaming_callback:
                await streaming_callback("plan_created", plan.get("steps", []))

            return {
                "current_plan": plan,
                "plan_step_index": 0,
                "replan_count": 0,
            }
        except Exception as e:
            print(f"[Agent] Plan creation failed: {e}")
            return {
                "messages": [AIMessage(content=f"I couldn't create a plan: {str(e)}")],
                "current_plan": None,
            }

    async def _build_workflow_node(self, state: AgentState) -> Dict[str, Any]:
        """Convert the plan into workflow nodes and edges."""
        plan = state.get("current_plan")
        streaming_callback = state.get("streaming_callback")

        if not plan:
            return {"messages": [AIMessage(content="No plan to build workflow from.")]}

        steps = plan.get("steps", [])
        nodes = []
        edges = []

        # Calculate starting position
        start_x = 100
        start_y = 100
        x_spacing = 300

        for i, step in enumerate(steps):
            node_id = str(uuid.uuid4())[:8]
            tool_name = step.get("tool_name", "")

            # Determine node type
            if tool_name.startswith("browser."):
                node_type = "browser_agent"
            elif tool_name.startswith("scrape."):
                node_type = "mcp_tool"
            else:
                node_type = "mcp_tool"

            node = {
                "id": node_id,
                "type": node_type,
                "position": {"x": start_x + (i * x_spacing), "y": start_y},
                "data": {
                    "tool_name": tool_name,
                    "label": step.get("description", tool_name)[:40],
                    "params": step.get("params", {}),
                    "instruction": step.get("description", ""),
                },
            }
            nodes.append(node)

            # Create edge to previous node
            if i > 0:
                edges.append({
                    "id": f"e{i-1}-{i}",
                    "source": nodes[i-1]["id"],
                    "target": node_id,
                })

            if streaming_callback:
                await streaming_callback("workflow_update", {"nodes": nodes, "edges": edges})

        goal = plan.get("goal", "workflow")
        response_msg = f"I've created a workflow with {len(nodes)} steps to {goal}. You can review the nodes on the canvas and click 'Run Workflow' when ready."

        return {
            "workflow_nodes": nodes,
            "workflow_edges": edges,
            "messages": [AIMessage(content=response_msg)],
        }

    async def _execute_node(self, state: AgentState) -> Dict[str, Any]:
        """Execute the current step in the plan."""
        plan = state.get("current_plan")
        step_index = state.get("plan_step_index", 0)
        context = state.get("execution_context", {})
        streaming_callback = state.get("streaming_callback")

        if not plan:
            print("[Agent] Execute node: No plan available!")
            return {"messages": [AIMessage(content="No plan to execute.")]}

        print(f"\n[Agent] ========== EXECUTE STEP {step_index + 1}/{len(plan.get('steps', []))} ==========")
        print(f"[Agent] Context keys available: {list(context.keys())}")
        for key in context:
            if key.startswith("step_"):
                val_preview = str(context[key])[:200] if context[key] else "None"
                print(f"[Agent] Context[{key}]: {val_preview}...")

        steps = plan.get("steps", [])
        if step_index >= len(steps):
            return {"messages": [AIMessage(content="All steps completed.")]}

        step = steps[step_index]
        tool_name = step.get("tool_name", "")
        params = dict(step.get("params", {}))  # Make a copy

        # Resolve context references in params (e.g., ${step_0}, ${step_1})
        def resolve_references(value):
            """Recursively resolve ${step_N} references in values."""
            if isinstance(value, str):
                import re
                # Find all ${...} patterns
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, value)
                for match in matches:
                    if match in context:
                        replacement = context[match]
                        if isinstance(replacement, str):
                            value = value.replace(f"${{{match}}}", replacement)
                        else:
                            # If it's the entire value, replace with the object
                            if value == f"${{{match}}}":
                                value = replacement
                            else:
                                value = value.replace(f"${{{match}}}", str(replacement))
                return value
            elif isinstance(value, dict):
                return {k: resolve_references(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_references(v) for v in value]
            return value

        resolved_params = {k: resolve_references(v) for k, v in params.items()}
        print(f"[Agent] Tool: {tool_name}")
        print(f"[Agent] Original params: {params}")
        print(f"[Agent] Resolved params: {str(resolved_params)[:500]}")

        if streaming_callback:
            await streaming_callback("step_started", {"tool": tool_name, "params": resolved_params})
            await streaming_callback("node_status_change", {"nodeId": step.get("node_id"), "status": "executing"})

        try:
            result = await self.mcp_manager.call_tool(
                tool_name,
                resolved_params,
                context=context,
                user_id=self.user_id,
            )

            # Store result in context
            result_data = result.get("result", "")
            context[f"step_{step_index}"] = result_data
            context["last_result"] = result

            print(f"[Agent] Step {step_index} result success: {result.get('success')}")
            print(f"[Agent] Step {step_index} result preview: {str(result_data)[:300]}...")
            print(f"[Agent] Stored in context as 'step_{step_index}'")

            if streaming_callback:
                status = "success" if result.get("success") else "failed"
                await streaming_callback("step_completed", {"tool": tool_name, "output": result.get("result", "")[:500]})
                await streaming_callback("node_status_change", {"nodeId": step.get("node_id"), "status": status})

            return {
                "execution_context": context,
                "plan_step_index": step_index + 1,
            }

        except Exception as e:
            context["last_result"] = {"success": False, "error": str(e)}
            if streaming_callback:
                await streaming_callback("node_status_change", {"nodeId": step.get("node_id"), "status": "failed"})

            return {
                "execution_context": context,
            }

    async def _observe_node(self, state: AgentState) -> Dict[str, Any]:
        """Observe execution results and decide next action."""
        context = state.get("execution_context", {})
        plan = state.get("current_plan")
        step_index = state.get("plan_step_index", 0)
        streaming_callback = state.get("streaming_callback")

        last_result = context.get("last_result", {})

        if not plan:
            return {}

        steps = plan.get("steps", [])

        # Check if all steps completed
        if step_index >= len(steps):
            if streaming_callback:
                await streaming_callback("execution_complete", {"success": True})

            # Compile final result
            final_outputs = []
            for i in range(len(steps)):
                if f"step_{i}" in context:
                    final_outputs.append(context[f"step_{i}"])

            summary = "\n\n".join(final_outputs) if final_outputs else "Workflow completed."
            return {
                "messages": [AIMessage(content=f"## Workflow Complete\n\n{summary[:2000]}")],
            }

        # Check for failures
        if not last_result.get("success", True):
            return {}  # Will trigger replan

        return {}

    async def _replan_node(self, state: AgentState) -> Dict[str, Any]:
        """Replan after a failure."""
        context = state.get("execution_context", {})
        plan = state.get("current_plan")
        replan_count = state.get("replan_count", 0)
        streaming_callback = state.get("streaming_callback")

        if replan_count >= 3:
            if streaming_callback:
                await streaming_callback("execution_complete", {"success": False})
            return {
                "messages": [AIMessage(content="I've tried multiple times but couldn't complete the workflow. Please check the error and try again.")],
                "current_plan": None,
            }

        last_result = context.get("last_result", {})
        error = last_result.get("error", "Unknown error")

        if streaming_callback:
            await streaming_callback("agent_thinking", f"Replanning due to error: {error}")

        replan_prompt = f"""The previous step failed with error: {error}

Original plan: {json.dumps(plan, indent=2)}

Please create a modified plan that avoids this error. Respond with JSON only."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are a workflow planner. Fix the plan to avoid the error."),
                HumanMessage(content=replan_prompt)
            ])

            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            new_plan = json.loads(content.strip())

            return {
                "current_plan": new_plan,
                "plan_step_index": 0,
                "replan_count": replan_count + 1,
            }
        except Exception:
            return {
                "replan_count": replan_count + 1,
            }

    async def run(
        self,
        message: str,
        project_id: str,
        workflow_nodes: List[Dict] = None,
        workflow_edges: List[Dict] = None,
        streaming_callback: Any = None,
    ) -> Dict[str, Any]:
        """Run the agent with a user message."""
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "workflow_nodes": workflow_nodes or [],
            "workflow_edges": workflow_edges or [],
            "execution_context": {},
            "current_plan": None,
            "plan_step_index": 0,
            "replan_count": 0,
            "user_id": self.user_id,
            "project_id": project_id,
            "intent": None,
            "streaming_callback": streaming_callback,
        }

        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)

        # Extract response
        messages = final_state.get("messages", [])
        response_text = ""
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                response_text = msg.content
                break

        return {
            "message": response_text,
            "workflow_nodes": final_state.get("workflow_nodes", []),
            "workflow_edges": final_state.get("workflow_edges", []),
            "intent": final_state.get("intent"),
        }


async def create_agent(mcp_manager: Any, user_id: Optional[str] = None) -> LangGraphAgent:
    """Factory function to create a LangGraph agent."""
    return LangGraphAgent(mcp_manager, user_id)
