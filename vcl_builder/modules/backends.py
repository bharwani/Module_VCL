from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Literal

from .base import VCLModule, VCLSnippets


@dataclass
class HealthCheck:
    path: str = "/healthcheck"


@dataclass
class BackendConfig:
    name: str
    host: str
    port: int = 443
    use_ssl: bool = True
    ssl_check_cert: bool = True
    health_check: HealthCheck | None = None


class BackendsModule(VCLModule):
    """Generates backend declarations and optional director configuration."""

    def __init__(
        self,
        backends: list[BackendConfig],
        director_type: Literal["none", "random", "hash"] = "none",
    ) -> None:
        if not backends:
            raise ValueError("At least one backend is required.")
        self._backends = backends
        self._director_type = director_type

    @property
    def name(self) -> str:
        return "backends"

    @property
    def backends(self) -> list[BackendConfig]:
        return self._backends

    @property
    def director_type(self) -> str:
        return self._director_type

    def get_snippets(self) -> VCLSnippets:
        snippets = VCLSnippets()

        for b in self._backends:
            block = self._backend_block(b)
            snippets.backends.append(block)

        if self._director_type != "none" and len(self._backends) > 1:
            snippets.backends.append(self._director_block())
            snippets.vcl_recv.append(
                f"  set req.backend = vcl_director;\n"
            )
        else:
            # Route to the first (or only) backend
            snippets.vcl_recv.append(
                f"  set req.backend = {self._backends[0].name};\n"
            )

        return snippets

    def _backend_block(self, b: BackendConfig) -> str:
        lines = [f"backend {b.name} {{"]
        lines.append(f'  .host = "{b.host}";')
        lines.append(f"  .port = \"{b.port}\";")
        if b.use_ssl:
            lines.append("  .ssl = true;")
            ssl_val = "true" if b.ssl_check_cert else "false"
            lines.append(f"  .ssl_check_cert = {ssl_val};")
        if b.health_check:
            lines.append("  .probe = {")
            lines.append(f'    .url = "{b.health_check.path}";')
            lines.append("    .interval = 5s;")
            lines.append("    .timeout = 2s;")
            lines.append("    .window = 5;")
            lines.append("    .threshold = 3;")
            lines.append("  }")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _director_block(self) -> str:
        lines = [f"director vcl_director {self._director_type} {{"]
        for b in self._backends:
            lines.append("  {")
            lines.append(f"    .backend = {b.name};")
            lines.append("    .weight = 1;")
            lines.append("  }")
        lines.append("}")
        return "\n".join(lines) + "\n"
