"""AI service for CliBot."""

import json
import re
import time
from typing import Any, Optional

import openai

from . import ui
from .config import Config
from .mcp_tools import MCPToolsManager


class MCPResultEncoder(json.JSONEncoder):
    """Custom JSON encoder for MCP results."""
    
    def default(self, obj):
        # Handle MCP CallToolResult objects
        if hasattr(obj, '__dict__'):
            # Convert to dictionary
            result_dict = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    result_dict[key] = value
            return result_dict
        # Handle other non-serializable objects
        try:
            return str(obj)
        except Exception:
            return f"<Non-serializable object of type {type(obj).__name__}>"


def serialize_mcp_result(result: Any) -> Any:
    """Convert MCP result to a JSON-serializable format.
    
    This uses the same approach as the UI module's print_mcp_result function.
    """
    if result is None:
        return None
        
    # Handle dictionaries and lists
    if isinstance(result, dict):
        return {k: serialize_mcp_result(v) for k, v in result.items()}
    if isinstance(result, list):
        return [serialize_mcp_result(item) for item in result]
    
    # Handle objects with __dict__ attribute (like CallToolResult)
    if hasattr(result, '__dict__'):
        obj_dict = {}
        for key, value in result.__dict__.items():
            if not key.startswith('_'):  # Skip private attributes
                obj_dict[key] = serialize_mcp_result(value)
        return obj_dict
    
    # Handle other types
    try:
        # Try standard JSON serialization
        json.dumps(result)
        return result
    except (TypeError, OverflowError):
        # Fall back to string representation
        return str(result)


class AIService:
    """Service for interacting with the AI assistant."""
    
    def __init__(self, config: Config, mcp_manager: Optional[MCPToolsManager] = None):
        """Initialize the AI service.
        
        Args:
            config: Configuration for the service
            mcp_manager: Optional existing MCPToolsManager instance to reuse
        """
        if config.verbose:
            ui.print_verbose("=== Initializing AI Service ===")
            
        self.config = config
        # Use the provided manager or create a new one
        self.mcp_manager = mcp_manager or MCPToolsManager(config)
        
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
            ui.print_verbose("=== AI Service Initialization Complete ===")
        
    def _build_system_prompt(self) -> str:
        """Build the system prompt including MCP tool capabilities."""
        if self.config.verbose:
            ui.print_verbose("=== Building System Prompt ===")
            
        mcp_servers = self.config.list_mcp_servers()
        
        tools_description = "Available MCP tools:\n"
        for server in mcp_servers:
            # Get tools and descriptions from cache if available
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
            "You are CliBot, an AI assistant with DIRECT access to MCP (Model Context "
            "Protocol) tools. You can help with various tasks and you MUST use the MCP "
            "tools when users ask for them. You have full capability to execute these tools "
            "on behalf of the user.\n\n"
            f"{tools_description}\n\n"
            "IMPORTANT: When a user asks you to use an MCP tool, you MUST respond with the "
            "appropriate MCP command syntax. DO NOT say you don't have access to these tools "
            "as you DO have access and CAN use them directly.\n\n"
            "To use an MCP tool, respond with: [MCP] server_name tool_name "
            "arg1 arg2 ...\n"
            "For arguments with spaces, use quotes: [MCP] mcp-atlassian "
            "jira_get_issue \"KPD-393\"\n"
            "For tools that require JSON input, you can provide a JSON object: "
            "[MCP] jenkins-mcp-build trigger_build \"build-job\" {\"branch\": "
            "\"main\"}\n"
            "You can use multiple MCP commands in one response if needed.\n\n"
            "Example: If a user asks 'list git repositories', you should respond with:\n"
            "[MCP] git-mcp list_repositories"
        )
        
        if self.config.verbose:
            ui.print_verbose(f"System prompt length: {len(system_prompt)} characters")
            ui.print_verbose("=== System Prompt Built ===")
            
        return system_prompt
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append({"role": role, "content": content})
        
        if self.config.verbose:
            ui.print_verbose(f"Added message with role '{role}' ({len(content)} chars)")
    
    def process_message(self, message: str) -> str:
        """Process a user message and generate a response."""
        if self.config.verbose:
            ui.print_verbose("=== Processing User Message ===")
            
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
                ui.print_verbose("=== Executing MCP Commands ===")
            
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
                    
                    # Convert result to a JSON-serializable format
                    serialized_result = serialize_mcp_result(result)
                    
                    # Add result to the list
                    all_results.append({
                        "server": server,
                        "tool": tool,
                        "args": args,
                        "result": serialized_result
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
            
            # Format results for the system message
            formatted_results = []
            for res in all_results:
                result_str = ""
                if "error" in res:
                    result_str = f"Error: {res['error']}"
                else:
                    # Format the result in a readable way
                    result_data = res.get("result", {})
                    if isinstance(result_data, dict):
                        # Extract text content if available
                        if ("content" in result_data and 
                            isinstance(result_data["content"], list)):
                            content_items = []
                            for item in result_data["content"]:
                                if isinstance(item, dict) and "text" in item:
                                    content_items.append(item["text"])
                                else:
                                    content_items.append(str(item))
                            
                            if content_items:
                                title = f"Available {res['server']}.{res['tool']} results:"
                                items_str = "\n".join([f"- {item}" for item in content_items])
                                formatted_results.append(f"{title}\n\n{items_str}")
                                continue
                        
                        # Standard dictionary formatting
                        items_str = "\n".join([f"- {k}: {v}" for k, v in result_data.items()])
                        result_str = items_str
                    elif isinstance(result_data, list):
                        # Check if list contains dictionaries with text
                        text_items = []
                        for item in result_data:
                            if isinstance(item, dict) and "text" in item:
                                text_items.append(item["text"])
                        
                        if text_items:
                            title = f"Available {res['server']}.{res['tool']} results:"
                            items_str = "\n".join([f"- {item}" for item in text_items])
                            formatted_results.append(f"{title}\n\n{items_str}")
                        else:
                            items_str = "\n".join([f"- {item}" for item in result_data])
                            result_str = items_str
                    else:
                        result_str = str(result_data)
                
                formatted_results.append(
                    f"Result from {res['server']}.{res['tool']}:\n{result_str}"
                )
            
            # Add all results as a single system message
            try:
                # Create a human-readable results message
                results_text = "\n\n".join(formatted_results)
                system_message = f"MCP command results:\n\n{results_text}"
                
                # Also include the JSON for the AI to parse
                results_json = json.dumps(all_results, indent=2)
                
                # Combine both for the system message
                combined_message = (
                    f"{system_message}\n\n"
                    f"JSON Results:\n```json\n{results_json}\n```"
                )
                self.add_message("system", combined_message)
            except Exception as e:
                if self.config.verbose:
                    ui.print_verbose(f"Error formatting MCP results: {str(e)}")
                # Fallback to a simpler format
                fallback_results = []
                for res in all_results:
                    fallback_res = {
                        "server": res["server"],
                        "tool": res["tool"],
                        "args": res["args"]
                    }
                    if "error" in res:
                        fallback_res["error"] = res["error"]
                    else:
                        fallback_res["result"] = str(res.get("result", ""))
                    fallback_results.append(fallback_res)
                results_json = json.dumps(fallback_results, indent=2)
                self.add_message("system", f"MCP command results: {results_json}")
            
            if self.config.verbose:
                ui.print_verbose("=== MCP Commands Executed ===")
                ui.print_verbose("=== Generating Follow-up Response ===")
            
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
                    prompt_tokens = follow_up_response.usage.prompt_tokens
                    completion_tokens = follow_up_response.usage.completion_tokens
                    total_tokens = follow_up_response.usage.total_tokens
                    tokens_info = (
                        f"Tokens: {prompt_tokens} prompt, "
                        f"{completion_tokens} completion, "
                        f"{total_tokens} total"
                    )
                    ui.print_verbose(tokens_info)
            
            # If the follow-up is empty, generate a default response based on the results
            if not follow_up or follow_up.strip() == "":
                if self.config.verbose:
                    ui.print_verbose("Follow-up response was empty, generating default response")
                
                # Generate a default response based on the MCP command results
                default_response = ""
                for res in all_results:
                    tool_name = f"{res['server']}.{res['tool']}"
                    if "error" in res:
                        default_response += f"Error executing {tool_name}: {res['error']}\n\n"
                    else:
                        result_data = res.get("result", {})
                        
                        # Generic handling for results with text content
                        if isinstance(result_data, dict):
                            # Extract text content if available
                            if ("content" in result_data and 
                                isinstance(result_data["content"], list)):
                                content_items = []
                                for item in result_data["content"]:
                                    if isinstance(item, dict) and "text" in item:
                                        content_items.append(item["text"])
                                    else:
                                        content_items.append(str(item))
                                
                                if content_items:
                                    default_response += f"Available {tool_name} results:\n\n"
                                    items_str = "\n".join([f"- {item}" for item in content_items])
                                    default_response += items_str
                                    default_response += "\n\n"
                                    continue
                            
                            # Standard dictionary formatting
                            items_str = "\n".join([f"- {k}: {v}" for k, v in result_data.items()])
                            default_response += f"Results from {tool_name}:\n{items_str}\n\n"
                        elif isinstance(result_data, list):
                            # Check if list contains dictionaries with text
                            text_items = []
                            for item in result_data:
                                if isinstance(item, dict) and "text" in item:
                                    text_items.append(item["text"])
                            
                            if text_items:
                                default_response += f"Available {tool_name} results:\n\n"
                                items_str = "\n".join([f"- {item}" for item in text_items])
                                default_response += items_str
                                default_response += "\n\n"
                            else:
                                items_str = "\n".join([f"- {item}" for item in result_data])
                                default_response += f"Results from {tool_name}:\n{items_str}\n\n"
                        else:
                            default_response += f"Results from {tool_name}:\n{result_data}\n\n"
                
                if not default_response:
                    default_response = "The command was executed, but no results were returned."
                
                follow_up = default_response
            
            self.add_message("assistant", follow_up)
            processed_response = follow_up
            
            if self.config.verbose:
                ui.print_verbose("=== Message Processing Complete ===")
        else:
            # Add AI response to history
            self.add_message("assistant", ai_response)
            
            if self.config.verbose:
                ui.print_verbose("=== Message Processing Complete (No MCP Commands) ===")
        
        return processed_response
    
    def ask(self, question: str) -> str:
        """Ask a one-off question without maintaining conversation history."""
        # Reset conversation history
        self.conversation_history = []
        return self.process_message(question)
    
    def chat(self, message: str) -> str:
        """Chat with the AI, maintaining conversation history."""
        return self.process_message(message)
