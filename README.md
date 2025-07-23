# MCP Chat Simple

A powerful Streamlit application for testing and interacting with Model Context Protocol (MCP) servers using OpenAI's GPT models. This tool allows you to discover, connect to, and execute tools from various MCP servers in a user-friendly chat interface.

## Features

🤖 **AI Chat Interface**: Chat with OpenAI GPT models that can execute MCP tools  
🖥️ **MCP Server Management**: Connect, disconnect, and monitor multiple MCP servers  
🛠️ **Tool Discovery**: Automatically discover and use tools from connected servers  
📊 **Analytics Dashboard**: Monitor tool executions and conversation metrics  
🔄 **Real-time Updates**: Refresh servers and see live status indicators  
📥 **Export Conversations**: Download chat logs and tool execution history  
📁 **Safe File Operations**: All file operations are contained within the `./workspace/` directory  

## Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/haydentbs/mcp-testing-chatbot.git
cd mcp-chat-simple
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
# Create your environment file
cp .env.example .env

# Edit .env with your OpenAI API key
nano .env  # or use your preferred editor
```

4. **Run the application:**
```bash
# Using the run script (recommended)
python run.py

# Or directly with Streamlit
streamlit run app.py
```

5. **Open your browser** to `http://localhost:8501`

## Prerequisites

- **Python 3.8+**: The application is built with modern Python
- **Node.js**: Required for running MCP servers via npx (most servers use this)
- **OpenAI API Key**: Get one from [OpenAI Platform](https://platform.openai.com/api-keys)

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the project root with the following content:

```env
# =============================================================================
# REQUIRED SETTINGS
# =============================================================================

# OpenAI API Key (Required)
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# =============================================================================
# OPTIONAL SETTINGS (with defaults)
# =============================================================================

# OpenAI Model Configuration
OPENAI_MODEL=gpt-4o-mini           # Model to use for chat
OPENAI_MAX_TOKENS=1000             # Max tokens per response
OPENAI_TEMPERATURE=0.7             # Response creativity (0.0-1.0)

# MCP Configuration
MCP_TIMEOUT=30                     # Server connection timeout (seconds)
MCP_RETRY_ATTEMPTS=3               # Number of retry attempts
MCP_SERVERS_CONFIG=config/mcp_servers.json  # Path to server config

# Application Configuration
APP_TITLE=MCP Server Tester        # App title in browser
APP_ICON=🤖                        # App icon
DEBUG_MODE=false                   # Enable debug logging

# Logging Configuration
LOG_LEVEL=INFO                     # Logging level (DEBUG, INFO, WARNING, ERROR)
# LOG_FILE=app.log                 # Optional: log to file

# =============================================================================
# MCP SERVER SPECIFIC ENVIRONMENT VARIABLES
# =============================================================================

# Brave Search API (for brave-search server)
# Get your API key from: https://api.search.brave.com/app/keys
# BRAVE_API_KEY=your_brave_api_key_here


```

### Environment Variable Details

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | None | Your OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_MAX_TOKENS` | No | `1000` | Maximum tokens per response |
| `OPENAI_TEMPERATURE` | No | `0.7` | Response creativity (0.0-1.0) |
| `MCP_TIMEOUT` | No | `30` | Server connection timeout in seconds |
| `DEBUG_MODE` | No | `false` | Enable detailed logging |

## MCP Server Configuration

### Server Configuration File

The application uses `config/mcp_servers.json` to define available MCP servers. Here's a comprehensive example:

```json
[
  {
    "name": "filesystem",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"],
    "description": "File system operations server (workspace folder)",
    "enabled": true
  },
  {
    "name": "brave-search",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-brave-search"],
    "description": "Web search using Brave Search API",
    "enabled": false,
    "env": {
      "BRAVE_API_KEY": "your_brave_api_key_here"
    }
  },

  {
    "name": "custom-server",
    "command": "/usr/bin/python3",
    "args": ["/path/to/custom/server.py", "--port", "8080"],
    "description": "Custom MCP server with specific Python version",
    "enabled": false,
    "env": {
      "CUSTOM_CONFIG": "value",
      "API_ENDPOINT": "https://api.example.com"
    },
    "cwd": "/path/to/working/directory"
  }
]
```

### Server Configuration Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ Yes | Unique identifier for the server |
| `command` | ✅ Yes | Command to execute (e.g., `npx`, `python`, full path) |
| `args` | ✅ Yes | Array of command arguments |
| `description` | ✅ Yes | Human-readable description |
| `enabled` | ✅ Yes | Whether to load this server on startup |
| `env` | No | Environment variables for the server process |
| `cwd` | No | Working directory for the server process |

### Popular MCP Servers

Here are some commonly used MCP servers you can add:

```json
{
  "name": "filesystem",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"],
  "description": "File operations within workspace directory",
  "enabled": true
}
```

```json
{
  "name": "git",
  "command": "npx", 
  "args": ["-y", "@modelcontextprotocol/server-git", "--repository", "."],
  "description": "Git operations for current repository",
  "enabled": true
}
```

```json
{
  "name": "brave-search",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-brave-search"],
  "description": "Web search capabilities",
  "enabled": false,
  "env": {"BRAVE_API_KEY": "your_api_key"}
}
```

## Usage

### Starting the Application

**Option 1: Using the run script (recommended)**
```bash
python run.py
```
The run script will:
- Check all requirements are installed
- Verify your `.env` file exists and is configured
- Check for existing Streamlit instances
- Start the application with optimized settings

**Option 2: Direct Streamlit**
```bash
streamlit run app.py
```

**Option 3: Using start.sh**
```bash
./start.sh
```

### Basic Interaction

1. **Refresh MCP Servers**: Use the "🔄 Refresh Servers" button in the sidebar
2. **Monitor Server Status**: Check the status indicators next to each server name
3. **Start Chatting**: Type messages in the chat interface
4. **File Operations**: All file operations happen in the `./workspace/` directory

### Example Conversations

Here are some example interactions you can try:

**File Operations:**
- "Create a file called notes.txt with some bullet points about MCP"
- "List all files in the workspace directory"
- "Read the contents of the README.md file"
- "Create a Python script that prints hello world"

**Web Search (if Brave Search is configured):**
- "Search for the latest news about artificial intelligence"
- "Find information about the Model Context Protocol"


**Analysis and Processing:**
- "Analyze the word count and readability of notes.txt"
- "Count the lines of code in all Python files"

## Project Structure

```
mcp-chat-simple/
├── app.py                 # Main Streamlit application
├── run.py                 # Startup script with checks
├── start.sh               # Simple bash startup script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── config/
│   ├── __init__.py
│   ├── settings.py       # Configuration management
│   └── mcp_servers.json  # MCP server definitions
├── mcp_client/
│   ├── __init__.py
│   ├── client.py         # MCP protocol implementation
│   ├── server_manager.py # Server lifecycle management
│   └── tool_executor.py  # Tool execution handler
├── ai/
│   ├── __init__.py
│   ├── openai_client.py  # OpenAI API integration
│   └── function_handler.py # Function calling logic
├── utils/
│   ├── __init__.py
│   ├── logger.py         # Logging configuration
│   └── helpers.py        # Utility functions
└── workspace/            # Safe directory for file operations
```

## Key Features

### 🔒 Safe File Operations
All file operations through the filesystem MCP server are contained within the `./workspace/` directory. This ensures:
- No accidental modification of system files
- Easy cleanup and organization
- Safe testing environment

### 📊 Server Management Panel
- **Real-time Status**: Visual indicators show server connection status
- **Tool Discovery**: Automatically finds available tools from each server
- **Easy Management**: Connect/disconnect servers with one click
- **Configuration**: View and edit server settings

### 🤖 Intelligent Chat Interface
- **Natural Language**: Interact using plain English
- **Tool Integration**: AI automatically selects and uses appropriate tools
- **Streaming Responses**: Real-time response generation
- **History Preservation**: Conversation history maintained across sessions

### 📈 Analytics Dashboard
- **Usage Metrics**: Track tool usage and success rates
- **Performance Monitoring**: Monitor response times and errors
- **Export Capabilities**: Download conversation logs and analytics

## Troubleshooting

### Common Issues

**1. OpenAI API Errors**
```
Error: Invalid API key
```
- Check your API key in the `.env` file
- Ensure the key is active and has sufficient credits
- Verify the key format (should start with `sk-`)

**2. MCP Server Connection Failures**
```
Error: Failed to connect to server 'filesystem'
```
- Ensure Node.js is installed for npx-based servers
- Check server paths are correct for Python-based servers
- Verify environment variables are set for servers that need them
- Check the server logs in the Streamlit interface

**3. Import/Dependency Errors**
```
ModuleNotFoundError: No module named 'streamlit'
```
- Run `pip install -r requirements.txt`
- Consider using a virtual environment
- Check Python version (3.8+ required)

**4. Permission Errors**
```
PermissionError: [Errno 13] Permission denied
```
- Ensure the `./workspace/` directory is writable
- Check file permissions on the project directory
- On macOS/Linux, try `chmod +x start.sh` for the start script

**5. Port Already in Use**
```
Error: Port 8501 is already in use
```
- Kill existing Streamlit processes: `pkill -f streamlit`
- Use a different port: `streamlit run app.py --server.port 8502`

### Debug Mode

Enable debug mode for detailed logging:

1. Set `DEBUG_MODE=true` in your `.env` file
2. Restart the application
3. Check the console output for detailed logs
4. Optionally set `LOG_FILE=app.log` to save logs to a file

### Getting Help

If you encounter issues:

1. **Check the server status** in the sidebar
2. **Review the console output** for error messages
3. **Try refreshing servers** with the button in the sidebar
4. **Restart the application** if problems persist
5. **Check the GitHub issues** for known problems

## Development

### Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature-name`
3. **Make your changes** and add tests if applicable
4. **Test thoroughly** with different MCP servers
5. **Submit a pull request** with a clear description

### Adding New MCP Servers

To add support for a new MCP server:

1. **Add server configuration** to `config/mcp_servers.json`
2. **Test the connection** using the refresh button
3. **Verify tool discovery** works correctly
4. **Test tool execution** through the chat interface
5. **Update documentation** if needed

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your settings

# Run in development mode
streamlit run app.py --server.runOnSave true
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Model Context Protocol (MCP)**: The foundation protocol for tool integration
- **OpenAI**: GPT models and function calling capabilities
- **Streamlit**: Modern web application framework
- **MCP Community**: Various server implementations and tools

---

**Happy chatting! 🤖✨** 