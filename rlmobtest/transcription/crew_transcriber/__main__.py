"""CLI entry point for CrewAI transcriber."""

import argparse
from datetime import datetime

from rlmobtest.constants.llm import DEFAULT_CREWAI_MODEL, DEFAULT_OLLAMA_BASE_URL
from rlmobtest.constants.paths import OUTPUT_BASE
from rlmobtest.transcription.crew_transcriber.core import transcribe_folder
from rlmobtest.transcription.crew_transcriber.discovery import find_all_days


def main():
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
        default=DEFAULT_CREWAI_MODEL,
        help=f"Model to use (default: {DEFAULT_CREWAI_MODEL})",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_OLLAMA_BASE_URL,
        help=f"LLM API base URL (default: {DEFAULT_OLLAMA_BASE_URL})",
    )
    parser.add_argument(
        "--source-code",
        default=None,
        help="Source code archive filename in inputs/source_codes/ (for app context)",
    )
    parser.add_argument(
        "--package",
        default=None,
        help="Package name (required with --source-code for context extraction)",
    )

    args = parser.parse_args()

    # Determine which days to process
    if args.date:
        try:
            dt = datetime.strptime(args.date, "%Y-%m-%d")
            days_to_process = [(dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d"))]
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.")
            exit(1)
    else:
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

        day_path = OUTPUT_BASE / args.app / args.agent / year / month / day
        test_cases_path = day_path / "test_cases"
        apk_transcriptions_path = day_path / "transcriptions"
        screenshots_path = day_path / "screenshots"

        if not test_cases_path.exists():
            print(f"Skipping {year}-{month}-{day}: no test_cases folder")
            continue

        print(f"Input folder: {test_cases_path}")
        print(f"Output folder: {apk_transcriptions_path}")

        # Build app context if source code provided
        app_context = None
        if args.source_code and args.package:
            from rlmobtest.utils.app_context import build_app_context

            app_context = build_app_context(args.source_code, args.package)
            if app_context:
                print(f"App context extracted ({len(app_context)} chars)")

        transcribe_folder(
            input_folder=test_cases_path,
            output_folder=apk_transcriptions_path,
            model_name=args.model,
            base_url=args.base_url,
            screenshots_folder=screenshots_path,
            app_context=app_context,
        )

    print(f"\n{'=' * 50}")
    print("All days processed!")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
