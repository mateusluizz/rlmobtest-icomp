"""JaCoCo setup automation: build APK, copy classfiles, download jacococli."""

import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from rich.console import Console

from rlmobtest.constants.paths import (
    APKS_DIR,
    CLASSFILES_DIR,
    JACOCOCLI_URL,
    SOURCE_CODES_DIR,
    TOOLS_DIR,
)
from rlmobtest.utils.jacoco import find_classfiles, find_jacococli

console = Console()
logger = logging.getLogger(__name__)


def resolve_source_dir(source_code: str) -> Path | None:
    """Resolve source_code config value to a directory path.

    Handles:
        - Direct directories in inputs/source_codes/
        - .zip archives (extracted automatically)

    Returns:
        Path to the source code directory, or None on failure.
    """
    source_path = SOURCE_CODES_DIR / source_code

    # Direct directory (e.g. "open_money_tracker-dev")
    if source_path.is_dir():
        return source_path

    # ZIP archive (e.g. "open_money_tracker-dev.zip")
    if source_path.exists() and source_path.suffix == ".zip":
        extract_dir = SOURCE_CODES_DIR / source_path.stem
        if extract_dir.is_dir():
            return extract_dir
        try:
            console.print(f"  [dim]Extracting {source_code}...[/]")
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(extract_dir)
            return extract_dir
        except Exception as e:
            logger.warning("Failed to extract %s: %s", source_code, e)
            return None

    # Try without extension (directory name without .zip)
    stem_path = SOURCE_CODES_DIR / Path(source_code).stem
    if stem_path.is_dir():
        return stem_path

    console.print(f"  [yellow]Source code not found: {source_path}[/]")
    return None


def find_gradle_project(source_dir: Path) -> Path | None:
    """Find the Gradle project root containing gradlew.

    Searches the directory and one level deep.

    Returns:
        Path to the project root, or None if not found.
    """
    # Check directly
    gradlew = source_dir / "gradlew"
    if gradlew.exists():
        gradlew.chmod(gradlew.stat().st_mode | 0o111)
        return source_dir

    # Check one level deep (some archives have a single root folder)
    for child in source_dir.iterdir():
        if child.is_dir():
            gradlew = child / "gradlew"
            if gradlew.exists():
                gradlew.chmod(gradlew.stat().st_mode | 0o111)
                return child

    console.print(f"  [yellow]gradlew not found in {source_dir}[/]")
    return None


def build_apk(
    project_dir: Path,
    apk_name: str,
    force: bool = False,
) -> Path | None:
    """Build instrumented debug APK from source.

    Tries assembleFreeDebug first, falls back to assembleDebug.
    Skips if APK already exists in inputs/apks/ (unless force=True).

    Returns:
        Path to the APK in inputs/apks/, or None on failure.
    """
    target = APKS_DIR / apk_name
    if target.exists() and not force:
        console.print(f"  [dim]APK already exists: {target.name}[/]")
        return target

    # Check prerequisites
    android_home = os.environ.get("ANDROID_HOME")
    if not android_home:
        console.print(
            "[yellow]ANDROID_HOME not set. Cannot build APK.[/]\n"
            "  Set it with: export ANDROID_HOME=$HOME/android-sdk"
        )
        return None

    if not shutil.which("java"):
        console.print("[yellow]Java not found. Required to build APK.[/]")
        return None

    # Create/update local.properties
    local_props = project_dir / "local.properties"
    local_props.write_text(f"sdk.dir={android_home}\n")

    gradlew = str(project_dir / "gradlew")

    # Try assembleFreeDebug, fallback to assembleDebug
    for task in ["assembleFreeDebug", "assembleDebug"]:
        console.print(f"  [dim]Running {task}...[/]")
        result = subprocess.run(
            [gradlew, task],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            console.print(f"  [green]Build successful ({task})[/]")
            break
        logger.debug("Build %s failed: %s", task, result.stderr[-500:] if result.stderr else "")
    else:
        console.print("[red]APK build failed. Check ANDROID_HOME and Gradle setup.[/]")
        return None

    # Find the output APK
    apk_output_dir = project_dir / "app" / "build" / "outputs" / "apk"
    apk_files = list(apk_output_dir.rglob("*debug*.apk"))
    if not apk_files:
        console.print("[red]No debug APK found after build.[/]")
        return None

    # Copy to inputs/apks/
    APKS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(apk_files[0], target)
    console.print(f"  [green]APK copied to {target}[/]")
    return target


def copy_classfiles(
    project_dir: Path,
    package_name: str,
    force: bool = False,
) -> Path | None:
    """Copy compiled classfiles to inputs/classfiles/{package_name}/.

    Searches build intermediates for debug class files.
    Prefers freeDebug variant.

    Returns:
        Path to classfiles directory, or None on failure.
    """
    dest = CLASSFILES_DIR / package_name
    if not force and find_classfiles(package_name):
        console.print(f"  [dim]Classfiles already exist: {package_name}[/]")
        return dest

    # Search for compiled classes
    javac_dir = project_dir / "app" / "build" / "intermediates" / "javac"
    if not javac_dir.exists():
        console.print("[yellow]No compiled classes found. Build the APK first.[/]")
        return None

    # Prefer freeDebug, then any debug variant
    classes_dir = None
    for variant in ["freeDebug", "debug"]:
        candidate = javac_dir / variant / "classes"
        if candidate.exists() and any(candidate.rglob("*.class")):
            classes_dir = candidate
            break

    if not classes_dir:
        # Search any variant with classes
        for candidate in javac_dir.rglob("classes"):
            if candidate.is_dir() and any(candidate.rglob("*.class")):
                classes_dir = candidate
                break

    if not classes_dir:
        console.print("[yellow]No .class files found in build intermediates.[/]")
        return None

    # Copy
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(classes_dir, dest, dirs_exist_ok=True)
    class_count = sum(1 for _ in dest.rglob("*.class"))
    console.print(f"  [green]Classfiles copied ({class_count} .class files)[/]")
    return dest


def download_jacococli(force: bool = False) -> Path | None:
    """Download jacococli.jar from Maven Central if not present.

    Returns:
        Path to jacococli.jar, or None on failure.
    """
    existing = find_jacococli()
    if existing and not force:
        console.print(f"  [dim]jacococli.jar already exists[/]")
        return existing

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    target = TOOLS_DIR / "jacococli.jar"

    console.print(f"  [dim]Downloading jacococli.jar...[/]")
    try:
        urlretrieve(JACOCOCLI_URL, target)
        console.print(f"  [green]jacococli.jar downloaded[/]")
        return target
    except Exception as e:
        console.print(f"  [red]Download failed: {e}[/]")
        return None


def run_setup(config, force: bool = False) -> dict[str, bool]:
    """Run full JaCoCo setup for an app config.

    Steps:
        1. Resolve/extract source code
        2. Build instrumented APK
        3. Copy classfiles
        4. Download jacococli.jar

    All steps are idempotent — existing artifacts are skipped.

    Returns:
        Dict with step results: {"apk_built", "classfiles_copied", "jacococli_downloaded"}.
    """
    results = {
        "apk_built": False,
        "classfiles_copied": False,
        "jacococli_downloaded": False,
    }

    # Step 1: Download jacococli.jar (independent of source code)
    if download_jacococli(force=force):
        results["jacococli_downloaded"] = True

    # Steps 2-4: Require source code
    if not config.source_code:
        console.print("  [dim]No source_code configured, skipping APK build[/]")
        return results

    source_dir = resolve_source_dir(config.source_code)
    if not source_dir:
        return results

    project_dir = find_gradle_project(source_dir)
    if not project_dir:
        return results

    # Step 2: Build APK
    if build_apk(project_dir, config.apk_name, force=force):
        results["apk_built"] = True

    # Step 3: Copy classfiles
    if copy_classfiles(project_dir, config.package_name, force=force):
        results["classfiles_copied"] = True

    return results
