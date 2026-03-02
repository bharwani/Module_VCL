from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VCLSnippets:
    """Container for VCL code fragments contributed by a module."""

    backends: list[str] = field(default_factory=list)
    """Top-level backend/director/ratecounter/penaltybox declarations."""

    vcl_recv: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_recv {}."""

    vcl_hash: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_hash {}."""

    vcl_fetch: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_fetch {}."""

    vcl_deliver: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_deliver {}."""

    vcl_error: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_error {}."""

    vcl_log: list[str] = field(default_factory=list)
    """Snippets injected into sub vcl_log {}."""


class VCLModule(ABC):
    """Abstract base class for all VCL feature modules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable module name."""

    @abstractmethod
    def get_snippets(self) -> VCLSnippets:
        """Return VCL code fragments for this module's configuration."""
