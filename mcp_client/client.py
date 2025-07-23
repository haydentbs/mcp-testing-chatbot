"""
MCP Client implementation for connecting to and communicating with MCP servers.
"""
import asyncio
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from utils.logger import logger
from utils.helpers import Timer
from config.settings import settings


class ServerStatus(Enum):
    """Status of an MCP server."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class MCPTool:
    """Represents an MCP tool/function."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str


@dataclass
class MCPServer:
    """Represents an MCP server configuration and state."""
    name: str
    command: str
    args: List[str]
    description: str
    enabled: bool = True
    env: Dict[str, str] = field(default_factory=dict)
    status: ServerStatus = ServerStatus.DISCONNECTED
    tools: List[MCPTool] = field(default_factory=list)
    last_error: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    connection_time: Optional[float] = None
    # Enhanced error details
    stderr_output: Optional[str] = None
    stdout_output: Optional[str] = None
    process_exit_code: Optional[int] = None
    full_command: Optional[str] = None
    error_timestamp: Optional[float] = None


class MCPClient:
    """Client for managing MCP server connections and tool execution."""
    
    def __init__(self):
        self.servers: Dict[str, MCPServer] = {}
        self._lock = asyncio.Lock()
    
    async def add_server(self, server_config: Dict[str, Any]) -> bool:
        """Add a new MCP server configuration."""
        try:
            server = MCPServer(
                name=server_config["name"],
                command=server_config["command"],
                args=server_config["args"],
                description=server_config["description"],
                enabled=server_config.get("enabled", True),
                env=server_config.get("env", {})
            )
            
            async with self._lock:
                self.servers[server.name] = server
            
            logger.info(f"Added MCP server: {server.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add server {server_config.get('name', 'unknown')}: {e}")
            return False
    
    async def connect_server(self, server_name: str) -> bool:
        """Connect to an MCP server and discover its tools."""
        server = self.servers.get(server_name)
        if not server:
            logger.error(f"Server {server_name} not found")
            return False
        
        if not server.enabled:
            logger.info(f"Server {server_name} is disabled")
            return False
        
        try:
            server.status = ServerStatus.CONNECTING
            server.last_error = None
            # Clear previous error details
            server.stderr_output = None
            server.stdout_output = None
            server.process_exit_code = None
            server.error_timestamp = None
            
            # Store full command for debugging
            server.full_command = " ".join([server.command] + server.args)
            
            with Timer() as timer:
                # Start the MCP server process with proper environment inheritance
                env = os.environ.copy()  # Start with current environment (includes PATH)
                if server.env:
                    env.update(server.env)  # Add server-specific environment variables
                
                server.process = subprocess.Popen(
                    [server.command] + server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=env
                )
                
                # Initialize connection with the server
                await self._initialize_connection(server)
                
                # Discover available tools
                await self._discover_tools(server)
            
            server.status = ServerStatus.CONNECTED
            server.connection_time = timer.elapsed
            logger.info(f"Connected to MCP server {server_name} in {timer.elapsed:.2f}s")
            return True
            
        except Exception as e:
            server.status = ServerStatus.ERROR
            server.last_error = str(e)
            server.error_timestamp = time.time()
            
            # Capture detailed error information
            await self._capture_error_details(server, e)
            
            logger.error(f"Failed to connect to MCP server {server_name}: {e}")
            return False
    
    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from an MCP server."""
        server = self.servers.get(server_name)
        if not server:
            return False
        
        try:
            if server.process:
                server.process.terminate()
                try:
                    server.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.process.kill()
                server.process = None
            
            server.status = ServerStatus.DISCONNECTED
            server.tools = []
            server.connection_time = None
            logger.info(f"Disconnected from MCP server {server_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from server {server_name}: {e}")
            return False
    
    async def _initialize_connection(self, server: MCPServer) -> None:
        """Initialize connection with MCP server."""
        # Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "clientInfo": {
                    "name": "mcp-streamlit-tester",
                    "version": "1.0.0"
                }
            }
        }
        
        # Send request to server
        await self._send_request(server, init_request)
        
        # Send initialized notification
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        await self._send_request(server, initialized_notification)
    
    async def _discover_tools(self, server: MCPServer) -> None:
        """Discover tools available on the MCP server."""
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        
        response = await self._send_request(server, tools_request)
        
        if response and "result" in response and "tools" in response["result"]:
            server.tools = []
            for tool_data in response["result"]["tools"]:
                tool = MCPTool(
                    name=tool_data["name"],
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    server_name=server.name
                )
                server.tools.append(tool)
            
            logger.info(f"Discovered {len(server.tools)} tools on server {server.name}")
    
    async def _send_request(self, server: MCPServer, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a request to the MCP server and get response."""
        if not server.process or not server.process.stdin:
            raise Exception("Server process not available")
        
        # Send request
        request_str = json.dumps(request) + "\n"
        server.process.stdin.write(request_str)
        server.process.stdin.flush()
        
        # Read response (if expecting one)
        if "id" in request:
            response_str = server.process.stdout.readline()
            if response_str:
                try:
                    return json.loads(response_str.strip())
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse response: {e}")
        
        return None
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Any, Optional[str]]:
        """Execute a tool on the specified MCP server."""
        server = self.servers.get(server_name)
        if not server:
            return False, None, f"Server {server_name} not found"
        
        if server.status != ServerStatus.CONNECTED:
            return False, None, f"Server {server_name} is not connected"
        
        # Check if tool exists
        tool = next((t for t in server.tools if t.name == tool_name), None)
        if not tool:
            return False, None, f"Tool {tool_name} not found on server {server_name}"
        
        try:
            # Prepare tool call request
            tool_request = {
                "jsonrpc": "2.0",
                "id": int(time.time() * 1000),  # Use timestamp as ID
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            # Execute tool
            response = await self._send_request(server, tool_request)
            
            if response and "result" in response:
                return True, response["result"], None
            elif response and "error" in response:
                error_msg = response["error"].get("message", "Unknown error")
                return False, None, error_msg
            else:
                return False, None, "No response from server"
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name} on server {server_name}: {e}")
            return False, None, str(e)
    
    def get_server_status(self, server_name: str) -> Optional[ServerStatus]:
        """Get the status of a specific server."""
        server = self.servers.get(server_name)
        return server.status if server else None
    
    def get_all_tools(self) -> List[MCPTool]:
        """Get all tools from all connected servers."""
        all_tools = []
        for server in self.servers.values():
            if server.status == ServerStatus.CONNECTED:
                all_tools.extend(server.tools)
        return all_tools
    
    def get_server_tools(self, server_name: str) -> List[MCPTool]:
        """Get tools from a specific server."""
        server = self.servers.get(server_name)
        return server.tools if server else []
    
    async def refresh_servers(self) -> None:
        """Refresh all enabled servers."""
        for server_name, server in self.servers.items():
            if server.enabled and server.status != ServerStatus.CONNECTED:
                await self.connect_server(server_name)
    
    async def disconnect_all(self) -> None:
        """Disconnect from all servers."""
        for server_name in list(self.servers.keys()):
            await self.disconnect_server(server_name)
    
    async def _capture_error_details(self, server: MCPServer, exception: Exception) -> None:
        """Capture detailed error information when server connection fails."""
        try:
            # Capture process output if process exists
            if server.process:
                # Check if process is still running
                if server.process.poll() is None:
                    # Process is still running, terminate it
                    server.process.terminate()
                    try:
                        server.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        server.process.kill()
                        server.process.wait()
                
                # Get exit code
                server.process_exit_code = server.process.returncode
                
                # Read remaining output
                try:
                    if server.process.stderr:
                        stderr_data = server.process.stderr.read()
                        if stderr_data:
                            server.stderr_output = stderr_data.strip()
                    
                    if server.process.stdout:
                        stdout_data = server.process.stdout.read()
                        if stdout_data:
                            server.stdout_output = stdout_data.strip()
                
                except Exception as read_error:
                    logger.warning(f"Could not read process output for {server.name}: {read_error}")
                    if not server.stderr_output:
                        server.stderr_output = f"Error reading stderr: {read_error}"
            else:
                # Process was never created
                server.stderr_output = f"Process failed to start: {exception}"
                
        except Exception as capture_error:
            logger.warning(f"Error capturing detailed error info for {server.name}: {capture_error}")
            server.stderr_output = f"Error capturing details: {capture_error}" 