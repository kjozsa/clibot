"""UI components for CliBot."""

import json
import sys
from typing import Any, List

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

# Create console for output
console = Console()

# Create a separate console for verbose output
verbose_console = Console(stderr=True, style="dim")

def print_welcome():
    """Print welcome message."""
    welcome_text = """
# Welcome to CliBot

An AI assistant with MCP tools integration.
Type 'exit' or 'quit' to end the session.
"""
    console.print(Markdown(welcome_text))

def print_ai_message(message: str):
    """Print a message from the AI assistant."""
    console.print(Panel(Markdown(message), title="CliBot", border_style="blue"))

def print_user_message(message: str):
    """Print a message from the user."""
    console.print(Panel(Text(message), title="You", border_style="green"))

def print_error(message: str):
    """Print an error message."""
    console.print(Panel(Text(message, style="bold red"), title="Error", border_style="red"))

def print_verbose(message: str):
    """Print a verbose message if verbose mode is enabled."""
    verbose_console.print(f"[cyan]{message}")

def print_mcp_servers(servers: List[str]):
    """Print available MCP servers."""
    console.print("\n[bold blue]Available MCP Servers:[/bold blue]")
    for server in servers:
        console.print(f"  • [magenta]{server}[/magenta]")
    console.print()

def print_mcp_tools(server: str, tools: List[str]):
    """Print available tools for an MCP server."""
    console.print(f"\n[bold blue]Available Tools for {server}:[/bold blue]")
    for tool in tools:
        console.print(f"  • [magenta]{tool}[/magenta]")
    console.print()

def print_mcp_result(result: Any):
    """Print the result of an MCP command."""
    console.print("\n[bold blue]MCP Command Result:[/bold blue]")
    if isinstance(result, dict) or isinstance(result, list):
        console.print_json(json.dumps(result, indent=2))
    else:
        console.print(result)
    console.print()

def get_user_input() -> str:
    """Get input from the user."""
    try:
        return console.input("[bold green]You:[/] ")
    except (KeyboardInterrupt, EOFError):
        console.print("\nExiting...")
        sys.exit(0)

def show_spinner(text: str = "Thinking..."):
    """Show a spinner while processing."""
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{text}"),
        console=console,
        transient=True,
    )
