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
</style>
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
    
    # Refresh servers button
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            with st.spinner("Refreshing servers..."):
                results = async_to_sync(server_manager.refresh_servers)()
                
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    st.sidebar.success(f"Connected to {success_count}/{total_count} servers")
                else:
                    st.sidebar.error("Failed to connect to any servers")
    
    with col2:
        if st.button("🆕 Reload Config", use_container_width=True):
            with st.spinner("Reloading configuration..."):
                # Clear the cache and reinitialize
                st.cache_resource.clear()
                st.rerun()
    
    # Initialize servers if not done
    if not server_manager._initialized:
        with st.spinner("Initializing MCP servers..."):
            success = async_to_sync(server_manager.initialize)()
            if success:
                st.sidebar.success("MCP servers initialized")
            else:
                st.sidebar.error("Failed to initialize MCP servers")
    
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
                        with st.expander("📋 Server Configuration"):
                            st.json(error_details['server_config'])
                        
                        # Troubleshooting tips
                        with st.expander("💡 Troubleshooting Tips"):
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
    """Render the main chat interface."""
    st.header("💬 MCP Chat Interface")
    
    # Initialize session state for chat
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "conversation_turns" not in st.session_state:
        st.session_state.conversation_turns = []
    
    # Chat controls
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.subheader("Ask me anything!")
    with col2:
        if st.button("🧹 Clear Chat"):
            st.session_state.messages = []
            st.session_state.conversation_turns = []
            function_handler.clear_conversation()
            st.rerun()
    with col3:
        streaming_enabled = st.checkbox("Streaming", value=True)
    
    # Real-time AI Status Panel
    render_ai_status_panel(function_handler)
    
    # Display conversation
    chat_container = st.container()
    
    with chat_container:
        for i, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                elif message["role"] == "assistant":
                    st.write(message["content"])
                    
                    # Show tool executions if any
                    if i < len(st.session_state.conversation_turns):
                        turn = st.session_state.conversation_turns[i]
                        if turn.tool_executions:
                            with st.expander(f"🛠️ Tool Executions ({len(turn.tool_executions)})"):
                                for exec in turn.tool_executions:
                                    status_icon = "✅" if exec.success else "❌"
                                    time_str = f"({exec.execution_time:.2f}s)" if exec.execution_time else ""
                                    
                                    st.write(f"{status_icon} **{exec.tool_name}** on *{exec.server_name}* {time_str}")
                                    
                                    if exec.arguments:
                                        with st.expander("Arguments"):
                                            st.json(exec.arguments)
                                    
                                    if exec.success and exec.result:
                                        with st.expander("Result"):
                                            if isinstance(exec.result, (dict, list)):
                                                st.json(exec.result)
                                            else:
                                                st.code(str(exec.result))
                                    elif exec.error:
                                        st.error(f"Error: {exec.error}")
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message immediately
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            if streaming_enabled:
                # Streaming response
                message_placeholder = st.empty()
                full_response = ""
                
                with st.spinner("Thinking..."):
                    # Handle the user message
                    turn = async_to_sync(function_handler.handle_user_message)(prompt, stream=False)
                    full_response = turn.assistant_response
                    
                    # Add to session state
                    st.session_state.conversation_turns.append(turn)
                
                # Display the response
                message_placeholder.write(full_response)
                
                # Show tool executions
                if turn.tool_executions:
                    with st.expander(f"🛠️ Tool Executions ({len(turn.tool_executions)})"):
                        for exec in turn.tool_executions:
                            status_icon = "✅" if exec.success else "❌"
                            time_str = f"({exec.execution_time:.2f}s)" if exec.execution_time else ""
                            
                            st.write(f"{status_icon} **{exec.tool_name}** on *{exec.server_name}* {time_str}")
                            
                            if exec.arguments:
                                with st.expander("Arguments"):
                                    st.json(exec.arguments)
                            
                            if exec.success and exec.result:
                                with st.expander("Result"):
                                    if isinstance(exec.result, (dict, list)):
                                        st.json(exec.result)
                                    else:
                                        st.code(str(exec.result))
                            elif exec.error:
                                st.error(f"Error: {exec.error}")
            else:
                # Non-streaming response
                with st.spinner("Thinking..."):
                    turn = async_to_sync(function_handler.handle_user_message)(prompt, stream=False)
                    st.session_state.conversation_turns.append(turn)
                
                st.write(turn.assistant_response)
                
                # Show tool executions
                if turn.tool_executions:
                    with st.expander(f"🛠️ Tool Executions ({len(turn.tool_executions)})"):
                        for exec in turn.tool_executions:
                            status_icon = "✅" if exec.success else "❌"
                            time_str = f"({exec.execution_time:.2f}s)" if exec.execution_time else ""
                            
                            st.write(f"{status_icon} **{exec.tool_name}** on *{exec.server_name}* {time_str}")
                            
                            if exec.arguments:
                                with st.expander("Arguments"):
                                    st.json(exec.arguments)
                            
                            if exec.success and exec.result:
                                with st.expander("Result"):
                                    if isinstance(exec.result, (dict, list)):
                                        st.json(exec.result)
                                    else:
                                        st.code(str(exec.result))
                            elif exec.error:
                                st.error(f"Error: {exec.error}")
        
        # Add assistant response to chat
        st.session_state.messages.append({"role": "assistant", "content": turn.assistant_response})


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