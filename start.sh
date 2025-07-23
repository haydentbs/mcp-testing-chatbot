#!/bin/bash

echo "🤖 MCP Streamlit Chatbot"
echo "========================"

# Kill any existing streamlit processes
echo "🧹 Cleaning up existing processes..."
pkill -f streamlit 2>/dev/null || true

# Wait a moment for cleanup
sleep 1

# Start the application
echo "🚀 Starting application on http://localhost:8501"
echo "🛑 Press Ctrl+C to stop"
echo ""

streamlit run app.py \
  --server.port 8501 \
  --server.headless true \
  --server.fileWatcherType none \
  --server.allowRunOnSave false 