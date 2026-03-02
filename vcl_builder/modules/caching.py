from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .base import VCLModule, VCLSnippets


@dataclass
class PathRule:
    """TTL override for a specific URL path pattern."""
    pattern: str
    ttl: int  # seconds


class CachingModule(VCLModule):
    """Generates caching rules: TTLs, cookie bypass, query-string handling."""

    def __init__(
        self,
        default_ttl: int = 3600,
        cookie_bypass: bool = False,
        query_string_handling: Literal["keep_all", "strip_all", "keep_specific"] = "keep_all",
        keep_params: list[str] | None = None,
        path_rules: list[PathRule] | None = None,
    ) -> None:
        self._default_ttl = default_ttl
        self._cookie_bypass = cookie_bypass
        self._qs_handling = query_string_handling
        self._keep_params = keep_params or []
        self._path_rules = path_rules or []

    @property
    def name(self) -> str:
        return "caching"

    def get_snippets(self) -> VCLSnippets:
        snippets = VCLSnippets()

        recv_parts: list[str] = []

        # Cookie bypass: pass requests with cookies to origin, skip cache
        if self._cookie_bypass:
            recv_parts.append(
                "  if (req.http.Cookie) {\n"
                "    return(pass);\n"
                "  }\n"
            )

        # Query-string handling
        if self._qs_handling == "strip_all":
            recv_parts.append(
                "  set req.url = req.url.path;\n"
            )
        elif self._qs_handling == "keep_specific" and self._keep_params:
            # Build a regex that strips everything except the kept params
            params_pattern = "|".join(self._keep_params)
            recv_parts.append(
                f"  set req.url = regsuball(req.url,\n"
                f'    "(?i)([?&])(?!({params_pattern})=)[^&]*", "\\1");\n'
                "  set req.url = regsuball(req.url, \"[?&]$\", \"\");\n"
            )

        if recv_parts:
            snippets.vcl_recv.extend(recv_parts)

        # vcl_fetch: set TTLs and strip Set-Cookie for cached responses
        fetch_parts: list[str] = []

        # Per-path TTL rules (most specific first)
        for rule in self._path_rules:
            fetch_parts.append(
                f'  if (req.url ~ "^{rule.pattern}") {{\n'
                f"    set beresp.ttl = {rule.ttl}s;\n"
                f"  }}\n"
            )

        # Default TTL
        fetch_parts.append(
            f"  if (beresp.ttl <= 0s) {{\n"
            f"    set beresp.ttl = {self._default_ttl}s;\n"
            f"  }}\n"
        )

        # Strip Set-Cookie so Fastly caches the response
        fetch_parts.append(
            "  unset beresp.http.Set-Cookie;\n"
        )

        snippets.vcl_fetch.extend(fetch_parts)

        return snippets
