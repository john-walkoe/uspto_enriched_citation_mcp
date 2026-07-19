"""
Settings and configuration management for USPTO Enriched Citation MCP.
"""

# Import the main settings class from settings.py to avoid duplication
from .settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
