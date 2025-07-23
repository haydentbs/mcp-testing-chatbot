"""
Logging configuration for the MCP Streamlit Chatbot.
"""
import logging
import sys
from typing import Optional
from config.settings import settings


def setup_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Set up logger with appropriate configuration."""
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file or settings.log_file:
        file_handler = logging.FileHandler(log_file or settings.log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# Create global logger instance
logger = setup_logger("mcp_chatbot") 