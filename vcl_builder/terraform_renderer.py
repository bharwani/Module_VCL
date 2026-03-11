"""
Generates a Terraform project directory for a Fastly VCL service.

Produces:
  versions.tf   — required_providers block (fastly/fastly ~> 5.0)
  variables.tf  — fastly_api_key variable
  main.tf       — provider + fastly_service_vcl resource
  outputs.tf    — service_id and active_version outputs
  main.vcl      — the rendered VCL file (referenced by main.tf)
"""
from __future__ import annotations

from pathlib import Path

from .modules.backends import BackendConfig, BackendsModule
from .modules.log_streaming import LogStreamingModule
from .renderer import VCLConfig


def render_terraform(config: VCLConfig, vcl_content: str, output_dir: Path) -> None:
    """Write a ready-to-use Terraform project to *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)

    backends_mod: BackendsModule | None = next(
        (m for m in config.modules if isinstance(m, BackendsModule)), None
    )
    log_mod: LogStreamingModule | None = next(
        (m for m in config.modules if isinstance(m, LogStreamingModule)), None
    )

    (output_dir / "main.vcl").write_text(vcl_content, encoding="utf-8")
    (output_dir / "versions.tf").write_text(_versions_tf(), encoding="utf-8")
    (output_dir / "variables.tf").write_text(_variables_tf(), encoding="utf-8")
    (output_dir / "main.tf").write_text(_main_tf(config, backends_mod, log_mod), encoding="utf-8")
    (output_dir / "outputs.tf").write_text(_outputs_tf(), encoding="utf-8")


# ---------------------------------------------------------------------------
# File generators
# ---------------------------------------------------------------------------

def _versions_tf() -> str:
    return """\
terraform {
  required_version = ">= 1.3"

  required_providers {
    fastly = {
      source  = "fastly/fastly"
      version = "~> 5.0"
    }
  }
}
"""


def _variables_tf() -> str:
    return """\
variable "fastly_api_key" {
  description = "Fastly API key. Set via TF_VAR_fastly_api_key or pass with -var."
  type        = string
  sensitive   = true
}
"""


def _outputs_tf() -> str:
    return """\
output "service_id" {
  description = "Fastly service ID."
  value       = fastly_service_vcl.service.id
}

output "active_version" {
  description = "Active service version number."
  value       = fastly_service_vcl.service.active_version
}
"""


def _healthcheck_block(b: BackendConfig) -> str:
    assert b.health_check is not None
    hc_name = f"{b.name}_hc"
    return (
        f"  healthcheck {{\n"
        f'    name           = "{hc_name}"\n'
        f'    host           = "{b.host}"\n'
        f'    path           = "{b.health_check.path}"\n'
        f"    check_interval = 5000\n"
        f"    timeout        = 2000\n"
        f"    window         = 5\n"
        f"    threshold      = 3\n"
        f"  }}"
    )


def _backend_block(b: BackendConfig) -> str:
    lines = [
        "  backend {",
        f'    name    = "{b.name}"',
        f'    address = "{b.host}"',
        f"    port    = {b.port}",
        f"    use_ssl = {str(b.use_ssl).lower()}",
    ]
    if b.use_ssl:
        lines.append(f"    ssl_check_cert = {str(b.ssl_check_cert).lower()}")
    if b.health_check:
        lines.append(f'    healthcheck    = "{b.name}_hc"')
    lines.append("  }")
    return "\n".join(lines)


def _main_tf(
    config: VCLConfig,
    backends_mod: BackendsModule | None,
    log_mod: LogStreamingModule | None,
) -> str:
    lines: list[str] = [
        'provider "fastly" {',
        "  api_key = var.fastly_api_key",
        "}",
        "",
        'resource "fastly_service_vcl" "service" {',
        f'  name = "{config.service_name}"',
        "",
        "  # TODO: replace with your actual domain(s)",
        "  domain {",
        '    name = "example.com"',
        "  }",
        "",
    ]

    if backends_mod:
        for b in backends_mod.backends:
            if b.health_check:
                lines.append(_healthcheck_block(b))
                lines.append("")
            lines.append(_backend_block(b))
            lines.append("")
    else:
        lines += [
            "  # TODO: add backend block(s)",
            "  backend {",
            '    name    = "origin_1"',
            '    address = "example.com"',
            "    port    = 443",
            "    use_ssl = true",
            "  }",
            "",
        ]

    lines += [
        "  vcl {",
        '    name    = "main_vcl"',
        '    content = file("${path.module}/main.vcl")',
        "    main    = true",
        "  }",
        "",
    ]

    if log_mod:
        lines += [
            f'  # TODO: configure a logging endpoint block for "{log_mod.endpoint_name}".',
            "  # Choose the correct type for your destination, e.g. logging_s3 {}, logging_https {},",
            "  # logging_bigquery {}, logging_syslog {}, etc.",
            "  # See https://registry.terraform.io/providers/fastly/fastly/latest/docs",
            "",
        ]

    lines += [
        "  force_destroy = true",
        "",
        "  lifecycle {",
        "    create_before_destroy = true",
        "  }",
        "}",
        "",
    ]

    return "\n".join(lines)
