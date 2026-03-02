from __future__ import annotations

import importlib.resources
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

from .modules.base import VCLModule, VCLSnippets


@dataclass
class VCLConfig:
    service_name: str
    modules: list[VCLModule] = field(default_factory=list)


def _merge_snippets(modules: list[VCLModule]) -> VCLSnippets:
    """Merge snippet lists from all modules in order."""
    merged = VCLSnippets()
    for module in modules:
        s = module.get_snippets()
        merged.backends.extend(s.backends)
        merged.vcl_recv.extend(s.vcl_recv)
        merged.vcl_hash.extend(s.vcl_hash)
        merged.vcl_fetch.extend(s.vcl_fetch)
        merged.vcl_deliver.extend(s.vcl_deliver)
        merged.vcl_error.extend(s.vcl_error)
        merged.vcl_log.extend(s.vcl_log)
    return merged


def _get_jinja_env() -> Environment:
    """
    Build a Jinja2 environment that locates templates both when installed
    as a package and when run from the project root during development.
    """
    # Try the installed package first (works after `pip install -e .`)
    try:
        env = Environment(
            loader=PackageLoader("vcl_builder", package_path="../templates"),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Verify the template is accessible
        env.get_template("main.vcl.j2")
        return env
    except Exception:
        pass

    # Fall back to a file-system path relative to this file (development)
    templates_dir = Path(__file__).parent.parent / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_vcl(config: VCLConfig) -> str:
    """Render a complete VCL file from the given configuration."""
    snippets = _merge_snippets(config.modules)
    env = _get_jinja_env()
    template = env.get_template("main.vcl.j2")
    return template.render(
        service_name=config.service_name,
        backends=snippets.backends,
        vcl_recv=snippets.vcl_recv,
        vcl_hash=snippets.vcl_hash,
        vcl_fetch=snippets.vcl_fetch,
        vcl_deliver=snippets.vcl_deliver,
        vcl_error=snippets.vcl_error,
        vcl_log=snippets.vcl_log,
    )
