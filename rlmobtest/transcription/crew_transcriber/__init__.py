"""CrewAI-based test case transcription package."""

from rlmobtest.transcription.crew_transcriber.core import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    create_crew,
    create_llm,
    create_test_case_agent,
    create_transcription_task,
    transcribe_folder,
    transcribe_single,
)
from rlmobtest.transcription.crew_transcriber.discovery import find_all_days
from rlmobtest.transcription.crew_transcriber.multimodal import (
    MultimodalInput,
    encode_image_to_base64,
)

__all__ = [
    "OLLAMA_MODEL",
    "OLLAMA_BASE_URL",
    "create_llm",
    "create_test_case_agent",
    "create_transcription_task",
    "create_crew",
    "transcribe_single",
    "transcribe_folder",
    "find_all_days",
    "MultimodalInput",
    "encode_image_to_base64",
]
