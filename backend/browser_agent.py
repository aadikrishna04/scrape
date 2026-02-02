"""
Browser Agent Configuration - Uses Gemini for Browser Use
"""
import os
from browser_use import Agent, Browser
from browser_use.llm.google.chat import ChatGoogle

# Configure Gemini LLM for Browser Use
def get_gemini_llm():
    """Get Gemini LLM configured for Browser Use."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")
    
    return ChatGoogle(
        model="gemini-2.0-flash",
        api_key=api_key,
        temperature=0.1,
    )

async def close_browser():
    """Placeholder for compatibility - browser is now created per-execution."""
    pass

async def execute_browser_instruction(instruction: str, context: dict = None) -> dict:
    """
    Execute a natural language browser instruction.
    
    Args:
        instruction: Natural language description of what to do
        context: Previous node outputs for context
        
    Returns:
        Dict with result, logs, and any extracted data
    """
    llm = get_gemini_llm()
    
    # Build context-aware instruction
    full_instruction = instruction
    if context:
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        full_instruction = f"Context from previous steps:\n{context_str}\n\nTask: {instruction}"
    
    # Create fresh browser for each execution to avoid stale state
    headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
    browser = Browser(headless=headless)
    
    try:
        # Create and run agent with fresh browser
        agent = Agent(
            task=full_instruction,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        
        # Extract result properly
        if result.is_done():
            final_result = result.final_result()
            return {
                "success": result.is_successful(),
                "result": final_result if final_result else "Task completed but no result extracted",
                "action_count": len(result.history) if hasattr(result, 'history') else 0,
                "logs": [str(h) for h in result.history] if hasattr(result, 'history') else []
            }
        else:
            return {
                "success": False,
                "result": "Task did not complete",
                "action_count": len(result.history) if hasattr(result, 'history') else 0,
                "logs": [str(h) for h in result.history] if hasattr(result, 'history') else []
            }
            
    except Exception as e:
        return {
            "success": False,
            "result": f"Browser automation failed: {str(e)}",
            "action_count": 0,
            "logs": [f"Error: {str(e)}"]
        }
    finally:
        # Always close browser after execution
        try:
            await browser.close()
        except Exception:
            pass
