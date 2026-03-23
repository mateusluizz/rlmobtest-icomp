"""Extract app context from source code archives for transcription enrichment.

Parses AndroidManifest.xml, layout XMLs, and strings.xml from source code
archives to produce a concise text summary that helps LLMs generate
more user-friendly test cases.
"""

import logging
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_CODES_DIR = BASE_DIR / "inputs" / "source_codes"

ANDROID_NS = "http://schemas.android.com/apk/res/android"


def extract_xml_contents(archive_path: Path) -> list[tuple[str, str]]:
    """Read all XML files from a zip or tar.gz archive.

    Returns:
        List of (filename, text_content) pairs.
    """
    results: list[tuple[str, str]] = []
    name = archive_path.name.lower()

    if name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.isfile() and member.name.endswith(".xml"):
                    f = tar.extractfile(member)
                    if f is not None:
                        results.append((member.name, f.read().decode("utf-8", errors="ignore")))
    else:
        with zipfile.ZipFile(archive_path, "r") as z:
            for entry in z.namelist():
                if entry.endswith(".xml"):
                    with z.open(entry) as f:
                        results.append((entry, f.read().decode("utf-8", errors="ignore")))

    return results


def _parse_strings_xml(xml_contents: list[tuple[str, str]]) -> dict[str, str]:
    """Parse res/values/strings.xml (default locale) into a name→value dict."""
    strings: dict[str, str] = {}
    for filename, content in xml_contents:
        if re.search(r"res/values/strings\.xml$", filename):
            try:
                root = ET.fromstring(content)
                for elem in root.findall("string"):
                    name = elem.get("name")
                    text = "".join(elem.itertext()).strip()
                    if name and text:
                        strings[name] = text
            except ET.ParseError:
                logger.warning("Failed to parse strings.xml: %s", filename)
    return strings


def _resolve_string_ref(ref: str, strings: dict[str, str]) -> str:
    """Resolve @string/name reference to its value, or return as-is."""
    if ref and ref.startswith("@string/"):
        key = ref[len("@string/") :]
        return strings.get(key, ref)
    return ref or ""


def _parse_manifest(xml_contents: list[tuple[str, str]], strings: dict[str, str]) -> dict[str, str]:
    """Parse AndroidManifest.xml to build activity_name → label mapping."""
    activity_labels: dict[str, str] = {}
    for filename, content in xml_contents:
        if filename.endswith("AndroidManifest.xml"):
            try:
                root = ET.fromstring(content)
                app_elem = root.find("application")
                if app_elem is None:
                    continue
                for activity in app_elem.findall("activity"):
                    name = activity.get(f"{{{ANDROID_NS}}}name", "")
                    label_ref = activity.get(f"{{{ANDROID_NS}}}label", "")
                    label = _resolve_string_ref(label_ref, strings)
                    if name:
                        activity_labels[name] = label
            except ET.ParseError:
                logger.warning("Failed to parse manifest: %s", filename)
    return activity_labels


def _parse_layout_xmls(
    xml_contents: list[tuple[str, str]], strings: dict[str, str]
) -> dict[str, list[dict[str, str]]]:
    """Parse res/layout/*.xml files to extract UI component info.

    Returns:
        Dict mapping layout name (e.g. "activity_accounts") to a list of
        component dicts with keys: id, type, hint, text.
    """
    layouts: dict[str, list[dict[str, str]]] = {}
    for filename, content in xml_contents:
        match = re.search(r"res/layout/([\w]+)\.xml$", filename)
        if not match:
            continue
        layout_name = match.group(1)
        components: list[dict[str, str]] = []
        try:
            root = ET.fromstring(content)
            for elem in root.iter():
                widget_id = elem.get(f"{{{ANDROID_NS}}}id", "")
                if not widget_id:
                    continue
                short_id = widget_id.replace("@+id/", "").replace("@id/", "")
                tag = elem.tag.split(".")[-1] if "." in elem.tag else elem.tag
                hint = _resolve_string_ref(elem.get(f"{{{ANDROID_NS}}}hint", ""), strings)
                text = _resolve_string_ref(elem.get(f"{{{ANDROID_NS}}}text", ""), strings)

                comp: dict[str, str] = {"id": short_id, "type": tag}
                if hint:
                    comp["hint"] = hint
                if text:
                    comp["text"] = text
                components.append(comp)
        except ET.ParseError:
            logger.warning("Failed to parse layout: %s", filename)

        if components:
            layouts[layout_name] = components

    return layouts


def _format_app_context(
    package_name: str,
    activity_labels: dict[str, str],
    layouts: dict[str, list[dict[str, str]]],
) -> str:
    """Format parsed data into a concise text block for LLM consumption."""
    lines = [f"## App Context: {package_name}", ""]

    if activity_labels:
        lines.append("### Screens (Activities)")
        for name, label in sorted(activity_labels.items()):
            display = f'"{label}"' if label else "(no label)"
            lines.append(f"- {name} = {display}")
        lines.append("")

    # Only include activity_* and dialog_* layouts (skip menu, drawable, etc.)
    activity_layouts = {
        k: v for k, v in layouts.items() if k.startswith("activity_") or k.startswith("dialog_")
    }
    if activity_layouts:
        lines.append("### Screen Components")
        for layout_name, components in sorted(activity_layouts.items()):
            screen_label = layout_name.replace("activity_", "").replace("_", " ").title()
            lines.append(f"**{screen_label}** ({layout_name}.xml):")
            for comp in components:
                parts = [f'{comp["type"]} id="{comp["id"]}"']
                if comp.get("hint"):
                    parts.append(f'hint="{comp["hint"]}"')
                if comp.get("text"):
                    parts.append(f'text="{comp["text"]}"')
                lines.append(f"  - {' | '.join(parts)}")
            lines.append("")

    return "\n".join(lines)


def build_app_context(
    source_code: str,
    package_name: str,
    source_codes_dir: Path = SOURCE_CODES_DIR,
) -> str | None:
    """Build an app context string from source code archive.

    Args:
        source_code: Archive filename (e.g., "open_money_tracker-dev.zip")
        package_name: Android package name
        source_codes_dir: Directory containing source code archives

    Returns:
        Formatted context string, or None if source code is unavailable.
    """
    if not source_code:
        return None

    archive_path = source_codes_dir / source_code
    if not archive_path.exists():
        logger.warning("Source code archive not found: %s", archive_path)
        return None

    try:
        xml_contents = extract_xml_contents(archive_path)
    except Exception:
        logger.exception("Failed to read archive: %s", archive_path)
        return None

    strings = _parse_strings_xml(xml_contents)
    activity_labels = _parse_manifest(xml_contents, strings)
    layouts = _parse_layout_xmls(xml_contents, strings)

    context = _format_app_context(package_name, activity_labels, layouts)

    logger.info(
        "App context built: %d activities, %d layouts, %d chars",
        len(activity_labels),
        len(layouts),
        len(context),
    )
    return context
