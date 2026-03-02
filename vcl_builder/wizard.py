"""
Interactive wizard that guides the user through configuring each VCL module.
Returns a populated VCLConfig ready for rendering.
"""
from __future__ import annotations

import sys

import questionary
from rich.console import Console
from rich.table import Table

from .modules import (
    BackendConfig,
    BackendsModule,
    CachingModule,
    HealthCheck,
    LogStreamingModule,
    PathRule,
    RateLimitModule,
    RedirectRule,
    RedirectsModule,
    RewriteRule,
    VideoStreamingModule,
)
from .renderer import VCLConfig

console = Console()


def _ask(prompt: str, **kwargs) -> str:
    """Wrapper around questionary.text that exits cleanly on Ctrl-C."""
    try:
        answer = questionary.text(prompt, **kwargs).ask()
        if answer is None:
            console.print("\n[yellow]Wizard cancelled.[/yellow]")
            sys.exit(0)
        return answer
    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        sys.exit(0)


def _ask_int(prompt: str, default: int) -> int:
    raw = _ask(prompt, default=str(default))
    try:
        return int(raw)
    except ValueError:
        console.print(f"[red]Invalid number, using default {default}[/red]")
        return default


def _confirm(prompt: str, default: bool = True) -> bool:
    try:
        result = questionary.confirm(prompt, default=default).ask()
        if result is None:
            console.print("\n[yellow]Wizard cancelled.[/yellow]")
            sys.exit(0)
        return result
    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        sys.exit(0)


def _select(prompt: str, choices: list[str], default: str | None = None) -> str:
    try:
        result = questionary.select(prompt, choices=choices, default=default).ask()
        if result is None:
            console.print("\n[yellow]Wizard cancelled.[/yellow]")
            sys.exit(0)
        return result
    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Phase 1: Backends
# ---------------------------------------------------------------------------

def _collect_backends() -> BackendsModule:
    console.rule("[bold blue]Phase 1: Backends[/bold blue]")

    count = _ask_int("How many backends (origins) do you want to configure?", default=1)
    count = max(1, count)

    backends: list[BackendConfig] = []
    for i in range(count):
        console.print(f"\n[bold]Backend {i + 1}[/bold]")
        name = _ask(f"  Backend name (e.g. origin_{i + 1}):", default=f"origin_{i + 1}")
        host = _ask("  Hostname or IP:", default="example.com")
        port = _ask_int("  Port:", default=443)
        use_ssl = _confirm("  Use SSL?", default=True)
        ssl_check = _confirm("  Verify SSL certificate?", default=True) if use_ssl else False

        hc: HealthCheck | None = None
        if _confirm("  Add health check?", default=False):
            hc_path = _ask("  Health check path:", default="/healthcheck")
            hc = HealthCheck(path=hc_path)

        backends.append(
            BackendConfig(
                name=name,
                host=host,
                port=port,
                use_ssl=use_ssl,
                ssl_check_cert=ssl_check,
                health_check=hc,
            )
        )

    director_type = "none"
    if len(backends) > 1:
        director_type = _select(
            "Director (load-balancing) type:",
            choices=["none", "random", "hash"],
            default="random",
        )

    return BackendsModule(backends=backends, director_type=director_type)


# ---------------------------------------------------------------------------
# Phase 2: Caching
# ---------------------------------------------------------------------------

def _collect_caching() -> CachingModule | None:
    console.rule("[bold blue]Phase 2: Caching[/bold blue]")
    if not _confirm("Configure caching rules?", default=True):
        return None

    default_ttl = _ask_int("Default cache TTL (seconds):", default=3600)
    cookie_bypass = _confirm("Bypass cache for requests with cookies?", default=False)

    qs_handling = _select(
        "Query string handling:",
        choices=["keep_all", "strip_all", "keep_specific"],
        default="keep_all",
    )

    keep_params: list[str] = []
    if qs_handling == "keep_specific":
        raw = _ask("Comma-separated param names to keep (e.g. page,sort):", default="")
        keep_params = [p.strip() for p in raw.split(",") if p.strip()]

    path_rules: list[PathRule] = []
    while _confirm("Add a per-path TTL rule?", default=False):
        pattern = _ask("  URL path prefix or regex (e.g. /api/):", default="/api/")
        ttl = _ask_int("  TTL (seconds):", default=60)
        path_rules.append(PathRule(pattern=pattern, ttl=ttl))

    return CachingModule(
        default_ttl=default_ttl,
        cookie_bypass=cookie_bypass,
        query_string_handling=qs_handling,
        keep_params=keep_params,
        path_rules=path_rules,
    )


# ---------------------------------------------------------------------------
# Phase 3: Rate limiting
# ---------------------------------------------------------------------------

def _collect_rate_limit() -> RateLimitModule | None:
    console.rule("[bold blue]Phase 3: Rate Limiting[/bold blue]")
    if not _confirm("Configure rate limiting?", default=False):
        return None

    rps = _ask_int("Maximum requests per second per client:", default=10)
    window = _ask_int("Sliding window (seconds):", default=1)
    penalty = _ask_int("Penalty box duration (seconds):", default=60)

    scope = _select(
        "Rate limit scope:",
        choices=["per_ip", "per_ip_path"],
        default="per_ip",
    )

    action = _select(
        "Action when rate limit exceeded:",
        choices=["429", "redirect"],
        default="429",
    )

    redirect_url = ""
    if action == "redirect":
        redirect_url = _ask("Redirect URL:", default="https://example.com/rate-limited")

    return RateLimitModule(
        requests_per_second=rps,
        window_seconds=window,
        penalty_duration=penalty,
        scope=scope,
        action=action,
        redirect_url=redirect_url,
    )


# ---------------------------------------------------------------------------
# Phase 4: Redirects / rewrites
# ---------------------------------------------------------------------------

def _collect_redirects() -> RedirectsModule | None:
    console.rule("[bold blue]Phase 4: Redirects & Rewrites[/bold blue]")
    if not _confirm("Configure redirects or URL rewrites?", default=False):
        return None

    redirect_rules: list[RedirectRule] = []
    while _confirm("Add a redirect rule?", default=True):
        from_path = _ask("  From path (regex, e.g. ^/old-page):", default="^/old-page")
        to_url = _ask("  To URL:", default="https://example.com/new-page")
        status_raw = _select("  Status code:", choices=["301", "302"], default="301")
        status_code = int(status_raw)
        redirect_rules.append(
            RedirectRule(from_path=from_path, to_url=to_url, status_code=status_code)  # type: ignore[arg-type]
        )

    rewrite_rules: list[RewriteRule] = []
    while _confirm("Add a URL rewrite rule?", default=False):
        from_pattern = _ask("  From pattern (regex):", default="^/api/v1/(.*)")
        to_path = _ask("  To path (replacement, e.g. /api/v2/\\1):", default="/api/v2/\\1")
        rewrite_rules.append(RewriteRule(from_pattern=from_pattern, to_path=to_path))

    return RedirectsModule(redirects=redirect_rules, rewrites=rewrite_rules)


# ---------------------------------------------------------------------------
# Phase 5: Video streaming
# ---------------------------------------------------------------------------

def _collect_video_streaming() -> VideoStreamingModule | None:
    console.rule("[bold blue]Phase 5: Video Streaming[/bold blue]")
    if not _confirm("Configure video streaming optimisations?", default=False):
        return None

    mode = _select(
        "Streaming mode:",
        choices=["live", "vod"],
        default="live",
    )

    default_manifest_ttl = 2 if mode == "live" else 60
    manifest_ttl = _ask_int(
        f"Manifest TTL (seconds, default {default_manifest_ttl} for {mode}):",
        default=default_manifest_ttl,
    )
    segment_ttl = _ask_int("Segment TTL (seconds):", default=86400)
    enable_segmented_caching = _confirm("Enable segmented caching?", default=True)
    enable_streaming_miss = _confirm("Enable streaming miss?", default=True)
    strip_cookies = _confirm("Strip Set-Cookie / Vary on media responses?", default=True)

    return VideoStreamingModule(
        mode=mode,
        manifest_ttl=manifest_ttl,
        segment_ttl=segment_ttl,
        enable_segmented_caching=enable_segmented_caching,
        enable_streaming_miss=enable_streaming_miss,
        strip_cookies=strip_cookies,
    )


# ---------------------------------------------------------------------------
# Phase 6: Log streaming
# ---------------------------------------------------------------------------

def _collect_log_streaming() -> LogStreamingModule | None:
    console.rule("[bold blue]Phase 6: Remote Log Streaming[/bold blue]")
    if not _confirm("Configure remote log streaming?", default=False):
        return None

    endpoint_name = _ask("Fastly logging endpoint name (must match Fastly UI):")
    while not endpoint_name.strip():
        console.print("[red]Endpoint name is required.[/red]")
        endpoint_name = _ask("Fastly logging endpoint name (must match Fastly UI):")

    fmt = _select(
        "Log format:",
        choices=["combined", "json", "custom"],
        default="combined",
    )

    custom_format = ""
    if fmt == "custom":
        custom_format = _ask("VCL format expression:")

    errors_only = _confirm("Log errors only (4xx/5xx)?", default=False)

    return LogStreamingModule(
        endpoint_name=endpoint_name.strip(),
        format=fmt,
        custom_format=custom_format,
        errors_only=errors_only,
    )


# ---------------------------------------------------------------------------
# Phase 7: Summary & confirmation
# ---------------------------------------------------------------------------

def _show_summary(service_name: str, modules: list) -> None:
    console.rule("[bold green]Configuration Summary[/bold green]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Module", style="cyan")
    table.add_column("Status")
    table.add_column("Details")

    names = {m.name for m in modules}

    def status(name: str) -> tuple[str, str]:
        return ("✓ enabled", "green") if name in names else ("— skipped", "dim")

    for mod_name in ("backends", "caching", "rate_limit", "redirects", "video_streaming", "log_streaming"):
        st, color = status(mod_name)
        table.add_row(mod_name, f"[{color}]{st}[/{color}]", "")

    console.print(table)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_wizard() -> VCLConfig:
    """Run the interactive wizard and return a configured VCLConfig."""
    console.rule("[bold cyan]vcl-builder — Fastly VCL Wizard[/bold cyan]")

    # Phase 0: service name
    service_name = _ask("Service name (used as a comment header):", default="my-fastly-service")

    # Boilerplate-only shortcut: skip all phases and return the standard template
    if _confirm("Generate Fastly VCL boilerplate only (no custom configuration)?", default=False):
        return VCLConfig(service_name=service_name, modules=[])

    modules = []

    # Phase 1 (always)
    modules.append(_collect_backends())

    # Phase 2
    caching = _collect_caching()
    if caching:
        modules.append(caching)

    # Phase 3
    rate_limit = _collect_rate_limit()
    if rate_limit:
        modules.append(rate_limit)

    # Phase 4
    redirects = _collect_redirects()
    if redirects:
        modules.append(redirects)

    # Phase 5
    video_streaming = _collect_video_streaming()
    if video_streaming:
        modules.append(video_streaming)

    # Phase 6
    log_streaming = _collect_log_streaming()
    if log_streaming:
        modules.append(log_streaming)

    # Phase 7: summary + confirm
    _show_summary(service_name, modules)

    if not _confirm("\nGenerate VCL with this configuration?", default=True):
        console.print("[yellow]Aborted.[/yellow]")
        sys.exit(0)

    return VCLConfig(service_name=service_name, modules=modules)
