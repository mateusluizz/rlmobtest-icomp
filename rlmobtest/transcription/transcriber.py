#!/usr/bin/env python3
"""
Module for transcribing test cases using LangChain with Ollama.
"""

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from rich.console import Console

from rlmobtest.constants.llm import DEFAULT_LLM_MODEL
from rlmobtest.constants.paths import FEW_SHOT_EXAMPLES_PATH
from rlmobtest.transcription import similarity_filter
from rlmobtest.transcription.prompts import SYSTEM_PROMPT

# Default Ollama model configuration
DEFAULT_MODEL = DEFAULT_LLM_MODEL


def create_llm(model_name: str = DEFAULT_MODEL, temperature: float = 0.5):
    """
    Create LangChain Ollama client.

    Args:
        model_name: Name of the Ollama model to use
        temperature: Sampling temperature (0.0 to 1.0)

    Returns:
        ChatOllama instance
    """
    return ChatOllama(
        model=model_name,
        temperature=temperature,
    )


def read_text_file(file_path):
    """Read and clean text from a file."""
    with open(file_path, encoding="utf-8") as file:
        text = file.read()
        text = text.strip()
        text = "\n".join(line for line in text.splitlines() if line.strip())
        return text


def write_text_file(file_path, text):
    """Write text to a file."""
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)


def build_few_shot_messages(input_text: str, app_context: str | None = None) -> list:
    """
    Build messages with few-shot examples for the LLM.

    Args:
        input_text: The test case text to transcribe
        app_context: Optional app context string (screens, components, labels)

    Returns:
        List of HumanMessage and AIMessage for few-shot learning
    """
    scripts_path = FEW_SHOT_EXAMPLES_PATH / "scripts"
    transcriptions_path = FEW_SHOT_EXAMPLES_PATH / "transcriptions"

    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # Pairs of (script_filename, transcription_filename)
    example_pairs = [
        (
            "TC_.ImportExportActivity_20210401-002546.txt",
            "CleanTC_.ImportExportActivity_20210401-002546.txt",
        ),
    ]

    for script_file, transcription_file in example_pairs:
        script_path = scripts_path / script_file
        transcription_path = transcriptions_path / transcription_file

        if script_path.exists() and transcription_path.exists():
            messages.append(HumanMessage(content=read_text_file(script_path)))
            messages.append(AIMessage(content=read_text_file(transcription_path)))

    # Current input — enrich with app context when available
    if app_context:
        augmented_input = (
            f"{input_text}\n\n"
            f"## Application Reference Information\n"
            f"Use the following to write descriptive, user-friendly test steps. "
            f"Replace technical IDs with the labels below:\n\n"
            f"{app_context}"
        )
        messages.append(HumanMessage(content=augmented_input))
    else:
        messages.append(HumanMessage(content=input_text))

    return messages


def the_world_is_our(
    input_folder: str | Path,
    output_folder: str | Path,
    model_name: str = DEFAULT_MODEL,
    app_context: str | None = None,
):
    """
    Transcribe test cases from input folder to output folder using Ollama.

    Args:
        input_folder: Path to folder containing raw test cases
        output_folder: Path to folder for transcribed test cases
        model_name: Ollama model to use (default: gemma3:4b)
        app_context: Optional app context string (screens, components, labels)
    """
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    console = Console()
    console.print(f"[bold green][LangChain][/] Model: [bold]{model_name}[/]")
    llm = create_llm(model_name)

    print(len(list(input_folder.iterdir())))

    # Identify and discard similar documents
    _, documents_to_discard = similarity_filter.compare_documents_in_folder(input_folder)

    # List the remaining documents after discarding similar ones
    list_docs = similarity_filter.list_arquivos(input_folder, documents_to_discard)
    print(len(list_docs))

    output_folder.mkdir(parents=True, exist_ok=True)
    print("=======The program is running=======")

    for i, doc_path in enumerate(list_docs):
        try:
            tc_name = Path(doc_path).name
            input_text = read_text_file(doc_path)

            # Build messages with few-shot examples
            messages = build_few_shot_messages(input_text, app_context=app_context)

            # Invoke Ollama
            response = llm.invoke(messages)
            output_text = response.content.strip()

            output_file_path = output_folder / tc_name
            write_text_file(output_file_path, output_text)
            print(f"[{i + 1}/{len(list_docs)}] Saved: {output_file_path}")

        except Exception as e:
            print(f"Error processing {doc_path}: {e}")
            continue

    print("=======The program is finished========")
