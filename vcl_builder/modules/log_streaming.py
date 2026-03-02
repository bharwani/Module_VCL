from __future__ import annotations

from typing import Literal

from .base import VCLModule, VCLSnippets

# VCL format expressions appended after ":: "
_COMBINED_EXPR = (
    'req.http.Fastly-Client-IP + " " + req.request + " " + req.url + " " + resp.status'
)
_JSON_EXPR = (
    '"{\\\"host\\\":\\"" + req.http.host + "\\",\\"method\\":\\"" + req.request'
    ' + "\\",\\"url\\":\\"" + req.url + "\\",\\"status\\":" + resp.status'
    ' + ",\\"ip\\":\\"" + req.http.Fastly-Client-IP + "\\"}"'
)


class LogStreamingModule(VCLModule):
    """Emit a log statement in vcl_log to a named Fastly logging endpoint."""

    def __init__(
        self,
        endpoint_name: str,
        format: Literal["combined", "json", "custom"] = "combined",
        custom_format: str = "",
        errors_only: bool = False,
    ) -> None:
        self.endpoint_name = endpoint_name
        self.format = format
        self.custom_format = custom_format
        self.errors_only = errors_only

    @property
    def name(self) -> str:
        return "log_streaming"

    def get_snippets(self) -> VCLSnippets:
        if self.format == "json":
            fmt_expr = _JSON_EXPR
        elif self.format == "custom":
            fmt_expr = self.custom_format
        else:
            fmt_expr = _COMBINED_EXPR

        log_stmt = (
            f'  log "syslog " + req.service_id + " {self.endpoint_name} :: " + {fmt_expr};'
        )

        if self.errors_only:
            snippet = (
                f"  /* Log streaming: emit errors to Fastly endpoint \"{self.endpoint_name}\" */\n"
                f"  if (resp.status >= 400) {{\n"
                f"{log_stmt}\n"
                f"  }}"
            )
        else:
            snippet = (
                f"  /* Log streaming: emit to Fastly endpoint \"{self.endpoint_name}\" */\n"
                f"{log_stmt}"
            )

        return VCLSnippets(vcl_log=[snippet])
