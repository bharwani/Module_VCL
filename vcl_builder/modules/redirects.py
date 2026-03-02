from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .base import VCLModule, VCLSnippets

# Internal error codes: 700 = permanent redirect, 701 = temporary redirect
_STATUS_TO_ERROR_CODE: dict[int, int] = {
    301: 700,
    302: 701,
}


@dataclass
class RedirectRule:
    from_path: str
    to_url: str
    status_code: Literal[301, 302] = 301


@dataclass
class RewriteRule:
    from_pattern: str  # regex
    to_path: str        # replacement string (may include back-references)


class RedirectsModule(VCLModule):
    """
    Generates redirect and URL rewrite VCL.

    Redirects use internal error codes (700/701) so they exit vcl_recv
    immediately, with the destination URL carried in obj.response.
    Rewrites use regsuball() mutations in-place in vcl_recv.
    """

    def __init__(
        self,
        redirects: list[RedirectRule] | None = None,
        rewrites: list[RewriteRule] | None = None,
    ) -> None:
        self._redirects = redirects or []
        self._rewrites = rewrites or []

    @property
    def name(self) -> str:
        return "redirects"

    def get_snippets(self) -> VCLSnippets:
        snippets = VCLSnippets()

        recv_parts: list[str] = []

        # URL rewrites (applied before redirects so they can be combined)
        for rule in self._rewrites:
            recv_parts.append(
                f'  set req.url = regsuball(req.url, "{rule.from_pattern}", "{rule.to_path}");\n'
            )

        # Redirect rules: signal via internal error code, carry destination in error message
        for rule in self._redirects:
            error_code = _STATUS_TO_ERROR_CODE.get(rule.status_code, 700)
            recv_parts.append(
                f'  if (req.url ~ "^{rule.from_path}") {{\n'
                f'    error {error_code} "{rule.to_url}";\n'
                f"  }}\n"
            )

        if recv_parts:
            snippets.vcl_recv.extend(recv_parts)

        # vcl_error: convert internal codes to real HTTP redirects
        seen_codes: set[int] = set()
        for rule in self._redirects:
            error_code = _STATUS_TO_ERROR_CODE.get(rule.status_code, 700)
            http_status = rule.status_code
            http_reason = "Moved Permanently" if http_status == 301 else "Found"

            if error_code not in seen_codes:
                seen_codes.add(error_code)
                snippets.vcl_error.append(
                    f"  if (obj.status == {error_code}) {{\n"
                    f"    set obj.http.Location = obj.response;\n"
                    f"    set obj.status = {http_status};\n"
                    f'    set obj.response = "{http_reason}";\n'
                    f'    set obj.http.Content-Type = "text/plain";\n'
                    f'    synthetic "";\n'
                    f"    return(deliver);\n"
                    f"  }}\n"
                )

        return snippets
