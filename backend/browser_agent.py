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

# Global browser instance (shared across executions)
browser: Browser = None

def get_browser():
    """Get or create shared browser instance."""
    global browser
    if browser is None:
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        browser = Browser(headless=headless)
    return browser

async def close_browser():
    """Close the browser instance."""
    global browser
    if browser:
        await browser.close()
        browser = None

async def execute_browser_instruction(instruction: str, context: dict = None) -> dict:
    """
    Execute a natural language browser instruction.
    
    Args:
        instruction: Natural language description of what to do
        context: Previous node outputs for context
        
    Returns:
        Dict with result, logs, and any extracted data
    """
    global browser
    llm = get_gemini_llm()
    
    # Ensure browser is properly initialized
    if browser is None:
        headless = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        browser = Browser(headless=headless)
    
    # Build context-aware instruction
    full_instruction = instruction
    if context:
        context_str = "\n".join([f"{k}: {v}" for k, v in context.items()])
        full_instruction = f"Context from previous steps:\n{context_str}\n\nTask: {instruction}"
    
    try:
        # Create and run agent
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
        # If browser failed, close it so it will be reinitialized next time
        if browser:
            try:
                await browser.close()
            except:
                pass
            browser = None
        
        return {
            "success": False,
            "result": f"Browser automation failed: {str(e)}",
            "action_count": 0,
            "logs": [f"Error: {str(e)}"]
        }
