"""
Function handler for managing OpenAI function calling with MCP tools.
"""
import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

from ai.openai_client import OpenAIClient, ChatMessage
from mcp_client.tool_executor import MCPToolExecutor, ToolExecution
from utils.logger import logger
from utils.helpers import format_tool_call, format_tool_result


@dataclass
class ConversationTurn:
    """Represents a complete conversation turn with tool calls."""
    user_message: str
    assistant_response: str
    tool_executions: List[ToolExecution]
    success: bool
    error: Optional[str] = None


class FunctionHandler:
    """Handles OpenAI function calling integration with MCP tools."""
    
    def __init__(self, openai_client: OpenAIClient, tool_executor: MCPToolExecutor):
        self.openai_client = openai_client
        self.tool_executor = tool_executor
        self.conversation_history: List[ChatMessage] = []
        self.conversation_turns: List[ConversationTurn] = []
        
        # System message for MCP tool usage
        self.system_message = self._create_system_message()
        self.conversation_history.append(self.system_message)
    
    def _create_system_message(self) -> ChatMessage:
        """Create the system message that explains MCP tool usage."""
        content = """You are a helpful AI assistant with access to various tools through MCP (Model Context Protocol) servers. 

When a user asks you to perform tasks, you can:
1. Use available tools to accomplish the task
2. Execute multiple tools in sequence if needed
3. Provide detailed explanations of what you're doing
4. Handle errors gracefully and explain what went wrong

Available tools will be provided dynamically based on connected MCP servers. Each tool description includes the server name in brackets [server_name].

Always be helpful, accurate, and explain your actions clearly to the user."""
        
        return self.openai_client.create_system_message(content)
    
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
        logger.info(f"Handling user message: {user_input[:100]}...")
        
        # Add user message to conversation
        user_message = self.openai_client.create_user_message(user_input)
        self.conversation_history.append(user_message)
        
        tool_executions = []
        max_iterations = 5  # Prevent infinite loops
        iteration = 0
        
        try:
            while iteration < max_iterations:
                iteration += 1
                
                # Get available functions
                functions = self.tool_executor.get_openai_function_definitions()
                
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
            
            # Create conversation turn
            turn = ConversationTurn(
                user_message=user_input,
                assistant_response=assistant_response,
                tool_executions=tool_executions,
                success=True
            )
            
            self.conversation_turns.append(turn)
            return turn
            
        except Exception as e:
            error_msg = f"Error handling user message: {str(e)}"
            logger.error(error_msg)
            
            # Create error turn
            turn = ConversationTurn(
                user_message=user_input,
                assistant_response=f"I encountered an error: {error_msg}",
                tool_executions=tool_executions,
                success=False,
                error=error_msg
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
            for tool_call in tool_calls:
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
            for tool_call in tool_calls:
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
        
        try:
            # Parse arguments
            if isinstance(function_args, str):
                arguments = json.loads(function_args)
            else:
                arguments = function_args
            
            # Execute the tool
            execution = await self.tool_executor.execute_tool_by_name(function_name, arguments)
            return execution
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid function arguments: {e}")
            return ToolExecution(
                tool_name=function_name,
                server_name="unknown",
                arguments={},
                success=False,
                error=f"Invalid function arguments: {e}"
            )
        except Exception as e:
            logger.error(f"Error executing tool call: {e}")
            return ToolExecution(
                tool_name=function_name,
                server_name="unknown", 
                arguments={},
                success=False,
                error=str(e)
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
        
        successful_turns = [t for t in self.conversation_turns if t.success]
        failed_turns = [t for t in self.conversation_turns if not t.success]
        
        all_tool_executions = []
        for turn in self.conversation_turns:
            all_tool_executions.extend(turn.tool_executions)
        
        unique_tools = list(set(e.tool_name for e in all_tool_executions))
        unique_servers = list(set(e.server_name for e in all_tool_executions))
        
        return {
            "total_turns": len(self.conversation_turns),
            "successful_turns": len(successful_turns),
            "failed_turns": len(failed_turns),
            "total_tool_executions": len(all_tool_executions),
            "unique_tools_used": unique_tools,
            "unique_servers_used": unique_servers
        }
    
    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = [self.system_message]
        self.conversation_turns = []
        logger.info("Cleared conversation history")
    
    def get_recent_turns(self, limit: int = 5) -> List[ConversationTurn]:
        """Get recent conversation turns."""
        return self.conversation_turns[-limit:] if self.conversation_turns else []
    
    def export_conversation(self) -> Dict[str, Any]:
        """Export the conversation for analysis or saving."""
        return {
            "conversation_history": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "tool_calls": msg.tool_calls,
                    "tool_call_id": msg.tool_call_id,
                    "name": msg.name
                }
                for msg in self.conversation_history
            ],
            "conversation_turns": [
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
                    "success": turn.success,
                    "error": turn.error
                }
                for turn in self.conversation_turns
            ],
            "summary": self.get_conversation_summary()
        } 