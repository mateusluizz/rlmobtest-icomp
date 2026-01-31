"""Transcription module for test case processing using LangChain Ollama and CrewAI."""

from transcription.similarity_filter import compare_documents_in_folder, list_arquivos
from transcription.transcriber import DEFAULT_MODEL, create_llm, the_world_is_our
from transcription.crew_transcriber import (
    create_test_case_agent,
    transcribe_single,
    transcribe_folder,
    MultimodalInput,
)

__all__ = [
    # Original transcriber (LangChain)
    "the_world_is_our",
    "create_llm",
    "DEFAULT_MODEL",
    # Similarity filter
    "compare_documents_in_folder",
    "list_arquivos",
    # CrewAI transcriber
    "create_test_case_agent",
    "transcribe_single",
    "transcribe_folder",
    "MultimodalInput",
]
