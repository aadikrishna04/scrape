"""
Agent Orchestrator - Agentic loop for plan → execute → observe → replan
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from google import genai
from google.genai import types

from mcp_manager import get_mcp_manager, MCPTool
from agent_prompts import (
    PLANNER_SYSTEM_PROMPT,
    OBSERVER_SYSTEM_PROMPT,
    REPLANNER_SYSTEM_PROMPT,
    SYNTHESIZER_SYSTEM_PROMPT,
    format_tools_for_prompt,
    format_history_for_prompt,
)


@dataclass
class AgentStep:
    """Represents a single step in the agent's execution."""
    id: int
    tool: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    status: str = "pending"  # pending, executing, success, failed, skipped
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class AgentPlan:
    """Represents the agent's current plan."""
    thinking: str
    steps: List[AgentStep]
    estimated_steps: int


@dataclass
class AgentState:
    """Current state of the agent execution."""
    goal: str
    history: List[AgentStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    current_plan: Optional[AgentPlan] = None
    is_complete: bool = False
    final_result: Optional[str] = None
    error: Optional[str] = None
    replan_count: int = 0
    max_replans: int = 3
    max_steps: int = 20


class AgentOrchestrator:
    """
    Orchestrates the agentic loop: plan → execute → observe → replan.
    """

    def __init__(self, stream_callback=None, user_id: Optional[str] = None):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.mcp_manager = get_mcp_manager()
        self.stream_callback = stream_callback  # For real-time updates
        self.user_id = user_id  # User ID for per-user integrations
        self._fast_scrape_handler = None

    def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools including fast_scrape."""
        tools = []

        # Add fast_scrape as a first-class tool
        tools.append({
            "name": "fast_scrape",
            "description": "Fast HTTP-based web scraping with LLM extraction. Use this for reading web pages without interaction. Much faster than browser automation.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to scrape"},
                    "extract_prompt": {"type": "string", "description": "What information to extract from the page"}
                },
                "required": ["url", "extract_prompt"]
            }
        })

        # Add MCP tools (pass user_id to get per-user tools like Gmail if connected)
        for tool in self.mcp_manager.get_all_tools(user_id=self.user_id):
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema
            })

        return tools

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to the stream callback."""
        if self.stream_callback:
            await self.stream_callback({
                "type": event_type,
                "timestamp": datetime.now().isoformat(),
                **data
            })

    async def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """Call Gemini with the given prompts."""
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=system_prompt
            )
        )
        return response.text

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    async def plan(self, state: AgentState) -> AgentPlan:
        """Generate a plan for achieving the goal."""
        await self._emit_event("planning", {"goal": state.goal})

        tools = self._get_available_tools()
        tools_description = format_tools_for_prompt(tools)

        system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_description=tools_description)

        context_info = ""
        if state.context:
            context_info = f"\n\nPreviously gathered information:\n{json.dumps(state.context, indent=2)}"

        prompt = f"Goal: {state.goal}{context_info}"

        response = await self._call_llm(prompt, system_prompt)

        try:
            plan_data = self._parse_json_response(response)
        except json.JSONDecodeError:
            # Fallback: try to extract a simple plan
            plan_data = {
                "thinking": "Failed to parse plan, using fallback",
                "steps": [{"id": 1, "tool": "browser.execute_instruction", "description": state.goal, "params": {"instruction": state.goal}, "depends_on": []}],
                "estimated_steps": 1
            }

        steps = []
        for step_data in plan_data.get("steps", []):
            steps.append(AgentStep(
                id=step_data.get("id", len(steps) + 1),
                tool=step_data.get("tool", "unknown"),
                description=step_data.get("description", ""),
                params=step_data.get("params", {}),
                depends_on=step_data.get("depends_on", [])
            ))

        plan = AgentPlan(
            thinking=plan_data.get("thinking", ""),
            steps=steps,
            estimated_steps=plan_data.get("estimated_steps", len(steps))
        )

        await self._emit_event("plan_created", {
            "thinking": plan.thinking,
            "steps": [{"id": s.id, "tool": s.tool, "description": s.description} for s in plan.steps]
        })

        return plan

    async def execute_step(self, step: AgentStep, context: Dict[str, Any]) -> AgentStep:
        """Execute a single step and return the updated step."""
        step.status = "executing"
        step.started_at = datetime.now()

        await self._emit_event("step_started", {
            "step_id": step.id,
            "tool": step.tool,
            "description": step.description
        })

        try:
            # Resolve parameter references from context
            resolved_params = self._resolve_params(step.params, context)

            if step.tool == "fast_scrape":
                # Use fast scrape
                from fast_scrape import fast_scrape
                result = await fast_scrape(
                    url=resolved_params.get("url", ""),
                    extract_prompt=resolved_params.get("extract_prompt", "")
                )
                if result.get("success"):
                    step.status = "success"
                    step.output = result.get("data")
                else:
                    step.status = "failed"
                    step.error = result.get("error", "Unknown error")
            else:
                # Use MCP manager for other tools (pass user_id for per-user integrations)
                result = await self.mcp_manager.call_tool(
                    step.tool, resolved_params, context, user_id=self.user_id
                )

                if result.get("success"):
                    step.status = "success"
                    step.output = result.get("result")
                else:
                    step.status = "failed"
                    step.error = result.get("error", "Unknown error")

        except Exception as e:
            step.status = "failed"
            step.error = str(e)

        step.completed_at = datetime.now()

        await self._emit_event("step_completed", {
            "step_id": step.id,
            "status": step.status,
            "output": str(step.output)[:500] if step.output else None,
            "error": step.error
        })

        return step

    def _resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter references like {{step_1_output}} from context."""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                # Replace references with context values
                for ctx_key, ctx_value in context.items():
                    placeholder = "{{" + ctx_key + "}}"
                    if placeholder in value:
                        if isinstance(ctx_value, str):
                            value = value.replace(placeholder, ctx_value)
                        else:
                            value = value.replace(placeholder, json.dumps(ctx_value))
            resolved[key] = value
        return resolved

    async def observe(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:
        """Observe the result of a step and determine next action."""
        await self._emit_event("observing", {"step_id": step.id})

        history_str = format_history_for_prompt([
            {"description": s.description, "tool": s.tool, "status": s.status, "output": s.output}
            for s in state.history
        ])

        system_prompt = OBSERVER_SYSTEM_PROMPT.format(
            goal=state.goal,
            history=history_str,
            tool_name=step.tool,
            status=step.status,
            output=str(step.output)[:1000] if step.output else "No output"
        )

        response = await self._call_llm("Analyze the execution result.", system_prompt)

        try:
            observation = self._parse_json_response(response)
        except json.JSONDecodeError:
            observation = {
                "analysis": "Failed to parse observation",
                "goal_achieved": False,
                "key_information": {},
                "needs_replan": step.status == "failed",
                "next_action": "continue" if step.status == "success" else "replan"
            }

        await self._emit_event("observation", observation)

        return observation

    async def replan(self, state: AgentState, failed_step: AgentStep) -> AgentPlan:
        """Create a new plan after a failure."""
        await self._emit_event("replanning", {
            "reason": failed_step.error or "Step failed",
            "failed_step": failed_step.description
        })

        tools = self._get_available_tools()
        tools_description = format_tools_for_prompt(tools)

        completed_steps_str = "\n".join([
            f"- {s.description}: {s.status}" for s in state.history if s.status == "success"
        ])

        system_prompt = REPLANNER_SYSTEM_PROMPT.format(
            goal=state.goal,
            completed_steps=completed_steps_str or "None",
            failed_step=failed_step.description,
            error=failed_step.error or "Unknown error",
            tools_description=tools_description
        )

        response = await self._call_llm("Create a new plan.", system_prompt)

        try:
            plan_data = self._parse_json_response(response)
        except json.JSONDecodeError:
            plan_data = {"analysis": "Failed to parse replan", "new_approach": "", "steps": []}

        steps = []
        for step_data in plan_data.get("steps", []):
            steps.append(AgentStep(
                id=step_data.get("id", len(steps) + 1),
                tool=step_data.get("tool", "unknown"),
                description=step_data.get("description", ""),
                params=step_data.get("params", {}),
                depends_on=step_data.get("depends_on", [])
            ))

        plan = AgentPlan(
            thinking=plan_data.get("analysis", "") + "\n" + plan_data.get("new_approach", ""),
            steps=steps,
            estimated_steps=len(steps)
        )

        await self._emit_event("replan_created", {
            "analysis": plan_data.get("analysis", ""),
            "new_approach": plan_data.get("new_approach", ""),
            "steps": [{"id": s.id, "tool": s.tool, "description": s.description} for s in plan.steps]
        })

        return plan

    async def synthesize(self, state: AgentState) -> str:
        """Synthesize final results from all completed steps."""
        await self._emit_event("synthesizing", {})

        results_str = "\n\n".join([
            f"Step: {s.description}\nOutput: {s.output}"
            for s in state.history if s.status == "success" and s.output
        ])

        system_prompt = SYNTHESIZER_SYSTEM_PROMPT.format(
            goal=state.goal,
            results=results_str
        )

        response = await self._call_llm("Synthesize the final result.", system_prompt)

        await self._emit_event("synthesis_complete", {"result": response[:500]})

        return response

    async def run(self, goal: str) -> Dict[str, Any]:
        """
        Run the full agentic loop for a given goal.

        Returns:
            Dict with execution results
        """
        state = AgentState(goal=goal)

        await self._emit_event("started", {"goal": goal})

        try:
            # Initial planning
            state.current_plan = await self.plan(state)

            step_index = 0
            total_steps_executed = 0

            while not state.is_complete and total_steps_executed < state.max_steps:
                if not state.current_plan or step_index >= len(state.current_plan.steps):
                    # No more steps, check if goal is achieved
                    if state.history:
                        last_observation = await self.observe(state, state.history[-1])
                        if last_observation.get("goal_achieved"):
                            state.is_complete = True
                            break
                        elif last_observation.get("needs_replan") and state.replan_count < state.max_replans:
                            state.current_plan = await self.replan(state, state.history[-1])
                            state.replan_count += 1
                            step_index = 0
                        else:
                            state.is_complete = True
                    else:
                        state.is_complete = True
                    continue

                # Execute next step
                step = state.current_plan.steps[step_index]
                executed_step = await self.execute_step(step, state.context)
                state.history.append(executed_step)
                total_steps_executed += 1

                # Update context with step output
                if executed_step.status == "success" and executed_step.output:
                    state.context[f"step_{executed_step.id}_output"] = executed_step.output

                # Observe result
                observation = await self.observe(state, executed_step)

                # Update context with key information
                if observation.get("key_information"):
                    state.context.update(observation["key_information"])

                # Check if goal is achieved
                if observation.get("goal_achieved"):
                    state.is_complete = True
                    break

                # Check if we need to replan
                if observation.get("needs_replan"):
                    if state.replan_count < state.max_replans:
                        state.current_plan = await self.replan(state, executed_step)
                        state.replan_count += 1
                        step_index = 0
                    else:
                        state.error = "Max replans exceeded"
                        state.is_complete = True
                else:
                    step_index += 1

            # Synthesize final result
            if state.history:
                state.final_result = await self.synthesize(state)

            await self._emit_event("completed", {
                "success": not state.error,
                "steps_executed": total_steps_executed,
                "replans": state.replan_count
            })

            return {
                "success": not state.error,
                "goal": goal,
                "result": state.final_result,
                "steps_executed": total_steps_executed,
                "replans": state.replan_count,
                "history": [
                    {
                        "id": s.id,
                        "tool": s.tool,
                        "description": s.description,
                        "status": s.status,
                        "output": str(s.output)[:500] if s.output else None,
                        "error": s.error
                    }
                    for s in state.history
                ],
                "context": {k: str(v)[:500] for k, v in state.context.items()},
                "error": state.error
            }

        except Exception as e:
            await self._emit_event("error", {"error": str(e)})
            return {
                "success": False,
                "goal": goal,
                "error": str(e),
                "history": [
                    {
                        "id": s.id,
                        "tool": s.tool,
                        "description": s.description,
                        "status": s.status,
                        "output": str(s.output)[:500] if s.output else None,
                        "error": s.error
                    }
                    for s in state.history
                ]
            }


async def run_agent(
    goal: str,
    stream_callback=None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to run the agent orchestrator.

    Args:
        goal: The user's goal to achieve
        stream_callback: Optional callback for real-time updates
        user_id: Optional user ID for per-user integrations (Gmail, etc.)

    Returns:
        Execution results
    """
    orchestrator = AgentOrchestrator(stream_callback=stream_callback, user_id=user_id)
    return await orchestrator.run(goal)
