"""
Bridge module to import TestCase, TestSuite and MetricsCalculator
from sbse_prototype/ which uses bare imports (no package structure).
"""

import sys
from pathlib import Path

_SBSE_PATH = Path(__file__).resolve().parents[2] / "sbse_prototype"
if str(_SBSE_PATH) not in sys.path:
    sys.path.insert(0, str(_SBSE_PATH))

try:
    from metrics_calculator import (
        MetricsCalculator,  # noqa: F401
        ObjectiveMetrics,
    )
    from test_case_representation import TestCase, TestSuite  # noqa: F401

    SBSE_AVAILABLE = True
except ImportError:
    SBSE_AVAILABLE = False
    TestCase = None
    TestSuite = None
    MetricsCalculator = None
    ObjectiveMetrics = None
