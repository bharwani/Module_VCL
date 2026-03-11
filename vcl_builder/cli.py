"""
vcl-builder CLI entry point.

Usage:
    vcl-builder generate [--output <file>]
    vcl-builder --version
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.syntax import Syntax

from . import __version__
from .renderer import render_vcl
from .terraform_renderer import render_terraform
from .wizard import run_wizard

app = typer.Typer(
    name="vcl-builder",
    help="Interactive wizard to generate Fastly-ready VCL configuration files.",
    add_completion=False,
)

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"vcl-builder [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            callback=_version_callback,
            is_eager=True,
            help="Show version and exit.",
        ),
    ] = None,
) -> None:
    """vcl-builder — Modular Fastly VCL generator."""


@app.command()
def generate(
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Write generated VCL to this file. Prints to stdout if omitted.",
        ),
    ] = None,
    preview: Annotated[
        bool,
        typer.Option(
            "--preview",
            help="Print a syntax-highlighted preview before writing.",
        ),
    ] = False,
    terraform: Annotated[
        Optional[Path],
        typer.Option(
            "--terraform",
            "-T",
            help=(
                "Write a Terraform project to this directory "
                "(main.tf, variables.tf, outputs.tf, versions.tf, main.vcl)."
            ),
        ),
    ] = None,
) -> None:
    """Run the interactive wizard and generate a Fastly VCL file."""
    config = run_wizard()

    vcl_output = render_vcl(config)

    if preview or (output is None and terraform is None):
        syntax = Syntax(vcl_output, "c", theme="monokai", line_numbers=True)
        console.print(syntax)

    if output:
        output.write_text(vcl_output, encoding="utf-8")
        console.print(f"\n[bold green]VCL written to:[/bold green] {output}")
    elif not preview and terraform is None:
        # If no --output, no --preview, and no --terraform, print raw text to stdout
        print(vcl_output)

    if terraform:
        render_terraform(config, vcl_output, terraform)
        console.print(f"\n[bold green]Terraform project written to:[/bold green] {terraform}/")
        console.print("  [dim]versions.tf, variables.tf, main.tf, outputs.tf, main.vcl[/dim]")
