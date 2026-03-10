"""JaCoCo coverage processing: merge .ec files, generate CSV report, parse metrics."""

import logging
import shutil
import subprocess
from pathlib import Path

import pandas as pd
from rich.console import Console

from rlmobtest.constants.paths import CLASSFILES_DIR, SOURCE_CODES_DIR, TOOLS_DIR

console = Console()
logger = logging.getLogger(__name__)

JACOCOCLI_JAR_NAME = "jacococli.jar"
LEGACY_JAR_NAME = "jacoco-legacy-0.7.4.jar"
LEGACY_REPORT_CLASS = "JacocoLegacyReport"


def find_jacococli() -> Path | None:
    """Find jacococli.jar in inputs/tools/.

    Returns:
        Path to jacococli.jar or None if not found.
    """
    jar_path = TOOLS_DIR / JACOCOCLI_JAR_NAME
    if jar_path.exists():
        return jar_path
    return None


def _find_all_jacococli() -> list[Path]:
    """Find all jacococli JARs in inputs/tools/ (for version fallback).

    Returns the primary jacococli.jar first, then any versioned variants
    like jacococli-0.8.8.jar, sorted newest first.
    """
    jars = []
    primary = TOOLS_DIR / JACOCOCLI_JAR_NAME
    if primary.exists():
        jars.append(primary)
    for jar in sorted(TOOLS_DIR.glob("jacococli-*.jar"), reverse=True):
        jars.append(jar)
    return jars


def _check_java() -> bool:
    """Check if Java is available on the system PATH."""
    return shutil.which("java") is not None


def find_classfiles(package_name: str) -> Path | None:
    """Find classfiles directory for a given package.

    Looks in inputs/classfiles/{package_name}/ for .class files or JARs.

    Returns:
        Path to classfiles directory or None if not found.
    """
    classfiles_dir = CLASSFILES_DIR / package_name
    if not classfiles_dir.exists():
        return None
    has_content = any(classfiles_dir.rglob("*.class")) or any(classfiles_dir.glob("*.jar"))
    return classfiles_dir if has_content else None


def merge_ec_files(coverage_dir: Path, jacococli: Path) -> Path | None:
    """Merge multiple .ec files into a single file.

    Args:
        coverage_dir: Directory containing .ec files.
        jacococli: Path to jacococli.jar.

    Returns:
        Path to the (merged) .ec file, or None if no .ec files found.
    """
    ec_files = sorted(coverage_dir.glob("*.ec"))
    if not ec_files:
        return None

    if len(ec_files) == 1:
        return ec_files[0]

    merged = coverage_dir / "merged.ec"
    cmd = [
        "java", "-jar", str(jacococli),
        "merge",
        *[str(f) for f in ec_files],
        "--destfile", str(merged),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        console.print(f"  [dim]Merged {len(ec_files)} .ec files[/]")
        return merged
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to merge .ec files: %s", e.stderr)
        return ec_files[0]


def generate_csv_report(
    ec_file: Path,
    classfiles_dir: Path,
    output_csv: Path,
    jacococli: Path,
    html_dir: Path | None = None,
    sourcefiles_dir: Path | None = None,
) -> Path | None:
    """Generate JaCoCo CSV (and optionally HTML) report.

    Args:
        ec_file: Path to .ec execution data file.
        classfiles_dir: Path to directory with .class files or JARs.
        output_csv: Path for output CSV file.
        jacococli: Path to jacococli.jar.
        html_dir: Optional directory for HTML report output.
        sourcefiles_dir: Optional path to Java sources (enables source highlighting in HTML).

    Returns:
        Path to generated CSV or None on failure.
    """
    cmd = [
        "java", "-jar", str(jacococli),
        "report", str(ec_file),
        "--classfiles", str(classfiles_dir),
        "--csv", str(output_csv),
    ]
    if html_dir:
        html_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--html", str(html_dir)])
    if sourcefiles_dir and sourcefiles_dir.exists():
        cmd.extend(["--sourcefiles", str(sourcefiles_dir)])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        if html_dir:
            console.print(f"  [green]JaCoCo HTML report: {html_dir}/index.html[/]")
        return output_csv
    except subprocess.CalledProcessError as e:
        logger.warning("Failed to generate JaCoCo report: %s", e.stderr)
        return None


def parse_coverage_csv(csv_path: Path) -> dict[str, float] | None:
    """Parse JaCoCo CSV report and compute coverage percentages.

    JaCoCo CSV columns: GROUP, PACKAGE, CLASS,
    INSTRUCTION_MISSED, INSTRUCTION_COVERED,
    BRANCH_MISSED, BRANCH_COVERED,
    LINE_MISSED, LINE_COVERED,
    COMPLEXITY_MISSED, COMPLEXITY_COVERED,
    METHOD_MISSED, METHOD_COVERED

    Returns:
        Dict with line_pct, branch_pct, method_pct or None on failure.
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        logger.warning("Failed to read JaCoCo CSV: %s", csv_path)
        return None

    if df.empty:
        return None

    def _pct(missed_col: str, covered_col: str) -> float:
        missed = df[missed_col].sum()
        covered = df[covered_col].sum()
        total = missed + covered
        return round(covered / total * 100, 1) if total > 0 else 0.0

    return {
        "line_pct": _pct("LINE_MISSED", "LINE_COVERED"),
        "branch_pct": _pct("BRANCH_MISSED", "BRANCH_COVERED"),
        "method_pct": _pct("METHOD_MISSED", "METHOD_COVERED"),
    }


def _find_legacy_tools() -> tuple[Path, Path] | None:
    """Find legacy JaCoCo tools (0.7.4 jar + compiled report class).

    Returns:
        Tuple of (legacy_jar, tools_dir) or None if not available.
    """
    legacy_jar = TOOLS_DIR / LEGACY_JAR_NAME
    legacy_class = TOOLS_DIR / f"{LEGACY_REPORT_CLASS}.class"
    if legacy_jar.exists() and legacy_class.exists():
        return legacy_jar, TOOLS_DIR
    return None


def _generate_legacy_report(
    coverage_dir: Path,
    classfiles_dir: Path,
    output_csv: Path,
    html_dir: Path | None = None,
    sourcefiles_dir: Path | None = None,
) -> Path | None:
    """Generate coverage report using legacy JaCoCo 0.7.4 tool (format 0x1006).

    Falls back to this when modern jacococli fails with IncompatibleExecDataVersionException.
    """
    legacy = _find_legacy_tools()
    if not legacy:
        logger.debug("Legacy JaCoCo tools not found in %s", TOOLS_DIR)
        return None

    legacy_jar, tools_dir = legacy
    # Build classpath: legacy jar + directory containing .class file
    sep = ":" if shutil.which("cmd") is None else ";"
    classpath = f"{legacy_jar}{sep}{tools_dir}"

    cmd = [
        "java", "-cp", classpath,
        LEGACY_REPORT_CLASS,
        "--ecdir", str(coverage_dir),
        "--classfiles", str(classfiles_dir),
        "--csv", str(output_csv),
    ]
    if html_dir:
        html_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--html", str(html_dir)])
    if sourcefiles_dir and sourcefiles_dir.exists():
        cmd.extend(["--sourcefiles", str(sourcefiles_dir)])

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        console.print("  [dim]Used legacy JaCoCo 0.7.4 (format 0x1006)[/]")
        if html_dir:
            console.print(f"  [green]JaCoCo HTML report: {html_dir}/index.html[/]")
        return output_csv if output_csv.exists() else None
    except subprocess.CalledProcessError as e:
        logger.warning("Legacy JaCoCo report failed: %s", e.stderr)
        return None


def _resolve_sourcefiles(source_code: str) -> Path | None:
    """Resolve source code config to Java sourcefiles directory."""
    from rlmobtest.utils.jacoco_setup import find_gradle_project, resolve_source_dir

    source_dir = resolve_source_dir(source_code)
    if not source_dir:
        return None
    project_dir = find_gradle_project(source_dir)
    if not project_dir:
        return None
    src_main = project_dir / "app" / "src" / "main" / "java"
    return src_main if src_main.exists() else None


def process_coverage(
    coverage_dir: Path,
    package_name: str,
    html_report: bool = False,
    source_code: str | None = None,
) -> dict[str, float] | None:
    """Process JaCoCo coverage data end-to-end.

    1. Find jacococli.jar
    2. Find classfiles for the package
    3. Merge .ec files
    4. Generate CSV report (and optionally HTML)
    5. Parse and return coverage percentages

    Args:
        coverage_dir: Directory containing .ec files.
        package_name: Android package name (for classfiles lookup).
        html_report: If True, also generate HTML report in coverage_dir/jacoco_html/.
        source_code: Source code config value (for source-annotated HTML).

    Returns:
        Dict with line_pct, branch_pct, method_pct or None if any step fails.
    """
    # Check prerequisites
    all_jars = _find_all_jacococli()
    has_legacy = _find_legacy_tools() is not None
    if not all_jars and not has_legacy:
        logger.debug("No jacococli.jar or legacy tools found in %s", TOOLS_DIR)
        return None

    if not _check_java():
        console.print("[yellow]Java not found. Required for JaCoCo coverage processing.[/]")
        return None

    classfiles = find_classfiles(package_name)
    if not classfiles:
        logger.debug("No classfiles found for %s in %s", package_name, CLASSFILES_DIR)
        return None

    # Resolve optional params for HTML report
    html_dir = (coverage_dir / "jacoco_html") if html_report else None
    sourcefiles_dir = _resolve_sourcefiles(source_code) if source_code else None

    # Try each jacococli version (handles exec data version mismatches)
    result_csv = None
    for jacococli in (all_jars or []):
        # Merge .ec files
        ec_file = merge_ec_files(coverage_dir, jacococli)
        if not ec_file:
            return None

        # Generate CSV + optional HTML report
        csv_path = coverage_dir / "coverage_report.csv"
        result_csv = generate_csv_report(
            ec_file, classfiles, csv_path, jacococli,
            html_dir=html_dir,
            sourcefiles_dir=sourcefiles_dir,
        )
        if result_csv:
            if jacococli.name != JACOCOCLI_JAR_NAME:
                console.print(f"  [dim]Used fallback: {jacococli.name}[/]")
            break
        # Clean up merged.ec from failed attempt before retrying
        merged = coverage_dir / "merged.ec"
        if merged.exists():
            merged.unlink()

    # Fallback: try legacy JaCoCo 0.7.4 for old format (0x1006) .ec files
    if not result_csv:
        console.print("  [yellow]Modern jacococli failed — trying legacy JaCoCo 0.7.4...[/]")
        csv_path = coverage_dir / "coverage_report.csv"
        result_csv = _generate_legacy_report(
            coverage_dir, classfiles, csv_path,
            html_dir=html_dir,
            sourcefiles_dir=sourcefiles_dir,
        )

    if not result_csv:
        return None

    # Parse and return
    metrics = parse_coverage_csv(result_csv)
    if metrics:
        console.print(
            f"  [green]JaCoCo:[/] Line={metrics['line_pct']}% "
            f"Branch={metrics['branch_pct']}% "
            f"Method={metrics['method_pct']}%"
        )
    return metrics
