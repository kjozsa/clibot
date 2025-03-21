"""MCP tools integration for CliBot."""

import subprocess
import json
import os
from typing import Dict, List, Any, Optional
from .config import Config, MCPServer

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
        # This implementation depends on how MCP tools expose their capabilities
        # For now, return predefined lists based on server type
        server_tools = {
            "jenkins-mcp-build": ["list_jobs", "get_build_status", "trigger_build"],
            "jenkins-mcp-deploy": ["list_jobs", "get_build_status", "trigger_build"],
            "git-mcp": ["list_repositories", "get_last_git_tag", "list_commits_since_last_tag", 
                        "create_git_tag", "push_git_tag", "refresh_repository"],
            "mcp-atlassian": ["jira_search", "jira_get_issue", "jira_create_issue", 
                             "jira_update_issue", "confluence_search", "confluence_get_page"]
        }
        
        return server_tools.get(server_name, [])
