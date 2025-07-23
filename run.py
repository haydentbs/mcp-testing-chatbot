#!/usr/bin/env python3
"""
Simple run script for the MCP Streamlit Chatbot.
"""
import subprocess
import sys
import os
from pathlib import Path

def check_requirements():
    """Check if requirements are installed."""
    try:
        import streamlit
        import openai
        import pydantic
        print("✅ All requirements appear to be installed")
        return True
    except ImportError as e:
        print(f"❌ Missing requirements: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_env_file():
    """Check if .env file exists."""
    if not os.path.exists(".env"):
        print("⚠️  No .env file found. Please copy .env.example to .env and configure your settings.")
        return False
    
    # Check for OpenAI API key
    try:
        from dotenv import load_dotenv
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            print("⚠️  OPENAI_API_KEY not found in .env file. Please add your OpenAI API key.")
            return False
        print("✅ Environment configuration found")
        return True
    except ImportError:
        print("⚠️  python-dotenv not installed. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "python-dotenv"])
        return check_env_file()

def check_existing_streamlit():
    """Check if Streamlit is already running."""
    try:
        result = subprocess.run(["pgrep", "-f", "streamlit"], capture_output=True, text=True)
        if result.returncode == 0:
            print("⚠️  Streamlit is already running!")
            print("🛑 Please stop existing instances first with: pkill -f streamlit")
            return True
        return False
    except:
        return False

def main():
    """Main function to run the application."""
    print("🤖 MCP Streamlit Chatbot")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    if not check_env_file():
        print("\n📝 To get started:")
        print("1. Copy .env.example to .env")
        print("2. Add your OpenAI API key to the .env file")
        print("3. Run this script again")
        sys.exit(1)
    
    # Check for existing Streamlit instances
    if check_existing_streamlit():
        sys.exit(1)
    
    # Start the application
    print("🚀 Starting Streamlit application...")
    print("🌐 Open your browser to http://localhost:8501")
    print("🛑 Press Ctrl+C to stop the application")
    print()
    
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.port", "8501",
            "--server.headless", "true",
            "--server.fileWatcherType", "none",
            "--server.allowRunOnSave", "false"
        ])
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 