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
            if not tools:
                continue
                
            # Get tool descriptions if available
            tool_descriptions = self.mcp_manager.get_tool_descriptions(server)
            
            tools_description += f"\n## {server}:\n"
            for tool in tools:
                description = tool_descriptions.get(tool, "")
                if description:
                    tools_description += f"- **{tool}**: {description}\n"
                else:
                    tools_description += f"- **{tool}**\n"
        
        system_prompt = (
            "You are CliBot, an AI assistant with access to MCP (Model Context "
            "Protocol) tools. You can help with various tasks and can use MCP "
            "tools to interact with systems.\n\n"
            f"{tools_description}\n\n"
            "To use an MCP tool, respond with: [MCP] server_name tool_name "
            "arg1 arg2 ...\n"
            "For arguments with spaces, use quotes: [MCP] mcp-atlassian "
            "jira_get_issue \"KPD-393\"\n"
            "For tools that require JSON input, you can provide a JSON object: "
            "[MCP] jenkins-mcp-build trigger_build \"build-job\" {\"branch\": "
            "\"main\"}\n"
            "You can use multiple MCP commands in one response if needed."
        )
        
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
        
        # Check if the response contains MCP commands
        processed_response = ai_response
        mcp_pattern = r'\[MCP\]\s+([\w-]+)\s+([\w_-]+)(?:\s+(.+)?)?'
        mcp_commands = re.findall(mcp_pattern, ai_response)
        
        if mcp_commands:
            if self.config.verbose:
                ui.print_verbose(f"Found {len(mcp_commands)} MCP commands in response")
            
            # Process each MCP command
            all_results = []
            for cmd_match in mcp_commands:
                server = cmd_match[0]
                tool = cmd_match[1]
                args_str = cmd_match[2] or ""
                
                # Parse arguments using the format_tool_arguments method
                args = self.mcp_manager.format_tool_arguments(args_str)
                
                if self.config.verbose:
                    ui.print_verbose(f"Processing MCP command: {server} {tool} {args}")
                
                try:
                    # Get tool schema if available
                    schema = self.mcp_manager.get_tool_schema(server, tool)
                    if schema and self.config.verbose:
                        schema_preview = json.dumps(schema, indent=2)[:100]
                        ui.print_verbose(f"Tool schema available: {schema_preview}...")
                    
                    # Execute MCP command
                    result = self.mcp_manager.execute_mcp_command(server, tool, args)
                    
                    if self.config.verbose:
                        ui.print_verbose("MCP command executed successfully")
                        result_size = len(json.dumps(result)) if result else 0
                        ui.print_verbose(f"Result size: {result_size} characters")
                    
                    # Add result to the list
                    all_results.append({
                        "server": server,
                        "tool": tool,
                        "args": args,
                        "result": result
                    })
                    
                except Exception as e:
                    if self.config.verbose:
                        ui.print_verbose(f"MCP command execution failed: {str(e)}")
                    
                    # Add error to the list
                    all_results.append({
                        "server": server,
                        "tool": tool,
                        "args": args,
                        "error": str(e)
                    })
            
            # Add AI response to history
            self.add_message("assistant", ai_response)
            
            # Add all results as a single system message
            results_json = json.dumps(all_results, indent=2)
            self.add_message("system", f"MCP command results: {results_json}")
            
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
                    tokens_info = (
                        f"Tokens: {follow_up_response.usage.prompt_tokens} prompt, "
                        f"{follow_up_response.usage.completion_tokens} completion, "
                        f"{follow_up_response.usage.total_tokens} total"
                    )
                    ui.print_verbose(tokens_info)
            
            self.add_message("assistant", follow_up)
            processed_response = follow_up
        else:
            # Add AI response to history
            self.add_message("assistant", ai_response)
        
        return processed_response
    
    def ask(self, question: str) -> str:
        """Ask a one-off question without maintaining conversation history."""
        # Reset conversation history
        self.conversation_history = []
        return self.process_message(question)
    
    def chat(self, message: str) -> str:
        """Chat with the AI, maintaining conversation history."""
        return self.process_message(message)
