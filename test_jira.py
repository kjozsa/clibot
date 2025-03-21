#!/usr/bin/env python3
"""Test script for JIRA MCP integration using CliBot's AI assistant."""

import os
import subprocess
from pathlib import Path


def main():
    """Test JIRA ticket retrieval using CliBot's AI assistant."""
    # Set up environment for verbose output
    os.environ["CLIBOT_VERBOSE"] = "true"
    
    # Path to the CliBot executable in the virtual environment
    clibot_path = Path(".venv/bin/clibot")
    
    # Command to ask about the JIRA ticket
    cmd = [
        str(clibot_path), 
        "ask", 
        "What is the title of JIRA ticket KPD-393? Use the mcp-atlassian JIRA tools to find out."
    ]
    
    try:
        # Execute the command
        print("Asking CliBot about JIRA ticket KPD-393...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        # Print the output
        print("\nOutput:")
        print(result.stdout)
        
        if result.stderr:
            print("\nErrors/Verbose Output:")
            print(result.stderr)
        
        # Check if the command was successful
        if result.returncode != 0:
            print(f"\nCommand failed with exit code: {result.returncode}")
    
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
