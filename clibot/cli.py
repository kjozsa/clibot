"""Command-line interface for CliBot."""

import sys
from pathlib import Path
from typing import List, Optional

import typer

from .config import Config
from .mcp_tools import MCPToolsManager
from .ai_service import AIService
from . import ui

app = typer.Typer(help="CliBot - AI Assistant with MCP Tools")
mcp_app = typer.Typer(help="Execute MCP tools")
app.add_typer(mcp_app, name="mcp")

# Global instances
config = None
mcp_manager = None
ai_service = None

# Define common options
CONFIG_OPTION = typer.Option(None, "--config", "-c", help="Path to MCP config file")
VERBOSE_OPTION = typer.Option(False, "--verbose", "-v", help="Enable verbose output")

# Define common arguments
SERVER_ARGUMENT = typer.Argument(..., help="MCP server name")
TOOL_ARGUMENT = typer.Argument(..., help="MCP tool name")
ARGS_ARGUMENT = typer.Argument(None, help="Arguments for the MCP tool")
QUESTION_ARGUMENT = typer.Argument(..., help="Question to ask the AI assistant")

def initialize(config_path: Optional[str] = None, verbose: bool = False):
    """Initialize global instances."""
    global config, mcp_manager, ai_service
    config = Config(config_path, verbose=verbose)
    mcp_manager = MCPToolsManager(config)
    ai_service = AIService(config)

@app.callback()
def callback(
    config_path: Optional[Path] = CONFIG_OPTION,
    verbose: bool = VERBOSE_OPTION
):
    """Initialize CliBot."""
    initialize(config_path, verbose)
    if not config.openrouter_api_key:
        ui.print_error("OPENROUTER_API_KEY environment variable is not set")
        raise typer.Exit(1)
    
    if verbose:
        ui.print_verbose("Verbose mode enabled")
        ui.print_verbose(f"Using model: {config.openai_model}")

@app.command("ask")
def ask(
    question: str = QUESTION_ARGUMENT,
    verbose: bool = VERBOSE_OPTION
):
    """Ask a one-off question to the AI assistant."""
    if verbose and config and not config.verbose:
        config.verbose = True
        ui.print_verbose("Verbose mode enabled for this command")
    
    with ui.show_spinner():
        response = ai_service.ask(question)
    ui.print_ai_message(response)

@app.command("chat")
def chat(
    verbose: bool = VERBOSE_OPTION
):
    """Start an interactive chat session with the AI assistant."""
    if verbose and config and not config.verbose:
        config.verbose = True
        ui.print_verbose("Verbose mode enabled for this session")
    
    ui.print_welcome()
    
    while True:
        user_input = ui.get_user_input()
        
        if user_input.lower() in ("exit", "quit"):
            break
        
        ui.print_user_message(user_input)
        
        with ui.show_spinner():
            response = ai_service.chat(user_input)
        
        ui.print_ai_message(response)

@mcp_app.command("list-servers")
def list_mcp_servers(
    verbose: bool = VERBOSE_OPTION
):
    """List available MCP servers."""
    if verbose and config and not config.verbose:
        config.verbose = True
        ui.print_verbose("Verbose mode enabled for this command")
    
    servers = config.list_mcp_servers()
    if not servers:
        ui.print_error("No MCP servers configured")
        return
    
    ui.print_mcp_servers(servers)

@mcp_app.command("list-tools")
def list_mcp_tools(
    server: str = SERVER_ARGUMENT,
    verbose: bool = VERBOSE_OPTION
):
    """List available tools for an MCP server."""
    if verbose and config and not config.verbose:
        config.verbose = True
        ui.print_verbose("Verbose mode enabled for this command")
    
    if server not in config.list_mcp_servers():
        ui.print_error(f"MCP server '{server}' not found in configuration")
        raise typer.Exit(1)
    
    tools = mcp_manager.list_available_tools(server)
    ui.print_mcp_tools(server, tools)

@mcp_app.command("run")
def run_mcp_command(
    server: str = SERVER_ARGUMENT,
    tool: str = TOOL_ARGUMENT,
    args: List[str] = ARGS_ARGUMENT,
    verbose: bool = VERBOSE_OPTION
):
    """Run an MCP command on the specified server."""
    if verbose and config and not config.verbose:
        config.verbose = True
        ui.print_verbose("Verbose mode enabled for this command")
    
    try:
        with ui.show_spinner(f"Running {server} {tool}..."):
            result = mcp_manager.execute_mcp_command(server, tool, args)
        ui.print_mcp_result(result)
    except Exception as e:
        ui.print_error(str(e))
        raise typer.Exit(1) from None

def main():
    """Main entry point for the CLI."""
    try:
        app()
    except Exception as e:
        ui.print_error(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
