"""Configuration module for CliBot."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import dotenv
from pydantic import BaseModel

# Load environment variables from .env file
dotenv.load_dotenv()

class MCPServer(BaseModel):
    """Configuration for an MCP server."""
    command: str
    args: List[str]
    env: Dict[str, str]

class MCPConfig(BaseModel):
    """MCP configuration structure."""
    mcpServers: Dict[str, MCPServer]

class Config:
    """Main configuration class for CliBot."""
    
    def __init__(self, config_path: Optional[str] = None, verbose: Optional[bool] = None):
        self.mcp_config = self._load_mcp_config(config_path)
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url = "https://openrouter.ai/api/v1"
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        
        # Set verbose mode from parameter or environment variable
        if verbose is not None:
            self.verbose = verbose
        else:
            verbose_env = os.getenv("CLIBOT_VERBOSE", "false").lower()
            self.verbose = verbose_env in ("true", "1", "yes", "y")
        
    def _load_mcp_config(self, config_path: Optional[str] = None) -> MCPConfig:
        """Load MCP configuration from file."""
        if config_path:
            path = Path(config_path)
        else:
            # Try standard locations
            locations = [
                Path.home() / ".codeium/windsurf-next/mcp_config.json",
                Path.home() / ".config/clibot/mcp_config.json",
                Path.cwd() / "mcp_config.json"
            ]
            
            for loc in locations:
                if loc.exists():
                    path = loc
                    break
            else:
                # No config found, return empty config
                return MCPConfig(mcpServers={})
        
        with open(path, "r") as f:
            config_data = json.load(f)
            
        return MCPConfig(**config_data)
    
    def get_mcp_server(self, server_name: str) -> Optional[MCPServer]:
        """Get configuration for a specific MCP server."""
        return self.mcp_config.mcpServers.get(server_name)
    
    def list_mcp_servers(self) -> List[str]:
        """List available MCP servers."""
        return list(self.mcp_config.mcpServers.keys())
