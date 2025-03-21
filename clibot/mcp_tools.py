"""MCP tools integration for CliBot."""

import json
import shlex
import subprocess
from typing import Any, Dict, List, Optional
import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import ui
from .config import Config

class MCPToolsManager:
    """Manager for MCP tools execution."""
    
    def __init__(self, config: Config):
        self.config = config
        self.processes = {}  # Cache for MCP server processes
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    def _run_async(self, coro):
        """Run an async coroutine in a new event loop in a separate thread."""
        loop = asyncio.new_event_loop()
        
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    def _create_server_params(self, server_name: str) -> StdioServerParameters:
        """Create server parameters for the specified server."""
        server_config = self.config.get_mcp_server(server_name)
        if not server_config:
            raise ValueError("MCP server '%s' not found in configuration" % server_name)
        
        # Create server parameters for stdio connection
        server_params = StdioServerParameters(
            command=server_config.command,
            args=server_config.args,
            env=server_config.env
        )
        
        if self.config.verbose:
            ui.print_verbose(f"Creating MCP client for server: {server_name}")
            ui.print_verbose(f"Command: {server_config.command}")
            ui.print_verbose(f"Args: {server_config.args}")
        
        return server_params
    
    async def _execute_with_session(self, server_name: str, operation):
        """Execute an operation with a new session."""
        server_params = self._create_server_params(server_name)
        
        if self.config.verbose:
            ui.print_verbose(f"Starting MCP session for server: {server_name}")
        
        # Create a new session for each operation
        try:
            if self.config.verbose:
                ui.print_verbose(f"Opening stdio client for server: {server_name}")
            
            async with stdio_client(server_params) as (read, write):
                if self.config.verbose:
                    ui.print_verbose(f"Creating client session for server: {server_name}")
                
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    if self.config.verbose:
                        ui.print_verbose(f"Initializing session for server: {server_name}")
                    
                    await session.initialize()
                    
                    if self.config.verbose:
                        ui.print_verbose(f"Session initialized for server: {server_name}")
                    
                    # Execute the operation
                    if self.config.verbose:
                        ui.print_verbose(f"Executing operation for server: {server_name}")
                    
                    result = await operation(session)
                    
                    if self.config.verbose:
                        ui.print_verbose(f"Operation executed for server: {server_name}")
                        ui.print_verbose(f"Result type: {type(result)}")
                        if isinstance(result, tuple):
                            ui.print_verbose(f"Tuple length: {len(result)}")
                            for i, item in enumerate(result):
                                ui.print_verbose(f"Item {i} type: {type(item)}")
                        elif isinstance(result, dict):
                            ui.print_verbose(f"Dict keys: {result.keys()}")
                        elif isinstance(result, list):
                            ui.print_verbose(f"List length: {len(result)}")
                    
                    return result
        except Exception as e:
            if self.config.verbose:
                ui.print_verbose(f"Error in _execute_with_session for server {server_name}: {str(e)}")
                import traceback
                ui.print_verbose(f"Traceback: {traceback.format_exc()}")
            raise
    
    def execute_mcp_command(
        self, server_name: str, tool_name: str, args: List[str] = None
    ) -> Dict[str, Any]:
        """Execute an MCP command on the specified server."""
        try:
            # Convert args list to kwargs dict if needed
            kwargs = {}
            if args:
                # If args is a list of strings, convert to a single JSON string
                if len(args) == 1 and args[0].startswith('{') and args[0].endswith('}'):
                    try:
                        kwargs = json.loads(args[0])
                    except json.JSONDecodeError:
                        # If not valid JSON, treat each arg as a positional parameter
                        for i, arg in enumerate(args):
                            kwargs["arg%i" % (i+1)] = arg
                else:
                    # Convert positional args to kwargs based on position
                    for i, arg in enumerate(args):
                        kwargs["arg%i" % (i+1)] = arg
            
            if self.config.verbose:
                ui.print_verbose("Executing MCP command: %s %s" % (server_name, tool_name))
                if kwargs:
                    ui.print_verbose("With kwargs: %s" % json.dumps(kwargs, indent=2))
                elif args:
                    ui.print_verbose("With args: %s" % args)
            
            # Define the async operation
            async def operation(session):
                return await session.call_tool(tool_name, arguments=kwargs)
            
            # Run the async operation in a new event loop
            result = self._run_async(self._execute_with_session(server_name, operation))
            
            if self.config.verbose:
                ui.print_verbose("MCP command executed successfully")
                result_size = len(json.dumps(result)) if result else 0
                ui.print_verbose("Result size: %i characters" % result_size)
            
            return result
            
        except Exception as e:
            if self.config.verbose:
                ui.print_verbose("Exception during MCP command execution: %s" % str(e))
            raise RuntimeError("MCP error: %s" % str(e)) from e
    
    def list_available_tools(self, server_name: str) -> List[str]:
        """List available tools for a specific MCP server."""
        try:
            # Define the async operation
            async def operation(session):
                if self.config.verbose:
                    ui.print_verbose(f"Calling list_tools for server: {server_name}")
                
                tools_data = await session.list_tools()
                
                if self.config.verbose:
                    ui.print_verbose(f"list_tools returned type: {type(tools_data)}")
                
                return tools_data
            
            # Run the async operation in a new event loop
            if self.config.verbose:
                ui.print_verbose(f"Running async operation for server: {server_name}")
            
            tools_data = self._run_async(self._execute_with_session(server_name, operation))
            
            if self.config.verbose:
                ui.print_verbose(f"Async operation completed for server: {server_name}")
                ui.print_verbose(f"Result type: {type(tools_data)}")
            
            # Extract tool names, handling different data structures
            tool_names = []
            
            # Handle ListToolsResult type (from MCP SDK)
            if hasattr(tools_data, "tools") and isinstance(tools_data.tools, list):
                if self.config.verbose:
                    ui.print_verbose(f"Processing ListToolsResult with {len(tools_data.tools)} tools")
                tool_names = [tool.name for tool in tools_data.tools if hasattr(tool, "name")]
            # Handle tuple type
            elif isinstance(tools_data, tuple) and len(tools_data) > 0:
                first_item = tools_data[0]
                if self.config.verbose:
                    ui.print_verbose(f"Processing tuple result with {len(tools_data)} items")
                    ui.print_verbose(f"First item type: {type(first_item)}")
                
                if isinstance(first_item, list):
                    tool_names = [tool.get("name") for tool in first_item if tool.get("name")]
                elif hasattr(first_item, "tools") and isinstance(first_item.tools, list):
                    tool_names = [tool.name for tool in first_item.tools if hasattr(tool, "name")]
            # Handle list type
            elif isinstance(tools_data, list):
                if self.config.verbose:
                    ui.print_verbose(f"Processing list result with {len(tools_data)} items")
                tool_names = [tool.get("name") for tool in tools_data if tool.get("name")]
            # Handle dictionary type
            elif isinstance(tools_data, dict) and "tools" in tools_data:
                if self.config.verbose:
                    ui.print_verbose(f"Processing dict result with 'tools' key containing {len(tools_data['tools'])} items")
                tool_names = [tool.get("name") for tool in tools_data["tools"] if tool.get("name")]
            
            if self.config.verbose:
                msg = "Retrieved %i tools for server: %s" % (
                    len(tool_names), server_name
                )
                ui.print_verbose(msg)
            
            return tool_names
            
        except Exception as e:
            if self.config.verbose:
                msg = "Failed to list tools for server %s: %s" % (
                    server_name, str(e)
                )
                ui.print_verbose(msg)
                import traceback
                ui.print_verbose(f"Traceback: {traceback.format_exc()}")
            
            # Fall back to config-based tools
            return self._get_config_tools(server_name)
    
    def _get_config_tools(self, server_name: str) -> List[str]:
        """Get tools from config for a specific MCP server."""
        config_tools = self.config.get_mcp_server_tools(server_name)
        if config_tools:
            if self.config.verbose:
                msg = "Using %i tools from config for server: %s" % (
                    len(config_tools), server_name
                )
                ui.print_verbose(msg)
            return config_tools
        
        # No default tools - rely on discovery
        if self.config.verbose:
            ui.print_verbose(f"No tools found in config for server: {server_name}")
        return []
    
    def get_tool_schema(
        self, server_name: str, tool_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get the schema for a specific MCP tool."""
        try:
            # Define the async operation
            async def operation(session):
                tools_data = await session.list_tools()
                
                # Handle ListToolsResult type (from MCP SDK)
                if hasattr(tools_data, "tools") and isinstance(tools_data.tools, list):
                    for tool in tools_data.tools:
                        if hasattr(tool, "name") and tool.name == tool_name:
                            # Convert tool object to dictionary
                            return {
                                "name": tool.name,
                                "description": tool.description if hasattr(tool, "description") else "",
                                "parameters": tool.parameters if hasattr(tool, "parameters") else {}
                            }
                
                # Handle other types as before
                if isinstance(tools_data, tuple) and len(tools_data) > 0:
                    tools = tools_data[0]
                else:
                    tools = tools_data
                
                if isinstance(tools, dict) and "tools" in tools:
                    tools = tools["tools"]
                
                if isinstance(tools, list):
                    for tool in tools:
                        if tool.get("name") == tool_name:
                            return tool
                
                return None
            
            # Run the async operation in a new event loop
            tool = self._run_async(self._execute_with_session(server_name, operation))
            
            if tool:
                if self.config.verbose:
                    ui.print_verbose("Retrieved schema for tool: %s" % tool_name)
                return tool
            
            if self.config.verbose:
                ui.print_verbose("Tool %s not found" % tool_name)
            return None
            
        except Exception as e:
            if self.config.verbose:
                ui.print_verbose(
                    "Failed to get schema for tool %s: %s" % (tool_name, str(e))
                )
            return None
    
    def get_tool_descriptions(self, server_name: str) -> Dict[str, str]:
        """Get descriptions for all tools on a specific MCP server."""
        try:
            # Define the async operation
            async def operation(session):
                return await session.list_tools()
            
            # Run the async operation in a new event loop
            tools_data = self._run_async(self._execute_with_session(server_name, operation))
            
            # Extract tool descriptions, handling different data structures
            descriptions = {}
            
            # Handle ListToolsResult type (from MCP SDK)
            if hasattr(tools_data, "tools") and isinstance(tools_data.tools, list):
                if self.config.verbose:
                    ui.print_verbose(f"Processing ListToolsResult with {len(tools_data.tools)} tools")
                
                for tool in tools_data.tools:
                    if hasattr(tool, "name"):
                        name = tool.name
                        description = tool.description if hasattr(tool, "description") else f"{name} tool"
                        descriptions[name] = description
            # Handle other types as before
            else:
                tools_list = []
                
                if isinstance(tools_data, list):
                    tools_list = tools_data
                elif isinstance(tools_data, dict) and "tools" in tools_data:
                    tools_list = tools_data["tools"]
                elif isinstance(tools_data, tuple) and len(tools_data) > 0:
                    first_item = tools_data[0]
                    if isinstance(first_item, list):
                        tools_list = first_item
                    elif hasattr(first_item, "tools"):
                        tools_list = first_item.tools
                
                for tool in tools_list:
                    if isinstance(tool, dict):
                        name = tool.get("name")
                        description = tool.get("description") or f"{name} tool"
                        if name:
                            descriptions[name] = description
                    elif hasattr(tool, "name"):
                        name = tool.name
                        description = tool.description if hasattr(tool, "description") else f"{name} tool"
                        descriptions[name] = description
            
            if self.config.verbose:
                msg = "Retrieved descriptions for %i tools on server: %s" % (
                    len(descriptions), server_name
                )
                ui.print_verbose(msg)
            
            return descriptions
            
        except Exception as e:
            if self.config.verbose:
                msg = "Failed to get tool descriptions for server %s: %s" % (
                    server_name, str(e)
                )
                ui.print_verbose(msg)
            return {}
    
    def format_tool_arguments(self, args_str: str) -> List[str]:
        """Format tool arguments from a string to a list, handling quotes properly."""
        if not args_str:
            return []
        
        # Use shlex to properly handle quoted arguments
        return shlex.split(args_str)
    
    def close(self):
        """Close all resources."""
        self._executor.shutdown(wait=False)

    def _start_server_process(self, server_name: str) -> subprocess.Popen:
        """Start an MCP server process."""
        server_config = self.config.get_mcp_server(server_name)
        if not server_config:
            raise ValueError("MCP server '%s' not found in configuration" % server_name)
        
        if server_name in self.processes and self.processes[server_name].poll() is None:
            # Process is still running
            return self.processes[server_name]
        
        # Create environment with server config
        env = os.environ.copy()
        if server_config.env:
            env.update(server_config.env)
        
        command = [server_config.command] + server_config.args
        
        if self.config.verbose:
            ui.print_verbose("Starting MCP server: %s" % server_name)
            ui.print_verbose("Command: %s" % ' '.join(command))
            env_vars = ', '.join("%s=%s..." % (k, v[:3]) for k, v in server_config.env.items())
            ui.print_verbose("Environment variables: %s" % env_vars)
        
        # Start the process
        process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        
        # Store the process
        self.processes[server_name] = process
        
        # Give the server a moment to start up
        time.sleep(0.5)
        
        return process
