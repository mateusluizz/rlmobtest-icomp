"""JaCoCo setup automation: build APK, copy classfiles, download jacococli."""

import logging
import os
import re
import shutil
import subprocess
import tarfile
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

# Gradle major version → maximum compatible Java major version.
# Source: https://docs.gradle.org/current/userguide/compatibility.html
_GRADLE_MAX_JAVA: list[tuple[int, int]] = [
    (8, 21),   # Gradle 8.x → Java 21
    (7, 19),   # Gradle 7.x → Java 19
    (6, 15),   # Gradle 6.x → Java 15
    (5, 12),   # Gradle 5.x → Java 12
    (4, 9),    # Gradle 4.x → Java 9
]

# More conservative: what actually works without Groovy/reflection issues.
# Older Gradle uses older Groovy which crashes on modern JVMs.
_GRADLE_RECOMMENDED_JAVA: list[tuple[int, int]] = [
    (8, 17),
    (7, 17),
    (6, 11),
    (5, 11),
    (4, 8),
    (3, 8),
    (2, 8),
]

# AGP version → recommended Gradle version + recommended Java version.
# Source: https://developer.android.com/build/releases/gradle-plugin
_AGP_COMPAT: list[tuple[str, str, int]] = [
    ("8.4", "8.6",   17),
    ("8.3", "8.4",   17),
    ("8.2", "8.2",   17),
    ("8.1", "8.0",   17),
    ("8.0", "8.0",   17),
    ("7.4", "7.5",   11),
    ("7.3", "7.4",   11),
    ("7.2", "7.3.3", 11),
    ("7.1", "7.2",   11),
    ("7.0", "7.0",   11),
    ("4.2", "6.7.1", 11),
    ("4.1", "6.5",   11),
    ("4.0", "6.1.1", 11),
    ("3.6", "5.6.4",  8),
    ("3.5", "5.4.1",  8),
    ("3.4", "5.1.1",  8),
    ("3.3", "4.10.1", 8),
    ("3.2", "4.6",    8),
    ("3.1", "4.4",    8),
    ("3.0", "4.1",    8),
    ("2.3", "3.3",    8),
    ("2.2", "2.14.1", 8),
    ("2.1", "2.12",   8),
    ("2.0", "2.10",   8),
    ("1.5", "2.10",   8),
    ("1.3", "2.4",    8),
    ("1.2", "2.4",    8),
    ("1.1", "2.3",    8),
    ("1.0", "2.3",    8),
]


def _parse_gradle_version(project_dir: Path) -> str | None:
    """Extract Gradle version from gradle-wrapper.properties."""
    props = project_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not props.exists():
        return None
    text = props.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"gradle-(\d+\.\d+(?:\.\d+)?)", text)
    return m.group(1) if m else None


def _parse_java_version() -> int | None:
    """Get the current Java major version (e.g. 21, 17, 11)."""
    java = shutil.which("java")
    if not java:
        return None
    try:
        result = subprocess.run(
            [java, "-version"], capture_output=True, text=True, timeout=10,
        )
        output = result.stderr or result.stdout
        m = re.search(r'"(\d+)[\._]', output)
        if m:
            major = int(m.group(1))
            # Old-style: "1.8.0" → 8
            return 8 if major == 1 else major
    except Exception:
        pass
    return None


def _max_java_for_gradle(gradle_version: str) -> int | None:
    """Return recommended max Java version for a given Gradle version."""
    try:
        major = int(gradle_version.split(".")[0])
    except (ValueError, IndexError):
        return None
    for gradle_major, java_max in _GRADLE_RECOMMENDED_JAVA:
        if major >= gradle_major:
            return java_max
    return 8


def _parse_agp_version(project_dir: Path) -> str | None:
    """Extract Android Gradle Plugin version from build.gradle."""
    for gradle_file in [
        project_dir / "build.gradle",
        project_dir / "build.gradle.kts",
    ]:
        if not gradle_file.exists():
            continue
        text = gradle_file.read_text(encoding="utf-8", errors="replace")
        m = re.search(
            r"com\.android\.tools\.build:gradle[:\"].*?(\d+\.\d+(?:\.\d+)?)",
            text,
        )
        if m:
            return m.group(1)
    return None


def _gradle_for_agp(agp_version: str) -> tuple[str, int] | None:
    """Return (recommended_gradle_version, recommended_java) for an AGP version."""
    try:
        parts = agp_version.split(".")
        agp_major_minor = f"{parts[0]}.{parts[1]}"
    except (ValueError, IndexError):
        return None
    for agp_prefix, gradle_ver, java_ver in _AGP_COMPAT:
        if agp_major_minor >= agp_prefix:
            return gradle_ver, java_ver
    return "2.3", 8


_WRAPPER_PROPERTIES_TEMPLATE = """\
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{version}-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""


def _generate_gradle_wrapper(
    project_dir: Path, gradle_version: str,
) -> Path | None:
    """Generate Gradle wrapper files for a project that lacks them.

    Strategy:
      1. If `gradle` is on PATH, run `gradle wrapper --gradle-version=X`.
      2. Otherwise, create gradle-wrapper.properties manually and download
         the standard gradlew script from the Gradle distribution.

    Returns the path to gradlew, or None on failure.
    """
    system_gradle = shutil.which("gradle")
    gradlew = project_dir / "gradlew"

    if system_gradle:
        # Use system gradle to generate a proper wrapper
        console.print(
            f"  [dim]Generating wrapper via "
            f"`gradle wrapper --gradle-version={gradle_version}`[/]"
        )
        result = subprocess.run(
            [
                system_gradle, "wrapper",
                f"--gradle-version={gradle_version}",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and gradlew.exists():
            gradlew.chmod(gradlew.stat().st_mode | 0o111)
            console.print(
                f"  [green]Generated Gradle wrapper "
                f"(Gradle {gradle_version})[/]"
            )
            return gradlew
        logger.warning(
            "gradle wrapper failed: %s",
            result.stderr[-300:] if result.stderr else "unknown",
        )

    # Fallback: create wrapper properties only; build_apk will
    # use system gradle directly
    wrapper_dir = project_dir / "gradle" / "wrapper"
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    props = wrapper_dir / "gradle-wrapper.properties"
    props.write_text(
        _WRAPPER_PROPERTIES_TEMPLATE.format(version=gradle_version),
        encoding="utf-8",
    )

    if not system_gradle:
        console.print(
            f"  [yellow]`gradle` not found on PATH. "
            f"Install Gradle {gradle_version} to build.[/]\n"
            f"  With asdf: [cyan]asdf install gradle "
            f"{gradle_version} && "
            f"asdf set -p gradle {gradle_version}[/]"
        )
        return None

    console.print(
        f"  [green]Generated wrapper properties "
        f"(Gradle {gradle_version})[/]"
    )
    return gradlew


def check_prerequisites(
    project_dir: Path | None = None,
    package_name: str | None = None,
) -> dict:
    """Check all prerequisites and return a status dict.

    Returns a dict with keys:
        java_version, gradle_version, agp_version,
        recommended_gradle, recommended_java_for_agp,
        java_compatible, recommended_java,
        android_home, has_adb, has_classfiles, has_jacococli
    """
    info: dict = {}

    # Java
    java_ver = _parse_java_version()
    info["java_version"] = java_ver
    info["java_path"] = shutil.which("java")

    # Android SDK
    android_home = _find_android_home()
    info["android_home"] = android_home
    info["has_adb"] = shutil.which("adb") is not None

    # AGP + Gradle (requires project_dir)
    info["agp_version"] = None
    info["recommended_gradle"] = None
    info["recommended_java_for_agp"] = None

    if project_dir:
        agp_ver = _parse_agp_version(project_dir)
        info["agp_version"] = agp_ver
        if agp_ver:
            compat = _gradle_for_agp(agp_ver)
            if compat:
                info["recommended_gradle"] = compat[0]
                info["recommended_java_for_agp"] = compat[1]

        gradle_ver = _parse_gradle_version(project_dir)
        info["gradle_version"] = gradle_ver
        if gradle_ver and java_ver:
            max_java = _max_java_for_gradle(gradle_ver)
            info["recommended_java"] = max_java
            info["java_compatible"] = java_ver <= max_java if max_java else None
        else:
            info["recommended_java"] = None
            info["java_compatible"] = None
    else:
        info["gradle_version"] = None
        info["recommended_java"] = None
        info["java_compatible"] = None

    # Existing artifacts
    if package_name:
        info["has_classfiles"] = find_classfiles(package_name) is not None
    else:
        info["has_classfiles"] = None
    info["has_jacococli"] = find_jacococli() is not None

    return info


def _extract_stem(source_code: str) -> str:
    """Get directory name from archive filename, stripping .zip/.tar.gz/.tgz."""
    name = source_code
    for suffix in (".tar.gz", ".tgz"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def resolve_source_dir(source_code: str) -> Path | None:
    """Resolve source_code config value to a directory path.

    Handles:
        - Direct directories in inputs/source_codes/
        - .zip archives (extracted automatically)
        - .tar.gz / .tgz archives (extracted automatically)

    Returns:
        Path to the source code directory, or None on failure.
    """
    source_path = SOURCE_CODES_DIR / source_code

    # Direct directory (e.g. "open_money_tracker-dev")
    if source_path.is_dir():
        return source_path

    extract_dir = SOURCE_CODES_DIR / _extract_stem(source_code)

    # Already extracted
    if extract_dir.is_dir():
        return extract_dir

    if not source_path.exists():
        console.print(f"  [yellow]Source code not found: {source_path}[/]")
        return None

    # ZIP archive
    if source_path.suffix == ".zip":
        try:
            console.print(f"  [dim]Extracting {source_code}...[/]")
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(extract_dir)
            return extract_dir
        except Exception as e:
            logger.warning("Failed to extract %s: %s", source_code, e)
            return None

    # tar.gz / tgz / tar archive
    if source_code.endswith((".tar.gz", ".tgz", ".tar")):
        try:
            console.print(f"  [dim]Extracting {source_code}...[/]")
            # Use "r:*" to auto-detect compression (gz, bz2, xz, or none)
            with tarfile.open(source_path, "r:*") as tf:
                tf.extractall(extract_dir)
            return extract_dir
        except Exception as e:
            logger.warning("Failed to extract %s: %s", source_code, e)
            return None

    console.print(f"  [yellow]Unsupported archive format: {source_path}[/]")
    return None


def find_gradle_project(source_dir: Path) -> Path | None:
    """Find the Gradle project root.

    Searches for gradlew first. If not found, looks for build.gradle
    and auto-generates a Gradle wrapper based on the AGP version.

    Searches the directory and one level deep.

    Returns:
        Path to the project root, or None if not found.
    """
    # Pass 1: look for gradlew
    for candidate in _iter_project_candidates(source_dir):
        gradlew = candidate / "gradlew"
        if gradlew.exists():
            gradlew.chmod(gradlew.stat().st_mode | 0o111)
            return candidate

    # Pass 2: look for build.gradle and generate wrapper
    for candidate in _iter_project_candidates(source_dir):
        build_gradle = candidate / "build.gradle"
        if not build_gradle.exists():
            build_gradle = candidate / "build.gradle.kts"
        if build_gradle.exists():
            agp_ver = _parse_agp_version(candidate)
            if agp_ver:
                compat = _gradle_for_agp(agp_ver)
                if compat:
                    gradle_ver, java_ver = compat
                    console.print(
                        f"  [yellow]No gradlew found. "
                        f"Detected AGP {agp_ver} → "
                        f"Gradle {gradle_ver} + Java {java_ver}[/]"
                    )
                    _generate_gradle_wrapper(candidate, gradle_ver)
                    return candidate
            console.print(
                f"  [yellow]build.gradle found but could not "
                f"determine AGP version in {candidate}[/]"
            )
            return None

    console.print(
        f"  [yellow]No Gradle project found in {source_dir}[/]"
    )
    return None


def _iter_project_candidates(source_dir: Path):
    """Yield source_dir and its immediate subdirectories."""
    yield source_dir
    try:
        for child in source_dir.iterdir():
            if child.is_dir():
                yield child
    except OSError:
        pass


_ANDROID_SDK_CANDIDATES = [
    Path.home() / "Android" / "Sdk",           # Linux (Android Studio default)
    Path.home() / "android-sdk",                # Manual install
    Path.home() / "Library" / "Android" / "sdk",  # macOS
    Path("/opt/android-sdk"),
    Path("/usr/local/android-sdk"),
]


def _find_android_home() -> str | None:
    """Auto-detect ANDROID_HOME from env, common paths, or adb location."""
    # 1. Environment variable
    from_env = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if from_env and Path(from_env).is_dir():
        return from_env

    # 2. Common installation paths
    for candidate in _ANDROID_SDK_CANDIDATES:
        if candidate.is_dir() and (candidate / "platform-tools").is_dir():
            console.print(f"  [dim]Auto-detected ANDROID_HOME: {candidate}[/]")
            os.environ["ANDROID_HOME"] = str(candidate)
            return str(candidate)

    # 3. Infer from adb location (e.g. /home/user/Android/Sdk/platform-tools/adb)
    adb_path = shutil.which("adb")
    if adb_path:
        sdk_dir = Path(adb_path).resolve().parent.parent
        if (sdk_dir / "platform-tools").is_dir():
            console.print(f"  [dim]Auto-detected ANDROID_HOME from adb: {sdk_dir}[/]")
            os.environ["ANDROID_HOME"] = str(sdk_dir)
            return str(sdk_dir)

    return None


_JACOCO_GRADLE_MARKER = "apply plugin: 'jacoco'"

_JACOCO_GRADLE_BLOCK = """\

// --- RLMobTest JaCoCo instrumentation ---
apply plugin: 'jacoco'

jacoco {
    toolVersion = "0.8.12"
}
// --- end RLMobTest JaCoCo ---
"""

_COVERAGE_ENABLED_SNIPPET = """\
        debug {
            testCoverageEnabled true
        }"""

_COVERAGE_RECEIVER_TEMPLATE = """\
package {package_name};

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

public class CoverageReceiver extends BroadcastReceiver {{
    @Override
    public void onReceive(Context context, Intent intent) {{
        try {{
            Class<?> rtClass = Class.forName("org.jacoco.agent.rt.RT");
            Object agent = rtClass.getMethod("getAgent").invoke(null);
            byte[] data = (byte[]) agent.getClass()
                    .getMethod("getExecutionData", boolean.class)
                    .invoke(agent, false);
            File coverageFile = new File(context.getFilesDir(), "coverage.ec");
            OutputStream out = new FileOutputStream(coverageFile);
            out.write(data);
            out.close();
            Log.i("CoverageReceiver", "Coverage dumped (" + data.length + " bytes)");
        }} catch (Exception e) {{
            Log.e("CoverageReceiver", "Failed to dump coverage", e);
        }}
    }}
}}
"""

_RECEIVER_MANIFEST_SNIPPET = """\
        <receiver android:name=".CoverageReceiver" android:exported="true">
            <intent-filter>
                <action android:name="{package_name}.DUMP_COVERAGE" />
            </intent-filter>
        </receiver>"""


def _ensure_maven_central(project_dir: Path) -> None:
    """Add mavenCentral() and google() to root build.gradle if missing.

    jcenter() is sunset and many artifacts are no longer available there.
    google() hosts Android support libraries and AndroidX artifacts.
    Adding both before jcenter() ensures dependencies resolve.
    """
    root_gradle = project_dir / "build.gradle"
    if not root_gradle.exists():
        return

    text = root_gradle.read_text(encoding="utf-8")
    changed = False

    # Add Google Maven repo if missing (needed for com.android.support / androidx)
    # google() shorthand only works on Gradle 4.0+; older versions need the URL
    _GOOGLE_MAVEN_URL = "https://maven.google.com"
    has_google = "google()" in text or "maven.google.com" in text
    if not has_google:
        # google() shorthand requires Gradle 4.0+; older versions need the URL
        props_file = project_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
        use_url = False
        if props_file.exists():
            props = props_file.read_text(encoding="utf-8")
            import re as _re
            m = _re.search(r"gradle-(\d+)\.", props)
            if m and int(m.group(1)) < 4:
                use_url = True
        google_line = (
            f"maven {{ url '{_GOOGLE_MAVEN_URL}' }}"
            if use_url
            else "google()"
        )
        if "jcenter()" in text:
            text = text.replace("jcenter()", f"{google_line}\n        jcenter()")
            changed = True
        elif "mavenCentral()" in text:
            text = text.replace("mavenCentral()", f"{google_line}\n        mavenCentral()")
            changed = True
        if changed:
            console.print("  [green]Added Google Maven repo to root build.gradle (Android support libs)[/]")

    # Add mavenCentral() if missing (jcenter replacement)
    if "mavenCentral()" not in text:
        if "jcenter()" in text:
            text = text.replace("jcenter()", "mavenCentral()\n        jcenter()")
            changed = True
            console.print("  [green]Added mavenCentral() to root build.gradle (jcenter is deprecated)[/]")

    if changed:
        root_gradle.write_text(text, encoding="utf-8")


def instrument_source_code(project_dir: Path, package_name: str) -> bool:
    """Instrument an Android project for JaCoCo coverage collection.

    Idempotent — skips steps already applied. Modifies:
      0. Root build.gradle — adds mavenCentral() if missing (jcenter fix)
      1. app/build.gradle — adds jacoco plugin + testCoverageEnabled
      2. CoverageReceiver.java — creates the BroadcastReceiver
      3. AndroidManifest.xml — registers the receiver

    Returns True if all instrumentation is in place.
    """
    # Step 0: Ensure mavenCentral() is present in root build.gradle
    _ensure_maven_central(project_dir)

    build_gradle = project_dir / "app" / "build.gradle"
    if not build_gradle.exists():
        console.print("  [yellow]app/build.gradle not found, skipping instrumentation[/]")
        return False

    gradle_text = build_gradle.read_text(encoding="utf-8")
    changed = False

    # 1. Add jacoco plugin
    if _JACOCO_GRADLE_MARKER not in gradle_text:
        gradle_text += _JACOCO_GRADLE_BLOCK
        changed = True
        console.print("  [green]Added JaCoCo plugin to build.gradle[/]")

    # 2. Add testCoverageEnabled true in debug buildType
    if "testCoverageEnabled" not in gradle_text:
        # Insert inside buildTypes block
        if "buildTypes {" in gradle_text:
            gradle_text = gradle_text.replace(
                "buildTypes {",
                "buildTypes {\n" + _COVERAGE_ENABLED_SNIPPET,
            )
            changed = True
            console.print("  [green]Added testCoverageEnabled to build.gradle[/]")
        else:
            console.print("  [yellow]No buildTypes block found, add testCoverageEnabled manually[/]")

    if changed:
        build_gradle.write_text(gradle_text, encoding="utf-8")

    # 3. Create CoverageReceiver.java
    package_path = package_name.replace(".", "/")
    java_src = project_dir / "app" / "src" / "main" / "java" / package_path
    receiver_file = java_src / "CoverageReceiver.java"
    if not receiver_file.exists():
        java_src.mkdir(parents=True, exist_ok=True)
        receiver_file.write_text(
            _COVERAGE_RECEIVER_TEMPLATE.format(package_name=package_name),
            encoding="utf-8",
        )
        console.print(f"  [green]Created CoverageReceiver.java[/]")
    else:
        console.print(f"  [dim]CoverageReceiver.java already exists[/]")

    # 4. Register receiver in AndroidManifest.xml
    manifest = project_dir / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        console.print("  [yellow]AndroidManifest.xml not found[/]")
        return False

    manifest_text = manifest.read_text(encoding="utf-8")
    if "CoverageReceiver" not in manifest_text:
        snippet = _RECEIVER_MANIFEST_SNIPPET.format(package_name=package_name)
        # Insert before </application>
        manifest_text = manifest_text.replace(
            "</application>",
            snippet + "\n    </application>",
        )
        manifest.write_text(manifest_text, encoding="utf-8")
        console.print("  [green]Registered CoverageReceiver in AndroidManifest.xml[/]")
    else:
        console.print("  [dim]CoverageReceiver already in AndroidManifest.xml[/]")

    return True


_DEPENDENCY_RE = re.compile(
    r"Could not find (\S+)\.",
)


def _diagnose_build_failure(output: str) -> None:
    """Parse build output and display actionable diagnostics."""
    # Detect missing dependencies
    missing = _DEPENDENCY_RE.findall(output)
    if missing:
        console.print("\n  [bold red]Missing dependencies detected:[/]")
        for dep in dict.fromkeys(missing):  # deduplicate preserving order
            parts = dep.split(":")
            if len(parts) >= 2:
                group, artifact = parts[0], parts[1]
                console.print(f"    [red]• {dep}[/]")
                console.print(
                    f"      [dim]This artifact may have been removed from jcenter.[/]\n"
                    f"      [cyan]Try: search for it on https://jitpack.io or "
                    f"https://search.maven.org with '{group}:{artifact}'[/]"
                )
            else:
                console.print(f"    [red]• {dep}[/]")
        return

    # Detect missing SDK platform or build tools
    sdk_match = re.search(r"failed to find target (android-\d+)", output)
    bt_match = re.search(r"failed to find Build Tools revision ([\d.]+)", output)
    if sdk_match or bt_match:
        installs = []
        if sdk_match:
            target = sdk_match.group(1)
            installs.append(f"\"platforms;{target}\"")
        if bt_match:
            bt_ver = bt_match.group(1)
            installs.append(f"\"build-tools;{bt_ver}\"")
        console.print(
            f"\n  [bold red]Missing Android SDK components[/]\n"
            f"  [cyan]Fix: sdkmanager {' '.join(installs)}[/]\n"
            f"  [dim]Note: sdkmanager requires Java 11+. "
            f"Switch Java before running it if needed.[/]"
        )
        return

    # Detect Java/Groovy reflection errors (wrong Java version)
    if "IncrementalTaskInputs" in output or "ReflectionCache" in output:
        console.print(
            "\n  [bold red]Java version incompatible with this Gradle version.[/]\n"
            "  [cyan]Use `rlmobtest check` to see the recommended Java version.[/]"
        )
        return

    # Generic: show last 40 lines
    lines = output.splitlines()
    if len(lines) > 40:
        console.print(f"  [dim]... ({len(lines) - 40} lines omitted)[/]")
    for line in lines[-40:]:
        console.print(f"  [dim]{line}[/]")


def build_apk(
    project_dir: Path,
    apk_name: str,
    force: bool = False,
) -> Path | None:
    """Build instrumented debug APK from source.

    Runs assembleDebug using the project's gradlew.
    Skips if APK already exists in inputs/apks/ (unless force=True).

    Returns:
        Path to the APK in inputs/apks/, or None on failure.
    """
    target = APKS_DIR / apk_name
    if target.exists() and not force:
        console.print(f"  [dim]APK already exists: {target.name}[/]")
        return target

    # Check prerequisites
    android_home = _find_android_home()
    if not android_home:
        console.print(
            "[yellow]Android SDK not found. Cannot build APK.[/]\n"
            "  Set ANDROID_HOME or install the SDK in a standard location."
        )
        return None

    if not shutil.which("java"):
        console.print("[yellow]Java not found. Required to build APK.[/]")
        return None

    # Check Java/Gradle compatibility
    gradle_ver = _parse_gradle_version(project_dir)
    java_ver = _parse_java_version()
    if gradle_ver and java_ver:
        max_java = _max_java_for_gradle(gradle_ver)
        if max_java and java_ver > max_java:
            console.print(
                f"[red]Java {java_ver} is incompatible with Gradle {gradle_ver} "
                f"(max Java {max_java}).[/]\n"
                f"  Switch to Java {max_java} or lower. "
                f"With asdf: [cyan]asdf install java temurin-{max_java}.0.25+9 && "
                f"asdf set -p java temurin-{max_java}.0.25+9[/]"
            )
            return None
        console.print(f"  [dim]Gradle {gradle_ver} + Java {java_ver} (compatible)[/]")

    # Create/update local.properties
    local_props = project_dir / "local.properties"
    local_props.write_text(f"sdk.dir={android_home}\n")

    gradlew_path = project_dir / "gradlew"
    if gradlew_path.exists():
        build_cmd = [str(gradlew_path), "assembleDebug"]
    else:
        system_gradle = shutil.which("gradle")
        if not system_gradle:
            console.print(
                "[yellow]No gradlew and no system gradle found.[/]"
            )
            return None
        build_cmd = [system_gradle, "assembleDebug"]

    console.print(f"  [dim]Running {build_cmd[0]} assembleDebug...[/]")
    result = subprocess.run(
        build_cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        console.print("[red]APK build failed.[/]")
        output = (result.stderr or result.stdout or "").strip()
        if output:
            _diagnose_build_failure(output)
        return None

    console.print("  [green]Build successful (assembleDebug)[/]")

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

    # Search for compiled classes in both modern and legacy paths
    # Modern AGP (3.x+): intermediates/javac/<variant>/classes/
    # Legacy AGP (1.x-2.x): intermediates/classes/<variant>/
    intermediates = project_dir / "app" / "build" / "intermediates"
    if not intermediates.exists():
        console.print("[yellow]No compiled classes found. Build the APK first.[/]")
        return None

    classes_dir = None

    # Try modern path first (javac/)
    javac_dir = intermediates / "javac"
    if javac_dir.exists():
        for variant in ["freeDebug", "debug"]:
            candidate = javac_dir / variant / "classes"
            if candidate.exists() and any(candidate.rglob("*.class")):
                classes_dir = candidate
                break
        if not classes_dir:
            for candidate in javac_dir.rglob("classes"):
                if candidate.is_dir() and any(candidate.rglob("*.class")):
                    classes_dir = candidate
                    break

    # Try legacy path (classes/)
    if not classes_dir:
        legacy_dir = intermediates / "classes"
        if legacy_dir.exists():
            for variant in ["freeDebug", "debug"]:
                candidate = legacy_dir / variant
                if candidate.exists() and any(candidate.rglob("*.class")):
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

    # Step 2: Instrument source code for JaCoCo
    instrument_source_code(project_dir, config.package_name)

    # Step 3: Build APK
    if build_apk(project_dir, config.apk_name, force=force):
        results["apk_built"] = True

    # Step 4: Copy classfiles
    if copy_classfiles(project_dir, config.package_name, force=force):
        results["classfiles_copied"] = True

    return results
