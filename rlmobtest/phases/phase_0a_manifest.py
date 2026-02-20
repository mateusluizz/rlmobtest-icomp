"""
Phase 0a: APK Manifest Parser
Reads AndroidManifest.xml from an APK file to discover all declared Activities
before any training begins. Uses aapt2 (Android SDK tool) with a fallback to
zipfile-based binary parsing.
"""

import logging
import re
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rlmobtest.metrics.phase_observer import PhaseObserver

logger = logging.getLogger(__name__)


@dataclass
class ManifestResult:
    """Result of APK manifest parsing."""

    package: str
    activities: list = field(default_factory=list)  # All declared activity class names
    launcher_activity: str | None = None  # The MAIN/LAUNCHER activity
    exported_activities: list = field(default_factory=list)  # Activities navigable via am start
    raw_output: str = ""  # Raw aapt2 output for debugging
    parse_errors: list = field(default_factory=list)  # Non-fatal warnings


def parse_manifest(
    apk_path: str | Path,
    observer: "PhaseObserver",
    package_name: str | None = None,
) -> ManifestResult:
    """
    Parse AndroidManifest.xml from an APK to discover all declared Activities.

    Strategy (in order):
    1. aapt2 / aapt dump on the APK file
    2. zipfile binary regex on the APK file
    3. ADB device query — works when the APK file is not present on disk

    Args:
        apk_path: Path to the APK file (may not exist on disk)
        observer: PhaseObserver for recording events
        package_name: Package name used for the ADB fallback when APK is missing

    Returns:
        ManifestResult with list of activity class names
    """
    apk_path = Path(apk_path)

    # If the path doesn't point to an APK file, try to find one in common locations
    if not apk_path.exists() or apk_path.suffix != ".apk":
        apk_path = _find_apk(apk_path)

    if apk_path is None or not apk_path.exists():
        if package_name:
            # Try pulling the APK from the connected device first (gives full manifest)
            observer.record_event(
                "0a", "apk_not_found_pulling_from_device", {"package": package_name}
            )
            pulled_apk = _pull_apk_from_device(package_name)
            if pulled_apk is not None:
                logger.info("Pulled APK from device: %s", pulled_apk)
                observer.record_event("0a", "apk_pulled_from_device", {"path": str(pulled_apk)})
                apk_path = pulled_apk
            else:
                # Last resort: query pm dump on the device (only running activities)
                observer.record_event(
                    "0a", "apk_pull_failed_using_pm_dump", {"package": package_name}
                )
                activities = _get_activities_from_device(package_name)
                if activities:
                    logger.info(
                        "pm dump fallback found %d activities for %s",
                        len(activities),
                        package_name,
                    )
                    observer.record_event(
                        "0a", "pm_dump_fallback_success", {"activities": len(activities)}
                    )
                    return ManifestResult(
                        package=package_name,
                        activities=activities,
                        launcher_activity=activities[0] if activities else None,
                        parse_errors=["APK not on disk; used ADB pm dump (may be incomplete)"],
                    )

        if apk_path is None or not apk_path.exists():
            logger.warning("APK file not found and all ADB fallbacks unavailable")
            observer.record_event("0a", "apk_not_found", {"path": str(apk_path)})
            return ManifestResult(package="unknown", parse_errors=["APK file not found"])

    observer.record_event("0a", "apk_found", {"path": str(apk_path)})

    # Try aapt2 first
    try:
        result = subprocess.run(
            ["aapt2", "dump", "xmltree", str(apk_path), "--file", "AndroidManifest.xml"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            observer.record_event("0a", "aapt2_success", {"returncode": result.returncode})
            activities, launcher, exported = _parse_aapt2_output(result.stdout)
            package = _extract_package_aapt2(result.stdout)
            observer.record_event(
                "0a",
                "activities_parsed",
                {"total": len(activities), "navigable": len(exported)},
            )
            return ManifestResult(
                package=package,
                activities=activities,
                launcher_activity=launcher,
                exported_activities=exported,
                raw_output=result.stdout,
            )
    except FileNotFoundError:
        logger.warning("aapt2 not found on PATH, trying aapt")
        observer.record_event("0a", "aapt2_not_found", {})

    # Try aapt (older tool)
    try:
        result = subprocess.run(
            ["aapt", "dump", "badging", str(apk_path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            observer.record_event("0a", "aapt_success", {})
            activities, launcher, package = _parse_aapt_badging(result.stdout)
            return ManifestResult(
                package=package,
                activities=activities,
                launcher_activity=launcher,
                raw_output=result.stdout,
            )
    except FileNotFoundError:
        logger.warning("aapt not found on PATH, using zipfile fallback")
        observer.record_event("0a", "aapt_not_found", {})

    # Fallback: zipfile + regex on binary AXML
    activities, package, errors = _fallback_parse_zipfile(apk_path)
    observer.record_event("0a", "zipfile_fallback_used", {"activities_found": len(activities)})
    return ManifestResult(
        package=package,
        activities=activities,
        launcher_activity=activities[0] if activities else None,
        parse_errors=errors,
    )


def _find_apk(path: Path) -> Path | None:
    """Try to find an APK file given a partial path or filename stem."""
    stem = path.stem  # e.g. "budgetwatch" from "budgetwatch.apk"
    search_dirs = [Path("."), Path("apks"), Path("dist"), Path("rlmobtest/config")]

    # First try exact filename match in each directory
    for d in search_dirs:
        if d.exists():
            candidate = d / path.name
            if candidate.exists():
                return candidate
            # Also try just stem.apk
            candidate = d / f"{stem}.apk"
            if candidate.exists():
                return candidate

    # Last resort: any .apk in search dirs
    for d in search_dirs:
        if d.exists():
            for apk in d.glob("*.apk"):
                return apk

    return None


def _pull_apk_from_device(package_name: str) -> Path | None:
    """
    Pull the installed APK from the connected device using adb.
    Returns the local path of the pulled APK, or None on failure.
    """
    try:
        # Get APK path on device
        result = subprocess.run(
            ["adb", "shell", "pm", "path", package_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        # "package:/data/app/.../base.apk"
        line = result.stdout.strip()
        if not line.startswith("package:"):
            return None
        device_path = line[len("package:") :]

        local_path = Path(tempfile.gettempdir()) / f"{package_name}_pulled.apk"
        pull_result = subprocess.run(
            ["adb", "pull", device_path, str(local_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if pull_result.returncode == 0 and local_path.exists():
            return local_path

    except Exception as exc:
        logger.warning("Failed to pull APK from device: %s", exc)

    return None


def _get_activities_from_device(package_name: str) -> list:
    """
    Query ADB for activities registered to an installed package.
    Parses 'adb shell pm dump {package}' output.
    Works without the APK file on disk.
    """
    try:
        result = subprocess.run(
            ["adb", "shell", "pm", "dump", package_name],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            return []

        activities = []
        seen: set = set()

        # Valid activity short-name: optional leading dot, then a capital letter,
        # then alphanumeric / dot / dollar / underscore only (no @, =, {, }, etc.)
        _valid = re.compile(r"^\.?[A-Za-z][A-Za-z0-9_.$]*$")

        # ── Pass 1: parse the "Activities:" section (most reliable) ──────────
        in_activities = False
        for line in result.stdout.splitlines():
            stripped = line.strip()

            if stripped == "Activities:":
                in_activities = True
                continue

            # Leave the section on any other keyword ending with ":"
            if (
                in_activities
                and stripped
                and not stripped.startswith(package_name)
                and stripped.endswith(":")
            ):
                in_activities = False
                continue

            if in_activities and stripped.startswith(package_name + "/"):
                # First token only — no trailing filter hash or garbage
                token = stripped.split()[0]
                short = token[len(package_name) + 1 :]
                if _valid.match(short) and token not in seen:
                    activities.append(token)
                    seen.add(token)

        # ── Pass 2: fallback — scan Activity Resolver Table ──────────────────
        if not activities:
            # Only match lines that end with the activity name (no trailing garbage)
            pattern = re.compile(
                rf"{re.escape(package_name)}"
                rf"/(\.?[A-Za-z][A-Za-z0-9_.$]*Activity[A-Za-z0-9_$]*)(?=[\s]|$)"
            )
            for line in result.stdout.splitlines():
                m = pattern.search(line)
                if m:
                    full_name = f"{package_name}/{m.group(1)}"
                    if full_name not in seen:
                        activities.append(full_name)
                        seen.add(full_name)

        return activities

    except Exception as exc:
        logger.warning("ADB device query failed: %s", exc)
        return []


def _parse_aapt2_output(output: str) -> tuple[list[str], str | None, list[str]]:
    """
    Parse aapt2 xmltree output to extract activity names, launcher, and exported status.

    aapt2 uses indentation-based depth (2 spaces per level). Activities
    appear as `E: activity` elements. Their android:name is one level
    deeper. The exit condition is based on depth, not a fixed number.

    Returns:
        (all_activities, launcher_activity, navigable_activities)
        navigable_activities: activities that can be launched via `adb am start`
          — those with explicit android:exported=true, or any <intent-filter>
          (pre-Android-12 default: activities with intent-filters were implicitly exported)
    """
    activities: list[str] = []
    exported_activities: list[str] = []
    launcher_activity: str | None = None
    in_activity = False
    in_intent_filter = False
    has_main = False
    has_launcher = False
    has_any_intent_filter = False
    current_activity: str | None = None
    current_exported: bool | None = None  # None = attribute absent
    activity_depth = -1
    intent_filter_depth = -1

    def _commit() -> None:
        nonlocal launcher_activity
        if current_activity and current_activity not in activities:
            activities.append(current_activity)
            if has_main and has_launcher and launcher_activity is None:
                launcher_activity = current_activity
            # Navigable if explicitly exported=True OR has any <intent-filter>
            # (apps built before Android 12 had intent-filter → implicitly exported)
            if current_exported is True or has_any_intent_filter:
                exported_activities.append(current_activity)

    for line in output.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        current_depth = indent // 2

        if stripped.startswith("E: activity "):
            # Save previous activity before starting a new one
            if in_activity:
                _commit()
            in_activity = True
            in_intent_filter = False
            has_main = False
            has_launcher = False
            has_any_intent_filter = False
            current_activity = None
            current_exported = None
            activity_depth = current_depth

        elif in_activity:
            # Exited activity block: non-attribute element at same or higher level
            if current_depth <= activity_depth and stripped.startswith("E: "):
                _commit()
                in_activity = False
                in_intent_filter = False
                current_activity = None
                current_exported = None
                continue

            # Exited intent-filter: element at same or higher level
            if (
                in_intent_filter
                and current_depth <= intent_filter_depth
                and stripped.startswith("E: ")
            ):
                in_intent_filter = False

            if stripped.startswith("E: intent-filter"):
                in_intent_filter = True
                has_any_intent_filter = True
                has_main = False
                has_launcher = False
                intent_filter_depth = current_depth

            elif "android.intent.action.MAIN" in stripped:
                has_main = True

            elif "android.intent.category.LAUNCHER" in stripped:
                has_launcher = True

            elif not in_intent_filter and stripped.startswith("A: ") and "android:name" in stripped:
                # Activity-level android:name attribute (not nested inside intent-filter)
                match = re.search(r'="([^"]+)"', stripped)
                if match:
                    name = match.group(1)
                    if not name.startswith("android") and not name.startswith("androidx"):
                        current_activity = name

            elif (
                not in_intent_filter
                and stripped.startswith("A: ")
                and "android:exported" in stripped
            ):
                # aapt2 formats:
                #   (type 0x12)0xffffffff  — older aapt2 boolean true
                #   (type 0x12)0x00000000  — older aapt2 boolean false
                #   =true / =false         — newer aapt2 without quotes
                #   ="true" / ="false"     — alternative quoting
                low = stripped.lower()
                if "0xffffffff" in low or "=true" in low:
                    current_exported = True
                elif "0x00000000" in low or "=false" in low:
                    current_exported = False

    # Catch last activity
    if in_activity:
        _commit()

    return activities, launcher_activity, exported_activities


def _extract_package_aapt2(output: str) -> str:
    """Extract package name from aapt2 output."""
    for line in output.splitlines():
        if "A: package=" in line or "package=" in line:
            match = re.search(r'"([a-z][a-z0-9._]+)"', line)
            if match:
                return match.group(1)
    return "unknown"


def _parse_aapt_badging(output: str) -> tuple[list[str], str | None, str]:
    """Parse aapt dump badging output."""
    activities = []
    launcher = None
    package = "unknown"

    for line in output.splitlines():
        if line.startswith("package:"):
            m = re.search(r"name='([^']+)'", line)
            if m:
                package = m.group(1)
        elif line.startswith("launchable-activity:"):
            m = re.search(r"name='([^']+)'", line)
            if m:
                launcher = m.group(1)
                if launcher not in activities:
                    activities.append(launcher)
        elif line.startswith("activity:") or "activity-alias:" in line:
            m = re.search(r"name='([^']+)'", line)
            if m and m.group(1) not in activities:
                activities.append(m.group(1))

    return activities, launcher, package


def _fallback_parse_zipfile(apk_path: Path) -> tuple[list[str], str, list[str]]:
    """
    Fallback: open APK as ZIP and use regex to find activity names in binary AXML.
    This is a best-effort approach that works without Android SDK tools.
    """
    activities = []
    package = "unknown"
    errors = []

    try:
        with zipfile.ZipFile(apk_path, "r") as z:
            if "AndroidManifest.xml" not in z.namelist():
                errors.append("AndroidManifest.xml not found in APK")
                return activities, package, errors

            data = z.read("AndroidManifest.xml")

        # Extract printable ASCII strings from binary AXML
        # Activity class names follow Java package naming conventions
        strings = re.findall(rb"[a-zA-Z][a-zA-Z0-9_$.]{5,}Activity[a-zA-Z0-9_$]*", data)
        seen = set()
        for s in strings:
            decoded = s.decode("ascii", errors="ignore")
            if decoded not in seen and len(decoded) < 200:
                activities.append(decoded)
                seen.add(decoded)

        # Try to extract package name
        pkg_matches = re.findall(rb"[a-z][a-z0-9_]{1,20}(?:\.[a-z][a-z0-9_]{1,20}){1,5}", data)
        for m in pkg_matches:
            candidate = m.decode("ascii", errors="ignore")
            if 2 <= candidate.count(".") <= 4 and len(candidate) < 100:
                package = candidate
                break

    except Exception as e:
        errors.append(f"zipfile parsing error: {e}")
        logger.warning("zipfile fallback failed: %s", e)

    return activities, package, errors
