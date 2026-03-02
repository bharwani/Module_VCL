from __future__ import annotations

from typing import Literal

from .base import VCLModule, VCLSnippets


class RateLimitModule(VCLModule):
    """
    Generates Fastly rate-limiting VCL using ratecounter + penaltybox.

    Uses Fastly's built-in ratelimit.check_rate() function which requires
    the ratecounter and penaltybox to be declared at the top level.
    """

    def __init__(
        self,
        requests_per_second: int = 10,
        window_seconds: int = 1,
        penalty_duration: int = 60,
        scope: Literal["per_ip", "per_ip_path"] = "per_ip",
        action: Literal["429", "redirect"] = "429",
        redirect_url: str = "",
    ) -> None:
        self._rps = requests_per_second
        self._window = window_seconds
        self._penalty = penalty_duration
        self._scope = scope
        self._action = action
        self._redirect_url = redirect_url

    @property
    def name(self) -> str:
        return "rate_limit"

    def get_snippets(self) -> VCLSnippets:
        snippets = VCLSnippets()

        # Top-level declarations (ratecounter + penaltybox)
        snippets.backends.append(
            "ratecounter req_rate_counter {\n"
            "}\n"
        )
        snippets.backends.append(
            "penaltybox client_penaltybox {\n"
            "}\n"
        )

        # vcl_recv: rate check
        if self._scope == "per_ip":
            bucket_key = "req.http.Fastly-Client-IP"
        else:
            # per_ip_path: combine IP + path for a unique bucket
            bucket_key = 'req.http.Fastly-Client-IP ":" req.url.path'

        recv_snippet = (
            f"  if (ratelimit.check_rate(\n"
            f"    {bucket_key},\n"
            f"    req_rate_counter,\n"
            f"    {self._rps},\n"
            f"    {self._window},\n"
            f"    {self._penalty},\n"
            f"    client_penaltybox\n"
            f"  )) {{\n"
        )

        if self._action == "redirect" and self._redirect_url:
            recv_snippet += (
                f'    error 750 "{self._redirect_url}";\n'
                f"  }}\n"
            )
        else:
            recv_snippet += (
                "    error 429 \"Rate limit exceeded\";\n"
                "  }\n"
            )

        snippets.vcl_recv.append(recv_snippet)

        # vcl_error: synthetic response for rate-limit hits
        if self._action == "redirect" and self._redirect_url:
            snippets.vcl_error.append(
                "  if (obj.status == 750) {\n"
                f'    set obj.http.Location = obj.response;\n'
                "    set obj.status = 302;\n"
                '    set obj.response = "Found";\n'
                '    set obj.http.Content-Type = "text/plain";\n'
                '    synthetic "";\n'
                "    return(deliver);\n"
                "  }\n"
            )
        else:
            snippets.vcl_error.append(
                "  if (obj.status == 429) {\n"
                '    set obj.http.Content-Type = "application/json";\n'
                '    synthetic {"{"error":"rate_limit_exceeded","retry_after":"}' +
                str(self._penalty) +
                '{"}"}\n'
                ";  \n"
                "    return(deliver);\n"
                "  }\n"
            )

        return snippets
