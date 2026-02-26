"""Clean command for the RLMobTest CLI."""

import contextlib
from pathlib import Path
from typing import Annotated

import typer

from rlmobtest.cli import OUTPUT_SUBFOLDERS, app, console
from rlmobtest.constants.paths import OUTPUT_BASE


@app.command()
def clean(
    folder: Annotated[
        str | None,
        typer.Argument(
            help="Subfolder to clean (e.g., screenshots). If omitted, cleans all.",
        ),
    ] = None,
    app_name: Annotated[
        str | None,
        typer.Option(
            "--app",
            "-a",
            help="Clean only specific app (e.g., protect.budgetwatch)",
        ),
    ] = None,
    agent: Annotated[
        str | None,
        typer.Option(
            "--agent",
            help="Clean only specific agent type (original/improved)",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="Show what would be deleted without deleting",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Skip confirmation prompt",
        ),
    ] = False,
):
    """
    Clean output folders.

    Output structure: output/{app}/{agent_type}/{year}/{month}/{day}/{subfolder}/

    Examples:
        rlmobtest clean                              # Clean all (with confirmation)
        rlmobtest clean screenshots                  # Clean only screenshots
        rlmobtest clean --app protect.budgetwatch   # Clean specific app
        rlmobtest clean --agent original            # Clean only original agent outputs
        rlmobtest clean --dry-run                   # Show what would be deleted
        rlmobtest clean -f                          # Clean all without confirmation
    """
    import shutil

    # Validate folder name if provided
    if folder and folder not in OUTPUT_SUBFOLDERS:
        console.print(f"[red]Error: '{folder}' is not a valid subfolder[/red]")
        console.print(f"[dim]Valid options: {', '.join(OUTPUT_SUBFOLDERS)}[/dim]")
        raise typer.Exit(code=1)

    # Validate agent type if provided
    if agent and agent not in ["original", "improved"]:
        console.print(f"[red]Error: '{agent}' is not a valid agent type[/red]")
        console.print("[dim]Valid options: original, improved[/dim]")
        raise typer.Exit(code=1)

    if not OUTPUT_BASE.exists():
        console.print("[dim]Nothing to clean - output folder doesn't exist[/dim]")
        return

    if dry_run:
        console.print("[yellow][DRY-RUN] No files will be deleted[/yellow]\n")

    folders_to_clean = [folder] if folder else OUTPUT_SUBFOLDERS

    # Find all matching paths based on filters
    # Structure: output/{app}/{agent_type}/{year}/{month}/{day}/{subfolder}/
    files_to_delete = []
    dirs_to_delete = []

    for app_dir in OUTPUT_BASE.iterdir():
        if not app_dir.is_dir():
            continue
        if app_name and app_dir.name != app_name:
            continue

        for agent_dir in app_dir.iterdir():
            if not agent_dir.is_dir():
                continue
            if agent and agent_dir.name != agent:
                continue

            # Traverse year/month/day structure
            for year_dir in agent_dir.iterdir():
                if not year_dir.is_dir():
                    continue
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue

                        # Find target subfolders
                        for subfolder in folders_to_clean:
                            subfolder_path = day_dir / subfolder
                            if subfolder_path.exists():
                                for item in subfolder_path.rglob("*"):
                                    if item.is_file():
                                        files_to_delete.append(item)
                                dirs_to_delete.append(subfolder_path)

    if not files_to_delete:
        console.print("[dim]Nothing to clean - no matching files found[/dim]")
        return

    # Show filter info
    filter_info = []
    if app_name:
        filter_info.append(f"app={app_name}")
    if agent:
        filter_info.append(f"agent={agent}")
    if folder:
        filter_info.append(f"folder={folder}")
    if filter_info:
        console.print(f"[dim]Filters: {', '.join(filter_info)}[/dim]\n")

    # Confirmation prompt
    if not dry_run and not force:
        confirm = typer.confirm(f"Delete {len(files_to_delete)} files?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(code=0)

    # Delete files
    deleted = 0
    for item in files_to_delete:
        if dry_run:
            # Show relative path for readability
            rel_path = item.relative_to(OUTPUT_BASE)
            console.print(f"  [dim]Would delete: {rel_path}[/dim]")
        else:
            item.unlink()
        deleted += 1

    # Remove empty directories
    if not dry_run:
        for dir_path in sorted(set(dirs_to_delete), reverse=True):
            if dir_path.exists():
                # Remove directory and empty parents
                with contextlib.suppress(OSError):
                    shutil.rmtree(dir_path)

        # Clean up empty date/agent/app directories
        for app_dir in OUTPUT_BASE.iterdir():
            if app_dir.is_dir():
                _remove_empty_dirs(app_dir)

    action = "Would delete" if dry_run else "Deleted"
    console.print(f"\n[bold]{action} {deleted} files[/bold]")


def _remove_empty_dirs(path: Path):
    """Recursively remove empty directories."""
    if not path.is_dir():
        return
    for child in path.iterdir():
        if child.is_dir():
            _remove_empty_dirs(child)
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()
