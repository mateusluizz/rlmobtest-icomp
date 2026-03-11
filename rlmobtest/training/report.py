"""Pipeline report generation — HTML with coverage percentages."""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd
from rich.console import Console

from rlmobtest.constants.actions import ACTION_TYPE_ALIASES, INVALID_ID_RE

console = Console()

# Maps test-case line prefixes → requirements CSV action_type
_ACTION_MAP = {
    "clicked": "click",
    "long click": "long_click",
    "checked": "click",
    "scroll": "scroll",
    "rotate": "rotate",
    "home": "home",
    "go to": "go_to",
    "type": "type",
    "typed": "type",
    "entered": "type",
    "input": "type",
}

_ACTION_RE = re.compile(
    r"^(Clicked|Long click\b|Checked|Scroll\s+\w+"
    r"|Rotate\s+\w+|Home activity|Go to next activity"
    r"|Type\b|typed\s+in\b|Entered\b|Input\b)",
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
        activity_full = str(row["activity"]).strip()
        activity_short = _ACTIVITY_SEP_RE.split(activity_full)[-1]
        raw_action = str(row["action_type"]).strip().lower()
        action_type = ACTION_TYPE_ALIASES.get(raw_action, raw_action)
        rid = str(row["id"]).strip()

        actions_set = tc_actions.get(activity_short, set())
        if not actions_set:
            continue

        # Treat invalid IDs as N/A (match by action_type only)
        rid_is_invalid = (
            not rid or rid == "N/A" or rid == "nan"
            or INVALID_ID_RE.search(rid)
        )

        if rid_is_invalid:
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


def _collect_jacoco_coverage(
    run_paths: list[Path],
    package_name: str,
    source_code: str | None = None,
) -> dict:
    """Try to process JaCoCo .ec files and return coverage metrics."""
    from rlmobtest.utils.jacoco import process_coverage

    for rp in run_paths:
        cov_dir = rp / "coverage"
        if cov_dir.exists() and any(cov_dir.glob("*.ec")):
            metrics = process_coverage(
                cov_dir, package_name,
                html_report=True,
                source_code=source_code,
            )
            if metrics:
                jacoco_html = cov_dir / "jacoco_html" / "index.html"
                return {
                    "jacoco_line_coverage_pct": metrics["line_pct"],
                    "jacoco_branch_coverage_pct": metrics["branch_pct"],
                    "jacoco_method_coverage_pct": metrics["method_pct"],
                    "jacoco_html_path": str(jacoco_html) if jacoco_html.exists() else None,
                }
    return {
        "jacoco_line_coverage_pct": None,
        "jacoco_branch_coverage_pct": None,
        "jacoco_method_coverage_pct": None,
        "jacoco_html_path": None,
    }


def _collect_data(
    run_paths: list[Path],
    package_name: str,
    agent_type: str,
    source_code: str | None = None,
) -> dict:
    """Aggregate metrics from all run_paths into a report dict."""
    total_episodes = 0
    total_steps = 0
    total_training_seconds = 0.0
    all_rewards = []
    all_activity_counts = []
    all_episode_durations = []
    all_losses = []
    all_q_values = []
    all_epsilon_values = []
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
            all_losses.extend(data.get("episode_losses", []))
            all_q_values.extend(data.get("episode_q_values", []))
            all_epsilon_values.extend(data.get("epsilon_values", []))

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
        min(len(discovered_activities) / len(required_activities) * 100, 100.0)
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
        # Raw time-series data for interactive charts
        "episode_rewards": [round(r, 2) for r in all_rewards],
        "episode_losses": [round(l, 4) for l in all_losses],
        "episode_q_values": [round(q, 4) for q in all_q_values],
        "episode_durations": [round(d, 1) for d in all_episode_durations],
        "episode_activity_counts": all_activity_counts,
        "epsilon_values": all_epsilon_values,
        **_collect_jacoco_coverage(run_paths, package_name, source_code=source_code),
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


def _moving_avg(values: list, window: int = 10) -> list:
    """Compute a moving average, returning values aligned to the end."""
    if len(values) < window:
        return []
    kernel = [1.0 / window] * window
    result = []
    for i in range(len(values) - window + 1):
        result.append(round(sum(values[i:i + window]) / window, 2))
    return result


def _render_html(data: dict) -> str:
    """Render the report data as a self-contained HTML page with interactive charts."""
    # Prepare chart data
    rewards = data.get("episode_rewards", [])
    losses = data.get("episode_losses", [])
    q_values = data.get("episode_q_values", [])
    durations = data.get("episode_durations", [])
    activity_counts = data.get("episode_activity_counts", [])
    epsilon_vals = data.get("epsilon_values", [])

    rewards_ma = _moving_avg(rewards, 10)
    q_values_ma = _moving_avg(q_values, 10)

    cumulative_rewards = []
    s = 0
    for r in rewards:
        s += r
        cumulative_rewards.append(round(s, 2))

    cumulative_activities = []
    s = 0
    for a in activity_counts:
        s += a
        cumulative_activities.append(s)

    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    # Downsample epsilon if too many points (keep max 500 for performance)
    eps_downsampled = epsilon_vals
    eps_steps = list(range(1, len(epsilon_vals) + 1))
    if len(epsilon_vals) > 500:
        step_size = len(epsilon_vals) // 500
        eps_downsampled = epsilon_vals[::step_size]
        eps_steps = list(range(1, len(epsilon_vals) + 1, step_size))

    has_charts = len(rewards) >= 2

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RLMobTest Report — {data['package_name']}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 2rem; }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
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
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
  .chart-wrapper {{ position: relative; background: #0d1117; border-radius: 6px; padding: 0.5rem; min-height: 300px; }}
  .chart-wrapper.chart-wide {{ grid-column: 1 / -1; }}
  .chart-help {{ position: absolute; top: 8px; right: 8px; z-index: 10; width: 22px; height: 22px; border-radius: 50%; background: #30363d; color: #8b949e; font-size: 13px; font-weight: 700; text-align: center; line-height: 22px; cursor: help; transition: background 0.2s, color 0.2s; }}
  .chart-help:hover {{ background: #58a6ff; color: #0d1117; }}
  .chart-tooltip {{ display: none; position: absolute; top: 34px; right: 4px; z-index: 20; width: 300px; background: #1c2128; border: 1px solid #444c56; border-radius: 8px; padding: 0.75rem; font-size: 0.8rem; color: #adbac7; line-height: 1.45; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
  .chart-help:hover + .chart-tooltip {{ display: block; }}
  .chart-tooltip strong {{ color: #c9d1d9; }}
  .chart-tooltip ul {{ margin: 0.4rem 0 0 0; padding-left: 1.1rem; }}
  .chart-tooltip li {{ margin-bottom: 0.25rem; }}
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
    {'<div style="margin-top: 0.5rem;"><a href="coverage/jacoco_html/index.html" style="color: #58a6ff; text-decoration: none;">View detailed JaCoCo report (per-class/method) &rarr;</a></div>' if data.get('jacoco_html_path') else ''}
  </div>

  <!-- Interactive Training Charts -->
  {'<div class="card"><h2>Training Metrics</h2><div class="charts-grid">' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Episode Rewards</strong><br>Total reward the agent accumulated per episode.<ul><li><strong>Rising trend</strong> — agent is learning better navigation</li><li><strong>Stable values</strong> — policy has converged</li><li><strong>Sharp drops</strong> — agent hit crashes, loops, or exited the app</li></ul></div><div id="chart-rewards"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Training Loss</strong><br>DQN neural network prediction error.<ul><li><strong>Gradual decrease</strong> — Q-value estimates are improving and the network is converging</li><li><strong>High/unstable values</strong> — possible hyperparameter issues (learning rate, batch size)</li></ul></div><div id="chart-loss"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Q-Values</strong><br>Average estimated value of available actions. Represents agent confidence in action quality.<ul><li><strong>Gradual growth</strong> — agent is learning to estimate action values better</li><li><strong>Very high values</strong> — possible overestimation bias (common in vanilla DQN)</li></ul></div><div id="chart-qvalues"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Episode Duration</strong><br>How long each episode lasted in seconds.<ul><li><strong>Bars near the limit (300s)</strong> — agent used the full time budget, exploring broadly</li><li><strong>Short bars</strong> — episode ended early due to app crash or navigation to home screen</li></ul></div><div id="chart-duration"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Cumulative Reward</strong><br>Running sum of all rewards across episodes.<ul><li><strong>Linear growth</strong> — consistent reward per episode</li><li><strong>Accelerating curve</strong> — agent is progressively improving</li><li><strong>Plateau</strong> — agent stopped gaining significant rewards (saturation)</li></ul></div><div id="chart-cumulative"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Epsilon Decay</strong><br>Controls exploration vs exploitation balance.<ul><li><strong>High epsilon (~0.9)</strong> — mostly random actions (exploration)</li><li><strong>Low epsilon (~0.05)</strong> — mostly learned policy (exploitation)</li><li>Exponential decay transitions the agent from exploring to exploiting</li></ul></div><div id="chart-epsilon"></div></div>' if has_charts else ''}

  {'<div class="chart-wrapper chart-wide"><span class="chart-help">?</span><div class="chart-tooltip"><strong>Activity Coverage</strong><br>Android activities (screens) discovered during training.<ul><li><strong>Green bars</strong> — unique activities found per episode</li><li><strong>Red line</strong> — cumulative total of distinct activities</li><li><strong>Rising line</strong> — new screens still being discovered</li><li><strong>Flat line</strong> — agent has explored most reachable screens</li></ul></div><div id="chart-activities"></div></div>' if has_charts else ''}

  {'</div></div>' if has_charts else ''}

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

{'<script>' + _render_charts_js(
    rewards, rewards_ma, losses, q_values, q_values_ma,
    durations, avg_duration, cumulative_rewards,
    eps_steps, eps_downsampled,
    activity_counts, cumulative_activities,
) + '</script>' if has_charts else ''}
</body>
</html>"""


def _render_charts_js(
    rewards, rewards_ma, losses, q_values, q_values_ma,
    durations, avg_duration, cumulative_rewards,
    eps_steps, eps_downsampled,
    activity_counts, cumulative_activities,
) -> str:
    """Generate Plotly.js chart initialization code."""
    dark_layout = """{
      paper_bgcolor: '#0d1117',
      plot_bgcolor: '#0d1117',
      font: { color: '#c9d1d9', size: 12 },
      margin: { t: 40, r: 20, b: 60, l: 50 },
      xaxis: { gridcolor: '#21262d', zerolinecolor: '#30363d' },
      yaxis: { gridcolor: '#21262d', zerolinecolor: '#30363d' },
      legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.18, bgcolor: 'rgba(0,0,0,0)', font: { size: 10 } },
      hovermode: 'x unified'
    }"""

    episodes = list(range(1, len(rewards) + 1))
    loss_episodes = list(range(1, len(losses) + 1))
    q_episodes = list(range(1, len(q_values) + 1))
    ma_episodes = list(range(10, len(rewards) + 1)) if len(rewards_ma) > 0 else []
    q_ma_episodes = list(range(10, len(q_values) + 1)) if len(q_values_ma) > 0 else []

    return f"""
    var darkLayout = {dark_layout};

    // 1. Episode Rewards
    Plotly.newPlot('chart-rewards', [
      {{ x: {episodes}, y: {rewards}, type: 'scatter', mode: 'lines',
         name: 'Reward', line: {{ color: '#58a6ff', width: 1 }}, opacity: 0.5 }},
      {{ x: {ma_episodes}, y: {rewards_ma}, type: 'scatter', mode: 'lines',
         name: 'Moving Avg (10)', line: {{ color: '#f85149', width: 2 }} }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Episode Rewards</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Reward' }}
    }}), {{ responsive: true }});

    // 2. Training Loss
    Plotly.newPlot('chart-loss', [
      {{ x: {loss_episodes}, y: {losses}, type: 'scatter', mode: 'lines',
         name: 'Loss', line: {{ color: '#3fb950', width: 1.5 }} }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Training Loss</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Loss' }}
    }}), {{ responsive: true }});

    // 3. Q-Values
    Plotly.newPlot('chart-qvalues', [
      {{ x: {q_episodes}, y: {q_values}, type: 'scatter', mode: 'lines',
         name: 'Q-Value', line: {{ color: '#79c0ff', width: 1 }}, opacity: 0.5 }},
      {{ x: {q_ma_episodes}, y: {q_values_ma}, type: 'scatter', mode: 'lines',
         name: 'Moving Avg (10)', line: {{ color: '#56d4dd', width: 2 }} }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Q-Values</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Mean Q-Value' }}
    }}), {{ responsive: true }});

    // 4. Episode Duration
    Plotly.newPlot('chart-duration', [
      {{ x: {episodes}, y: {durations}, type: 'bar',
         name: 'Duration', marker: {{ color: '#d29922', opacity: 0.7 }} }},
      {{ x: {episodes}, y: {[avg_duration] * len(episodes)}, type: 'scatter', mode: 'lines',
         name: 'Mean: {avg_duration}s', line: {{ color: '#f85149', dash: 'dash', width: 2 }} }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Episode Duration</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Duration (s)' }},
      bargap: 0.15
    }}), {{ responsive: true }});

    // 5. Cumulative Reward
    Plotly.newPlot('chart-cumulative', [
      {{ x: {episodes}, y: {cumulative_rewards}, type: 'scatter', mode: 'lines',
         name: 'Cumulative', line: {{ color: '#a371f7', width: 2 }},
         fill: 'tozeroy', fillcolor: 'rgba(163,113,247,0.15)' }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Cumulative Reward</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Cumulative Reward' }}
    }}), {{ responsive: true }});

    // 6. Epsilon Decay
    Plotly.newPlot('chart-epsilon', [
      {{ x: {eps_steps}, y: {eps_downsampled}, type: 'scatter', mode: 'lines',
         name: 'Epsilon', line: {{ color: '#db61a2', width: 1.5 }} }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Epsilon Decay (Exploration Rate)</b>', font: {{ size: 15 }} }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Step' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Epsilon', range: [-0.05, 1.05] }}
    }}), {{ responsive: true }});

    // 7. Activity Coverage (dual axis)
    Plotly.newPlot('chart-activities', [
      {{ x: {episodes}, y: {activity_counts}, type: 'bar',
         name: 'Activities per Episode', marker: {{ color: '#3fb950', opacity: 0.7 }},
         yaxis: 'y' }},
      {{ x: {episodes}, y: {cumulative_activities}, type: 'scatter', mode: 'lines+markers',
         name: 'Cumulative Activities', line: {{ color: '#f85149', width: 2 }},
         marker: {{ size: 5 }}, yaxis: 'y2' }}
    ], Object.assign({{}}, darkLayout, {{
      title: {{ text: '<b>Activity Coverage</b>', font: {{ size: 15 }} }},
      margin: {{ t: 40, r: 60, b: 60, l: 50 }},
      xaxis: {{ ...darkLayout.xaxis, title: 'Episode' }},
      yaxis: {{ ...darkLayout.yaxis, title: 'Unique Activities', titlefont: {{ color: '#3fb950' }}, tickfont: {{ color: '#3fb950' }}, side: 'left' }},
      yaxis2: {{ title: 'Cumulative', titlefont: {{ color: '#f85149' }}, tickfont: {{ color: '#f85149' }}, overlaying: 'y', side: 'right', gridcolor: 'rgba(0,0,0,0)' }},
      bargap: 0.15
    }}), {{ responsive: true }});
    """


def generate_report(
    run_paths: list[Path],
    package_name: str,
    agent_type: str = "improved",
    source_code: str | None = None,
) -> dict:
    """
    Generate a consolidated HTML pipeline report for an app.

    Args:
        run_paths: List of day-level run paths for this app
        package_name: App package name
        agent_type: Agent type (original/improved)
        source_code: Source code config value (for JaCoCo HTML report)

    Returns:
        Report data dictionary
    """
    data = _collect_data(run_paths, package_name, agent_type, source_code=source_code)

    # Save HTML report in each day-level run_path
    if run_paths:
        for rp in run_paths:
            html_path = rp / "report.html"
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(_render_html(data), encoding="utf-8")
            console.print(f"[green]Report saved:[/green] {html_path}")

    return data
