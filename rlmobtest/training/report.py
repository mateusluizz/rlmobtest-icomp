"""Pipeline report generation — HTML with coverage percentages."""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console

console = Console()

# Maps test-case line prefixes → requirements CSV action_type
_ACTION_MAP = {
    "clicked": "click",
    "long click": "click",
    "checked": "click",
    "scroll": "scroll",
    "rotate": "rotate",
    "home": "home",
    "go to": "go_to",
}

_ACTION_RE = re.compile(
    r"^(Clicked|Long click\b|Checked|Scroll\s+\w+|Rotate\s+\w+|Home activity|Go to next activity)",
    re.IGNORECASE,
)

# Separators found in activity names (both "." and "/" are used inconsistently)
_ACTIVITY_SEP_RE = re.compile(r"[./]")


def _find_metrics_files(run_path: Path) -> list[Path]:
    """Find all metrics JSON files in a run_path."""
    metrics_dir = run_path / "metrics"
    if not metrics_dir.exists():
        return []
    return sorted(metrics_dir.glob("metrics_*.json"))


def _load_metrics(path: Path) -> dict:
    """Load a single metrics JSON file."""
    with open(path) as f:
        return json.load(f)


def _load_requirements(run_path: Path) -> pd.DataFrame | None:
    """Load requirements.csv if it exists."""
    csv_path = run_path / "requirements.csv"
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
        # Support legacy files without header row
        if list(df.columns) != ["activity", "field", "id", "action_type", "value"]:
            df = pd.read_csv(
                csv_path,
                header=None,
                names=["activity", "field", "id", "action_type", "value"],
            )
        return df
    except Exception:
        return None


def _parse_tc_actions(tc_path: Path) -> list[tuple[str, str]]:
    """Parse a test-case file and return (action_type, resource_id) pairs.

    action_type values match the CSV: click, scroll, rotate, home, go_to.
    resource_id is the Android resource-id found on the line, or '' if none.
    """
    actions: list[tuple[str, str]] = []
    try:
        text = tc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return actions

    for line in text.splitlines():
        line = line.strip()
        m = _ACTION_RE.match(line)
        if not m:
            continue
        prefix = m.group(1).lower()
        # Map prefix → CSV action_type
        action_type = "click"  # default
        for key, val in _ACTION_MAP.items():
            if prefix.startswith(key):
                action_type = val
                break
        # Extract resource-id (pattern: package:id/name)
        rid_match = re.search(r"[\w.]+:id/\w+", line)
        resource_id = rid_match.group(0) if rid_match else ""
        actions.append((action_type, resource_id))
    return actions


def _compute_requirements_coverage(
    run_paths: list[Path],
    all_requirements: pd.DataFrame | None,
) -> tuple[int, int]:
    """Return (covered_count, total_count) for requirements coverage.

    A requirement is covered when at least one test-case in a matching activity
    contains a line with the same action_type AND resource-id.
    """
    if all_requirements is None or all_requirements.empty:
        return 0, 0

    # Build per-activity action sets from test cases: {class_name: {(action_type, rid)}}
    # Normalize activity names by extracting just the class name (last component).
    # TC filename: TC_.activity.account.AccountsActivity_20260301-... → AccountsActivity
    tc_actions: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for run_path in run_paths:
        tc_dir = run_path / "test_cases"
        if not tc_dir.exists():
            continue
        for f in tc_dir.glob("*.txt"):
            parts = f.stem.split("_")
            if len(parts) >= 2 and parts[1]:
                raw_activity = parts[1].lstrip(".")
                # Extract class name: "activity.account.AccountsActivity" → "AccountsActivity"
                class_name = _ACTIVITY_SEP_RE.split(raw_activity)[-1]
                for pair in _parse_tc_actions(f):
                    tc_actions[class_name].add(pair)

    total = len(all_requirements)
    covered = 0
    for _, row in all_requirements.iterrows():
        # Normalize requirement activity the same way.
        # Handles both "." and "/" separators found in requirements.csv:
        #   "com.blogspot.e_kanivets.moneytracker.activity.account.AccountsActivity" → "AccountsActivity"
        #   "com.blogspot.e_kanivets.moneytracker/activity/account/AccountsActivity" → "AccountsActivity"
        activity_full = str(row["activity"]).strip()
        activity_short = _ACTIVITY_SEP_RE.split(activity_full)[-1]
        action_type = str(row["action_type"]).strip().lower()
        rid = str(row["id"]).strip()

        actions_set = tc_actions.get(activity_short, set())
        if not actions_set:
            continue

        if rid == "N/A" or rid == "nan" or not rid:
            # Match by action_type only
            if any(a == action_type for a, _ in actions_set):
                covered += 1
        else:
            if (action_type, rid) in actions_set:
                covered += 1

    return covered, total


def _count_files(folder: Path, pattern: str = "*.txt") -> int:
    if not folder.exists():
        return 0
    return len(list(folder.glob(pattern)))


def _pct(part: float, total: float) -> str:
    """Format a percentage string."""
    if total <= 0:
        return "N/A"
    return f"{part / total * 100:.1f}%"


def _collect_data(run_paths: list[Path], package_name: str, agent_type: str) -> dict:
    """Aggregate metrics from all run_paths into a report dict."""
    total_episodes = 0
    total_steps = 0
    total_training_seconds = 0.0
    all_rewards = []
    all_activity_counts = []
    all_episode_durations = []
    test_case_count = 0
    transcription_count = 0
    old_transcription_count = 0
    requirements_count = 0
    required_activities: set[str] = set()
    discovered_activities: set[str] = set()
    all_requirements_dfs: list[pd.DataFrame] = []

    for run_path in run_paths:
        for mf in _find_metrics_files(run_path):
            data = _load_metrics(mf)
            summary = data.get("summary", {})
            total_episodes += summary.get("total_episodes", 0)
            total_steps += summary.get("total_steps", 0)
            total_training_seconds += summary.get("training_time_seconds", 0)
            all_rewards.extend(data.get("episode_rewards", []))
            all_activity_counts.extend(data.get("episode_activity_counts", []))
            all_episode_durations.extend(data.get("episode_durations", []))

        req_df = _load_requirements(run_path)
        if req_df is not None:
            requirements_count += len(req_df)
            required_activities.update(
                _ACTIVITY_SEP_RE.split(a.strip())[-1]
                for a in req_df["activity"].unique()
            )
            all_requirements_dfs.append(req_df)

        # Collect activity class names from test_case filenames (TC_.ActivityName_...)
        tc_dir = run_path / "test_cases"
        if tc_dir.exists():
            for f in tc_dir.glob("*.txt"):
                test_case_count += 1
                parts = f.stem.split("_")
                if len(parts) >= 2 and parts[1]:
                    raw = parts[1].lstrip(".")
                    discovered_activities.add(_ACTIVITY_SEP_RE.split(raw)[-1])

        transcription_count += _count_files(run_path / "transcriptions")
        old_transcription_count += _count_files(run_path / "old_transcriptions")

    avg_reward = sum(all_rewards) / len(all_rewards) if all_rewards else 0
    max_reward = max(all_rewards) if all_rewards else 0
    min_reward = min(all_rewards) if all_rewards else 0
    total_activity_discoveries = sum(all_activity_counts)
    avg_episode_duration = (
        sum(all_episode_durations) / len(all_episode_durations)
        if all_episode_durations
        else 0
    )

    hours, remainder = divmod(int(total_training_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)

    # Coverage calculations
    activity_coverage_pct = (
        len(discovered_activities) / len(required_activities) * 100
        if required_activities
        else 0
    )
    transcription_coverage_pct = (
        transcription_count / test_case_count * 100 if test_case_count else 0
    )

    # Requirements coverage: match each CSV row against test-case actions
    merged_reqs = (
        pd.concat(all_requirements_dfs, ignore_index=True).drop_duplicates()
        if all_requirements_dfs
        else None
    )
    req_covered, req_total = _compute_requirements_coverage(
        run_paths, merged_reqs,
    )
    requirements_coverage_pct = (
        req_covered / req_total * 100 if req_total else 0
    )

    return {
        "package_name": package_name,
        "agent_type": agent_type,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_paths_count": len(run_paths),
        "total_episodes": total_episodes,
        "total_steps": total_steps,
        "training_time": f"{hours}h {minutes}m {seconds}s",
        "training_time_seconds": round(total_training_seconds, 1),
        "avg_episode_duration": round(avg_episode_duration, 1),
        "avg_reward": round(avg_reward, 2),
        "max_reward": round(max_reward, 2),
        "min_reward": round(min_reward, 2),
        "total_activity_discoveries": total_activity_discoveries,
        "discovered_activities": len(discovered_activities),
        "required_activities": len(required_activities),
        "activity_coverage_pct": round(activity_coverage_pct, 1),
        "requirements_count": requirements_count,
        "requirements_covered": req_covered,
        "requirements_total": req_total,
        "requirements_coverage_pct": round(requirements_coverage_pct, 1),
        "test_cases_generated": test_case_count,
        "old_transcriptions": old_transcription_count,
        "transcriptions": transcription_count,
        "transcription_coverage_pct": round(transcription_coverage_pct, 1),
        "jacoco_line_coverage_pct": None,
        "jacoco_branch_coverage_pct": None,
        "jacoco_method_coverage_pct": None,
    }


def _progress_bar(pct: float | None, label: str = "") -> str:
    """Generate an HTML progress bar snippet."""
    if pct is None:
        return f"""
        <div class="metric-row">
          <span class="metric-label">{label}</span>
          <span class="metric-value na">N/A</span>
        </div>"""
    color = "#4caf50" if pct >= 70 else "#ff9800" if pct >= 40 else "#f44336"
    return f"""
        <div class="metric-row">
          <span class="metric-label">{label}</span>
          <div class="progress-bar">
            <div class="progress-fill" style="width:{min(pct, 100):.1f}%;background:{color}"></div>
          </div>
          <span class="metric-value">{pct:.1f}%</span>
        </div>"""


def _render_html(data: dict) -> str:
    """Render the report data as a self-contained HTML page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RLMobTest Report — {data['package_name']}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
  .container {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ color: #58a6ff; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #8b949e; margin-bottom: 2rem; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }}
  .card h2 {{ color: #58a6ff; font-size: 1.1rem; margin-bottom: 1rem; border-bottom: 1px solid #21262d; padding-bottom: 0.5rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; }}
  .stat {{ text-align: center; padding: 1rem; background: #0d1117; border-radius: 6px; }}
  .stat .value {{ font-size: 1.8rem; font-weight: 700; color: #f0f6fc; }}
  .stat .label {{ font-size: 0.85rem; color: #8b949e; margin-top: 0.25rem; }}
  .metric-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }}
  .metric-label {{ min-width: 180px; font-size: 0.9rem; color: #8b949e; }}
  .metric-value {{ min-width: 60px; text-align: right; font-weight: 600; font-size: 0.95rem; }}
  .metric-value.na {{ color: #484f58; }}
  .progress-bar {{ flex: 1; height: 12px; background: #21262d; border-radius: 6px; overflow: hidden; }}
  .progress-fill {{ height: 100%; border-radius: 6px; transition: width 0.5s; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ text-align: left; padding: 0.6rem 0.75rem; border-bottom: 1px solid #21262d; font-size: 0.9rem; }}
  th {{ color: #8b949e; font-weight: 500; }}
  td {{ color: #c9d1d9; }}
  .footer {{ text-align: center; margin-top: 2rem; color: #484f58; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="container">
  <h1>RLMobTest Pipeline Report</h1>
  <p class="subtitle">{data['package_name']} &mdash; {data['agent_type']} &mdash; {data['generated_at']}</p>

  <!-- Training Overview -->
  <div class="card">
    <h2>Training Overview</h2>
    <div class="grid">
      <div class="stat">
        <div class="value">{data['total_episodes']}</div>
        <div class="label">Episodes</div>
      </div>
      <div class="stat">
        <div class="value">{data['total_steps']}</div>
        <div class="label">Total Steps</div>
      </div>
      <div class="stat">
        <div class="value">{data['training_time']}</div>
        <div class="label">Training Time</div>
      </div>
      <div class="stat">
        <div class="value">{data['avg_episode_duration']}s</div>
        <div class="label">Avg Episode Duration</div>
      </div>
    </div>
  </div>

  <!-- Rewards -->
  <div class="card">
    <h2>Rewards</h2>
    <div class="grid">
      <div class="stat">
        <div class="value">{data['avg_reward']}</div>
        <div class="label">Avg Reward</div>
      </div>
      <div class="stat">
        <div class="value">{data['max_reward']}</div>
        <div class="label">Max Reward</div>
      </div>
      <div class="stat">
        <div class="value">{data['min_reward']}</div>
        <div class="label">Min Reward</div>
      </div>
    </div>
  </div>

  <!-- Coverage -->
  <div class="card">
    <h2>Coverage</h2>
    {_progress_bar(data['activity_coverage_pct'], f"Activity Coverage ({data['discovered_activities']}/{data['required_activities']} activities)")}
    {_progress_bar(data['requirements_coverage_pct'], f"Requirements Coverage ({data['requirements_covered']}/{data['requirements_total']} requirements)")}
    {_progress_bar(data['transcription_coverage_pct'], f"Transcription Coverage ({data['transcriptions']}/{data['test_cases_generated']} test cases)")}
    {_progress_bar(data['jacoco_line_coverage_pct'], "JaCoCo Line Coverage")}
    {_progress_bar(data['jacoco_branch_coverage_pct'], "JaCoCo Branch Coverage")}
    {_progress_bar(data['jacoco_method_coverage_pct'], "JaCoCo Method Coverage")}
  </div>

  <!-- Artifacts -->
  <div class="card">
    <h2>Artifacts</h2>
    <table>
      <tr><th>Artifact</th><th>Count</th></tr>
      <tr><td>Test Cases Generated</td><td>{data['test_cases_generated']}</td></tr>
      <tr><td>Requirements (CSV rows)</td><td>{data['requirements_count']}</td></tr>
      <tr><td>Required Activities</td><td>{data['required_activities']}</td></tr>
      <tr><td>Transcriptions (LangChain)</td><td>{data['old_transcriptions']}</td></tr>
      <tr><td>Transcriptions (CrewAI)</td><td>{data['transcriptions']}</td></tr>
      <tr><td>Run Paths</td><td>{data['run_paths_count']}</td></tr>
    </table>
  </div>

  <div class="footer">
    Generated by RLMobTest &mdash; {data['generated_at']}
  </div>
</div>
</body>
</html>"""


def generate_report(
    run_paths: list[Path],
    package_name: str,
    agent_type: str = "improved",
) -> dict:
    """
    Generate a consolidated HTML pipeline report for an app.

    Args:
        run_paths: List of day-level run paths for this app
        package_name: App package name
        agent_type: Agent type (original/improved)

    Returns:
        Report data dictionary
    """
    data = _collect_data(run_paths, package_name, agent_type)

    # Save HTML report in each day-level run_path
    if run_paths:
        for rp in run_paths:
            html_path = rp / "report.html"
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(_render_html(data), encoding="utf-8")
            console.print(f"[green]Report saved:[/green] {html_path}")

    return data
