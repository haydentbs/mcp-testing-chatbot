"""
Tool executor for handling MCP tool execution with OpenAI integration.
"""
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from mcp_client.server_manager import MCPServerManager
from utils.logger import logger
from utils.helpers import format_tool_call, format_tool_result, Timer


@dataclass
class ToolExecution:
    """Represents a tool execution result."""
    tool_name: str
    server_name: str
    arguments: Dict[str, Any]
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


class MCPToolExecutor:
    """Handles execution of MCP tools and integration with OpenAI function calling."""
    
    def __init__(self, server_manager: MCPServerManager):
        self.server_manager = server_manager
        self.execution_history: List[ToolExecution] = []
    
    async def execute_tool_by_name(self, tool_name: str, arguments: Dict[str, Any]) -> ToolExecution:
        """Execute a tool by name, finding the appropriate server."""
        # Find which server has this tool
        server_name = None
        for srv_name, server in self.server_manager.client.servers.items():
            for tool in server.tools:
                if tool.name == tool_name:
                    server_name = srv_name
                    break
            if server_name:
                break
        
        if not server_name:
            execution = ToolExecution(
                tool_name=tool_name,
                server_name="unknown",
                arguments=arguments,
                success=False,
                error=f"Tool '{tool_name}' not found on any connected server"
            )
            self.execution_history.append(execution)
            return execution
        
        return await self.execute_tool(server_name, tool_name, arguments)
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> ToolExecution:
        """Execute a specific tool on a specific server."""
        logger.info(f"Executing tool {tool_name} on server {server_name} with args: {arguments}")
        
        with Timer() as timer:
            result_data = await self.server_manager.execute_tool(server_name, tool_name, arguments)
        
        execution = ToolExecution(
            tool_name=tool_name,
            server_name=server_name,
            arguments=arguments,
            success=result_data["success"],
            result=result_data["result"],
            error=result_data["error"],
            execution_time=timer.elapsed
        )
        
        self.execution_history.append(execution)
        
        if execution.success:
            logger.info(f"Tool {tool_name} executed successfully in {timer.elapsed:.2f}s")
        else:
            logger.error(f"Tool {tool_name} failed: {execution.error}")
        
        return execution
    
    def get_openai_function_definitions(self) -> List[Dict[str, Any]]:
        """Get OpenAI function definitions for all available tools."""
        functions = []
        
        tools_by_server = self.server_manager.get_available_tools()
        
        for server_name, tools in tools_by_server.items():
            for tool in tools:
                # Convert MCP tool schema to OpenAI function schema
                function_def = {
                    "name": tool["name"],
                    "description": f"[{server_name}] {tool['description']}",
                    "parameters": tool.get("input_schema", {
                        "type": "object",
                        "properties": {},
                        "required": []
                    })
                }
                
                # Ensure proper schema format
                if "type" not in function_def["parameters"]:
                    function_def["parameters"]["type"] = "object"
                if "properties" not in function_def["parameters"]:
                    function_def["parameters"]["properties"] = {}
                if "required" not in function_def["parameters"]:
                    function_def["parameters"]["required"] = []
                
                functions.append(function_def)
        
        return functions
    
    async def execute_function_call(self, function_name: str, function_args: str) -> Tuple[bool, str]:
        """Execute a function call from OpenAI and return formatted result."""
        try:
            # Parse arguments
            if isinstance(function_args, str):
                arguments = json.loads(function_args)
            else:
                arguments = function_args
            
            # Execute the tool
            execution = await self.execute_tool_by_name(function_name, arguments)
            
            # Format result for display
            if execution.success:
                result_text = format_tool_result(execution.result)
                return True, result_text
            else:
                error_text = format_tool_result(None, execution.error)
                return False, error_text
                
        except json.JSONDecodeError as e:
            error_msg = f"Invalid function arguments JSON: {e}"
            logger.error(error_msg)
            return False, format_tool_result(None, error_msg)
        except Exception as e:
            error_msg = f"Unexpected error executing function: {e}"
            logger.error(error_msg)
            return False, format_tool_result(None, error_msg)
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of tool executions."""
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "tools_used": [],
                "servers_used": [],
                "average_execution_time": 0
            }
        
        successful = [e for e in self.execution_history if e.success]
        failed = [e for e in self.execution_history if not e.success]
        
        tools_used = list(set(e.tool_name for e in self.execution_history))
        servers_used = list(set(e.server_name for e in self.execution_history))
        
        execution_times = [e.execution_time for e in self.execution_history if e.execution_time]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0
        
        return {
            "total_executions": len(self.execution_history),
            "successful_executions": len(successful),
            "failed_executions": len(failed),
            "tools_used": tools_used,
            "servers_used": servers_used,
            "average_execution_time": avg_time
        }
    
    def get_recent_executions(self, limit: int = 10) -> List[ToolExecution]:
        """Get recent tool executions."""
        return self.execution_history[-limit:] if self.execution_history else []
    
    def clear_execution_history(self) -> None:
        """Clear the execution history."""
        self.execution_history = []
        logger.info("Cleared tool execution history")
    
    def format_execution_for_display(self, execution: ToolExecution) -> str:
        """Format a tool execution for display in the UI."""
        status = "✅" if execution.success else "❌"
        time_str = f"({execution.execution_time:.2f}s)" if execution.execution_time else ""
        
        result = f"{status} **{execution.tool_name}** on *{execution.server_name}* {time_str}\n"
        
        # Add arguments
        if execution.arguments:
            result += format_tool_call(execution.tool_name, execution.arguments) + "\n"
        
        # Add result or error
        if execution.success and execution.result:
            result += format_tool_result(execution.result)
        elif execution.error:
            result += format_tool_result(None, execution.error)
        
        return result 