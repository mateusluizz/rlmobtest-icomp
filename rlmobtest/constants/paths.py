from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BASE_PATH = PROJECT_DIR / "rlmobtest"

# Output goes to CWD (current working directory)
OUTPUT_PATH = Path.cwd() / "output"

# Config and data stay in package
CONFIG_PATH = BASE_PATH / "config"
DATA_PATH = BASE_PATH / "data"

# Output
LOGS_PATH = OUTPUT_PATH / "logs"
TEST_CASES_PATH = OUTPUT_PATH / "test_cases"
TRANSCRIPTIONS_PATH = OUTPUT_PATH / "transcriptions"
SCREENSHOTS_PATH = OUTPUT_PATH / "screenshots"
CRASHES_PATH = OUTPUT_PATH / "crashes"
ERRORS_PATH = OUTPUT_PATH / "errors"
COVERAGE_PATH = OUTPUT_PATH / "coverage"
CHECKPOINTS_PATH = OUTPUT_PATH / "checkpoints"
METRICS_PATH = OUTPUT_PATH / "metrics"
PLOTS_PATH = OUTPUT_PATH / "plots"

# Config
CONFIG_JSON_PATH = CONFIG_PATH / "settings.json"

FEW_SHOT_EXAMPLES_PATH = DATA_PATH / "few_shot_examples"
