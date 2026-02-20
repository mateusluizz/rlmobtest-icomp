from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
BASE_PATH = PROJECT_DIR / "rlmobtest"

# Output base goes to CWD (current working directory)
OUTPUT_BASE = Path.cwd() / "output"

# Config and data stay in package
CONFIG_PATH = BASE_PATH / "config"
DATA_PATH = BASE_PATH / "data"

# Config
CONFIG_JSON_PATH = CONFIG_PATH / "settings.json"

FEW_SHOT_EXAMPLES_PATH = DATA_PATH / "few_shot_examples"


class OutputPaths:
    """
    Manages output paths with structure: {apk_name}/{agent_type}/{year}/{month}/{day}/

    Usage:
        paths = OutputPaths("com.example.app", agent_type="improved")
        paths.logs  # output/com.example.app/improved/2026/02/01/logs/
        paths.get_file("logs", "run", "log")  # .../logs/run_020516.log
    """

    def __init__(
        self,
        apk_name: str,
        agent_type: str = "improved",
        base_path: Path = OUTPUT_BASE,
    ):
        self.apk_name = apk_name
        self.agent_type = agent_type
        self.base_path = base_path
        self.now = datetime.now()

        # Build date-based path: {apk}/{agent_type}/{year}/{month}/{day}/
        self.run_path = (
            base_path
            / apk_name
            / agent_type
            / self.now.strftime("%Y")
            / self.now.strftime("%m")
            / self.now.strftime("%d")
        )

        # Define subfolders
        self.logs = self.run_path / "logs"
        self.checkpoints = self.run_path / "checkpoints"
        self.metrics = self.run_path / "metrics"
        self.plots = self.run_path / "plots"
        self.test_cases = self.run_path / "test_cases"
        self.transcriptions = self.run_path / "transcriptions"
        self.screenshots = self.run_path / "screenshots"
        self.crashes = self.run_path / "crashes"
        self.errors = self.run_path / "errors"
        self.coverage = self.run_path / "coverage"
        self.xml_dumps = self.run_path / "xml_dumps"
        self.phase_reports = self.run_path / "phase_reports"

    def create_all(self):
        """Create all output directories."""
        for path in [
            self.logs,
            self.checkpoints,
            self.metrics,
            self.plots,
            self.test_cases,
            self.transcriptions,
            self.screenshots,
            self.crashes,
            self.errors,
            self.coverage,
            self.xml_dumps,
            self.phase_reports,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def get_file(self, folder: str, prefix: str, extension: str) -> Path:
        """
        Generate a timestamped filename.

        Args:
            folder: Subfolder name (logs, checkpoints, etc.)
            prefix: File prefix (run, checkpoint, metrics, etc.)
            extension: File extension without dot (log, pt, json, png)

        Returns:
            Path like: .../logs/run_020516.log
        """
        timestamp = self.now.strftime("%H%M%S")
        folder_path = getattr(self, folder.replace("-", "_"), self.run_path / folder)
        return folder_path / f"{prefix}_{timestamp}.{extension}"


# Legacy paths for backward compatibility (used during module import)
# These will be overwritten when OutputPaths is instantiated in run()
OUTPUT_PATH = OUTPUT_BASE
LOGS_PATH = OUTPUT_BASE / "logs"
TEST_CASES_PATH = OUTPUT_BASE / "test_cases"
TRANSCRIPTIONS_PATH = OUTPUT_BASE / "transcriptions"
SCREENSHOTS_PATH = OUTPUT_BASE / "screenshots"
CRASHES_PATH = OUTPUT_BASE / "crashes"
ERRORS_PATH = OUTPUT_BASE / "errors"
COVERAGE_PATH = OUTPUT_BASE / "coverage"
CHECKPOINTS_PATH = OUTPUT_BASE / "checkpoints"
METRICS_PATH = OUTPUT_BASE / "metrics"
PLOTS_PATH = OUTPUT_BASE / "plots"
