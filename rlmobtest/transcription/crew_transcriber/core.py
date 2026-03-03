"""Core CrewAI transcription logic: LLM, agents, tasks, and transcription functions."""

import logging
import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM

from rlmobtest.constants.llm import DEFAULT_CREWAI_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.constants.paths import FEW_SHOT_EXAMPLES_PATH
from rlmobtest.transcription import similarity_filter
from rlmobtest.transcription.prompts import SYSTEM_PROMPT

# Default LLM configuration
OLLAMA_MODEL = DEFAULT_CREWAI_MODEL
OLLAMA_BASE_URL = DEFAULT_OLLAMA_BASE_URL


def create_llm(
    model_name: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    temperature: float = 0.5,
) -> LLM:
    """
    Create LLM instance for CrewAI.

    Args:
        model_name: Name of the model (format: provider/model)
        base_url: Base URL for the LLM API
        temperature: Sampling temperature (0.0 to 1.0)

    Returns:
        LLM instance configured for CrewAI
    """
    return LLM(
        model=model_name,
        base_url=base_url,
        temperature=temperature,
    )


def read_text_file(file_path: str | Path) -> str:
    """Read and clean text from a file."""
    with open(file_path, encoding="utf-8") as file:
        text = file.read()
        text = text.strip()
        text = "\n".join(line for line in text.splitlines() if line.strip())
        return text


def write_text_file(file_path: str | Path, text: str) -> None:
    """Write text to a file."""
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)


def load_few_shot_examples() -> str:
    """
    Load few-shot examples for the agent's context.

    Returns:
        Formatted string with input/output examples
    """
    scripts_path = FEW_SHOT_EXAMPLES_PATH / "scripts"
    transcriptions_path = FEW_SHOT_EXAMPLES_PATH / "transcriptions"

    examples = []

    # Pairs of (script_filename, transcription_filename)
    example_pairs = [
        (
            "TC_.ImportExportActivity_20210401-002546.txt",
            "CleanTC_.ImportExportActivity_20210401-002546.txt",
        ),
    ]

    for i, (script_file, transcription_file) in enumerate(example_pairs, 1):
        script_path = scripts_path / script_file
        transcription_path = transcriptions_path / transcription_file

        if not script_path.exists() or not transcription_path.exists():
            logging.warning("Few-shot example files not found: %s", script_file)
            continue

        script_content = read_text_file(script_path)
        transcription_content = read_text_file(transcription_path)

        examples.append(
            f"### Example {i}\n"
            f"**Input:**\n```\n{script_content}\n```\n\n"
            f"**Output:**\n```\n{transcription_content}\n```"
        )

    if not examples:
        return "No few-shot examples available."

    return "\n\n".join(examples)


def create_test_case_agent(llm: LLM, app_context: str | None = None) -> Agent:
    """
    Create the test case generation agent.

    Args:
        llm: LLM instance to use
        app_context: Optional app context string (screens, components, labels)

    Returns:
        Configured Agent for test case creation
    """
    few_shot_examples = load_few_shot_examples()

    context_parts = [
        "Here are examples of the expected input/output transformation.\n"
        "Follow this output format and quality level:\n\n"
        f"{few_shot_examples}",
    ]

    if app_context:
        context_parts.append(
            "\n\n## Application Reference Information\n"
            "Use the following information to write more descriptive, "
            "user-friendly test steps. Replace technical IDs with the "
            "human-readable labels shown below:\n\n"
            f"{app_context}"
        )

    return Agent(
        role="Mobile Test Case Specialist",
        goal=(
            "Transform raw mobile application interaction logs into clean, "
            "human-readable test cases in English. Never include technical "
            "IDs, screenshot paths, error file references, or widget class names."
        ),
        backstory=SYSTEM_PROMPT,
        llm=llm,
        verbose=True,
        memory=True,
        context="\n".join(context_parts),
    )


def create_transcription_task(
    agent: Agent,
    input_text: str,
    image_path: str | None = None,
    app_context: str | None = None,
) -> Task:
    """
    Create a task for transcribing a test case.

    Args:
        agent: The agent to perform the task
        input_text: Raw test case text to transcribe
        image_path: Optional path to screenshot image
        app_context: Optional app context string (screens, components, labels)

    Returns:
        Configured Task for transcription
    """
    description = f"""
Analyze the following mobile application interaction log and convert it into
a clean, structured test case in English following ISO/IEC/IEEE 29119-3.

**Raw Interaction Log:**
```
{input_text}
```
"""

    if app_context:
        description += f"""
**Application Context (use for reference only, do not copy verbatim):**
{app_context}
"""

    description += """
Your task:
1. Identify the sequence of user actions from the raw log
2. Describe each action in plain language (e.g., "Tap the Save button")
3. Do NOT include Android resource IDs, widget class names, coordinate bounds,
   screenshot paths, or references to errors.txt / crash.txt
4. If an error occurred, describe it as an expected application behavior
5. Maintain the logical flow of the test scenario
6. Use the exact ISO/IEC/IEEE 29119-3 format shown in the examples provided in your context
"""

    # image_path is accepted for API compatibility but not injected into the
    # prompt to avoid screenshot path leakage in output.

    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "A test case following ISO/IEC/IEEE 29119-3 format with these sections: "
            "Test Case ID, Test Case Title, Description, Priority, Preconditions, "
            "Test Steps (as a table with Step/Action/Test Data/Expected Result columns), "
            "and Postconditions. "
            "The output must NOT contain resource IDs, widget types, screenshot paths, "
            "or error file references."
        ),
    )


def create_crew(agent: Agent, task: Task) -> Crew:
    """
    Create a crew with the given agent and task.

    Args:
        agent: The test case agent
        task: The transcription task

    Returns:
        Configured Crew
    """
    return Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=True,
    )


def transcribe_single(
    input_text: str,
    llm: LLM,
    image_path: str | None = None,
    app_context: str | None = None,
) -> str:
    """
    Transcribe a single test case.

    Args:
        input_text: Raw test case text
        llm: LLM instance to use
        image_path: Optional screenshot path
        app_context: Optional app context string (screens, components, labels)

    Returns:
        Transcribed test case text
    """
    agent = create_test_case_agent(llm, app_context=app_context)
    task = create_transcription_task(agent, input_text, image_path, app_context=app_context)
    crew = create_crew(agent, task)

    result = crew.kickoff()
    return str(result).strip()


def transcribe_folder(
    input_folder: str | Path,
    output_folder: str | Path,
    model_name: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    screenshots_folder: str | Path | None = None,
    app_context: str | None = None,
) -> None:
    """
    Transcribe test cases from input folder to output folder using CrewAI.

    Args:
        input_folder: Path to folder containing raw test cases
        output_folder: Path to folder for transcribed test cases
        model_name: Model to use (format: provider/model)
        base_url: Base URL for the LLM API
        screenshots_folder: Optional folder containing screenshots
        app_context: Optional app context string (screens, components, labels)
    """
    input_folder = Path(input_folder)
    output_folder = Path(output_folder)

    logging.info("Using model: %s", model_name)
    llm = create_llm(model_name, base_url)

    logging.info("Total files in input folder: %d", len(os.listdir(input_folder)))

    # Identify and discard similar documents
    _, documents_to_discard = similarity_filter.compare_documents_in_folder(input_folder)

    # List remaining documents after filtering
    list_docs = similarity_filter.list_arquivos(input_folder, documents_to_discard)
    logging.info("Files to process after similarity filter: %d", len(list_docs))

    os.makedirs(output_folder, exist_ok=True)
    print("=" * 50)
    print("Starting CrewAI transcription pipeline")
    print("=" * 50)

    for i, doc_path in enumerate(list_docs):
        try:
            tc_name = os.path.basename(doc_path)
            input_text = read_text_file(doc_path)

            # Check for corresponding screenshot
            image_path = None
            if screenshots_folder:
                screenshots_folder = Path(screenshots_folder)
                possible_image = screenshots_folder / tc_name.replace(".txt", ".png")
                if possible_image.exists():
                    image_path = str(possible_image)

            # Transcribe using CrewAI agent
            output_text = transcribe_single(input_text, llm, image_path, app_context=app_context)

            output_file_path = output_folder / tc_name
            write_text_file(output_file_path, output_text)
            print(f"[{i + 1}/{len(list_docs)}] Saved: {output_file_path}")

        except Exception as e:
            print(f"Error processing {doc_path}: {e}")
            continue

    print("=" * 50)
    print("CrewAI transcription pipeline completed")
    print("=" * 50)
