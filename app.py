
"""
Main Streamlit application for the MCP Server Tester.
"""
import asyncio
import streamlit as st
import pandas as pd
from typing import Dict, List, Optional
import time
import json

# Import our custom modules
from config.settings import settings
from mcp_client.server_manager import MCPServerManager
from mcp_client.tool_executor import MCPToolExecutor
from ai.openai_client import OpenAIClient
from ai.function_handler import FunctionHandler
from utils.logger import logger
from utils.helpers import async_to_sync, format_tool_call, format_tool_result


# Page configuration
st.set_page_config(
    page_title=settings.app_title,
    page_icon=settings.app_icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        margin-bottom: 2rem;
    }
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-connected { background-color: #00ff00; }
    .status-disconnected { background-color: #ff4444; }
    .status-error { background-color: #ff8800; }
    .status-connecting { background-color: #ffff00; }
    
    .tool-execution {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 10px;
        margin: 5px 0;
        background-color: #f9f9f9;
    }
    .tool-success { border-left: 4px solid #00ff00; }
    .tool-error { border-left: 4px solid #ff4444; }
    
    .server-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        background-color: #fafafa;
    }
    
    .error-details-section {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 15px;
        margin: 10px 0;
    }
    
    .error-details-header {
        color: #856404;
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    /* Chat Interface Styling */
    .chat-container {
        max-height: 600px;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #fafafa;
    }
    
    /* Chat messages container styling */
    #chat-messages-container {
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: #fafafa;
        scroll-behavior: smooth;
    }
    
    #chat-messages-container::-webkit-scrollbar {
        width: 8px;
    }
    
    #chat-messages-container::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    #chat-messages-container::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 10px;
    }
    
    #chat-messages-container::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    
    /* Improve chat message styling */
    [data-testid="chat-message"] {
        margin-bottom: 1.5rem !important;
        padding: 0.75rem !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
    }
    
    /* User messages styling */
    [data-testid="chat-message"][data-testid*="user"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        margin-left: 2rem !important;
    }
    
    /* Assistant messages styling */
    [data-testid="chat-message"]:not([data-testid*="user"]) {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
        background: #ffffff !important;
        border: 1px solid #e1e5e9 !important;
        margin-right: 2rem !important;
    }
    
    /* Chat input styling */
    .stChatInput > div > div > div > div {
        border-radius: 20px !important;
        border: 2px solid #e1e5e9 !important;
    }
    
    .stChatInput > div > div > div > div:focus-within {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Status indicators */
    .status-processing {
        background: linear-gradient(90deg, #667eea, #764ba2);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 500;
    }
    
    /* Tool execution styling */
    .tool-execution-summary {
        background: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 8px;
        padding: 0.75rem;
        margin: 0.5rem 0;
    }
    
    /* Auto-scroll styling */
    div[data-testid="stVerticalBlock"] > div::-webkit-scrollbar {
        width: 8px;
    }
    
    div[data-testid="stVerticalBlock"] > div::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    div[data-testid="stVerticalBlock"] > div::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 10px;
    }
    
    div[data-testid="stVerticalBlock"] > div::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
    }
    
    /* Remove old unused styles */
    .chat-message, .user-message, .assistant-message, .chat-input-container, .message-timestamp {
        display: none;
    }
</style>

<script>
    // Auto-scroll to bottom function
    function scrollToBottom() {
        window.scrollTo({
            top: document.body.scrollHeight,
            behavior: 'smooth'
        });
    }
    
    // Auto-scroll when new messages are added
    function setupAutoScroll() {
        // Watch for changes in the main content area
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    // Small delay to ensure content is rendered
                    setTimeout(scrollToBottom, 100);
                }
            });
        });
        
        // Start observing
        const targetNode = document.querySelector('[data-testid="stVerticalBlock"]');
        if (targetNode) {
            observer.observe(targetNode, {
                childList: true,
                subtree: true
            });
        }
    }
    
    // Initialize auto-scroll when page loads
    document.addEventListener('DOMContentLoaded', setupAutoScroll);
    
    // Also setup when Streamlit reruns
    window.addEventListener('load', setupAutoScroll);
</script>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_components():
    """Initialize all components with caching."""
    try:
        # Initialize OpenAI client
        openai_client = OpenAIClient()
        
        # Initialize MCP server manager
        server_manager = MCPServerManager()
        
        # Initialize tool executor
        tool_executor = MCPToolExecutor(server_manager)
        
        # Initialize function handler
        function_handler = FunctionHandler(openai_client, tool_executor)
        
        return openai_client, server_manager, tool_executor, function_handler
    except Exception as e:
        st.error(f"Failed to initialize components: {e}")
        return None, None, None, None


def render_status_indicator(status: str) -> str:
    """Render a status indicator for servers."""
    status_classes = {
        "connected": "status-connected",
        "disconnected": "status-disconnected",
        "error": "status-error",
        "connecting": "status-connecting"
    }
    class_name = status_classes.get(status, "status-disconnected")
    return f'<span class="status-indicator {class_name}"></span>{status.title()}'


def render_server_panel(server_manager: MCPServerManager):
    """Render the MCP server management panel."""
    st.sidebar.header("🖥️ MCP Servers")
    
    # Server status summary
    if server_manager._initialized:
        status_summary = server_manager.get_server_status_summary()
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Connected", status_summary["connected"])
        with col2:
            st.metric("Total", status_summary["total"])
        
        # Auto-connection info
        if status_summary["total"] > 0:
            if status_summary["connected"] == status_summary["total"]:
                st.sidebar.info("ℹ️ All servers auto-connected on startup")
            elif status_summary["connected"] > 0:
                st.sidebar.info("ℹ️ Servers auto-connect on startup")
            else:
                st.sidebar.warning("⚠️ Auto-connection failed - check configurations below")
        else:
            st.sidebar.info("ℹ️ No servers configured - add servers via config files")
    
    # Manual server controls
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Reconnect All", use_container_width=True):
            with st.spinner("Reconnecting servers..."):
                results = async_to_sync(server_manager.refresh_servers)()
                
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    if success_count == total_count:
                        st.sidebar.success(f"✅ All {success_count} servers connected")
                    else:
                        st.sidebar.success(f"✅ {success_count}/{total_count} servers connected")
                else:
                    st.sidebar.error("❌ Failed to connect to any servers")
    
    with col2:
        if st.button("🆕 Reload Config", use_container_width=True):
            with st.spinner("Reloading configuration..."):
                # Clear the cache and session state to force re-initialization
                st.cache_resource.clear()
                if "servers_initialized" in st.session_state:
                    del st.session_state.servers_initialized
                if "initial_connection_results" in st.session_state:
                    del st.session_state.initial_connection_results
                st.rerun()
    
    # Servers are now auto-initialized when the app starts
    
    # Display server list
    st.sidebar.subheader("Server Status")
    servers_info = server_manager.get_all_servers_info()
    
    for server_info in servers_info:
        with st.sidebar.expander(f"{server_info['name']} ({server_info['tools_count']} tools)"):
            # Status
            status_html = render_status_indicator(server_info['status'])
            st.markdown(status_html, unsafe_allow_html=True)
            
            # Description
            st.caption(server_info['description'])
            
            # Tools
            if server_info['tools']:
                st.write("**Available Tools:**")
                for tool in server_info['tools']:
                    st.write(f"• `{tool['name']}`: {tool['description']}")
            
            # Connection info
            if server_info['connection_time']:
                st.write(f"**Connection Time:** {server_info['connection_time']:.2f}s")
            
            # Error info
            if server_info['last_error']:
                st.error(f"**Error:** {server_info['last_error']}")
            
            # Server controls
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"Connect", key=f"connect_{server_info['name']}"):
                    success = async_to_sync(server_manager.connect_server)(server_info['name'])
                    if success:
                        st.success("Connected!")
                        st.rerun()
                    else:
                        st.error("Connection failed")
            
            with col2:
                if st.button(f"Disconnect", key=f"disconnect_{server_info['name']}"):
                    success = async_to_sync(server_manager.disconnect_server)(server_info['name'])
                    if success:
                        st.success("Disconnected!")
                        st.rerun()
            
            # Show Error Details button for servers with errors
            if server_info.get('has_detailed_errors', False):
                if st.button(f"🔍 Show Error Details", key=f"error_details_{server_info['name']}", use_container_width=True):
                    error_details = server_manager.get_server_error_details(server_info['name'])
                    if error_details:
                        st.subheader(f"🚨 Error Details: {error_details['server_name']}")
                        
                        # Basic error info
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Status:** {error_details['status']}")
                            if error_details['error_time_formatted']:
                                st.write(f"**Error Time:** {error_details['error_time_formatted']}")
                        with col2:
                            if error_details['process_exit_code'] is not None:
                                st.write(f"**Exit Code:** {error_details['process_exit_code']}")
                            if error_details['full_command']:
                                st.write(f"**Command:** `{error_details['full_command']}`")
                        
                        # Main error message
                        if error_details['last_error']:
                            st.write("**Error Message:**")
                            st.code(error_details['last_error'])
                        
                        # Process output tabs
                        if error_details['stderr_output'] or error_details['stdout_output']:
                            tab1, tab2 = st.tabs(["stderr", "stdout"])
                            
                            with tab1:
                                if error_details['stderr_output']:
                                    st.write("**Standard Error Output:**")
                                    st.code(error_details['stderr_output'], language="text")
                                else:
                                    st.info("No stderr output captured")
                            
                            with tab2:
                                if error_details['stdout_output']:
                                    st.write("**Standard Output:**")
                                    st.code(error_details['stdout_output'], language="text")
                                else:
                                    st.info("No stdout output captured")
                        
                        # Server configuration
                        st.markdown("**📋 Server Configuration:**")
                        st.json(error_details['server_config'])
                        
                        # Troubleshooting tips
                        st.markdown("**💡 Troubleshooting Tips:**")
                        st.markdown("""
                        **Common Issues:**
                        - **Command not found**: Make sure the command is installed and in your PATH
                        - **Permission denied**: Check file permissions and execution rights
                        - **Module not found**: Ensure all dependencies are installed
                        - **Port already in use**: Check if another instance is running
                        - **Environment variables**: Verify required environment variables are set
                        
                        **Debug Steps:**
                        1. Try running the command manually in your terminal
                        2. Check the stderr output above for specific error messages
                        3. Verify the command path and arguments are correct
                        4. Ensure all required dependencies are installed
                        """)
                    else:
                        st.warning("No detailed error information available for this server.")


def render_ai_status_panel(function_handler: FunctionHandler):
    """Render the real-time AI status panel."""
    current_status = function_handler.get_current_status()
    
    # Create expandable status panel
    with st.expander("🧠 AI Activity Monitor", expanded=False):
        # Status indicator with color coding
        state_colors = {
            "idle": "🟢",
            "thinking": "🟡", 
            "executing_tool": "🔵",
            "responding": "🟠"
        }
        
        state_color = state_colors.get(current_status.state, "⚪")
        st.markdown(f"**Status:** {state_color} {current_status.state.title()}")
        st.markdown(f"**Activity:** {current_status.current_activity}")
        
        # Show elapsed time
        elapsed = time.time() - current_status.start_time
        st.markdown(f"**Elapsed:** {elapsed:.1f}s")
        
        # Show tool-specific information
        if current_status.state == "executing_tool":
            if current_status.current_tool:
                st.markdown(f"**Tool:** {current_status.current_tool}")
            
            if current_status.tool_progress:
                st.markdown(f"**Progress:** {current_status.tool_progress}")
            
            # Show progress bar if we have tool counts
            if current_status.total_tools > 0:
                progress = current_status.tools_completed / current_status.total_tools
                st.progress(progress)
                st.markdown(f"**Tools:** {current_status.tools_completed}/{current_status.total_tools}")
        
        # Show recent status history
        status_history = function_handler.get_status_history()
        if status_history:
            st.markdown("**Recent Activities:**")
            # Show last 5 activities
            for status in status_history[-5:]:
                elapsed_for_status = time.time() - status.start_time
                st.markdown(f"• {status.current_activity} ({elapsed_for_status:.1f}s ago)")
        
        # Auto-refresh when AI is active
        if current_status.state != "idle":
            time.sleep(0.5)  # Small delay to prevent excessive updates
            st.rerun()


def render_chat_interface(function_handler: FunctionHandler):
    """Render the main chat interface with improved UI."""
    st.header("💬 MCP Chat Interface")
    
    # Initialize session state for chat
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_turns" not in st.session_state:
        st.session_state.conversation_turns = []
    
    # Chat controls row
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.subheader("Ask me anything!")
    with col2:
        if st.button("🧹 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.conversation_turns = []
            function_handler.clear_conversation()
            st.rerun()
    with col3:
        streaming_enabled = st.checkbox("Streaming", value=True)
    with col4:
        auto_scroll = st.checkbox("Auto-scroll", value=True)
    
    # Real-time AI Status Panel
    render_ai_status_panel(function_handler)
    
    # Chat History Container with fixed height and scrolling
    st.markdown("### 💬 Chat History")
    
    # Create a scrollable container for chat messages
    with st.container():
        # If there are no messages, show a welcome message
        if not st.session_state.messages:
            st.info("""
            👋 **Welcome to MCP Chat!**
            
            Start a conversation by typing a message below. I can help you with various tasks using the connected MCP servers.
            
            **Try asking:**
            - "List files in the workspace"
            - "Create a new file with some content" 
            - "Search for information about Python"
            - "Show me the git status"
            """)
        else:
            # Create a container with fixed height for scrolling
            # Add a unique identifier for the chat container
            st.markdown('<div id="chat-messages-container">', unsafe_allow_html=True)
            chat_container = st.container()
            
            with chat_container:
                # Display messages in reverse order (newest first for better UX)
                for i, message in enumerate(st.session_state.messages):
                    timestamp = message.get("timestamp", "")
                    
                    # Use Streamlit's native chat message components
                    with st.chat_message(message["role"]):
                        if message["role"] == "user":
                            st.markdown(f"**You** _{timestamp}_")
                            st.write(message["content"])
                        
                        elif message["role"] == "assistant":
                            st.markdown(f"**🤖 Assistant** _{timestamp}_")
                            st.write(message["content"])
                            
                            # Calculate the correct conversation turn index
                            # Count how many assistant messages we've seen up to this point
                            assistant_message_count = sum(1 for msg in st.session_state.messages[:i+1] if msg["role"] == "assistant")
                            turn_index = assistant_message_count - 1  # Convert to 0-based index
                            
                            # Show tool executions if any for this turn
                            if turn_index < len(st.session_state.conversation_turns):
                                turn = st.session_state.conversation_turns[turn_index]
                                if turn.tool_executions:
                                    # Summary of tool executions
                                    success_count = sum(1 for exec in turn.tool_executions if exec.success)
                                    total_count = len(turn.tool_executions)
                                    
                                    if success_count == total_count:
                                        status_color = "🟢"
                                        status_text = "All successful"
                                    elif success_count > 0:
                                        status_color = "🟡"
                                        status_text = f"{success_count}/{total_count} successful"
                                    else:
                                        status_color = "🔴"
                                        status_text = "All failed"
                                    
                                    with st.expander(f"🛠️ Tool Executions ({total_count}) {status_color} {status_text}", expanded=False):
                                        for j, exec in enumerate(turn.tool_executions):
                                            status_icon = "✅" if exec.success else "❌"
                                            time_str = f"({exec.execution_time:.2f}s)" if exec.execution_time else ""
                                            
                                            st.markdown(f"**{j+1}.** {status_icon} **{exec.tool_name}** on *{exec.server_name}* {time_str}")
                                            
                                            # Create columns for arguments and results
                                            exec_col1, exec_col2 = st.columns(2)
                                            
                                            with exec_col1:
                                                if exec.arguments:
                                                    st.markdown("**📋 Arguments:**")
                                                    st.json(exec.arguments)
                                            
                                            with exec_col2:
                                                if exec.success and exec.result:
                                                    st.markdown("**📤 Result:**")
                                                    if isinstance(exec.result, (dict, list)):
                                                        st.json(exec.result)
                                                    else:
                                                        st.code(str(exec.result))
                                                elif exec.error:
                                                    st.markdown("**❌ Error:**")
                                                    st.error(exec.error)
                                            
                                            if j < len(turn.tool_executions) - 1:
                                                st.divider()
            
            # Close the chat container div
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Fixed Chat Input Section
    st.markdown("---")
    st.markdown("### 📝 Send Message")
    
    # Chat input using columns for better layout
    input_col1, input_col2 = st.columns([5, 1])
    
    with input_col1:
        # Use chat input for the main message
        user_input = st.chat_input("Type your message here... Press Enter to send!")
    
    with input_col2:
        st.write("")  # Spacer to align with chat input height
    
    # Handle chat input
    if user_input and user_input.strip():
        # Add timestamp to messages
        timestamp = time.strftime("%H:%M:%S")
        
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user", 
            "content": user_input,
            "timestamp": timestamp
        })
        
        # Show processing status with enhanced AI status information
        with st.status("🤖 Processing your message...", expanded=True) as status:
            # Show initial thinking status
            st.write("🧠 **AI is analyzing your request...**")
            
            try:
                # Handle the user message with enhanced status tracking
                turn = async_to_sync(function_handler.handle_user_message)(user_input, stream=streaming_enabled)
                
                # Get final AI status to show what happened during processing
                final_status = function_handler.get_current_status()
                recent_history = function_handler.get_status_history()
                
                # Show processing summary
                st.write("✅ **Response generated successfully!**")
                
                # Display tool execution details if any tools were used
                if turn.tool_executions:
                    st.write("🛠️ **Tool Execution Summary:**")
                    
                    # Show overview first
                    total_tools = len(turn.tool_executions)
                    successful_tools = [exec for exec in turn.tool_executions if exec.success]
                    failed_tools = [exec for exec in turn.tool_executions if not exec.success]
                    
                    overview_parts = []
                    if successful_tools:
                        overview_parts.append(f"✅ {len(successful_tools)} successful")
                    if failed_tools:
                        overview_parts.append(f"❌ {len(failed_tools)} failed")
                    
                    st.info(f"📊 **Total:** {total_tools} tool(s) executed - {', '.join(overview_parts)}")
                    
                    # Show individual tool executions in a simple list
                    for i, exec in enumerate(turn.tool_executions, 1):
                        status_icon = "✅" if exec.success else "❌"
                        execution_time = f" ({exec.execution_time:.2f}s)" if exec.execution_time else ""
                        
                        # Show each tool execution
                        st.write(f"  **{i}.** {status_icon} **{exec.tool_name}** on *{exec.server_name}*{execution_time}")
                        
                        # Show tool arguments in a compact format
                        if exec.arguments:
                            args_str = ", ".join([f"{k}={v}" for k, v in exec.arguments.items() if len(str(v)) < 50])
                            if len(args_str) > 100:
                                args_str = args_str[:100] + "..."
                            st.write(f"     📋 **Args:** {args_str}")
                        
                        # Show result or error
                        if exec.success and exec.result:
                            result_str = str(exec.result)
                            if len(result_str) > 150:
                                result_str = result_str[:150] + "..."
                            st.write(f"     📤 **Result:** {result_str}")
                        elif not exec.success and exec.error:
                            st.write(f"     ❌ **Error:** {exec.error}")
                
                # Show AI processing stages from status history
                if recent_history:
                    st.write("---")
                    st.write("🔍 **AI Processing Stages:**")
                    
                    # Show last few status updates
                    relevant_statuses = [s for s in recent_history[-10:] if s.state != "idle"]
                    if relevant_statuses:
                        for i, status_item in enumerate(relevant_statuses, 1):
                            elapsed = time.time() - status_item.start_time
                            state_icon = {
                                "thinking": "🧠",
                                "executing_tool": "🔧", 
                                "responding": "💬"
                            }.get(status_item.state, "⚡")
                            
                            stage_info = f"  **{i}.** {state_icon} {status_item.current_activity}"
                            
                            # Add tool-specific information
                            if status_item.current_tool:
                                stage_info += f" → **{status_item.current_tool}**"
                            if status_item.tool_progress:
                                stage_info += f" *({status_item.tool_progress})*"
                            
                            # Add progress information if available
                            if status_item.total_tools > 0 and status_item.tools_completed >= 0:
                                progress_info = f" [{status_item.tools_completed}/{status_item.total_tools}]"
                                stage_info += progress_info
                            
                            st.write(stage_info)
                    
                    # Show summary of what the AI did
                    if turn.tool_executions:
                        st.write("**Summary:** AI analyzed your request, decided to use tools, and executed them to provide a response.")
                    else:
                        st.write("**Summary:** AI analyzed your request and provided a direct response without using any tools.")
                
                # Add assistant response
                response_timestamp = time.strftime("%H:%M:%S")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": turn.assistant_response,
                    "timestamp": response_timestamp
                })
                
                # Store the conversation turn
                st.session_state.conversation_turns.append(turn)
                
                # Show final summary
                if turn.tool_executions:
                    executed_tools = [exec.tool_name for exec in turn.tool_executions if exec.success]
                    failed_tools = [exec.tool_name for exec in turn.tool_executions if not exec.success]
                    
                    summary_parts = []
                    if executed_tools:
                        summary_parts.append(f"✅ {len(executed_tools)} successful")
                    if failed_tools:
                        summary_parts.append(f"❌ {len(failed_tools)} failed")
                    
                    if summary_parts:
                        st.info(f"🛠️ **Tools used:** {', '.join(summary_parts)}")
                
                status.update(label="✅ Message processed successfully!", state="complete")
                
            except Exception as e:
                st.write(f"❌ **Error during processing:** {str(e)}")
                status.update(label="❌ Error processing message", state="error")
                
                # Add error message to chat
                error_timestamp = time.strftime("%H:%M:%S")
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"I encountered an error: {str(e)}",
                    "timestamp": error_timestamp
                })
        
        # Trigger auto-scroll to bottom if enabled
        if auto_scroll:
            st.markdown("""
            <script>
                // Force scroll to chat container bottom after message processing
                setTimeout(function() {
                    // Find the chat messages container
                    const chatContainer = document.getElementById('chat-messages-container');
                    if (chatContainer) {
                        // Scroll the chat container to show the latest message
                        chatContainer.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'end',
                            inline: 'nearest' 
                        });
                    }
                    
                    // Also find the last chat message and scroll to it
                    const chatMessages = document.querySelectorAll('[data-testid="chat-message"]');
                    if (chatMessages.length > 0) {
                        const lastMessage = chatMessages[chatMessages.length - 1];
                        lastMessage.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'nearest',
                            inline: 'nearest' 
                        });
                    }
                }, 500);
            </script>
            """, unsafe_allow_html=True)
        
        # Always rerun to update the chat
        st.rerun()
    
    # Show helpful tips when no messages
    if len(st.session_state.messages) == 0:
        st.markdown("---")
        
        tip_col1, tip_col2 = st.columns(2)
        
        with tip_col1:
            st.markdown("""
            ### 💡 Example Commands
            - `"List files in the workspace"`
            - `"Create a new file called hello.txt"`
            - `"Search for Python tutorials"`
            - `"Show me the git status"`
            - `"Count words in a text file"`
            """)
        
        with tip_col2:
            st.markdown("""
            ### ✨ Features
            - 🔄 Real-time tool execution monitoring
            - 🔍 Detailed error reporting for failed servers
            - ⚡ Streaming responses for faster interaction
            - 📊 Export conversation history
            - 📱 Auto-scroll to latest messages
            """)
    
    # Add scroll anchor at the bottom for auto-scroll functionality
    st.markdown('<div id="chat-bottom-anchor"></div>', unsafe_allow_html=True)
    
    # Enhanced auto-scroll script for better reliability
    if auto_scroll and len(st.session_state.messages) > 0:
        st.markdown("""
        <script>
            // Multiple scroll strategies targeting the chat container
            function scrollToChatBottom() {
                // Strategy 1: Scroll to the chat messages container
                const chatContainer = document.getElementById('chat-messages-container');
                if (chatContainer) {
                    chatContainer.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'end',
                        inline: 'nearest' 
                    });
                }
                
                // Strategy 2: Scroll to the last chat message
                setTimeout(() => {
                    const chatMessages = document.querySelectorAll('[data-testid="chat-message"]');
                    if (chatMessages.length > 0) {
                        const lastMessage = chatMessages[chatMessages.length - 1];
                        lastMessage.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center',
                            inline: 'nearest' 
                        });
                    }
                }, 200);
                
                // Strategy 3: Scroll to the bottom anchor for final positioning
                setTimeout(() => {
                    const anchor = document.getElementById('chat-bottom-anchor');
                    if (anchor) {
                        anchor.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'start',
                            inline: 'nearest' 
                        });
                    }
                }, 400);
            }
            
            // Execute scroll
            scrollToChatBottom();
        </script>
        """, unsafe_allow_html=True)


def render_analytics_tab(function_handler: FunctionHandler, tool_executor: MCPToolExecutor):
    """Render the analytics and monitoring tab."""
    st.header("📊 Analytics & Monitoring")
    
    # Conversation summary
    conv_summary = function_handler.get_conversation_summary()
    exec_summary = tool_executor.get_execution_summary()
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Conversation Turns", conv_summary["total_turns"])
    with col2:
        st.metric("Tool Executions", exec_summary["total_executions"])
    with col3:
        st.metric("Success Rate", 
                 f"{(exec_summary['successful_executions'] / max(exec_summary['total_executions'], 1) * 100):.1f}%")
    with col4:
        st.metric("Avg Execution Time", 
                 f"{exec_summary['average_execution_time']:.2f}s")
    
    # Tools used
    if exec_summary["tools_used"]:
        st.subheader("Tools Used")
        tools_df = pd.DataFrame({
            "Tool": exec_summary["tools_used"],
            "Server": [exec.server_name for exec in tool_executor.get_recent_executions(100) 
                      if exec.tool_name in exec_summary["tools_used"]][:len(exec_summary["tools_used"])]
        })
        st.dataframe(tools_df, use_container_width=True)
    
    # Recent executions
    recent_executions = tool_executor.get_recent_executions(10)
    if recent_executions:
        st.subheader("Recent Tool Executions")
        
        for exec in recent_executions:
            status_color = "green" if exec.success else "red"
            time_str = f"({exec.execution_time:.2f}s)" if exec.execution_time else ""
            
            with st.expander(f"{'✅' if exec.success else '❌'} {exec.tool_name} on {exec.server_name} {time_str}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Arguments:**")
                    st.json(exec.arguments)
                with col2:
                    if exec.success and exec.result:
                        st.write("**Result:**")
                        if isinstance(exec.result, (dict, list)):
                            st.json(exec.result)
                        else:
                            st.code(str(exec.result))
                    elif exec.error:
                        st.write("**Error:**")
                        st.error(exec.error)
    
    # Export conversation
    if st.button("📥 Export Conversation"):
        conversation_data = function_handler.export_conversation()
        st.download_button(
            label="Download JSON",
            data=json.dumps(conversation_data, indent=2),
            file_name=f"mcp_conversation_{int(time.time())}.json",
            mime="application/json"
        )


def main():
    """Main application function."""
    # App header
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.title(f"{settings.app_icon} {settings.app_title}")
    st.markdown("*Test and interact with MCP servers using OpenAI's GPT models*")
    st.markdown('</div>', unsafe_allow_html=True)
    

    
    # Initialize components
    openai_client, server_manager, tool_executor, function_handler = initialize_components()
    
    if not all([openai_client, server_manager, tool_executor, function_handler]):
        st.error("Failed to initialize application components. Please check your configuration.")
        return
    
    # Test OpenAI connection
    with st.spinner("Testing OpenAI connection..."):
        success, message = async_to_sync(openai_client.test_connection)()
        if success:
            st.success("✅ OpenAI connection successful")
        else:
            st.error(f"❌ OpenAI connection failed: {message}")
            st.stop()
    
    # Auto-initialize and connect MCP servers (only once per session)
    # Use a lock mechanism to prevent concurrent initialization
    if "servers_initialized" not in st.session_state:
        if "initializing_servers" not in st.session_state:
            st.session_state.initializing_servers = True
            
            with st.spinner("Connecting to MCP servers..."):
                try:
                    # Initialize server manager if not done
                    if not server_manager._initialized:
                        init_success = async_to_sync(server_manager.initialize)()
                        if init_success:
                            logger.info("MCP server manager initialized")
                        else:
                            st.warning("⚠️ Failed to initialize MCP server manager")
                    
                    # Auto-connect to all enabled servers with improved startup sequence
                    results = async_to_sync(server_manager.startup_connect_servers)()
                    
                    # Store results in session state
                    st.session_state.servers_initialized = True
                    st.session_state.initial_connection_results = results
                    
                    # Show connection summary
                    success_count = sum(1 for success in results.values() if success)
                    total_count = len(results)
                    
                    if success_count > 0:
                        if success_count == total_count:
                            st.success(f"✅ Connected to all {success_count} MCP servers")
                        else:
                            st.success(f"✅ Connected to {success_count}/{total_count} MCP servers")
                            if success_count < total_count:
                                failed_servers = [name for name, success in results.items() if not success]
                                st.warning(f"⚠️ Failed to connect to: {', '.join(failed_servers)}")
                    else:
                        if total_count > 0:
                            st.warning("⚠️ No MCP servers connected - check server configurations in sidebar")
                        else:
                            st.info("ℹ️ No MCP servers configured")
                            
                finally:
                    # Always clear the initializing flag
                    if "initializing_servers" in st.session_state:
                        del st.session_state.initializing_servers
                        
        else:
            # If already initializing, show a waiting message
            st.info("🔄 Initializing MCP servers, please wait...")
            time.sleep(0.5)
            st.rerun()
    
    # Render server panel in sidebar
    render_server_panel(server_manager)
    
    # Main content tabs
    tab1, tab2 = st.tabs(["💬 Chat", "📊 Analytics"])
    
    with tab1:
        render_chat_interface(function_handler)
    
    with tab2:
        render_analytics_tab(function_handler, tool_executor)
    
    # Footer
    st.markdown("---")
    st.markdown(
        f"**{settings.app_title}** - Built with Streamlit • "
        f"Model: {settings.openai_model} • "
        f"Debug: {settings.debug_mode}"
    )


if __name__ == "__main__":
    main() 