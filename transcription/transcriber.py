#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module for transcribing test cases using LangChain with Ollama.
"""

import os

from langchain_core.messages import AIMessage, HumanMessage
from langchain_ollama import ChatOllama

from constants.paths import FEW_SHOT_EXAMPLES_PATH
from transcription import similarity_filter

# Default Ollama model configuration
DEFAULT_MODEL = "llama3.2"


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
    with open(file_path, "r") as file:
        text = file.read()
        text = text.strip()
        text = "\n".join(line for line in text.splitlines() if line.strip())
        return text


def write_text_file(file_path, text):
    """Write text to a file."""
    with open(file_path, "w") as file:
        file.write(text)


def build_few_shot_messages(input_text: str) -> list:
    """
    Build messages with few-shot examples for the LLM.

    Args:
        input_text: The test case text to transcribe

    Returns:
        List of HumanMessage and AIMessage for few-shot learning
    """
    scripts_path = FEW_SHOT_EXAMPLES_PATH / "scripts"
    transcriptions_path = FEW_SHOT_EXAMPLES_PATH / "transcriptions"

    messages = [
        # Example 1
        HumanMessage(
            content=read_text_file(
                scripts_path
                / "TC_.activity.account.AccountsActivity_20210411-144635.txt"
            )
        ),
        AIMessage(
            content=read_text_file(
                transcriptions_path
                / "TC_.activity.account.AccountsActivity_20210411-144635.txt"
            )
        ),
        # Example 2
        HumanMessage(
            content=read_text_file(
                scripts_path
                / "TC_.activity.account.TransferActivity_20210411-144754.txt"
            )
        ),
        AIMessage(
            content=read_text_file(
                transcriptions_path
                / "TC_.activity.account.TransferActivity_20210411-144754.txt"
            )
        ),
        # Current input
        HumanMessage(content=input_text),
    ]
    return messages


def the_world_is_our(input_folder, output_folder, model_name: str = DEFAULT_MODEL):
    """
    Transcribe test cases from input folder to output folder using Ollama.

    Args:
        input_folder: Path to folder containing raw test cases
        output_folder: Path to folder for transcribed test cases
        model_name: Ollama model to use (default: llama3.2)
    """
    print(f"Using model: {model_name}")
    llm = create_llm(model_name)

    print(len(os.listdir(input_folder)))

    # Identify and discard similar documents
    similar_documents, documents_to_discard = (
        similarity_filter.compare_documents_in_folder(input_folder)
    )

    # List the remaining documents after discarding similar ones
    list_docs = similarity_filter.list_arquivos(input_folder, documents_to_discard)
    print(len(list_docs))

    os.makedirs(output_folder, exist_ok=True)
    print("=======The program is running=======")

    for i, doc_path in enumerate(list_docs):
        try:
            tc_name = os.path.basename(doc_path)
            input_text = read_text_file(doc_path)

            # Build messages with few-shot examples
            messages = build_few_shot_messages(input_text)

            # Invoke Ollama
            response = llm.invoke(messages)
            output_text = response.content.strip()

            output_file_path = os.path.join(output_folder, tc_name)
            write_text_file(output_file_path, output_text)
            print(f"[{i + 1}/{len(list_docs)}] Saved: {output_file_path}")

        except Exception as e:
            print(f"Error processing {doc_path}: {e}")
            continue

    print("=======The program is finished========")
