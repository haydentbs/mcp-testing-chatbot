# MCP Streamlit Chatbot

A powerful Streamlit application for testing and interacting with Model Context Protocol (MCP) servers using OpenAI's GPT models. This tool allows you to discover, connect to, and execute tools from various MCP servers in a user-friendly chat interface.

## Features

🤖 **AI Chat Interface**: Chat with OpenAI GPT-4o-mini that can execute MCP tools
🖥️ **MCP Server Management**: Connect, disconnect, and monitor MCP servers
🛠️ **Tool Discovery**: Automatically discover and use tools from connected servers
📊 **Analytics Dashboard**: Monitor tool executions and conversation metrics
🔄 **Real-time Updates**: Refresh servers and see live status indicators
📥 **Export Conversations**: Download chat logs and tool execution history

## Architecture

The application consists of several key components:

- **Frontend**: Streamlit web interface with chat and server management
- **MCP Integration**: Client to discover, connect, and execute tools from MCP servers
- **AI Integration**: OpenAI GPT-4o-mini with function calling for MCP tools
- **Configuration**: Server definitions and API key management

## Prerequisites

- Python 3.8+
- Node.js (for running MCP servers via npx)
- OpenAI API key

## Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd mcp-chat-simple
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and other settings
```

4. **Configure MCP servers (optional):**
   - Edit `config/mcp_servers.json` to add/modify server configurations
   - Default servers include filesystem, git, and brave-search

## Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=1000
OPENAI_TEMPERATURE=0.7
MCP_TIMEOUT=30
APP_TITLE=MCP Server Tester
DEBUG_MODE=false
```

### MCP Server Configuration

Edit `config/mcp_servers.json` to configure available MCP servers:

```json
[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "description": "File system operations server",
    "enabled": true
  },
  {
    "name": "brave-search",
    "command": "npx", 
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "description": "Web search using Brave Search API",
    "enabled": false,
    "env": {
      "BRAVE_API_KEY": "your_brave_api_key"
    }
  }
]
```

## Usage

1. **Start the application:**
```bash
streamlit run app.py
```

2. **Open your browser** to `http://localhost:8501`

3. **Refresh MCP servers** using the button in the sidebar

4. **Start chatting** with the AI in the main interface

### Example Interactions

- "List the files in the workspace directory"
- "Search for information about MCP protocol"
- "Create a new file called test.txt with some content in the workspace"
- "Show me the git status of this repository"
- "Read the contents of a file I created earlier"

### File Operations

The filesystem MCP server operates within the `./workspace/` folder to keep all file operations contained and safe. Any files you create, read, or modify through the chatbot will be stored in this directory.

## Project Structure

```
mcp-chat-simple/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── config/
│   ├── settings.py       # Configuration management
│   └── mcp_servers.json  # MCP server definitions
├── mcp_client/
│   ├── client.py         # MCP client implementation
│   ├── server_manager.py # Server discovery and management
│   └── tool_executor.py  # Tool execution handler
├── ai/
│   ├── openai_client.py  # OpenAI integration
│   └── function_handler.py # Function calling logic
└── utils/
    ├── logger.py         # Logging configuration
    └── helpers.py        # Utility functions
```

## Key Components

### MCP Client (`mcp_client/`)
- **client.py**: Core MCP protocol implementation
- **server_manager.py**: Manages server lifecycle and configurations
- **tool_executor.py**: Handles tool execution and result formatting

### AI Integration (`ai/`)
- **openai_client.py**: OpenAI API wrapper with streaming support
- **function_handler.py**: Manages function calling and conversation flow

### Configuration (`config/`)
- **settings.py**: Application settings with environment variable support
- **mcp_servers.json**: Server configurations

## Features in Detail

### Server Management Panel
- Real-time server status indicators
- Connect/disconnect individual servers
- View available tools per server
- Server configuration management

### Chat Interface
- Natural language interaction with AI
- Automatic tool discovery and execution
- Real-time tool execution feedback
- Conversation history preservation

### Analytics Dashboard
- Conversation metrics and statistics
- Tool execution success rates
- Performance monitoring
- Export functionality for analysis

## Troubleshooting

### Common Issues

1. **OpenAI API errors**: Check your API key in the `.env` file
2. **MCP server connection fails**: Ensure Node.js is installed and servers are accessible
3. **Import errors**: Verify all dependencies are installed via `pip install -r requirements.txt`

### Debug Mode

Enable debug mode by setting `DEBUG_MODE=true` in your `.env` file for detailed logging.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built on the Model Context Protocol (MCP) standard
- Uses OpenAI's function calling capabilities
- Streamlit for the web interface
- Various MCP server implementations from the community 