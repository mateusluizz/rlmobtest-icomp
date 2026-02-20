#!/usr/bin/env python3
"""
Module for transcribing test cases using CrewAI agents.

This module provides an agent-based approach to generate test cases
from text inputs (with future support for images).
"""

import base64
import logging
import os
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM

from rlmobtest.constants.paths import FEW_SHOT_EXAMPLES_PATH
from rlmobtest.transcription import similarity_filter

# Default LLM configuration
OLLAMA_MODEL = "ollama/gemma3:4b"
OLLAMA_BASE_URL = "http://localhost:11434"


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


def encode_image_to_base64(image_path: str | Path) -> str:
    """
    Encode an image file to base64 string.

    Args:
        image_path: Path to the image file

    Returns:
        Base64 encoded string of the image
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


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
            "Output2TC_.ImportExportActivity_20210401-002546.txt",
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


def create_test_case_agent(llm: LLM) -> Agent:
    """
    Create the test case generation agent.

    Args:
        llm: LLM instance to use

    Returns:
        Configured Agent for test case creation
    """
    few_shot_examples = load_few_shot_examples()

    return Agent(
        role="Mobile Test Case Specialist",
        goal=(
            "Transform raw mobile application interaction logs into clear, "
            "structured test cases that can be understood and executed by QA engineers."
        ),
        backstory=(
            "You are an expert QA engineer specialized in mobile application testing. "
            "You have years of experience analyzing user interaction logs and converting "
            "them into well-structured, reproducible test cases. You understand mobile "
            "UI patterns, gestures, and can identify the intent behind each action. "
            "Your test cases are known for being clear, concise, and actionable."
        ),
        llm=llm,
        verbose=True,
        memory=True,
        context=f"""
You have access to the following examples of how to transform interaction logs
into test cases. Follow this format strictly:

{few_shot_examples}
""",
    )


def create_transcription_task(
    agent: Agent,
    input_text: str,
    image_path: str | None = None,
) -> Task:
    """
    Create a task for transcribing a test case.

    Args:
        agent: The agent to perform the task
        input_text: Raw test case text to transcribe
        image_path: Optional path to screenshot image (for future multimodal support)

    Returns:
        Configured Task for transcription
    """
    description = f"""
Analyze the following mobile application interaction log and convert it into
a clear, structured test case.

**Raw Interaction Log:**
```
{input_text}
```

Your task:
1. Identify the sequence of user actions
2. Understand the purpose of each interaction
3. Convert actions into clear test steps
4. Maintain the logical flow of the test scenario
5. Use consistent terminology for UI elements and actions

IMPORTANT — Element naming rules:
- NEVER include raw resource-ids (e.g. `protect.budgetwatch:id/action_settings`) in the output.
  Instead, derive a human-readable name from the id: "Settings button", "Add button", etc.
- NEVER include Android widget class names (e.g. `android.widget.Button`) in the output.
  Replace with the plain element type: "button", "text field", "spinner", etc.
- NEVER include pixel coordinates or bounds (e.g. `bounds:[28,667][692,751]`) in the output.
- For resource-ids with package prefix (`com.pkg:id/foo`), use only the short part (`foo`)
  and convert underscores/camelCase to natural language (e.g. `action_add` → "Add button",
  `edit_amount` → "Amount field").

Follow the exact format shown in the examples provided in your context.
"""

    if image_path:
        description += f"""

**Note:** A screenshot is available at: {image_path}
Use this visual context to better understand the UI state and elements.
"""

    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "A well-structured test case following the format from the examples. "
            "The output should contain clear steps that describe user actions "
            "and expected system behaviors."
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
) -> str:
    """
    Transcribe a single test case.

    Args:
        input_text: Raw test case text
        llm: LLM instance to use
        image_path: Optional screenshot path

    Returns:
        Transcribed test case text
    """
    agent = create_test_case_agent(llm)
    task = create_transcription_task(agent, input_text, image_path)
    crew = create_crew(agent, task)

    result = crew.kickoff()
    return str(result).strip()


def transcribe_folder(
    input_folder: str | Path,
    output_folder: str | Path,
    model_name: str = OLLAMA_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    screenshots_folder: str | Path | None = None,
) -> None:
    """
    Transcribe test cases from input folder to output folder using CrewAI.

    Args:
        input_folder: Path to folder containing raw test cases
        output_folder: Path to folder for transcribed test cases
        model_name: Model to use (format: provider/model)
        base_url: Base URL for the LLM API
        screenshots_folder: Optional folder containing screenshots for multimodal processing
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

            # Check for corresponding screenshot (future multimodal support)
            image_path = None
            if screenshots_folder:
                screenshots_folder = Path(screenshots_folder)
                stem = Path(tc_name).stem
                possible_image = screenshots_folder / f"{stem}.png"
                if possible_image.exists():
                    image_path = str(possible_image)

            # Transcribe using CrewAI agent
            output_text = transcribe_single(input_text, llm, image_path)

            output_file_path = output_folder / tc_name
            write_text_file(output_file_path, output_text)
            print(f"[{i + 1}/{len(list_docs)}] Saved: {output_file_path}")

        except Exception as e:
            print(f"Error processing {doc_path}: {e}")
            continue

    print("=" * 50)
    print("CrewAI transcription pipeline completed")
    print("=" * 50)


def create_annotation_task(
    agent: "Agent",
    xml_content: str,
    screenshot_path,
    activity_name: str,
) -> "Task":
    """
    Create a CrewAI Task for semantic annotation of an Android activity.
    Used in Phase 0b (Semantic Crawling) to interpret UI hierarchy.

    Args:
        agent: CrewAI Agent with mobile testing expertise
        xml_content: Raw XML from uiautomator2 dump_hierarchy()
        screenshot_path: Path to screenshot PNG (optional)
        activity_name: Full activity class name

    Returns:
        CrewAI Task configured for activity annotation
    """
    xml_snippet = xml_content[:3000] + ("..." if len(xml_content) > 3000 else "")

    description = f"""Analyze the Android activity '{activity_name}'.

**UI Hierarchy (XML):**
```xml
{xml_snippet}
```

Your tasks:
1. Write a 2-3 sentence description of what this screen does functionally
2. List all interactive element resource-ids (clickable, editable, scrollable)
3. Identify the likely user workflows on this screen
4. For EditText fields: identify if they accept text, numbers, emails, etc.

Extract the ACTUAL resource-id values from the XML above (the `resource-id` attribute of each node).
Output ONLY a valid JSON object — no markdown, no explanation, just the JSON:
{{
  "description": "two sentences describing what this screen does",
  "elements": ["action_settings", "btn_add_transaction", "edit_amount"],
  "workflows": ["User taps Add to create a new transaction"],
  "field_types": {{"edit_amount": "number", "edit_note": "text"}}
}}

IMPORTANT: The values in "elements" must be the EXACT resource-id strings found in the XML,
not placeholders like element_1 or resource_id_1."""

    if screenshot_path:
        try:
            img_b64 = encode_image_to_base64(screenshot_path)
            description += f"\n\n**Screenshot (base64):** data:image/png;base64,{img_b64}"
        except Exception:
            pass

    return Task(
        description=description,
        agent=agent,
        expected_output="JSON object with description, elements list, workflows list, and field_types dict",
    )


# Multimodal support utilities (for future implementation)
class MultimodalInput:
    """
    Container for multimodal test case inputs.

    Attributes:
        text: The raw interaction log text
        images: List of image paths or base64 encoded images
        metadata: Additional context metadata
    """

    def __init__(
        self,
        text: str,
        images: list[str | Path] | None = None,
        metadata: dict | None = None,
    ):
        self.text = text
        self.images = images or []
        self.metadata = metadata or {}

    def get_encoded_images(self) -> list[str]:
        """Get base64 encoded versions of all images."""
        encoded = []
        for img in self.images:
            if isinstance(img, (str, Path)) and Path(img).exists():
                encoded.append(encode_image_to_base64(img))
            elif isinstance(img, str):
                # Assume already base64 encoded
                encoded.append(img)
        return encoded


def find_all_days(app: str, agent: str, base_path: Path) -> list[tuple[str, str, str]]:
    """
    Find all available days in the output structure.

    Returns:
        List of (year, month, day) tuples sorted chronologically
    """
    agent_path = base_path / app / agent
    if not agent_path.exists():
        return []

    days = []
    for year_dir in sorted(agent_path.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir() or not day_dir.name.isdigit():
                    continue
                # Check if test_cases folder exists and has files
                tc_path = day_dir / "test_cases"
                if tc_path.exists() and any(tc_path.iterdir()):
                    days.append((year_dir.name, month_dir.name, day_dir.name))

    return days


if __name__ == "__main__":
    import argparse
    from datetime import datetime

    from rlmobtest.constants.paths import OUTPUT_BASE

    parser = argparse.ArgumentParser(description="Transcribe test cases using CrewAI")
    parser.add_argument(
        "--app",
        required=True,
        help="App name (e.g., protect.budgetwatch)",
    )
    parser.add_argument(
        "--agent",
        default="improved",
        choices=["original", "improved"],
        help="Agent type (default: improved)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Specific date to process (YYYY-MM-DD). If omitted, processes all available days.",
    )
    parser.add_argument(
        "--model",
        default="ollama/llama3.2:3b",
        help="Model to use (default: ollama/llama3.2:3b)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="LLM API base URL (default: http://localhost:11434)",
    )

    args = parser.parse_args()

    # Determine which days to process
    if args.date:
        # Parse specific date
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            days_to_process = [(dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))]
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            exit(1)
    else:
        # Find all available days
        days_to_process = find_all_days(args.app, args.agent, OUTPUT_BASE)
        if not days_to_process:
            print(f"No test cases found for {args.app}/{args.agent}")
            exit(1)
        print(f"Found {len(days_to_process)} day(s) with test cases")

    # Process each day
    for year, month, day in days_to_process:
        print(f"\n{'=' * 50}")
        print(f"Processing: {year}-{month}-{day}")
        print(f"{'=' * 50}")

        # Build paths for this specific day
        day_path = OUTPUT_BASE / args.app / args.agent / year / month / day
        test_cases_path = day_path / "test_cases"
        apk_transcriptions_path = day_path / "transcriptions"
        screenshots_path = day_path / "screenshots"

        if not test_cases_path.exists():
            print(f"Skipping {year}-{month}-{day}: no test_cases folder")
            continue

        print(f"Input folder: {test_cases_path}")
        print(f"Output folder: {apk_transcriptions_path}")

        transcribe_folder(
            input_folder=test_cases_path,
            output_folder=apk_transcriptions_path,
            model_name=args.model,
            base_url=args.base_url,
            screenshots_folder=screenshots_path,
        )

    print(f"\n{'=' * 50}")
    print("All days processed!")
    print(f"{'=' * 50}")
