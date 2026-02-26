"""Discovery utilities for finding available test case days in output structure."""

from pathlib import Path


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
