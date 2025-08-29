"""
OpenAI client integration with GPT-4o-nano and function calling support.
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator
from dataclasses import dataclass
import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from config.settings import settings
from utils.logger import logger
from utils.helpers import Timer


@dataclass
class ChatMessage:
    """Represents a chat message."""
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class OpenAIClient:
    """OpenAI client for chat completions with function calling."""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.temperature = settings.openai_temperature
        
        # Request deduplication
        self._active_requests = {}
        self._request_lock = asyncio.Lock()
        
    def _create_request_hash(self, messages: List[ChatMessage], functions: Optional[List[Dict]] = None) -> str:
        """Create a hash for request deduplication."""
        import hashlib
        
        # Create a deterministic hash based on messages and functions
        content = ""
        for msg in messages:
            content += f"{msg.role}:{msg.content or ''}"
            if msg.tool_calls:
                content += str(msg.tool_calls)
        
        if functions:
            # Only include function names and descriptions for hash (ignore full schemas)
            func_content = ""
            for func in functions:
                func_content += f"{func.get('name', '')}:{func.get('description', '')}"
            content += func_content
        
        return hashlib.md5(content.encode()).hexdigest()
        
    async def chat_completion(
        self,
        messages: List[ChatMessage],
        functions: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Tuple[bool, str, Optional[List[Dict]], Optional[str]]:
        """
        Get chat completion from OpenAI.
        
        Returns:
            (success, content, tool_calls, error)
        """
        try:
            # Convert our message format to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            # Prepare request parameters
            request_params = {
                "model": self.model,
                "messages": openai_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": stream
            }
            
            # Add functions if provided
            if functions:
                request_params["tools"] = [
                    {"type": "function", "function": func} for func in functions
                ]
                request_params["tool_choice"] = "auto"
            
            logger.info(f"Making OpenAI request with {len(openai_messages)} messages")
            
            with Timer() as timer:
                if stream:
                    return await self._handle_streaming_response(request_params)
                else:
                    response = await self.client.chat.completions.create(**request_params)
                    return self._handle_response(response, timer.elapsed)
                    
        except Exception as e:
            error_msg = f"OpenAI API error: {str(e)}"
            logger.error(error_msg)
            return False, "", None, error_msg
    
    async def chat_completion_stream(
        self,
        messages: List[ChatMessage],
        functions: Optional[List[Dict]] = None
    ) -> AsyncGenerator[Tuple[bool, str, Optional[List[Dict]], Optional[str]], None]:
        """
        Get streaming chat completion from OpenAI.
        
        Yields:
            (success, content_chunk, tool_calls, error)
        """
        try:
            # Convert our message format to OpenAI format
            openai_messages = self._convert_messages_to_openai(messages)
            
            # Prepare request parameters
            request_params = {
                "model": self.model,
                "messages": openai_messages,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "stream": True
            }
            
            # Add functions if provided
            if functions:
                request_params["tools"] = [
                    {"type": "function", "function": func} for func in functions
                ]
                request_params["tool_choice"] = "auto"
            
            logger.info(f"Making streaming OpenAI request with {len(openai_messages)} messages")
            
            collected_tool_calls = []
            
            async for chunk in await self.client.chat.completions.create(**request_params):
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    
                    # Handle content
                    if delta.content:
                        yield True, delta.content, None, None
                    
                    # Handle tool calls
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            # Extend collected tool calls list if needed
                            while len(collected_tool_calls) <= tool_call.index:
                                collected_tool_calls.append({
                                    "id": "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                })
                            
                            # Update the tool call
                            if tool_call.id:
                                collected_tool_calls[tool_call.index]["id"] = tool_call.id
                            if tool_call.function.name:
                                collected_tool_calls[tool_call.index]["function"]["name"] = tool_call.function.name
                            if tool_call.function.arguments:
                                collected_tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
                    
                    # Check if we're done
                    if choice.finish_reason == "tool_calls" and collected_tool_calls:
                        yield True, "", collected_tool_calls, None
                    elif choice.finish_reason == "stop":
                        yield True, "", None, None
                        
        except Exception as e:
            error_msg = f"OpenAI streaming error: {str(e)}"
            logger.error(error_msg)
            yield False, "", None, error_msg
    
    def _convert_messages_to_openai(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """Convert our message format to OpenAI format."""
        openai_messages = []
        
        for msg in messages:
            openai_msg = {
                "role": msg.role,
                "content": msg.content
            }
            
            # Add tool calls if present
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            
            # Add tool call ID if present (for tool response messages)
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            
            # Add name if present
            if msg.name:
                openai_msg["name"] = msg.name
            
            openai_messages.append(openai_msg)
        
        return openai_messages
    
    def _handle_response(self, response: ChatCompletion, elapsed_time: float) -> Tuple[bool, str, Optional[List[Dict]], Optional[str]]:
        """Handle non-streaming response."""
        try:
            choice = response.choices[0]
            message = choice.message
            
            content = message.content or ""
            tool_calls = None
            
            # Extract tool calls if present
            if message.tool_calls:
                tool_calls = []
                for tool_call in message.tool_calls:
                    tool_calls.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
            
            logger.info(f"OpenAI response received in {elapsed_time:.2f}s")
            return True, content, tool_calls, None
            
        except Exception as e:
            error_msg = f"Error processing OpenAI response: {str(e)}"
            logger.error(error_msg)
            return False, "", None, error_msg
    
    async def _handle_streaming_response(self, request_params: Dict) -> Tuple[bool, str, Optional[List[Dict]], Optional[str]]:
        """Handle streaming response for non-generator usage."""
        content_parts = []
        tool_calls = []
        
        try:
            async for chunk in await self.client.chat.completions.create(**request_params):
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    
                    if delta.content:
                        content_parts.append(delta.content)
                    
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            # Handle tool call collection (simplified for non-streaming)
                            if tool_call.function and tool_call.function.name:
                                tool_calls.append({
                                    "id": tool_call.id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments or ""
                                    }
                                })
            
            content = "".join(content_parts)
            return True, content, tool_calls if tool_calls else None, None
            
        except Exception as e:
            error_msg = f"Error processing streaming response: {str(e)}"
            logger.error(error_msg)
            return False, "", None, error_msg
    
    def create_system_message(self, content: str) -> ChatMessage:
        """Create a system message."""
        return ChatMessage(role="system", content=content)
    
    def create_user_message(self, content: str) -> ChatMessage:
        """Create a user message."""
        return ChatMessage(role="user", content=content)
    
    def create_assistant_message(self, content: str, tool_calls: Optional[List[Dict]] = None) -> ChatMessage:
        """Create an assistant message."""
        return ChatMessage(role="assistant", content=content, tool_calls=tool_calls)
    
    def create_tool_message(self, content: str, tool_call_id: str, name: str) -> ChatMessage:
        """Create a tool response message."""
        return ChatMessage(role="tool", content=content, tool_call_id=tool_call_id, name=name)
    
    async def test_connection(self) -> Tuple[bool, str]:
        """Test the OpenAI connection."""
        try:
            test_messages = [
                self.create_system_message("You are a helpful assistant."),
                self.create_user_message("Hello! Just say 'Hello back' to confirm the connection.")
            ]
            
            success, content, _, error = await self.chat_completion(test_messages)
            
            if success:
                return True, f"Connection successful. Model response: {content}"
            else:
                return False, f"Connection failed: {error}"
                
        except Exception as e:
            return False, f"Connection test failed: {str(e)}" 