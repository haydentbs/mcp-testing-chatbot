"""
AI function handler for integrating OpenAI with MCP tools.
"""
import json
import time
from typing import Dict, List, Optional, Any, AsyncGenerator, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ai.openai_client import OpenAIClient, ChatMessage
from mcp_client.tool_executor import MCPToolExecutor, ToolExecution
from utils.logger import logger


@dataclass 
class ConversationTurn:
    """Represents a complete conversation turn with tool executions."""
    user_message: str
    assistant_response: str
    tool_executions: List[ToolExecution] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    thinking_time: Optional[float] = None
    total_time: Optional[float] = None


@dataclass
class AIStatus:
    """Represents the current status of AI processing."""
    state: str  # "idle", "thinking", "executing_tool", "responding"
    current_activity: str
    start_time: float
    current_tool: Optional[str] = None
    tool_progress: Optional[str] = None
    tools_completed: int = 0
    total_tools: int = 0


class FunctionHandler:
    """Handles OpenAI function calling integration with MCP tools."""
    
    def __init__(self, openai_client: OpenAIClient, tool_executor: MCPToolExecutor):
        self.openai_client = openai_client
        self.tool_executor = tool_executor
        self.conversation_history: List[ChatMessage] = []
        self.conversation_turns: List[ConversationTurn] = []
        
        # Real-time status tracking
        self.current_status: AIStatus = AIStatus(
            state="idle",
            current_activity="Ready to chat",
            start_time=time.time()
        )
        self.status_history: List[AIStatus] = []
        
        # System message for MCP tool usage
        self.system_message = self._create_system_message()
        self.conversation_history.append(self.system_message)
    
    def _create_system_message(self) -> ChatMessage:
        """Create the system message that explains MCP tool usage."""
        content = f"""You are a helpful AI assistant with access to various tools through MCP (Model Context Protocol) servers. 

When a user asks you to perform tasks, you can:
1. Use available tools to accomplish the task
2. Execute multiple tools in sequence if needed
3. Provide detailed explanations of what you're doing
4. Handle errors gracefully and explain what went wrong

Available tools will be provided dynamically based on connected MCP servers. Each tool description includes the server name in brackets [server_name].

If you are saving a file, ensure you save it at the file path "workspace/FILE_NAME.EXTENSION"

Always be helpful, accurate, and explain your actions clearly to the user.

The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
        
        return self.openai_client.create_system_message(content)
    
    def _update_status(self, state: str, activity: str, current_tool: Optional[str] = None, 
                      tool_progress: Optional[str] = None, tools_completed: int = 0, total_tools: int = 0):
        """Update the current AI status."""
        # Archive current status
        if hasattr(self, 'current_status'):
            self.status_history.append(self.current_status)
        
        # Create new status
        self.current_status = AIStatus(
            state=state,
            current_activity=activity,
            start_time=time.time(),
            current_tool=current_tool,
            tool_progress=tool_progress,
            tools_completed=tools_completed,
            total_tools=total_tools
        )
        
        logger.info(f"AI Status: {state} - {activity}")
    
    def get_current_status(self) -> AIStatus:
        """Get the current AI status."""
        return self.current_status
    
    def get_status_history(self) -> List[AIStatus]:
        """Get the status history."""
        return self.status_history
    
    async def handle_user_message(
        self, 
        user_input: str, 
        stream: bool = False
    ) -> ConversationTurn:
        """
        Handle a user message, potentially making tool calls.
        
        Args:
            user_input: The user's message
            stream: Whether to use streaming responses
            
        Returns:
            ConversationTurn with the complete interaction
        """
        start_time = time.time()
        logger.info(f"Handling user message: {user_input[:100]}...")
        
        # Update status - starting to process
        self._update_status("thinking", "Processing your request...")
        
        # Add user message to conversation
        user_message = self.openai_client.create_user_message(user_input)
        self.conversation_history.append(user_message)
        
        tool_executions = []
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Update status - thinking
                self._update_status("thinking", f"Analyzing request (iteration {iteration})")
                
                # Get available functions
                functions = self.tool_executor.get_openai_function_definitions()
                
                # Update status - getting AI response
                self._update_status("thinking", "Getting AI response...")
                
                # Get response from OpenAI
                if stream:
                    # Handle streaming response
                    assistant_response, new_tool_executions = await self._handle_streaming_response(functions)
                else:
                    # Handle non-streaming response  
                    assistant_response, new_tool_executions = await self._handle_non_streaming_response(functions)
                
                tool_executions.extend(new_tool_executions)
                
                # If no tool calls were made, we're done
                if not new_tool_executions:
                    break
            
            # Update status - completing
            self._update_status("responding", "Finalizing response...")
            
            thinking_time = time.time() - start_time
            
            # Create conversation turn
            turn = ConversationTurn(
                user_message=user_input,
                assistant_response=assistant_response,
                tool_executions=tool_executions,
                thinking_time=thinking_time,
                total_time=thinking_time
            )
            
            # Update status - completed
            self._update_status("idle", "Ready for next message")
            
            self.conversation_turns.append(turn)
            return turn
            
        except Exception as e:
            error_msg = f"Error handling user message: {str(e)}"
            logger.error(error_msg)
            
            # Update status - error
            self._update_status("idle", f"Error: {error_msg}")
            
            # Create error turn
            turn = ConversationTurn(
                user_message=user_input,
                assistant_response=f"I encountered an error: {error_msg}",
                tool_executions=tool_executions,
                thinking_time=time.time() - start_time
            )
            
            self.conversation_turns.append(turn)
            return turn
    
    async def _handle_non_streaming_response(
        self, 
        functions: List[Dict]
    ) -> Tuple[str, List[ToolExecution]]:
        """Handle non-streaming response from OpenAI."""
        success, content, tool_calls, error = await self.openai_client.chat_completion(
            messages=self.conversation_history,
            functions=functions
        )
        
        if not success:
            raise Exception(f"OpenAI error: {error}")
        
        tool_executions = []
        
        # Create assistant message
        assistant_message = self.openai_client.create_assistant_message(content, tool_calls)
        self.conversation_history.append(assistant_message)
        
        # Execute tool calls if any
        if tool_calls:
            total_tools = len(tool_calls)
            for i, tool_call in enumerate(tool_calls):
                # Update status for tool execution
                self._update_status(
                    "executing_tool", 
                    f"Executing tool {i+1} of {total_tools}",
                    current_tool=tool_call["function"]["name"],
                    tools_completed=i,
                    total_tools=total_tools
                )
                
                execution = await self._execute_tool_call(tool_call)
                tool_executions.append(execution)
                
                # Add tool response to conversation
                tool_response = self.openai_client.create_tool_message(
                    content=self._format_tool_response(execution),
                    tool_call_id=tool_call["id"],
                    name=tool_call["function"]["name"]
                )
                self.conversation_history.append(tool_response)
        
        return content, tool_executions
    
    async def _handle_streaming_response(
        self, 
        functions: List[Dict]
    ) -> Tuple[str, List[ToolExecution]]:
        """Handle streaming response from OpenAI."""
        content_parts = []
        tool_calls = None
        
        self._update_status("thinking", "Receiving streaming response...")
        
        async for success, chunk, chunk_tool_calls, error in self.openai_client.chat_completion_stream(
            messages=self.conversation_history,
            functions=functions
        ):
            if not success:
                raise Exception(f"OpenAI streaming error: {error}")
            
            if chunk:
                content_parts.append(chunk)
            
            if chunk_tool_calls:
                tool_calls = chunk_tool_calls
        
        content = "".join(content_parts)
        tool_executions = []
        
        # Create assistant message
        assistant_message = self.openai_client.create_assistant_message(content, tool_calls)
        self.conversation_history.append(assistant_message)
        
        # Execute tool calls if any
        if tool_calls:
            total_tools = len(tool_calls)
            for i, tool_call in enumerate(tool_calls):
                # Update status for tool execution
                self._update_status(
                    "executing_tool", 
                    f"Executing tool {i+1} of {total_tools}",
                    current_tool=tool_call["function"]["name"],
                    tools_completed=i,
                    total_tools=total_tools
                )
                
                execution = await self._execute_tool_call(tool_call)
                tool_executions.append(execution)
                
                # Add tool response to conversation
                tool_response = self.openai_client.create_tool_message(
                    content=self._format_tool_response(execution),
                    tool_call_id=tool_call["id"],
                    name=tool_call["function"]["name"]
                )
                self.conversation_history.append(tool_response)
        
        return content, tool_executions
    
    async def _execute_tool_call(self, tool_call: Dict) -> ToolExecution:
        """Execute a single tool call."""
        function_name = tool_call["function"]["name"]
        function_args = tool_call["function"]["arguments"]
        
        logger.info(f"Executing tool call: {function_name}")
        
        # Update status with specific tool being executed
        self._update_status(
            "executing_tool", 
            f"Running {function_name}...",
            current_tool=function_name,
            tool_progress="Starting execution"
        )
        
        try:
            # Parse arguments
            if isinstance(function_args, str):
                arguments = json.loads(function_args)
            else:
                arguments = function_args
            
            # Update progress
            self._update_status(
                "executing_tool", 
                f"Running {function_name}...",
                current_tool=function_name,
                tool_progress="Executing with parsed arguments"
            )
            
            # Execute the tool
            execution = await self.tool_executor.execute_tool_by_name(function_name, arguments)
            
            # Update completion status
            status_msg = "✅ Completed successfully" if execution.success else "❌ Failed"
            self._update_status(
                "executing_tool", 
                f"{function_name}: {status_msg}",
                current_tool=function_name,
                tool_progress=status_msg
            )
            
            return execution
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid function arguments: {e}"
            logger.error(error_msg)
            
            self._update_status(
                "executing_tool", 
                f"{function_name}: ❌ Argument parsing failed",
                current_tool=function_name,
                tool_progress="Failed - Invalid arguments"
            )
            
            return ToolExecution(
                tool_name=function_name,
                server_name="unknown",
                arguments={},
                success=False,
                error=error_msg
            )
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error executing tool call: {e}")
            
            self._update_status(
                "executing_tool", 
                f"{function_name}: ❌ Execution failed",
                current_tool=function_name,
                tool_progress=f"Failed - {error_msg}"
            )
            
            return ToolExecution(
                tool_name=function_name,
                server_name="unknown", 
                arguments={},
                success=False,
                error=error_msg
            )
    
    def _format_tool_response(self, execution: ToolExecution) -> str:
        """Format tool execution result for OpenAI."""
        if execution.success:
            if execution.result:
                return json.dumps(execution.result, indent=2)
            else:
                return "Tool executed successfully with no output."
        else:
            return f"Error: {execution.error}"
    
    def get_conversation_summary(self) -> Dict[str, Any]:
        """Get summary of the conversation."""
        if not self.conversation_turns:
            return {
                "total_turns": 0,
                "successful_turns": 0,
                "failed_turns": 0,
                "total_tool_executions": 0,
                "unique_tools_used": [],
                "unique_servers_used": []
            }
        
        # Count successful turns based on whether they have any failed tool executions
        successful_turns = []
        failed_turns = []
        
        for turn in self.conversation_turns:
            has_failures = any(not exec.success for exec in turn.tool_executions)
            if has_failures:
                failed_turns.append(turn)
            else:
                successful_turns.append(turn)
        
        all_tool_executions = []
        for turn in self.conversation_turns:
            all_tool_executions.extend(turn.tool_executions)
        
        unique_tools = list(set(exec.tool_name for exec in all_tool_executions))
        unique_servers = list(set(exec.server_name for exec in all_tool_executions))
        
        return {
            "total_turns": len(self.conversation_turns),
            "successful_turns": len(successful_turns),
            "failed_turns": len(failed_turns),
            "total_tool_executions": len(all_tool_executions),
            "unique_tools_used": unique_tools,
            "unique_servers_used": unique_servers
        }
    
    def clear_conversation(self) -> None:
        """Clear the conversation history and reset status."""
        self.conversation_history = [self.system_message]  # Keep system message
        self.conversation_turns = []
        self.status_history = []
        self._update_status("idle", "Ready to chat")
        logger.info("Cleared conversation history")
    
    def get_recent_turns(self, limit: int = 5) -> List[ConversationTurn]:
        """Get recent conversation turns."""
        return self.conversation_turns[-limit:] if self.conversation_turns else []
    
    def export_conversation(self) -> Dict[str, Any]:
        """Export conversation data for analysis."""
        return {
            "conversation_summary": self.get_conversation_summary(),
            "turns": [
                {
                    "user_message": turn.user_message,
                    "assistant_response": turn.assistant_response,
                    "tool_executions": [
                        {
                            "tool_name": exec.tool_name,
                            "server_name": exec.server_name,
                            "arguments": exec.arguments,
                            "success": exec.success,
                            "result": exec.result,
                            "error": exec.error,
                            "execution_time": exec.execution_time
                        }
                        for exec in turn.tool_executions
                    ],
                    "thinking_time": turn.thinking_time,
                    "total_time": turn.total_time,
                    "timestamp": turn.timestamp
                }
                for turn in self.conversation_turns
            ],
            "status_history": [
                {
                    "state": status.state,
                    "activity": status.current_activity,
                    "start_time": status.start_time,
                    "current_tool": status.current_tool,
                    "tool_progress": status.tool_progress,
                    "tools_completed": status.tools_completed,
                    "total_tools": status.total_tools
                }
                for status in self.status_history
            ]
        } 