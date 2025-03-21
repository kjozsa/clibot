# CliBot - AI Assistant CLI Tool

CliBot is a command-line AI assistant that integrates with MCP tools, providing an interactive interface for AI-powered assistance directly from your terminal.

## Features

- Interactive AI assistant in your terminal
- Integration with MCP tools
- Rich text formatting for better readability
- Easy-to-use command structure
- Configurable AI model settings
- Verbose logging for debugging and development

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd clibot

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package using uv
uv pip install -e .
```

## Usage

```bash
# Basic usage
clibot ask "How do I create a Python virtual environment?"

# Use specific MCP tools
clibot mcp run jenkins-mcp-build list_jobs

# List available MCP servers
clibot mcp list-servers

# List available tools for a specific MCP server
clibot mcp list-tools jenkins-mcp-build

# Start interactive chat mode
clibot chat

# Enable verbose logging for any command
clibot ask "What's the weather today?" --verbose
clibot chat --verbose
```

## Configuration

Create a `.env` file in your project directory with the following variables:

```
# Required: OpenRouter API key (instead of OpenAI API key)
OPENROUTER_API_KEY=your_openrouter_api_key

# Optional: Specify the AI model to use (defaults to mistralai/mistral-small-3.1-24b-instruct:free)
OPENAI_MODEL=mistralai/mistral-small-3.1-24b-instruct:free

# Optional: Enable verbose logging globally
CLIBOT_VERBOSE=true
```

### Verbose Logging

The verbose logging feature provides detailed information about:

- Model initialization and configuration
- API requests and responses
- Token usage statistics
- Response times
- MCP command execution details

This is useful for debugging, development, and understanding how the AI assistant works. You can enable verbose logging in three ways:

1. Globally via the `CLIBOT_VERBOSE=true` environment variable
2. Per command with the `--verbose` or `-v` flag
3. Programmatically when initializing the `Config` class

## Development

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
isort .
```

## License

MIT
