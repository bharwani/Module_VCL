from __future__ import annotations

from typing import Literal

from .base import VCLModule, VCLSnippets

# Default manifest TTLs per mode (seconds)
_MANIFEST_TTL_DEFAULTS: dict[str, int] = {"live": 2, "vod": 60}


class VideoStreamingModule(VCLModule):
    """
    Generates VCL optimisations for video streaming delivery.

    Implements Fastly's official video streaming configuration guidelines:
    - Segmented caching for efficient byte-range handling
    - Streaming miss so origin bytes reach clients as they arrive
    - TTL differentiation between manifests (short) and segments (long)
    - Gzip disabled on segments (already compressed; incompatible with streaming miss)
    - Cookie/Vary stripping so responses are shared across clients
    """

    def __init__(
        self,
        mode: Literal["live", "vod"] = "live",
        manifest_ttl: int | None = None,
        segment_ttl: int = 86400,
        enable_segmented_caching: bool = True,
        enable_streaming_miss: bool = True,
        strip_cookies: bool = True,
    ) -> None:
        self._mode = mode
        self._manifest_ttl = manifest_ttl if manifest_ttl is not None else _MANIFEST_TTL_DEFAULTS[mode]
        self._segment_ttl = segment_ttl
        self._enable_segmented_caching = enable_segmented_caching
        self._enable_streaming_miss = enable_streaming_miss
        self._strip_cookies = strip_cookies

    @property
    def name(self) -> str:
        return "video_streaming"

    def get_snippets(self) -> VCLSnippets:
        snippets = VCLSnippets()

        # vcl_recv: enable segmented caching
        if self._enable_segmented_caching:
            snippets.vcl_recv.append(
                "  /* Video streaming: enable segmented caching for byte-range efficiency */\n"
                "  set req.enable_segmented_caching = true;\n"
            )

        # vcl_fetch: TTL differentiation + streaming miss + gzip disable + error recovery
        fetch_parts: list[str] = []

        fetch_parts.append(
            f'  /* Video streaming: manifest TTL (HLS .m3u8 / DASH .mpd) */\n'
            f'  if (req.url ~ "\\.(m3u8|mpd)(\\?|$)") {{\n'
            f'    set beresp.ttl = {self._manifest_ttl}s;\n'
            f'    set beresp.cacheable = true;\n'
            f'  }}\n'
        )

        fetch_parts.append(
            f'  /* Video streaming: segment TTL (.ts / .m4s / fragmented .mp4) */\n'
            f'  if (req.url ~ "\\.(ts|m4s|mp4)(\\?|$)") {{\n'
            f'    set beresp.ttl = {self._segment_ttl}s;\n'
            f'    set beresp.cacheable = true;\n'
            f'  }}\n'
        )

        fetch_parts.append(
            '  /* Video streaming: error recovery — short TTL so origin failures self-heal */\n'
            '  if (beresp.status >= 500 && beresp.status < 600) {\n'
            '    set beresp.ttl = 1s;\n'
            '    set beresp.grace = 5s;\n'
            '  }\n'
        )

        if self._enable_streaming_miss:
            fetch_parts.append(
                '  /* Streaming miss: proxy segment bytes to client as they arrive from origin */\n'
                '  if (req.url ~ "\\.(ts|m4s|mp4)(\\?|$)") {\n'
                '    set beresp.do_stream = true;\n'
                '    set beresp.gzip = false;      /* gzip incompatible with streaming miss */\n'
                '  }\n'
            )

        snippets.vcl_fetch.extend(fetch_parts)

        # vcl_deliver: strip Set-Cookie / Vary so responses are shared across clients
        if self._strip_cookies:
            snippets.vcl_deliver.append(
                '  /* Video streaming: strip cookies/Vary so responses are shared across clients */\n'
                '  if (req.url ~ "\\.(m3u8|mpd|ts|m4s|mp4)(\\?|$)") {\n'
                '    unset resp.http.Set-Cookie;\n'
                '    unset resp.http.Vary;\n'
                '  }\n'
            )

        return snippets
