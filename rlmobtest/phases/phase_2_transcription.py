"""
Phase 2: Enriched CrewAI Transcription
Runs the CrewAI transcriber with:
  - screenshots_folder activated (was never passed before)
  - XML content from Phase 0b injected as semantic context
  - LLM annotations from Phase 0b prepended to each test case
This produces test cases with semantic context about each screen.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rlmobtest.metrics.phase_observer import PhaseObserver
    from rlmobtest.phases.phase_0b_crawl import CrawlResult

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of the enriched transcription phase."""

    files_transcribed: int = 0
    files_skipped: int = 0
    output_dir: Path | None = None


def run_enriched_transcription(
    paths,
    crawl_result: "CrawlResult | None",
    observer: "PhaseObserver",
    model_name: str = "ollama/gemma3:4b",
    base_url: str = "http://localhost:11434",
) -> TranscriptionResult:
    """
    Run CrewAI transcription with enriched context (XML + screenshots).

    Activates the screenshots_folder parameter that was already wired in
    crew_transcriber.transcribe_folder() (lines 296-302) but was never passed.

    Args:
        paths: OutputPaths instance
        crawl_result: CrawlResult from Phase 0b (optional)
        observer: PhaseObserver for recording events
        model_name: LLM model identifier
        base_url: LLM API base URL

    Returns:
        TranscriptionResult with count of files processed
    """
    from rlmobtest.transcription.crew_transcriber import transcribe_folder

    test_cases_dir = paths.test_cases
    output_dir = paths.transcriptions

    if not test_cases_dir.exists():
        logger.warning("test_cases directory does not exist: %s", test_cases_dir)
        observer.record_event("2", "no_test_cases", {"path": str(test_cases_dir)})
        return TranscriptionResult(output_dir=output_dir)

    tc_files = list(test_cases_dir.glob("*.md"))
    if not tc_files:
        logger.info("No test case files found in %s", test_cases_dir)
        return TranscriptionResult(output_dir=output_dir)

    observer.record_event(
        "2",
        "transcription_started",
        {
            "files_count": len(tc_files),
            "has_crawl_result": crawl_result is not None,
        },
    )

    # Pre-process test case files to inject semantic context
    if crawl_result is not None:
        _inject_semantic_context(test_cases_dir, crawl_result)

    result = TranscriptionResult(output_dir=output_dir)

    try:
        transcribe_folder(
            input_folder=str(test_cases_dir),
            output_folder=str(output_dir),
            model_name=model_name,
            base_url=base_url,
            screenshots_folder=str(paths.screenshots),  # NOW ACTIVATED
        )
        result.files_transcribed = len(tc_files)

        observer.record_event(
            "2",
            "transcription_completed",
            {
                "files_transcribed": result.files_transcribed,
            },
        )
    except Exception as e:
        logger.error("Transcription failed: %s", e)
        observer.record_event("2", "transcription_failed", {"error": str(e)})

    return result


def _inject_semantic_context(test_cases_dir: Path, crawl_result: "CrawlResult") -> None:
    """
    Prepend LLM annotation and XML summary to each test case file
    so the transcriber has semantic context about each screen.
    Only modifies files that have a matching activity in the crawl result.
    """
    for tc_file in test_cases_dir.glob("*.md"):
        content = tc_file.read_text(encoding="utf-8", errors="replace")

        # Find matching activity snapshot based on filename
        matched_snapshot = None
        for activity_name, snapshot in crawl_result.snapshots.items():
            short = activity_name.split(".")[-1]
            if short in tc_file.name or activity_name in content:
                matched_snapshot = snapshot
                break

        if matched_snapshot is None:
            continue

        # Build context header
        xml_snippet = matched_snapshot.xml_content[:500] if matched_snapshot.xml_content else ""
        context_header = f"""--- SEMANTIC CONTEXT (Phase 0b annotation) ---
Activity: {matched_snapshot.activity_name}
Description: {matched_snapshot.llm_annotation}
Interactive elements: {", ".join(matched_snapshot.elements_found[:10])}
XML snippet: {xml_snippet}
--- END CONTEXT ---

"""
        # Only inject if not already present
        if "SEMANTIC CONTEXT" not in content:
            tc_file.write_text(context_header + content, encoding="utf-8")
