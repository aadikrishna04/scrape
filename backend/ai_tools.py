"""
AI Tools - Internal tools for AI-powered data processing and transformation
"""
import os
import json
from typing import Dict, Any, List, Optional

from google import genai
from google.genai import types

from mcp_manager import MCPManager, MCPTool


def get_ai_tools() -> List[MCPTool]:
    """Return AI processing tools in MCP format."""
    return [
        MCPTool(
            name="ai.process",
            server_name="ai",
            original_name="process",
            display_name="AI Process",
            description="Use AI to process, transform, or generate content from input data. Use this for tasks like summarizing, analyzing, generating text, converting formats, or any intelligent data transformation.",
            input_schema={
                "type": "object",
                "properties": {
                    "input_data": {
                        "type": "string",
                        "description": "The input data to process (text, JSON, etc.)"
                    },
                    "instruction": {
                        "type": "string",
                        "description": "What to do with the input data (e.g., 'summarize this', 'generate a business plan from this', 'extract key points', 'convert to markdown')"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Desired output format: 'text', 'json', 'markdown', 'html' (default: 'text')",
                        "enum": ["text", "json", "markdown", "html"],
                        "default": "text"
                    }
                },
                "required": ["input_data", "instruction"]
            },
            category="ai"
        ),
        MCPTool(
            name="ai.summarize",
            server_name="ai",
            original_name="summarize",
            display_name="AI Summarize",
            description="Summarize text content into a concise form.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to summarize"
                    },
                    "max_length": {
                        "type": "string",
                        "description": "Target length: 'short' (1-2 sentences), 'medium' (1 paragraph), 'long' (multiple paragraphs)",
                        "enum": ["short", "medium", "long"],
                        "default": "medium"
                    }
                },
                "required": ["text"]
            },
            category="ai"
        ),
        MCPTool(
            name="ai.extract",
            server_name="ai",
            original_name="extract",
            display_name="AI Extract",
            description="Extract specific information from text using AI.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to extract information from"
                    },
                    "extract_what": {
                        "type": "string",
                        "description": "What to extract (e.g., 'email addresses', 'dates', 'names', 'key facts', 'action items')"
                    }
                },
                "required": ["text", "extract_what"]
            },
            category="ai"
        ),
        MCPTool(
            name="ai.generate",
            server_name="ai",
            original_name="generate",
            display_name="AI Generate",
            description="Generate new content based on a prompt and optional context.",
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "What to generate (e.g., 'a business plan for...', 'an email response to...', 'a report about...')"
                    },
                    "context": {
                        "type": "string",
                        "description": "Optional context or background information to use"
                    },
                    "tone": {
                        "type": "string",
                        "description": "Tone of the output: 'professional', 'casual', 'formal', 'creative'",
                        "enum": ["professional", "casual", "formal", "creative"],
                        "default": "professional"
                    }
                },
                "required": ["prompt"]
            },
            category="ai"
        ),
    ]


class AIToolHandler:
    """Handler for AI processing tools."""

    def __init__(self):
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)

    async def handle(self, tool_name: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle AI tool calls."""
        try:
            if tool_name == "ai.process":
                return await self._process(params)
            elif tool_name == "ai.summarize":
                return await self._summarize(params)
            elif tool_name == "ai.extract":
                return await self._extract(params)
            elif tool_name == "ai.generate":
                return await self._generate(params)
            else:
                return {"success": False, "error": f"Unknown AI tool: {tool_name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM with given prompts."""
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                system_instruction=system_prompt
            )
        )
        return response.text

    async def _process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """General AI processing."""
        input_data = params.get("input_data", "")
        instruction = params.get("instruction", "")
        output_format = params.get("output_format", "text")

        if not input_data or not instruction:
            return {"success": False, "error": "Both input_data and instruction are required"}

        print(f"\n{'='*80}")
        print(f"[AI Process Tool] Context String Before Email Generation:")
        print(f"{'='*80}")
        print(f"INSTRUCTION: {instruction}")
        print(f"\nINPUT DATA:")
        print(input_data)
        print(f"{'='*80}\n")

        format_instructions = {
            "text": "Respond in plain text.",
            "json": "Respond with valid JSON only, no markdown.",
            "markdown": "Respond in well-formatted Markdown.",
            "html": "Respond in clean HTML."
        }

        system_prompt = f"""You are a helpful AI assistant that processes and transforms data.
{format_instructions.get(output_format, '')}
Be thorough but concise. Focus on quality output."""

        user_prompt = f"""Instruction: {instruction}

Input Data:
{input_data}

Process the input data according to the instruction above."""

        result = await self._call_llm(system_prompt, user_prompt)
        return {"success": True, "result": result}

    async def _summarize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Summarize text."""
        text = params.get("text", "")
        max_length = params.get("max_length", "medium")

        if not text:
            return {"success": False, "error": "Text is required"}

        length_instructions = {
            "short": "Provide a 1-2 sentence summary.",
            "medium": "Provide a concise paragraph summary.",
            "long": "Provide a comprehensive multi-paragraph summary."
        }

        system_prompt = f"""You are a summarization expert.
{length_instructions.get(max_length, length_instructions['medium'])}
Capture the key points and main ideas."""

        user_prompt = f"""Summarize the following text:

{text}"""

        result = await self._call_llm(system_prompt, user_prompt)
        return {"success": True, "result": result}

    async def _extract(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific information."""
        text = params.get("text", "")
        extract_what = params.get("extract_what", "")

        if not text or not extract_what:
            return {"success": False, "error": "Both text and extract_what are required"}

        system_prompt = """You are an information extraction expert.
Extract only the requested information.
If the information isn't present, say so clearly.
Format the output clearly and concisely."""

        user_prompt = f"""Extract the following from the text: {extract_what}

Text:
{text}"""

        result = await self._call_llm(system_prompt, user_prompt)
        return {"success": True, "result": result}

    async def _generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate new content."""
        prompt = params.get("prompt", "")
        context = params.get("context", "")
        tone = params.get("tone", "professional")

        if not prompt:
            return {"success": False, "error": "Prompt is required"}

        tone_instructions = {
            "professional": "Use a professional, business-appropriate tone.",
            "casual": "Use a friendly, conversational tone.",
            "formal": "Use a formal, academic tone.",
            "creative": "Be creative and engaging."
        }

        system_prompt = f"""You are a skilled content generator.
{tone_instructions.get(tone, tone_instructions['professional'])}
Create high-quality, well-structured content."""

        user_prompt = f"""Generate: {prompt}"""
        if context:
            user_prompt += f"""

Context/Background:
{context}"""

        result = await self._call_llm(system_prompt, user_prompt)
        return {"success": True, "result": result}


# Global handler instance
_ai_handler: Optional[AIToolHandler] = None


def get_ai_handler() -> AIToolHandler:
    """Get the global AI handler instance."""
    global _ai_handler
    if _ai_handler is None:
        _ai_handler = AIToolHandler()
    return _ai_handler


def register_ai_tools(manager: MCPManager) -> None:
    """Register all AI tools with the MCP manager."""
    handler = get_ai_handler()
    tools = get_ai_tools()

    for tool in tools:
        async def ai_handler(params: Dict[str, Any], context: Optional[Dict[str, Any]] = None, t=tool) -> Dict[str, Any]:
            return await handler.handle(t.name, params, context)
        manager.register_internal_tool(tool, ai_handler)

    print(f"[MCP] Registered {len(tools)} AI tools")
