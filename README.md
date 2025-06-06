# ProtectAI MCP Examples

A collection of example applications demonstrating securing Model Context Protocol (MCP) with various Protect AI's security platform.

## Overview

This repository contains practical examples of how to secure applications built using the Model Context Protocol (MCP) using Protect AI's Layer platform. Each example demonstrates different capabilities and integration patterns.

## Examples

### Weather Tools

The repository currently includes the following weather-related examples:

1. **MCP Weather Server** - A server that exposes weather forecast and alert tools to MCP clients like Claude for Desktop.
   - Fetches data from the National Weather Service API
   - Provides `get-forecast` and `get-alerts` tools
   - Demonstrates basic MCP server implementation

2. **Weather Analysis with Claude** - A Jupyter notebook that combines weather data with Claude's analytical capabilities.
   - Interactive Gradio UI for inputting locations
   - Multiple analysis perspectives (general, travel, emergency)
   - Demonstrates AI-powered insights from raw weather data
   - [View Notebook](weather-v1/mcp_weather_analysis_using_claude/weather_analysis_tool_claude.ipynb) - Interactive tool combining NWS API with Claude & [Protect AI's Layer IDR platform](https://protectai.com/layer)

## Getting Started

Each example contains its own README with specific setup instructions. Generally, you'll need:

- Python 3.10+ (3.12 recommended)
- MCP SDK 1.6.0+
- Various dependencies as specified in each example
- Layer SDK fork (included in this repo)

## Prerequisites

- Basic understanding of Python
- Familiarity with AI models like Claude
- API keys for relevant services (e.g., Anthropic API key for Claude examples)
- Layer account and client secret for logging

## License

MIT

## Additional Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io)
- [Anthropic Claude Documentation](https://docs.anthropic.com)
- [National Weather Service API](https://api.weather.gov)
- [Protect AI Layer](https://protectai.com/layer)