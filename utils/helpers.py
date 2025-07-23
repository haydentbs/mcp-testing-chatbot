"""
Utility helper functions for the MCP Streamlit Chatbot.
"""
import json
import asyncio
import time
from typing import Any, Dict, List, Optional
from functools import wraps


def async_to_sync(async_func):
    """Decorator to run async functions in sync context."""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(async_func(*args, **kwargs))
    
    return wrapper


def format_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Format a tool call for display."""
    args_str = json.dumps(arguments, indent=2)
    return f"**Tool Call:** `{tool_name}`\n```json\n{args_str}\n```"


def format_tool_result(result: Any, error: Optional[str] = None) -> str:
    """Format a tool result for display."""
    if error:
        return f"**Error:** {error}"
    
    if isinstance(result, (dict, list)):
        result_str = json.dumps(result, indent=2)
        return f"**Result:**\n```json\n{result_str}\n```"
    else:
        return f"**Result:** {str(result)}"


def truncate_text(text: str, max_length: int = 500) -> str:
    """Truncate text to maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def validate_json(json_str: str) -> tuple[bool, Optional[Dict]]:
    """Validate JSON string and return parsed result."""
    try:
        parsed = json.loads(json_str)
        return True, parsed
    except json.JSONDecodeError as e:
        return False, {"error": str(e)}


class Timer:
    """Simple timer context manager."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time


def sanitize_server_name(name: str) -> str:
    """Sanitize server name for use as identifier."""
    return "".join(c for c in name if c.isalnum() or c in "-_").lower() 