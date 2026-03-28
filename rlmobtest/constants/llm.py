"""Central LLM configuration constants.

Change the values here to switch the model or server used across all modules.
"""

import os

DEFAULT_LLM_MODEL = "gemma3:4b"
"""Ollama model name used by LangChain, generate_requirements, and CLI defaults."""

DEFAULT_CREWAI_MODEL = f"ollama/{DEFAULT_LLM_MODEL}"
"""Model name in CrewAI format (provider/model)."""

DEFAULT_OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
"""Base URL for the Ollama server. Override with OLLAMA_BASE_URL env var (e.g. in Docker)."""
