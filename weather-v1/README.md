# Weather Server Quickstart

## What We’ll Be Building

Many LLMs do not currently have the ability to fetch the forecast and severe weather alerts. Let’s use MCP to solve that!

We’ll build a server that exposes two tools: `get-alerts` and `get-forecast`. Then we’ll connect the server to an MCP host (in this case, Claude for Desktop).

Servers can connect to any client. We’ve chosen Claude for Desktop here for simplicity, but we also have guides on building your own client as well as a list of other clients [here](https://modelcontextprotocol.io/clients).

### Why Claude for Desktop and Not Claude.ai?

## Core MCP Concepts

MCP servers can provide three main types of capabilities:

- **Resources**: File-like data that can be read by clients (like API responses or file contents).
- **Tools**: Functions that can be called by the LLM (with user approval).
- **Prompts**: Pre-written templates that help users accomplish specific tasks.

This tutorial will primarily focus on **tools**.

## Let’s Get Started

We’ll be building our weather server! You can find the complete code for what we’ll be building [here](#).

---

## Prerequisite Knowledge

This quickstart assumes you have familiarity with:

- Python
- LLMs like Claude

---

## System Requirements

- Python 3.10 or higher installed.
- You must use the Python MCP SDK 1.2.0 or higher.

---

## Set Up Your Environment

### MacOS/Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Make sure to restart your terminal afterwards to ensure that the `uv` command gets picked up.

### Windows

Follow the same steps as above.

---

### Create and Set Up Your Project

#### MacOS/Linux

```bash
# Create a new directory for our project
uv init weather
cd weather

# Create virtual environment and activate it
uv venv
source .venv/bin/activate

# Install dependencies
uv add "mcp[cli]" httpx

# Create our server file
touch weather.py
```

#### Windows

Follow the equivalent steps for Windows.

---

## Building Your Server

### Importing Packages and Setting Up the Instance

Add these to the top of your `weather.py`:

```python
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("weather")

# Constants
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"
```

The `FastMCP` class uses Python type hints and docstrings to automatically generate tool definitions, making it easy to create and maintain MCP tools.

---

### Helper Functions

Next, add helper functions for querying and formatting the data from the National Weather Service API:

```python
async def make_nws_request(url: str) -> dict[str, Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/geo+json"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature["properties"]
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""
```

---

### Implementing Tool Execution

Add the tool execution handlers:

```python
@mcp.tool()
async def get_alerts(state: str) -> str:
    """Get weather alerts for a US state.

    Args:
        state: Two-letter US state code (e.g. CA, NY)
    """
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)

    if not data or "features" not in data:
        return "Unable to fetch alerts or no alerts found."

    if not data["features"]:
        return "No active alerts for this state."

    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n---\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude: float, longitude: float) -> str:
    """Get weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
    """
    # First get the forecast grid endpoint
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    points_data = await make_nws_request(points_url)

    if not points_data:
        return "Unable to fetch forecast data for this location."

    # Get the forecast URL from the points response
    forecast_url = points_data["properties"]["forecast"]
    forecast_data = await make_nws_request(forecast_url)

    if not forecast_data:
        return "Unable to fetch detailed forecast."

    # Format the periods into a readable forecast
    periods = forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:  # Only show next 5 periods
        forecast = f"""
{period['name']}:
Temperature: {period['temperature']}°{period['temperatureUnit']}
Wind: {period['windSpeed']} {period['windDirection']}
Forecast: {period['detailedForecast']}
"""
        forecasts.append(forecast)

    return "\n---\n".join(forecasts)
```

---

### Running the Server

Finally, initialize and run the server:

```python
if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
```

Your server is complete! Run `uv run weather.py` to confirm that everything’s working.

---

## Testing Your Server with Claude for Desktop

Claude for Desktop is not yet available on Linux. Linux users can proceed to the [Building a Client](#) tutorial to build an MCP client that connects to the server we just built.

### Configure Claude for Desktop

1. Install Claude for Desktop. You can install the latest version [here](#).
2. Open the configuration file at `~/Library/Application Support/Claude/claude_desktop_config.json` in a text editor. Create the file if it doesn’t exist.

#### Example Configuration

```json
{
    "mcpServers": {
        "weather": {
            "command":
You may need to put the full path to the uv executable in the command field. You can get this by running which uv on MacOS/Linux or where uv on Windows.

Make sure you pass in the absolute path to your server.

This tells Claude for Desktop:

There’s an MCP server named “weather”
To launch it by running uv --directory /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather run weather.py
Save the file, and restart Claude for Desktop.

​
Test with commands
Let’s make sure Claude for Desktop is picking up the two tools we’ve exposed in our weather server. You can do this by looking for the hammer  icon:


After clicking on the hammer icon, you should see two tools listed:


If your server isn’t being picked up by Claude for Desktop, proceed to the Troubleshooting section for debugging tips.

If the hammer icon has shown up, you can now test your server by running the following commands in Claude for Desktop:

What’s the weather in Sacramento?
What are the active weather alerts in Texas?


Since this is the US National Weather service, the queries will only work for US locations.

​
What’s happening under the hood
When you ask a question:

The client sends your question to Claude
Claude analyzes the available tools and decides which one(s) to use
The client executes the chosen tool(s) through the MCP server
The results are sent back to Claude
Claude formulates a natural language response
The response is displayed to you!
​
