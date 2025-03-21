"""AI service for CliBot."""

import json
import re
import time

import openai

from . import ui
from .config import Config
from .mcp_tools import MCPToolsManager

class AIService:
    """Service for interacting with the AI assistant."""
    
    def __init__(self, config: Config):
        self.config = config
        self.mcp_manager = MCPToolsManager(config)
        
        # Initialize OpenAI client with OpenRouter base URL and API key
        self.client = openai.OpenAI(
            api_key=config.openrouter_api_key,
            base_url=config.openrouter_base_url
        )
        
        self.model = config.openai_model
        self.conversation_history = []
        
        if self.config.verbose:
            ui.print_verbose(f"Initialized AI service with model: {self.model}")
            ui.print_verbose(f"Using OpenRouter API at: {config.openrouter_base_url}")
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt including MCP tool capabilities."""
        mcp_servers = self.config.list_mcp_servers()
        
        tools_description = "Available MCP tools:\n"
        for server in mcp_servers:
            tools = self.mcp_manager.list_available_tools(server)
            tools_description += f"\n{server}:\n"
            for tool in tools:
                tools_description += f"  - {tool}\n"
        
        system_prompt = f"""You are CliBot, an AI assistant with access to MCP tools.
You can help with various tasks and can use MCP tools to interact with systems.

{tools_description}

To use an MCP tool, respond with:
[MCP] server_name tool_name arg1 arg2 ...

Example:
[MCP] jenkins-mcp-build list_jobs
"""
        
        if self.config.verbose:
            ui.print_verbose(f"System prompt length: {len(system_prompt)} characters")
            
        return system_prompt
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
        
        if self.config.verbose:
            ui.print_verbose(f"Added message with role '{role}' ({len(content)} chars)")
    
    def process_message(self, message: str) -> str:
        """Process a user message and generate a response."""
        # Add user message to history
        self.add_message("user", message)
        
        # Prepare messages for API call
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            *self.conversation_history
        ]
        
        if self.config.verbose:
            ui.print_verbose(f"Sending request to OpenRouter with model: {self.model}")
            ui.print_verbose(f"Message count: {len(messages)}")
            token_estimate = sum(len(m["content"]) / 4 for m in messages)
            ui.print_verbose(f"Estimated input tokens: ~{int(token_estimate)}")
        
        # Measure response time
        start_time = time.time()
        
        # Get response from OpenRouter
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        
        elapsed_time = time.time() - start_time
        
        ai_response = response.choices[0].message.content
        
        if self.config.verbose:
            ui.print_verbose(f"Response received in {elapsed_time:.2f} seconds")
            ui.print_verbose(f"Response length: {len(ai_response)} characters")
            if hasattr(response, 'usage') and response.usage:
                ui.print_verbose(
                    f"Tokens: {response.usage.prompt_tokens} prompt, "
                    f"{response.usage.completion_tokens} completion, "
                    f"{response.usage.total_tokens} total"
                )
            if hasattr(response, 'model') and response.model:
                ui.print_verbose(f"Model used: {response.model}")
        
        # Check if the response contains an MCP command
        mcp_match = re.search(r'\[MCP\]\s+([\w-]+)\s+([\w_-]+)(?:\s+(.+))?', ai_response)
        if mcp_match:
            server = mcp_match.group(1)
            tool = mcp_match.group(2)
            args_str = mcp_match.group(3) or ""
            
            # Simple parsing of arguments (this could be improved)
            args = args_str.split()
            
            if self.config.verbose:
                ui.print_verbose(f"Detected MCP command: {server} {tool} {args_str}")
            
            try:
                # Execute MCP command
                if self.config.verbose:
                    ui.print_verbose("Executing MCP command...")
                
                result = self.mcp_manager.execute_mcp_command(server, tool, args)
                
                if self.config.verbose:
                    ui.print_verbose("MCP command executed successfully")
                    result_size = len(json.dumps(result))
                    ui.print_verbose(f"Result size: {result_size} characters")
                
                # Add AI response and MCP result to history
                self.add_message("assistant", ai_response)
                self.add_message("system", f"MCP command result: {json.dumps(result, indent=2)}")
                
                # Get follow-up response from AI
                follow_up_messages = [
                    {"role": "system", "content": self._build_system_prompt()},
                    *self.conversation_history
                ]
                
                if self.config.verbose:
                    ui.print_verbose("Sending follow-up request to OpenRouter")
                
                start_time = time.time()
                
                follow_up_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=follow_up_messages
                )
                
                elapsed_time = time.time() - start_time
                
                follow_up = follow_up_response.choices[0].message.content
                
                if self.config.verbose:
                    ui.print_verbose(f"Follow-up response received in {elapsed_time:.2f} seconds")
                    ui.print_verbose(f"Follow-up length: {len(follow_up)} characters")
                    if hasattr(follow_up_response, 'usage') and follow_up_response.usage:
                        ui.print_verbose(
                            f"Tokens: {follow_up_response.usage.prompt_tokens} prompt, "
                            f"{follow_up_response.usage.completion_tokens} completion, "
                            f"{follow_up_response.usage.total_tokens} total"
                        )
                
                self.add_message("assistant", follow_up)
                return follow_up
            except Exception as e:
                error_message = f"Error executing MCP command: {str(e)}"
                
                if self.config.verbose:
                    ui.print_verbose(f"MCP command execution failed: {str(e)}")
                
                self.add_message("system", error_message)
                return f"{ai_response}\n\n{error_message}"
        
        # Add AI response to history
        self.add_message("assistant", ai_response)
        return ai_response
    
    def ask(self, question: str) -> str:
        """Ask a one-off question without maintaining conversation history."""
        # Reset conversation history
        self.conversation_history = []
        return self.process_message(question)
    
    def chat(self, message: str) -> str:
        """Chat with the AI, maintaining conversation history."""
        return self.process_message(message)
