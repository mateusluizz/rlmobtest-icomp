"""
Phase 0b: Semantic Crawling + LLM Annotation
Navigates to each Activity discovered in Phase 0a, captures XML hierarchy and
screenshot, sends them to the LLM for semantic annotation, and auto-generates
requirements.csv for use in Phase 1 training.
"""

import csv
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rlmobtest.metrics.phase_observer import PhaseObserver
    from rlmobtest.phases.phase_0a_manifest import ManifestResult

logger = logging.getLogger(__name__)


@dataclass
class ActivitySnapshot:
    """Snapshot of a single Activity captured during crawling."""

    activity_name: str
    xml_content: str
    screenshot_path: Path | None
    llm_annotation: str
    elements_found: list = field(default_factory=list)  # resource-ids
    workflows: list = field(default_factory=list)
    field_types: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CrawlResult:
    """Aggregated result of the semantic crawl phase."""

    snapshots: dict = field(default_factory=dict)  # activity_name -> ActivitySnapshot
    requirements_csv_path: Path | None = None
    xml_dump_dir: Path | None = None
    crawl_duration: float = 0.0
    activities_reached: list = field(default_factory=list)
    activities_failed: list = field(default_factory=list)


def _wake_device(env, package: str, observer: "PhaseObserver") -> None:
    """
    Ensure the device screen is on and the app is in the foreground.
    Prevents dump_hierarchy() from capturing the lock screen instead of the app.
    """
    import subprocess

    try:
        # Turn screen on if off
        env.device.screen_on()
        time.sleep(0.5)

        # Dismiss keyguard (works without PIN/pattern)
        subprocess.run(
            ["adb", "shell", "input", "keyevent", "KEYCODE_MENU"],
            capture_output=True, timeout=5,
        )
        time.sleep(0.3)

        # Swipe up to unlock (handles swipe-to-unlock without PIN)
        env.device.swipe(0.5, 0.8, 0.5, 0.2, duration=0.3)
        time.sleep(0.5)

        # Launch the app to ensure foreground
        subprocess.run(
            ["adb", "shell", "monkey", "-p", package, "1"],
            capture_output=True, timeout=10,
        )
        time.sleep(2.0)

        logger.info("Phase 0b: device woken up and app launched (%s)", package)
        observer.record_event("0b", "device_woken", {"package": package})

    except Exception as e:
        logger.warning("Phase 0b: device wake failed (continuing anyway): %s", e)


def run_semantic_crawl(
    env,
    manifest: "ManifestResult",
    paths,
    observer: "PhaseObserver",
    llm_model: str = "ollama/gemma3:4b",
    llm_base_url: str = "http://localhost:11434",
) -> CrawlResult:
    """
    Navigate to each Activity, capture XML + screenshot, annotate with LLM.
    Auto-generates requirements.csv from LLM annotations.

    Args:
        env: AndroidEnv instance (device must be connected)
        manifest: ManifestResult from Phase 0a
        paths: OutputPaths instance
        observer: PhaseObserver for recording events
        llm_model: LLM model identifier for annotation
        llm_base_url: LLM API base URL

    Returns:
        CrawlResult with snapshots per activity and generated requirements.csv
    """
    start_time = time.time()
    xml_dump_dir = paths.xml_dumps
    xml_dump_dir.mkdir(parents=True, exist_ok=True)

    result = CrawlResult(xml_dump_dir=xml_dump_dir)
    package = manifest.package

    logger.info("Phase 0b: START — package=%s | llm=%s", package, llm_model)

    # Wake the device and dismiss the lock screen before crawling.
    # If the screen is locked, dump_hierarchy() captures the system lock screen
    # (com.android.systemui) instead of the app — resulting in empty requirements.
    _wake_device(env, package, observer)

    # Android 12+ blocks am start for non-exported activities (SecurityException).
    # Only crawl activities that are known-navigable: those with explicit
    # android:exported=true or any <intent-filter> (implicitly exported).
    # Fall back to all activities if the manifest parser couldn't determine
    # export status (e.g. pm dump fallback, zipfile fallback).
    exported = manifest.exported_activities
    crawl_targets = exported or manifest.activities
    total = len(crawl_targets)

    if exported and len(exported) < len(manifest.activities):
        skipped = [a for a in manifest.activities if a not in exported]
        logger.info(
            "Phase 0b: crawling %d/%d activities (skipping %d non-exported: %s)",
            len(crawl_targets),
            len(manifest.activities),
            len(skipped),
            skipped,
        )
        observer.record_event(
            "0b",
            "non_exported_skipped",
            {"skipped": skipped, "crawl_count": len(crawl_targets)},
        )
    else:
        logger.info("Phase 0b: %d activities to crawl: %s", total, crawl_targets)

    for idx, activity_name in enumerate(crawl_targets, 1):
        logger.info("Phase 0b [%d/%d]: Navigating to %s", idx, total, activity_name)
        observer.record_event("0b", "crawl_started", {"activity": activity_name})
        try:
            # Navigate to activity
            reached = _navigate_to_activity(env, package, activity_name)
            if not reached:
                logger.warning("Phase 0b [%d/%d]: FAILED navigation — %s", idx, total, activity_name)
                result.activities_failed.append(activity_name)
                observer.record_event(
                    "0b", "crawl_failed", {"activity": activity_name, "reason": "navigation_failed"}
                )
                continue

            time.sleep(1.5)  # Wait for activity to fully load

            # Capture XML and screenshot
            logger.info("Phase 0b [%d/%d]: Capturing XML + screenshot", idx, total)
            xml_content, screenshot_path = _capture_snapshot(
                env, activity_name, xml_dump_dir, paths.screenshots, package
            )
            logger.info(
                "Phase 0b [%d/%d]: XML captured (%d chars) | screenshot=%s",
                idx, total, len(xml_content), screenshot_path is not None,
            )

            # Annotate with LLM
            logger.info("Phase 0b [%d/%d]: Sending to LLM for annotation", idx, total)
            annotation, elements, workflows, field_types = _annotate_with_llm(
                xml_content, screenshot_path, activity_name, llm_model, llm_base_url, package
            )
            logger.info(
                "Phase 0b [%d/%d]: LLM done — elements=%s | workflows=%d | field_types=%s",
                idx, total, elements, len(workflows), field_types,
            )

            snapshot = ActivitySnapshot(
                activity_name=activity_name,
                xml_content=xml_content,
                screenshot_path=screenshot_path,
                llm_annotation=annotation,
                elements_found=elements,
                workflows=workflows,
                field_types=field_types,
            )
            result.snapshots[activity_name] = snapshot
            result.activities_reached.append(activity_name)

            observer.record_event(
                "0b",
                "crawl_completed",
                {
                    "activity": activity_name,
                    "elements_found": len(elements),
                    "xml_length": len(xml_content),
                    "annotation_words": len(annotation.split()),
                },
            )

        except Exception as e:
            logger.warning("Phase 0b [%d/%d]: ERROR crawling %s: %s", idx, total, activity_name, e)
            result.activities_failed.append(activity_name)
            observer.record_event("0b", "crawl_error", {"activity": activity_name, "error": str(e)})

    # Generate requirements.csv from annotations.
    # Primary location: run output directory (reproducible, per-APK).
    # Mirror copy: config dir, because env.get_requirements() reads from there.
    from rlmobtest.constants.paths import CONFIG_JSON_PATH

    run_csv_path = _generate_requirements_csv(result.snapshots, package, paths.run_path)
    config_dir = CONFIG_JSON_PATH.parent
    _mirror_requirements_csv(run_csv_path, config_dir / "requirements.csv")
    result.requirements_csv_path = run_csv_path
    result.crawl_duration = time.time() - start_time

    observer.record_event("0b", "requirements_csv_generated", {"path": str(run_csv_path)})
    return result


def _navigate_to_activity(env, package: str, activity: str) -> bool:
    """
    Navigate to an Activity using ADB am start.
    Returns True if successfully reached, False otherwise.
    """
    import subprocess

    try:
        # Normalize activity name to the component format accepted by am start:
        #   "protect.budgetwatch/.BudgetActivity"  (dot-relative short form)
        # Input formats handled:
        #   "protect.budgetwatch/.MainActivity"       → already has slash
        #   "protect.budgetwatch.BudgetActivity"      → aapt2 fully-qualified
        #   ".MainActivity"                           → already short form
        if "/" in activity:
            short_name = activity.split("/", 1)[1]
        elif activity.startswith(package + "."):
            # Convert fully-qualified "pkg.ClassName" → ".ClassName"
            short_name = "." + activity[len(package) + 1 :]
        else:
            short_name = activity

        cmd = f"adb shell am start -n {package}/{short_name}"
        result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=10)

        # adb am start exits 0 even for errors; check stdout for real errors
        combined_out = (result.stdout + result.stderr).lower()
        if result.returncode != 0 or "error:" in combined_out:
            logger.debug("am start failed for %s: %s", activity, result.stdout.strip())
            return False

        time.sleep(2.0)  # Extra time for activity to fully load and stabilize

        # Verify we reached the target (or at least the app is in foreground)
        current = env._get_activity()
        return current not in ("home", "outapp", "unknown")

    except Exception as e:
        logger.warning("Navigation failed for %s: %s", activity, e)
        return False


def _capture_snapshot(
    env,
    activity_name: str,
    xml_dump_dir: Path,
    screenshots_dir: Path,
    package: str = "",
) -> tuple[str, Path | None]:
    """
    Capture XML hierarchy and screenshot for the current screen.
    Saves both to disk.
    Returns (xml_content, screenshot_path).
    """
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    # Capture XML
    xml_content = ""
    try:
        xml_content = env.device.dump_hierarchy()

        # Sanity check: if the XML contains no app resource-ids but has the
        # Android lock screen package, the device is not showing the app.
        if package:
            app_prefix = f"{package}:id/"
            lock_screen = "com.android.systemui"
            if xml_content and app_prefix not in xml_content and lock_screen in xml_content:
                logger.warning(
                    "Phase 0b: XML for %s appears to be the lock screen "
                    "— app not in foreground. Requirements may be empty.",
                    activity_name,
                )

        # Save XML to file
        safe_name = activity_name.replace(".", "_").replace("/", "_")
        xml_file = xml_dump_dir / f"{safe_name}.xml"
        xml_file.write_text(xml_content, encoding="utf-8")
    except Exception as e:
        logger.warning("XML capture failed: %s", e)

    # Capture screenshot
    screenshot_path = None
    try:
        import time as time_mod

        timestr = time_mod.strftime("%Y%m%d-%H%M%S")
        safe_name = activity_name.replace(".", "_").replace("/", "_")
        screenshot_path = screenshots_dir / f"crawl_{safe_name}_{timestr}.png"
        env.device.screenshot(str(screenshot_path))
    except Exception as e:
        logger.warning("Screenshot capture failed: %s", e)
        screenshot_path = None

    return xml_content, screenshot_path


# Matches LLM placeholder hallucinations:
#   element_1, element1, resource_id_2, item3, button_4, view5 (generic names + digits)
#   E1, E2, A3, X4 (single letter + digits — common LLM shorthand placeholders)
_PLACEHOLDER_RE = re.compile(
    r"^(element|resource_id|item|button|view)\d*$|"
    r"^(element|resource_id|item|button|view)_\d+$|"
    r"^[A-Za-z]\d+$",
    re.IGNORECASE,
)

# Real Android resource-ids only contain letters, digits, and underscores.
# Any ID with spaces, hyphens, parentheses, or other chars is a hallucination.
_VALID_RESOURCE_ID_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_valid_resource_id(element_id: str) -> bool:
    """Return True if the string looks like a real Android resource-id."""
    return bool(_VALID_RESOURCE_ID_RE.match(element_id))


def _all_placeholders(elements: list[str]) -> bool:
    """Return True if every element looks like a LLM-generated placeholder."""
    return bool(elements) and all(_PLACEHOLDER_RE.match(e) for e in elements)


def _normalize_elements(raw: object) -> list[str]:
    """Convert whatever the LLM returned for 'elements' into a flat list of strings.

    The LLM may return:
      - ["id1", "id2"]                  → correct
      - [{"id": "id1"}, ...]            → list of dicts
      - "id1, id2"                      → comma-separated string
      - {"id1": "clickable", ...}       → dict keyed by id
    """
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(raw, dict):
        return [str(k) for k in raw if k]
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
        elif isinstance(item, dict):
            val = (
                item.get("id")
                or item.get("resource_id")
                or item.get("name")
                or next(iter(item.values()), None)
            )
            if val:
                result.append(str(val))
    return result


def _annotate_with_llm(
    xml_content: str,
    screenshot_path: Path | None,
    activity_name: str,
    llm_model: str,
    llm_base_url: str,
    package: str = "",
) -> tuple[str, list[str], list[str], dict]:
    """
    Send XML and screenshot to LLM for semantic annotation.
    Returns (annotation_text, elements_list, workflows_list, field_types_dict).
    Falls back to XML-based heuristic if LLM fails.
    """
    try:
        from crewai import Agent, Crew, Process

        from rlmobtest.transcription.crew_transcriber import create_annotation_task, create_llm

        llm = create_llm(model_name=llm_model, base_url=llm_base_url)

        agent = Agent(
            role="Mobile UI Analyst",
            goal="Analyze Android UI hierarchies and extract semantic information",
            backstory="Expert in Android UI testing and accessibility analysis",
            llm=llm,
            verbose=False,
        )

        task = create_annotation_task(agent, xml_content, screenshot_path, activity_name)
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        result = crew.kickoff()
        raw_output = str(result)

        # Parse JSON from output and normalize all values to plain Python types
        annotation_data = _parse_llm_json(raw_output)

        elements = _normalize_elements(annotation_data.get("elements", []))
        raw_ft = annotation_data.get("field_types", {})
        field_types = (
            {str(k): str(v) for k, v in raw_ft.items()} if isinstance(raw_ft, dict) else {}
        )

        # Discard any ID that is not a valid Android resource-id
        # (real IDs: only [a-zA-Z0-9_] — no spaces, hyphens, parens, etc.)
        invalid_fmt = [e for e in elements if not _is_valid_resource_id(e)]
        if invalid_fmt:
            logger.warning(
                "Phase 0b: discarding %d invalid-format resource-ids for %s: %s",
                len(invalid_fmt), activity_name, invalid_fmt[:5],
            )
        elements = [e for e in elements if _is_valid_resource_id(e)]

        # Detect LLM placeholder hallucination: if ALL remaining elements look
        # like "element_1", "element1", etc., fall back to heuristic.
        if not elements or _all_placeholders(elements):
            logger.warning("LLM returned placeholder ids for %s, using heuristic.", activity_name)
            return _heuristic_annotation(xml_content, activity_name, package)

        # Cross-validate against the actual XML: discard any ID the LLM invented
        # that does not exist in the captured hierarchy dump.
        xml_ids = _extract_xml_ids(xml_content, package)
        if xml_ids:
            hallucinated = [e for e in elements if e not in xml_ids]
            if hallucinated:
                logger.warning(
                    "Phase 0b: discarding %d hallucinated ids (not in XML) for %s: %s",
                    len(hallucinated), activity_name, hallucinated,
                )
            elements = [e for e in elements if e in xml_ids]
            # Also strip field_types for removed elements
            field_types = {k: v for k, v in field_types.items() if k in xml_ids}
            logger.info(
                "Phase 0b: XML cross-validation done — %d valid ids kept for %s: %s",
                len(elements), activity_name, elements,
            )

        # If all LLM IDs were hallucinated, fall back to heuristic
        if not elements:
            logger.warning(
                "Phase 0b: all LLM ids were hallucinated for %s, using heuristic.", activity_name
            )
            return _heuristic_annotation(xml_content, activity_name, package)

        return (
            str(annotation_data.get("description", raw_output)),
            elements,
            [str(w) for w in annotation_data.get("workflows", []) if w],
            field_types,
        )

    except Exception as e:
        logger.warning("LLM annotation failed for %s: %s. Using heuristic.", activity_name, e)
        return _heuristic_annotation(xml_content, activity_name)


def _extract_xml_ids(xml_content: str, package: str) -> set[str]:
    """
    Return the set of short resource-ids that actually exist in the XML dump.
    Only includes IDs belonging to the app's package (skips system/other packages).
    E.g. "protect.budgetwatch:id/action_settings" → "action_settings".
    """
    import xml.etree.ElementTree as ET

    ids: set[str] = set()
    app_prefix = f"{package}:id/" if package else ""
    try:
        tree = ET.fromstring(xml_content)
        for node in tree.iter("node"):
            rid = node.attrib.get("resource-id", "")
            if not rid:
                continue
            if app_prefix and not rid.startswith(app_prefix):
                continue  # skip system/other-package IDs
            short = rid.split("/")[-1] if "/" in rid else rid
            if short:
                ids.add(short)
    except Exception:
        pass
    return ids


def _parse_llm_json(text: str) -> dict:
    """Extract JSON object from LLM output text.

    Uses brace-depth counting so nested structures (field_types dict, arrays)
    are handled correctly.  Falls back to the empty-elements sentinel only when
    no valid JSON block is found.
    """
    # 1. Try the whole text first (LLM may return pure JSON)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. Find the outermost {...} block by counting brace depth
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # Keep scanning for a later well-formed block
                    start = -1

    return {"description": text[:200], "elements": [], "workflows": [], "field_types": {}}


def _heuristic_annotation(
    xml_content: str,
    activity_name: str,
    package: str = "",
) -> tuple[str, list, list, dict]:
    """
    Fallback when LLM is unavailable: extract elements from XML heuristically.
    Only includes resource-ids that belong to the app's own package to avoid
    polluting requirements with system navigation bar elements.
    """
    import xml.etree.ElementTree as ET

    elements = []
    field_types = {}
    app_prefix = f"{package}:id/" if package else ""

    try:
        tree = ET.fromstring(xml_content)
        seen_ids: set = set()
        for node in tree.iter("node"):
            resource_id = node.attrib.get("resource-id", "")
            cls = node.attrib.get("class", "")
            clickable = node.attrib.get("clickable", "false") == "true"
            long_clickable = node.attrib.get("long-clickable", "false") == "true"
            is_edit = "EditText" in cls
            # Skip resource-ids from other packages (e.g. com.android.systemui:id/back)
            if app_prefix and resource_id and not resource_id.startswith(app_prefix):
                continue
            if (
                resource_id
                and resource_id not in seen_ids
                and (clickable or long_clickable or is_edit)
            ):
                short_id = resource_id.split("/")[-1] if "/" in resource_id else resource_id
                elements.append(short_id)
                seen_ids.add(resource_id)
                if is_edit:
                    field_types[short_id] = "text"
    except Exception as exc:
        logger.warning("Heuristic XML parse failed for %s: %s", activity_name, exc)

    short_name = activity_name.split(".")[-1]
    description = f"Activity {short_name} (heuristic annotation)"
    return description, elements, [], field_types


def _mirror_requirements_csv(src: Path, dst: Path) -> None:
    """Copy requirements.csv to the config dir so env.get_requirements() can find it."""
    import shutil

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        logger.info("requirements.csv mirrored to %s", dst)
    except Exception as e:
        logger.warning("Could not mirror requirements.csv to %s: %s", dst, e)


def _generate_requirements_csv(
    snapshots: dict,
    package: str,
    output_dir: Path,
) -> Path:
    """
    Generate requirements.csv from crawl snapshots.
    Format: activity, field, id, action, type, size_start, size_end, value
    Compatible with env.get_requirements() (android_env.py line 1582).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "requirements.csv"
    rows = []

    for activity_name, snapshot in snapshots.items():
        # Short activity name for matching
        short_activity = activity_name
        if activity_name.startswith(package):
            short_activity = activity_name[len(package) :]

        for element_id in snapshot.elements_found:
            # Guard: skip non-string ids (e.g. if LLM returned dicts)
            if not isinstance(element_id, str) or not element_id:
                continue
            full_id = f"{package}:id/{element_id}" if ":" not in element_id else element_id
            field_type = snapshot.field_types.get(element_id, "")

            if field_type in ("text", "number", "email"):
                rows.append(
                    [
                        activity_name,
                        "edittext",
                        full_id,
                        "type",
                        field_type,
                        "1",
                        "100",
                        "",
                    ]
                )
            elif element_id:
                rows.append(
                    [
                        activity_name,
                        "button",
                        full_id,
                        "click",
                        "",
                        "",
                        "",
                        "",
                    ]
                )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["activity", "field", "id", "action", "type", "size_start", "size_end", "value"]
        )
        writer.writerows(rows)

    logger.info("requirements.csv generated with %d rows at %s", len(rows), csv_path)
    return csv_path
