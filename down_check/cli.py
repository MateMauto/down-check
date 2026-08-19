"""down-check — is it you, or is the service down?"""
from __future__ import annotations

import asyncio
from typing import Annotated

import questionary
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from down_check.catalog import (
    by_category,
    load_catalog,
    load_selection,
    save_selection,
    selected_services,
)
from down_check.checks import Result, Status, check_all, check_reports

app = typer.Typer(
    name="down-check",
    help="Check the status of the services you care about.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)

console = Console()


@app.command("list")
def list_services() -> None:
    """Pick the services you care about. Type to search, space toggles, Enter saves."""
    catalog = load_catalog()
    already = set(load_selection())

    choices: list[questionary.Choice | questionary.Separator] = []
    for category, services in by_category(catalog).items():
        choices.append(questionary.Separator(f"── {category} ──"))
        choices += [
            questionary.Choice(title=s.name, value=s.id, checked=s.id in already)
            for s in services
        ]

    picked = questionary.checkbox(
        "Services to check:",
        choices=choices,
        # Typing filters the list by name — the catalog is too long to arrow through.
        use_search_filter=True,
        use_jk_keys=False,  # j/k would be swallowed by the filter
        instruction="(type to search · ↑↓ move · space toggles · enter saves)",
    ).ask()
    if picked is None:  # Ctrl-C
        console.print("[dim]Cancelled — selection unchanged.[/dim]")
        raise typer.Exit(0)

    save_selection(picked)
    if picked:
        names = ", ".join(s.name for s in catalog if s.id in set(picked))
        console.print(f"[green]✓[/green] Saved {len(picked)}: {names}")
    else:
        console.print("[yellow]Nothing selected.[/yellow] Run it again to pick some.")


@app.command()
def check(
    reports: Annotated[
        bool,
        typer.Option(
            "--reports",
            "-r",
            help="Skip status pages, go straight to user reports.",
        ),
    ] = False,
) -> None:
    """Check your selected services. Anything not OK is cross-checked against user reports."""
    services = selected_services()
    if not services:
        console.print(
            "[yellow]No services selected.[/yellow] "
            "Run [bold]down-check list[/bold] first."
        )
        raise typer.Exit(1)

    if reports:
        with console.status(f"Checking user reports for {len(services)} service(s)…"):
            results = asyncio.run(check_reports(services))
        _render(results)
        _render_links(results)
        return

    with console.status(f"Checking {len(services)} service(s)…"):
        results = asyncio.run(check_all(services))
    _render(results)

    problems = [r.service for r in results if r.is_problem]
    if not problems:
        return

    with console.status("Cross-checking user reports…"):
        fallback = asyncio.run(check_reports(problems))
    if any(r.status is not Status.UNKNOWN for r in fallback):
        _render(fallback)
    else:
        console.print("[dim]No user reports available for these.[/dim]\n")
    _render_links(fallback)


def _render(results: list[Result]) -> None:
    table = Table(box=None, pad_edge=False, padding=(0, 2, 0, 0))
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")

    for result in results:
        label = f"{result.status.icon} {result.status.value.upper()}"
        badge = Text(label, style=result.status.style)
        table.add_row(result.service.name, badge, Text(result.detail, style="dim"))

    counts = {status: sum(r.status is status for r in results) for status in Status}
    summary = "  ·  ".join(
        f"[{status.style}]{count} {status.value}[/{status.style}]"
        for status, count in counts.items()
        if count
    )
    source = results[0].source if results else "status page"

    console.print()
    console.print(table)
    console.print(f"\n{summary}  [dim]({source})[/dim]\n")


def _render_links(results: list[Result]) -> None:
    """Print where to look next for anything that is not clearly OK."""
    unresolved = [r for r in results if r.status is not Status.OK]
    if not unresolved:
        return

    table = Table(box=None, pad_edge=False, padding=(0, 2, 0, 0), show_header=False)
    table.add_column(style="bold")
    table.add_column(style="blue", overflow="ignore")
    for result in unresolved:
        for index, link in enumerate(result.service.links):
            table.add_row(result.service.name if index == 0 else "", link)

    console.print("[dim]Look here:[/dim]")
    console.print(table)
    console.print()


def main() -> None:  # console-script entry point
    app()
