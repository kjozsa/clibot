"""MCP tools integration for CliBot."""

import json
import os
import subprocess
from typing import Any, Dict, List

from .config import Config

class MCPToolsManager:
    """Manager for MCP tools execution."""
    
    def __init__(self, config: Config):
        self.config = config
    
    def execute_mcp_command(self, server_name: str, tool_name: str, 
                           args: List[str] = None) -> Dict[str, Any]:
        """Execute an MCP command on the specified server."""
        server = self.config.get_mcp_server(server_name)
        if not server:
            raise ValueError(f"MCP server '{server_name}' not found in configuration")
        
        # Prepare environment
        env = os.environ.copy()
        env.update(server.env)
        
        # Prepare command
        cmd = [server.command, *server.args, tool_name]
        if args:
            cmd.extend(args)
        
        # Execute command
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"MCP command failed: {result.stderr}")
        
        # Parse JSON output
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw_output": result.stdout}
    
    def list_available_tools(self, server_name: str) -> List[str]:
        """List available tools for a specific MCP server."""
        # Get tools from the config file
        return self.config.get_mcp_server_tools(server_name)
