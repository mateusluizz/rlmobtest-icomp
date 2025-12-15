from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parent.parent

OUTPUT_PATH = ROOT_PATH / "output"
CONFIG_PATH = ROOT_PATH / "config"
DATA_PATH = ROOT_PATH / "data"
LOGS_PATH = ROOT_PATH / "logs"

TEST_CASES_PATH = OUTPUT_PATH / "test_cases"
TRANSCRIPTIONS_PATH = OUTPUT_PATH / "transcriptions"
SCREENSHOTS_PATH = OUTPUT_PATH / "screenshots"
CRASHES_PATH = OUTPUT_PATH / "crashes"
ERRORS_PATH = OUTPUT_PATH / "errors"
COVERAGE_PATH = OUTPUT_PATH / "coverage"

FEW_SHOT_EXAMPLES_PATH = DATA_PATH / "few_shot_examples"
