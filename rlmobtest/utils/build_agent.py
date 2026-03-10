"""Autonomous build agent for Android projects (old and new).

Analyzes a project's AGP version, determines the correct Gradle + Java versions,
sets up the environment, fixes common build issues, and retries until success.
"""

import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from rlmobtest.constants.paths import APKS_DIR
from rlmobtest.utils.jacoco_setup import (
    _ensure_maven_central,
    _find_android_home,
    _generate_gradle_wrapper,
    _gradle_for_agp,
    _max_java_for_gradle,
    _parse_agp_version,
    _parse_gradle_version,
    _parse_java_version,
    copy_classfiles,
    download_jacococli,
    find_gradle_project,
    instrument_source_code,
    resolve_source_dir,
)

console = Console()
logger = logging.getLogger(__name__)

MAX_RETRIES = 5

# --------------------------------------------------------------------------- #
#  Java version table for asdf — maps major version to a known installable ID #
# --------------------------------------------------------------------------- #
_ASDF_JAVA_CANDIDATES: dict[int, list[str]] = {
    8: [
        "temurin-8.0.442+6",
        "temurin-8.0.432+6",
        "temurin-8.0.422+5",
        "temurin-8.0.412+8",
        "temurin-8.0.402+6",
        "corretto-8.422.05.1",
    ],
    11: [
        "temurin-11.0.26+4",
        "temurin-11.0.25+9",
        "temurin-11.0.24+8",
        "corretto-11.0.25.9.1",
    ],
    17: [
        "temurin-17.0.14+7",
        "temurin-17.0.13+11",
        "temurin-17.0.12+7",
        "temurin-17.0.11+9",
        "corretto-17.0.13.11.1",
    ],
    21: [
        "temurin-21.0.6+7",
        "temurin-21.0.5+11",
        "temurin-21.0.4+7",
        "corretto-21.0.5.11.1",
    ],
}


# --------------------------------------------------------------------------- #
#  Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class ProjectProfile:
    """Everything the agent knows about the Android project."""

    project_dir: Path
    package_name: str
    apk_name: str

    agp_version: str | None = None
    recommended_gradle: str | None = None
    recommended_java: int | None = None
    current_java: int | None = None
    current_gradle: str | None = None
    android_home: str | None = None

    # Tracks which fixes have been applied (prevents re-applying)
    applied_fixes: set[str] = field(default_factory=set)


@dataclass
class BuildResult:
    """Outcome of a single build attempt."""

    success: bool
    apk_path: Path | None = None
    classfiles_path: Path | None = None
    error_output: str = ""
    diagnosis: str = ""
    fix_applied: str | None = None


# --------------------------------------------------------------------------- #
#  Diagnosis patterns                                                          #
# --------------------------------------------------------------------------- #

_ERROR_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    # Missing google() repository (support libs / AndroidX)
    (
        "missing_google_repo",
        "Missing Google Maven repository for Android support libraries",
        re.compile(
            r"Could not find (com\.android\.support[:\S]*|"
            r"androidx\.[:\S]*)",
        ),
    ),
    # google() not available on old Gradle
    (
        "google_shorthand_unsupported",
        "google() shorthand requires Gradle 4.0+",
        re.compile(r"Could not find method google\(\)"),
    ),
    # Missing SDK platform
    (
        "missing_sdk_platform",
        "Missing Android SDK platform",
        re.compile(r"failed to find target (android-\d+)"),
    ),
    # Missing build tools
    (
        "missing_build_tools",
        "Missing Android build tools",
        re.compile(r"failed to find Build Tools revision ([\d.]+)"),
    ),
    # Java incompatibility with Gradle (reflection errors)
    (
        "java_gradle_incompatible",
        "Java version incompatible with Gradle",
        re.compile(
            r"IncrementalTaskInputs|ReflectionCache|"
            r"BeanDynamicObject|GroovyRuntimeException|"
            r"Unable to make field.*accessible|"
            r"InaccessibleObjectException"
        ),
    ),
    # Missing dependencies (generic)
    (
        "missing_dependency",
        "Missing dependency (possibly removed from jcenter)",
        re.compile(r"Could not find (\S+)\."),
    ),
    # No SDK (ANDROID_HOME not set)
    (
        "no_android_sdk",
        "Android SDK not found",
        re.compile(r"SDK location not found|ANDROID_HOME|ANDROID_SDK_ROOT"),
    ),
    # compileSdkVersion / targetSdkVersion not installed
    (
        "missing_compile_sdk",
        "compileSdkVersion not installed",
        re.compile(
            r"Compilation target (android-\d+) not found|"
            r"failed to find target with hash string '(android-\d+)'"
        ),
    ),
    # License not accepted
    (
        "license_not_accepted",
        "Android SDK license not accepted",
        re.compile(r"License for package .* not accepted"),
    ),
]


# --------------------------------------------------------------------------- #
#  BuildAgent                                                                  #
# --------------------------------------------------------------------------- #


class BuildAgent:
    """Autonomous agent that builds any Android project with JaCoCo.

    Usage:
        agent = BuildAgent(config)
        result = agent.run()
    """

    def __init__(self, config, *, force: bool = False):
        self.config = config
        self.force = force
        self.profile: ProjectProfile | None = None
        self._log: list[str] = []

    # ----- public API ------------------------------------------------------ #

    def run(self) -> dict[str, bool]:
        """Run the full autonomous build pipeline.

        Returns dict compatible with run_setup():
            {"apk_built", "classfiles_copied", "jacococli_downloaded"}
        """
        results = {
            "apk_built": False,
            "classfiles_copied": False,
            "jacococli_downloaded": False,
        }

        console.print(
            Panel.fit(
                f"[bold cyan]Build Agent[/bold cyan]  {self.config.package_name}\n"
                f"[dim]Autonomous build with auto-fix (max {MAX_RETRIES} retries)[/dim]",
                border_style="cyan",
            )
        )

        # Step 1: Download jacococli (independent)
        if download_jacococli(force=self.force):
            results["jacococli_downloaded"] = True

        # Step 2: Resolve source code
        if not self.config.source_code:
            self._log_step("No source_code configured, skipping build")
            return results

        source_dir = resolve_source_dir(self.config.source_code)
        if not source_dir:
            return results

        project_dir = find_gradle_project(source_dir)
        if not project_dir:
            return results

        # Step 3: Profile the project
        self.profile = self._analyze_project(project_dir)
        self._print_profile()

        # Step 4: Pre-build environment setup
        self._setup_environment()

        # Step 5: Instrument for JaCoCo
        instrument_source_code(project_dir, self.config.package_name)

        # Step 6: Build with retry loop
        build_result = self._build_with_retry()
        if build_result.success:
            results["apk_built"] = True

            # Step 7: Copy classfiles
            if copy_classfiles(project_dir, self.config.package_name, force=self.force):
                results["classfiles_copied"] = True

        # Summary
        self._print_summary(results)
        return results

    # ----- project analysis ------------------------------------------------ #

    def _analyze_project(self, project_dir: Path) -> ProjectProfile:
        """Build a complete profile of the project."""
        pkg = self.config.package_name
        apk = self.config.apk_name

        profile = ProjectProfile(
            project_dir=project_dir,
            package_name=pkg,
            apk_name=apk,
        )

        # AGP version
        profile.agp_version = _parse_agp_version(project_dir)
        if profile.agp_version:
            compat = _gradle_for_agp(profile.agp_version)
            if compat:
                profile.recommended_gradle, profile.recommended_java = compat

        # Current versions
        profile.current_java = _parse_java_version()
        profile.current_gradle = _parse_gradle_version(project_dir)
        profile.android_home = _find_android_home()

        return profile

    def _print_profile(self):
        """Display project profile."""
        p = self.profile
        console.print("\n  [bold]Project Profile[/]")
        console.print(f"    AGP:              {p.agp_version or 'unknown'}")
        console.print(f"    Gradle (wrapper): {p.current_gradle or 'none'}")
        console.print(f"    Gradle (needed):  {p.recommended_gradle or 'unknown'}")
        console.print(f"    Java (current):   {p.current_java or 'not found'}")
        console.print(f"    Java (needed):    {p.recommended_java or 'unknown'}")
        console.print(f"    Android SDK:      {p.android_home or 'not found'}")

    # ----- environment setup ----------------------------------------------- #

    def _setup_environment(self):
        """Pre-build: ensure Java, Gradle, SDK are correct."""
        p = self.profile

        # 1. Ensure correct Java version
        if p.recommended_java and p.current_java:
            if p.current_java > p.recommended_java:
                self._switch_java(p.recommended_java)
            elif p.current_java < p.recommended_java:
                # Lower Java is usually fine unless it's too old
                self._log_step(
                    f"Java {p.current_java} < recommended {p.recommended_java} "
                    f"(usually OK for older projects)"
                )

        # 2. Ensure Gradle wrapper
        if not p.current_gradle and p.recommended_gradle:
            self._log_step(f"Generating Gradle {p.recommended_gradle} wrapper")
            _generate_gradle_wrapper(p.project_dir, p.recommended_gradle)
            p.current_gradle = _parse_gradle_version(p.project_dir)

        # 3. Fix repositories
        self._fix_repositories()

        # 4. Write local.properties
        if p.android_home:
            local_props = p.project_dir / "local.properties"
            local_props.write_text(f"sdk.dir={p.android_home}\n")

    def _fix_repositories(self):
        """Ensure google(), mavenCentral(), jitpack are in build.gradle."""
        p = self.profile
        _ensure_maven_central(p.project_dir)

        # Also add JitPack for libraries only available there
        root_gradle = p.project_dir / "build.gradle"
        if root_gradle.exists():
            text = root_gradle.read_text(encoding="utf-8")
            if "jitpack.io" not in text and "allprojects" in text:
                text = text.replace(
                    "jcenter()",
                    "jcenter()\n        maven { url 'https://jitpack.io' }",
                )
                root_gradle.write_text(text, encoding="utf-8")
                self._log_step("Added JitPack repository")

    # ----- build with retry ------------------------------------------------ #

    def _build_with_retry(self) -> BuildResult:
        """Try building, diagnose failures, apply fixes, retry."""
        p = self.profile

        for attempt in range(1, MAX_RETRIES + 1):
            console.print(f"\n  [bold]Build attempt {attempt}/{MAX_RETRIES}[/]")

            result = self._try_build()

            if result.success:
                console.print("  [bold green]Build successful![/]")
                return result

            # Diagnose
            diagnosis, fix_id = self._diagnose(result.error_output)
            result.diagnosis = diagnosis

            if not fix_id:
                console.print("  [red]Build failed. Could not auto-diagnose.[/]")
                self._show_error_tail(result.error_output)
                return result

            if fix_id in p.applied_fixes:
                console.print(
                    f"  [red]Fix '{fix_id}' already applied. Stopping to avoid infinite loop.[/]"
                )
                self._show_error_tail(result.error_output)
                return result

            # Apply fix
            console.print(f"  [yellow]Diagnosis:[/] {diagnosis}")
            fixed = self._apply_fix(fix_id, result.error_output)
            if fixed:
                p.applied_fixes.add(fix_id)
                result.fix_applied = fix_id
                console.print(f"  [green]Fix applied:[/] {fix_id}")
            else:
                console.print(f"  [red]Could not apply fix: {fix_id}[/]")
                return result

        console.print(f"  [red]Max retries ({MAX_RETRIES}) reached.[/]")
        return BuildResult(success=False)

    def _try_build(self) -> BuildResult:
        """Execute a single build attempt."""
        p = self.profile
        target = APKS_DIR / p.apk_name

        if target.exists() and not self.force:
            console.print(f"  [dim]APK already exists: {target.name}[/]")
            return BuildResult(success=True, apk_path=target)

        # Determine build command
        gradlew = p.project_dir / "gradlew"
        if gradlew.exists():
            gradlew.chmod(gradlew.stat().st_mode | 0o111)
            build_cmd = [str(gradlew), "assembleDebug"]
        else:
            system_gradle = shutil.which("gradle")
            if not system_gradle:
                return BuildResult(
                    success=False,
                    error_output="No gradlew and no system gradle found",
                )
            build_cmd = [system_gradle, "assembleDebug"]

        console.print(f"  [dim]Running: {' '.join(build_cmd[:2])}...[/]")

        env = os.environ.copy()
        if p.android_home:
            env["ANDROID_HOME"] = p.android_home
            env["ANDROID_SDK_ROOT"] = p.android_home

        result = subprocess.run(
            build_cmd,
            cwd=p.project_dir,
            capture_output=True,
            text=True,
            env=env,
        )

        if result.returncode == 0:
            # Find and copy APK
            apk_output_dir = p.project_dir / "app" / "build" / "outputs" / "apk"
            apk_files = list(apk_output_dir.rglob("*debug*.apk"))
            if apk_files:
                APKS_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(apk_files[0], target)
                console.print(f"  [green]APK copied to {target}[/]")
                return BuildResult(success=True, apk_path=target)
            return BuildResult(
                success=False,
                error_output="Build succeeded but no debug APK found in output",
            )

        output = (result.stderr + "\n" + result.stdout).strip()
        return BuildResult(success=False, error_output=output)

    # ----- diagnosis ------------------------------------------------------- #

    def _diagnose(self, output: str) -> tuple[str, str | None]:
        """Analyze build output and return (human description, fix_id)."""
        for fix_id, description, pattern in _ERROR_PATTERNS:
            m = pattern.search(output)
            if m:
                detail = m.group(0)
                return f"{description}: {detail}", fix_id
        return "Unknown build error", None

    # ----- fixes ----------------------------------------------------------- #

    def _apply_fix(self, fix_id: str, output: str) -> bool:
        """Apply a specific fix. Returns True if the fix was applied."""
        dispatch = {
            "missing_google_repo": self._fix_missing_google_repo,
            "google_shorthand_unsupported": self._fix_google_shorthand,
            "missing_sdk_platform": self._fix_missing_sdk,
            "missing_build_tools": self._fix_missing_sdk,
            "missing_compile_sdk": self._fix_missing_sdk,
            "java_gradle_incompatible": self._fix_java_version,
            "missing_dependency": self._fix_missing_dependency,
            "no_android_sdk": self._fix_no_sdk,
            "license_not_accepted": self._fix_license,
        }
        handler = dispatch.get(fix_id)
        if not handler:
            return False
        return handler(output)

    def _fix_missing_google_repo(self, output: str) -> bool:
        """Add Google Maven repository."""
        p = self.profile
        root_gradle = p.project_dir / "build.gradle"
        if not root_gradle.exists():
            return False

        text = root_gradle.read_text(encoding="utf-8")
        if "maven.google.com" in text or "google()" in text:
            return False  # already present, error is something else

        # Determine syntax based on Gradle version
        gradle_major = 0
        if p.current_gradle:
            try:
                gradle_major = int(p.current_gradle.split(".")[0])
            except ValueError:
                pass

        if gradle_major < 4:
            google_line = "maven { url 'https://maven.google.com' }"
        else:
            google_line = "google()"

        # Insert before jcenter() or mavenCentral()
        for anchor in ["jcenter()", "mavenCentral()"]:
            if anchor in text:
                text = text.replace(anchor, f"{google_line}\n        {anchor}")
                break
        else:
            return False

        root_gradle.write_text(text, encoding="utf-8")
        self._log_step(f"Added {google_line} to build.gradle")
        return True

    def _fix_google_shorthand(self, output: str) -> bool:
        """Replace google() with maven URL for old Gradle versions."""
        p = self.profile
        root_gradle = p.project_dir / "build.gradle"
        if not root_gradle.exists():
            return False

        text = root_gradle.read_text(encoding="utf-8")
        if "google()" not in text:
            return False

        text = text.replace(
            "google()",
            "maven { url 'https://maven.google.com' }",
        )
        root_gradle.write_text(text, encoding="utf-8")
        self._log_step("Replaced google() with maven URL (Gradle < 4.0)")
        return True

    def _fix_missing_sdk(self, output: str) -> bool:
        """Install missing SDK platforms and build tools via sdkmanager."""
        installs = []

        # Platforms
        for m in re.finditer(
            r"(?:failed to find target|hash string) '?(android-\d+)'?",
            output,
        ):
            installs.append(f"platforms;{m.group(1)}")

        # Build tools
        for m in re.finditer(
            r"failed to find Build Tools revision ([\d.]+)",
            output,
        ):
            installs.append(f"build-tools;{m.group(1)}")

        if not installs:
            return False

        sdkmanager = self._find_sdkmanager()
        if not sdkmanager:
            console.print(
                "  [yellow]sdkmanager not found. Install components manually:[/]\n"
                f"  [cyan]sdkmanager {' '.join(installs)}[/]"
            )
            return False

        # sdkmanager needs Java 17+; temporarily switch if needed
        current_java = _parse_java_version()
        need_switch = current_java and current_java < 17

        if need_switch:
            console.print("  [dim]sdkmanager requires Java 17+, switching temporarily...[/]")
            old_java_home = os.environ.get("JAVA_HOME")
            if not self._switch_java(17, temporary=True):
                console.print(
                    "  [yellow]Cannot switch to Java 17 for sdkmanager. "
                    "Install SDK components manually:[/]\n"
                    f"  [cyan]sdkmanager {' '.join(installs)}[/]"
                )
                return False

        console.print(f"  [dim]Installing SDK components: {', '.join(installs)}[/]")

        success = True
        for component in installs:
            result = subprocess.run(
                [sdkmanager, "--install", component],
                capture_output=True,
                text=True,
                input="y\n" * 10,  # accept licenses
                timeout=300,
            )
            if result.returncode != 0:
                console.print(f"  [red]Failed to install {component}[/]")
                logger.warning("sdkmanager error: %s", result.stderr[-300:])
                success = False
            else:
                console.print(f"  [green]Installed {component}[/]")

        # Switch Java back if we changed it
        if need_switch and self.profile.recommended_java:
            self._switch_java(self.profile.recommended_java)

        return success

    def _fix_java_version(self, output: str) -> bool:
        """Switch to the recommended Java version."""
        p = self.profile
        target = p.recommended_java
        if not target:
            # Try to infer from Gradle version
            if p.current_gradle:
                target = _max_java_for_gradle(p.current_gradle)
        if not target:
            return False
        return self._switch_java(target)

    def _fix_missing_dependency(self, output: str) -> bool:
        """Try to fix missing dependencies by adding repositories."""
        p = self.profile
        root_gradle = p.project_dir / "build.gradle"
        if not root_gradle.exists():
            return False

        text = root_gradle.read_text(encoding="utf-8")
        changed = False

        # Add JitPack if not present
        if "jitpack.io" not in text:
            for anchor in ["jcenter()", "mavenCentral()"]:
                if anchor in text:
                    text = text.replace(
                        anchor,
                        f"{anchor}\n        maven {{ url 'https://jitpack.io' }}",
                    )
                    changed = True
                    self._log_step("Added JitPack repository")
                    break

        # Add Google Maven if not present
        if "maven.google.com" not in text and "google()" not in text:
            gradle_major = 0
            if p.current_gradle:
                try:
                    gradle_major = int(p.current_gradle.split(".")[0])
                except ValueError:
                    pass
            google_line = (
                "maven { url 'https://maven.google.com' }" if gradle_major < 4 else "google()"
            )
            for anchor in ["jcenter()", "mavenCentral()"]:
                if anchor in text:
                    text = text.replace(anchor, f"{google_line}\n        {anchor}")
                    changed = True
                    self._log_step("Added Google Maven repository")
                    break

        if changed:
            root_gradle.write_text(text, encoding="utf-8")

        # Report unfixable dependencies
        missing = re.findall(r"Could not find (\S+)\.", output)
        if missing:
            unfixable = [
                dep
                for dep in dict.fromkeys(missing)
                if not dep.startswith("com.android.") and not dep.startswith("androidx.")
            ]
            if unfixable and not changed:
                console.print("  [yellow]Dependencies that may need manual fixes:[/]")
                for dep in unfixable:
                    console.print(f"    [dim]- {dep}[/]")
                console.print(
                    "  [dim]Try searching on https://jitpack.io or https://search.maven.org[/]"
                )

        return changed

    def _fix_no_sdk(self, output: str) -> bool:
        """Try to find and set ANDROID_HOME."""
        android_home = _find_android_home()
        if android_home:
            self.profile.android_home = android_home
            local_props = self.profile.project_dir / "local.properties"
            local_props.write_text(f"sdk.dir={android_home}\n")
            return True
        console.print("  [red]Android SDK not found. Install it and set ANDROID_HOME.[/]")
        return False

    def _fix_license(self, output: str) -> bool:
        """Accept SDK licenses."""
        sdkmanager = self._find_sdkmanager()
        if not sdkmanager:
            return False
        result = subprocess.run(
            [sdkmanager, "--licenses"],
            capture_output=True,
            text=True,
            input="y\n" * 20,
            timeout=60,
        )
        return result.returncode == 0

    # ----- tooling helpers ------------------------------------------------- #

    def _switch_java(self, target_major: int, *, temporary: bool = False) -> bool:
        """Switch Java version using asdf.

        Args:
            target_major: Target Java major version (8, 11, 17, 21).
            temporary: If True, only set env vars, don't persist.

        Returns True if switch succeeded.
        """
        asdf = shutil.which("asdf")
        if not asdf:
            console.print(f"  [yellow]asdf not found. Install Java {target_major} manually.[/]")
            return False

        # Check if target version is already installed
        installed = self._asdf_list_java()
        target_id = self._find_java_id(installed, target_major)

        if not target_id:
            # Try to install
            target_id = self._asdf_install_java(target_major)
            if not target_id:
                return False

        # Set the version
        if temporary:
            # Only set JAVA_HOME for subprocess calls
            result = subprocess.run(
                [asdf, "where", "java", target_id],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                java_home = result.stdout.strip()
                os.environ["JAVA_HOME"] = java_home
                os.environ["PATH"] = f"{java_home}/bin:{os.environ.get('PATH', '')}"
                console.print(f"  [dim]Temporarily set JAVA_HOME={java_home}[/]")
                return True
            return False

        # Persistent project-level switch
        result = subprocess.run(
            [asdf, "set", "-p", "java", target_id],
            capture_output=True,
            text=True,
            cwd=self.profile.project_dir if self.profile else None,
        )
        if result.returncode == 0:
            # Also update JAVA_HOME for current process
            where_result = subprocess.run(
                [asdf, "where", "java", target_id],
                capture_output=True,
                text=True,
            )
            if where_result.returncode == 0:
                java_home = where_result.stdout.strip()
                os.environ["JAVA_HOME"] = java_home
                os.environ["PATH"] = f"{java_home}/bin:{os.environ.get('PATH', '')}"

            self.profile.current_java = target_major
            console.print(f"  [green]Switched to Java {target_id}[/]")
            return True

        console.print(f"  [red]Failed to switch Java: {result.stderr}[/]")
        return False

    def _asdf_list_java(self) -> list[str]:
        """List installed Java versions via asdf."""
        asdf = shutil.which("asdf")
        if not asdf:
            return []
        result = subprocess.run(
            [asdf, "list", "java"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        # Parse output: each line like "  temurin-17.0.13+11" or " *temurin-17.0.13+11"
        versions = []
        for line in result.stdout.splitlines():
            v = line.strip().lstrip("*").strip()
            if v:
                versions.append(v)
        return versions

    def _find_java_id(self, installed: list[str], major: int) -> str | None:
        """Find an installed Java version matching the target major."""
        for v in installed:
            if self._java_id_major(v) == major:
                return v
        return None

    @staticmethod
    def _java_id_major(java_id: str) -> int | None:
        """Extract major version from asdf Java ID like 'temurin-17.0.13+11'."""
        m = re.search(r"-(\d+)\.", java_id)
        if m:
            major = int(m.group(1))
            return 8 if major == 1 else major  # "1.8" → 8
        # Try format like "corretto-8.422.05.1"
        m = re.search(r"-(\d+)\.\d+", java_id)
        if m:
            return int(m.group(1))
        return None

    def _asdf_install_java(self, major: int) -> str | None:
        """Install a Java version via asdf. Returns the version ID or None."""
        asdf = shutil.which("asdf")
        if not asdf:
            return None

        candidates = _ASDF_JAVA_CANDIDATES.get(major, [])
        if not candidates:
            # Try constructing a generic temurin ID
            candidates = [f"temurin-{major}.0.0+0"]

        for candidate in candidates:
            console.print(f"  [dim]Installing Java {candidate} via asdf...[/]")
            result = subprocess.run(
                [asdf, "install", "java", candidate],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode == 0:
                console.print(f"  [green]Installed Java {candidate}[/]")
                return candidate
            logger.debug(
                "asdf install java %s failed: %s",
                candidate,
                result.stderr[:200],
            )

        console.print(
            f"  [red]Could not install Java {major} via asdf.[/]\n"
            f"  [cyan]Try: asdf list-all java | grep temurin-{major}[/]"
        )
        return None

    def _find_sdkmanager(self) -> str | None:
        """Find sdkmanager binary."""
        # Check PATH first
        sdkmanager = shutil.which("sdkmanager")
        if sdkmanager:
            return sdkmanager

        # Check inside ANDROID_HOME
        android_home = self.profile.android_home if self.profile else None
        if not android_home:
            android_home = _find_android_home()
        if android_home:
            for subdir in ["cmdline-tools/latest/bin", "tools/bin"]:
                candidate = Path(android_home) / subdir / "sdkmanager"
                if candidate.exists():
                    return str(candidate)
        return None

    # ----- logging --------------------------------------------------------- #

    def _log_step(self, message: str):
        """Log and display a build agent step."""
        self._log.append(message)
        console.print(f"  [dim]{message}[/]")

    def _show_error_tail(self, output: str, lines: int = 30):
        """Show last N lines of build output."""
        all_lines = output.splitlines()
        if len(all_lines) > lines:
            console.print(f"  [dim]... ({len(all_lines) - lines} lines omitted)[/]")
        for line in all_lines[-lines:]:
            console.print(f"  [dim]{line}[/]")

    def _print_summary(self, results: dict[str, bool]):
        """Print final summary."""
        icons = {True: "[green]OK[/]", False: "[red]FAIL[/]"}
        console.print("\n  [bold]Build Agent Summary[/]")
        for key, ok in results.items():
            console.print(f"    {key}: {icons[ok]}")
        if self._log:
            console.print(f"\n  [bold]Actions taken ({len(self._log)}):[/]")
            for step in self._log:
                console.print(f"    [dim]- {step}[/]")


# --------------------------------------------------------------------------- #
#  Convenience entry point (replaces run_setup for agents)                     #
# --------------------------------------------------------------------------- #


def agent_setup(config, *, force: bool = False) -> dict[str, bool]:
    """Run the autonomous build agent for a single app config.

    Drop-in replacement for jacoco_setup.run_setup() with auto-fix capability.
    """
    agent = BuildAgent(config, force=force)
    return agent.run()
