"""
Browser Agent Configuration - Uses Gemini for Browser Use

To use your system Chrome with existing sessions (preserves auth, cookies, etc.):
1. Set BROWSER_USE_SYSTEM_CHROME=true in your .env
2. FULLY CLOSE all Chrome windows before running
3. The agent will launch Chrome with your existing profile

Environment variables:
- BROWSER_USE_SYSTEM_CHROME: Set to 'true' to use system Chrome with your profile
- BROWSER_HEADLESS: Set to 'false' to see the browser (default: false when using system Chrome)
- BROWSER_PROFILE: Chrome profile name (default: 'Default', or 'Profile 1', 'Profile 2', etc.)
"""
import os
import platform
from browser_use import Agent, Browser
from browser_use.llm.google.chat import ChatGoogle


def get_gemini_llm():
    """Get Gemini LLM configured for Browser Use (browser-use 0.11 API)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    return ChatGoogle(
        model="gemini-2.0-flash",  # gemini-2.0-flash-exp is deprecated; use stable gemini-2.0-flash
        api_key=api_key,
        temperature=0.1,
    )


def get_chrome_paths() -> dict:
    """Get Chrome executable and user data paths for the current platform."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Darwin":  # macOS
        return {
            "executable_path": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "user_data_dir": os.path.join(home, "Library", "Application Support", "Google", "Chrome"),
        }
    elif system == "Windows":
        return {
            "executable_path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "user_data_dir": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data"),
        }
    else:  # Linux
        return {
            "executable_path": "/usr/bin/google-chrome",
            "user_data_dir": os.path.join(home, ".config", "google-chrome"),
        }


def get_browser() -> Browser:
    """
    Get browser instance based on environment variables.

    If BROWSER_USE_SYSTEM_CHROME=true, uses your existing Chrome with all sessions/auth preserved.
    Otherwise, creates a fresh browser instance.
    """
    use_system_chrome = os.getenv("BROWSER_USE_SYSTEM_CHROME", "true").lower() == "true"
    headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
    profile = os.getenv("BROWSER_PROFILE", "Default")

    if use_system_chrome:
        paths = get_chrome_paths()
        executable_path = paths["executable_path"]
        user_data_dir = paths["user_data_dir"]

        if not os.path.exists(executable_path):
            print(f"[BrowserAgent] Warning: Chrome not found at {executable_path}, using default browser")
            return Browser(headless=headless)

        print(f"[BrowserAgent] Using system Chrome:")
        print(f"  - Executable: {executable_path}")
        print(f"  - User data: {user_data_dir}")
        print(f"  - Profile: {profile}")
        print(f"  - Make sure Chrome is FULLY CLOSED before running!")

        return Browser(
            executable_path=executable_path,
            headless=False,  # System Chrome with profile needs to be visible
            user_data_dir=user_data_dir,
            profile_directory=profile,
            disable_security=True,
            viewport={"width": 1280, "height": 900},
        )
    else:
        # Fresh browser instance
        return Browser(headless=headless, viewport={"width": 1280, "height": 900})


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

    # Get browser (system Chrome or fresh instance)
    browser = get_browser()

    try:
        # Create and run agent (browser-use 0.11 API: Agent with BrowserSession)
        agent = Agent(
            task=full_instruction,
            llm=llm,
            browser=browser,
        )

        result = await agent.run()

        # Extract result (AgentHistoryList has is_done, final_result, history)
        if result.is_done():
            final_result = result.final_result()
            return {
                "success": result.is_successful(),
                "result": final_result if final_result else "Task completed but no result extracted",
                "action_count": len(result.action_results()) if hasattr(result, "action_results") else 0,
                "logs": [str(h) for h in result.history] if hasattr(result, "history") else [],
            }
        else:
            return {
                "success": False,
                "result": "Task did not complete",
                "action_count": len(result.action_results()) if hasattr(result, "action_results") else 0,
                "logs": [str(h) for h in result.history] if hasattr(result, "history") else [],
            }

    except Exception as e:
        return {
            "success": False,
            "result": f"Browser automation failed: {str(e)}",
            "action_count": 0,
            "logs": [f"Error: {str(e)}"],
        }
    finally:
        # Always kill browser after execution (browser-use 0.11: BrowserSession.kill())
        try:
            await browser.kill()
        except Exception:
            pass
