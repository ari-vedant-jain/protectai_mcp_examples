# Weather Analysis Tool with Claude

An interactive demo that combines the National Weather Service (NWS) API tool call with Anthropic Claude and logging as Actions to Layer sessions.

## How It Works

1. The tool fetches weather data from the NWS API
2. Data is formatted and sent to Claude via the Anthropic API
3. Claude analyzes the data based on the selected perspective
4. Results are displayed in the interface
5. All interactions are logged to Layer with tool-specific attributes:
   - Weather API calls are logged with source URLs and parameters
   - Claude analyses are logged with model information and response details
   - Session tracking enables complete interaction history

## Features

- **Weather Data Retrieval**: Fetch forecasts and alerts from the NWS API
- **AI-Powered Analysis**: Analyze weather data using Claude with different perspectives:
  - General weather summary
  - Travel recommendations
  - Emergency preparedness guidance
- **Interactive UI**: User-friendly Gradio interface for inputting locations and viewing analyses
- **Layer Logging**: Comprehensive logging of AI interactions:
  - Logs Claude API calls as completion_output actions
  - Records tool usage with detailed attributes
  - Enables monitoring and analysis of AI system behavior
- **Interactive UI**: User-friendly Gradio interface for inputting locations and viewing analyses

## Prerequisites

- Python 3.7+
- Jupyter Notebook/Lab
- Anthropic API key

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install httpx nest_asyncio anthropic ipywidgets gradio
   ```
3. Create a `secrets.json` file with your Anthropic API key and Layer Client Secrethere:
   ```json
   {
     "ANTHROPIC_API_KEY": "your_api_key_here",
     "LAYER_DEMO_AUTH_CLIENT_SECRET": "your_layer_secret_here"
   }

## Usage

1. Open `weather_analysis_tool_claude.ipynb` in Jupyter
2. Run all cells to launch the Gradio interface
3. Enter coordinates (latitude/longitude) for weather forecasts
4. Select an analysis type (general, travel, emergency)
5. Click "Analyze Weather" to get Claude's insights

## Example Coordinates

- Austin, TX: 30.2672, -97.7431
- New York, NY: 40.7128, -74.0060
- San Francisco, CA: 37.7749, -122.4194
- Chicago, IL: 41.8781, -87.6298


## License

MIT