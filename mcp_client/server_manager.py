"""
MCP Server Manager for handling server configurations and lifecycle.
"""
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from mcp_client.client import MCPClient, MCPServer, ServerStatus
from config.settings import get_mcp_servers_config, save_mcp_servers_config
from utils.logger import logger


class MCPServerManager:
    """Manages MCP server configurations and lifecycle."""
    
    def __init__(self):
        self.client = MCPClient()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """Initialize the server manager with configured servers."""
        if self._initialized:
            return True
        
        try:
            # Load server configurations
            server_configs = get_mcp_servers_config()
            
            # Add servers to client
            for config in server_configs:
                await self.client.add_server(config)
            
            self._initialized = True
            logger.info(f"Initialized MCP server manager with {len(server_configs)} servers")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server manager: {e}")
            return False
    
    async def refresh_servers(self) -> Dict[str, bool]:
        """Refresh all enabled servers and return connection results."""
        if not self._initialized:
            await self.initialize()
        
        results = {}
        
        # Get list of servers to connect/disconnect
        servers_to_connect = []
        servers_to_disconnect = []
        
        for server_name, server in self.client.servers.items():
            if server.enabled:
                if server.status != ServerStatus.CONNECTED:
                    servers_to_connect.append(server_name)
                results[server_name] = True  # Will be updated after connection attempt
            else:
                if server.status == ServerStatus.CONNECTED:
                    servers_to_disconnect.append(server_name)
                results[server_name] = False
        
        # Disconnect servers that should be disabled (gracefully)
        for server_name in servers_to_disconnect:
            await self.client.disconnect_server(server_name)
        
        # Connect enabled servers one by one with delay to prevent overwhelming
        for i, server_name in enumerate(servers_to_connect):
            if i > 0:
                # Add small delay between connections to prevent overwhelming the system
                await asyncio.sleep(0.1)
            
            success = await self.client.connect_server(server_name)
            results[server_name] = success
            
            if not success:
                logger.warning(f"Failed to connect to server {server_name} during refresh")
        
        return results
    
    async def startup_connect_servers(self) -> Dict[str, bool]:
        """Connect to servers during startup with optimized sequence."""
        # Prevent concurrent startup sequences
        if hasattr(self, '_startup_in_progress') and self._startup_in_progress:
            logger.warning("Startup connection sequence already in progress, skipping...")
            return {}
        
        self._startup_in_progress = True
        
        try:
            if not self._initialized:
                await self.initialize()
            
            results = {}
            
            # Get enabled servers
            enabled_servers = [
                (name, server) for name, server in self.client.servers.items() 
                if server.enabled
            ]
            
            if not enabled_servers:
                return results
            
            logger.info(f"Starting connection to {len(enabled_servers)} enabled servers...")
            
            # Connect to servers one by one with spacing
            for i, (server_name, server) in enumerate(enabled_servers):
                if i > 0:
                    # Add delay between connections to prevent overwhelming
                    await asyncio.sleep(0.3)  # Increased delay
                
                logger.info(f"Connecting to server {i+1}/{len(enabled_servers)}: {server_name}")
                success = await self.connect_server(server_name)
                results[server_name] = success
                
                if success:
                    logger.info(f"✅ Successfully connected to {server_name}")
                else:
                    logger.warning(f"❌ Failed to connect to {server_name}")
            
            # Set disabled servers as false
            for server_name, server in self.client.servers.items():
                if not server.enabled:
                    results[server_name] = False
            
            return results
            
        finally:
            self._startup_in_progress = False
    
    async def connect_server(self, server_name: str) -> bool:
        """Connect to a specific server with retry logic."""
        max_retries = 2
        retry_delay = 1.0
        
        for attempt in range(max_retries + 1):
            try:
                success = await self.client.connect_server(server_name)
                if success:
                    return True
                
                if attempt < max_retries:
                    logger.info(f"Connection attempt {attempt + 1} failed for {server_name}, retrying in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed for {server_name}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 1.5
        
        logger.error(f"Failed to connect to {server_name} after {max_retries + 1} attempts")
        return False
    
    async def disconnect_server(self, server_name: str) -> bool:
        """Disconnect from a specific server."""
        return await self.client.disconnect_server(server_name)
    
    def get_server_info(self, server_name: str) -> Optional[Dict]:
        """Get information about a specific server."""
        server = self.client.servers.get(server_name)
        if not server:
            return None
        
        return {
            "name": server.name,
            "description": server.description,
            "status": server.status.value,
            "enabled": server.enabled,
            "tools_count": len(server.tools),
            "tools": [{"name": t.name, "description": t.description} for t in server.tools],
            "last_error": server.last_error,
            "connection_time": server.connection_time,
            "has_detailed_errors": bool(server.last_error or server.stderr_output or server.stdout_output)
        }
    
    def get_all_servers_info(self) -> List[Dict]:
        """Get information about all servers."""
        servers_info = []
        for server_name in self.client.servers:
            info = self.get_server_info(server_name)
            if info:
                servers_info.append(info)
        return servers_info
    
    def get_connected_servers(self) -> List[str]:
        """Get list of connected server names."""
        connected = []
        for server_name, server in self.client.servers.items():
            if server.status == ServerStatus.CONNECTED:
                connected.append(server_name)
        return connected
    
    def get_available_tools(self) -> Dict[str, List[Dict]]:
        """Get all available tools grouped by server."""
        tools_by_server = {}
        for server_name, server in self.client.servers.items():
            if server.status == ServerStatus.CONNECTED:
                tools_by_server[server_name] = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.input_schema
                    }
                    for tool in server.tools
                ]
        return tools_by_server
    
    async def execute_tool(self, server_name: str, tool_name: str, arguments: Dict) -> Dict:
        """Execute a tool and return formatted result."""
        success, result, error = await self.client.execute_tool(server_name, tool_name, arguments)
        
        return {
            "success": success,
            "result": result,
            "error": error,
            "server_name": server_name,
            "tool_name": tool_name,
            "arguments": arguments
        }
    
    async def add_server_config(self, config: Dict) -> bool:
        """Add a new server configuration."""
        try:
            # Add to current client
            success = await self.client.add_server(config)
            if not success:
                return False
            
            # Update configuration file
            current_configs = get_mcp_servers_config()
            current_configs.append(config)
            return save_mcp_servers_config(current_configs)
            
        except Exception as e:
            logger.error(f"Failed to add server config: {e}")
            return False
    
    async def update_server_config(self, server_name: str, updates: Dict) -> bool:
        """Update an existing server configuration."""
        try:
            # Update configuration file
            current_configs = get_mcp_servers_config()
            for config in current_configs:
                if config["name"] == server_name:
                    config.update(updates)
                    break
            else:
                return False  # Server not found
            
            if not save_mcp_servers_config(current_configs):
                return False
            
            # Update client (requires reconnection)
            server = self.client.servers.get(server_name)
            if server:
                await self.client.disconnect_server(server_name)
                # Update server object
                for key, value in updates.items():
                    if hasattr(server, key):
                        setattr(server, key, value)
                
                # Reconnect if enabled
                if server.enabled:
                    await self.client.connect_server(server_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update server config: {e}")
            return False
    
    async def toggle_server(self, server_name: str) -> bool:
        """Toggle server enabled/disabled state."""
        server = self.client.servers.get(server_name)
        if not server:
            return False
        
        new_enabled = not server.enabled
        return await self.update_server_config(server_name, {"enabled": new_enabled})
    
    async def remove_server_config(self, server_name: str) -> bool:
        """Remove a server configuration."""
        try:
            # Disconnect first
            await self.client.disconnect_server(server_name)
            
            # Remove from client
            if server_name in self.client.servers:
                del self.client.servers[server_name]
            
            # Update configuration file
            current_configs = get_mcp_servers_config()
            updated_configs = [c for c in current_configs if c["name"] != server_name]
            return save_mcp_servers_config(updated_configs)
            
        except Exception as e:
            logger.error(f"Failed to remove server config: {e}")
            return False
    
    def get_server_status_summary(self) -> Dict[str, int]:
        """Get summary of server statuses."""
        summary = {
            "total": 0,
            "connected": 0,
            "disconnected": 0,
            "error": 0,
            "connecting": 0
        }
        
        for server in self.client.servers.values():
            summary["total"] += 1
            if server.status == ServerStatus.CONNECTED:
                summary["connected"] += 1
            elif server.status == ServerStatus.DISCONNECTED:
                summary["disconnected"] += 1
            elif server.status == ServerStatus.ERROR:
                summary["error"] += 1
            elif server.status == ServerStatus.CONNECTING:
                summary["connecting"] += 1
        
        return summary
    
    def get_server_error_details(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed error information for a specific server."""
        server = self.client.servers.get(server_name)
        if not server:
            return None
        
        # Only return error details if server is in error state or has error info
        if server.status != ServerStatus.ERROR and not server.last_error:
            return None
        
        import datetime
        
        error_details = {
            "server_name": server.name,
            "status": server.status.value,
            "last_error": server.last_error,
            "error_timestamp": server.error_timestamp,
            "error_time_formatted": None,
            "full_command": server.full_command,
            "process_exit_code": server.process_exit_code,
            "stderr_output": server.stderr_output,
            "stdout_output": server.stdout_output,
            "server_config": {
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "enabled": server.enabled,
                "description": server.description
            }
        }
        
        # Format timestamp if available
        if server.error_timestamp:
            error_details["error_time_formatted"] = datetime.datetime.fromtimestamp(
                server.error_timestamp
            ).strftime("%Y-%m-%d %H:%M:%S")
        
        return error_details 