"""Unit tests for terraform_renderer.py."""
import pytest
from pathlib import Path

from vcl_builder.modules.backends import BackendConfig, BackendsModule, HealthCheck
from vcl_builder.modules.log_streaming import LogStreamingModule
from vcl_builder.renderer import VCLConfig
from vcl_builder.terraform_renderer import (
    render_terraform,
    _versions_tf,
    _variables_tf,
    _outputs_tf,
    _backend_block,
    _healthcheck_block,
    _main_tf,
)


# ---------------------------------------------------------------------------
# Static file generators
# ---------------------------------------------------------------------------

class TestVersionsTf:
    def test_returns_string(self):
        assert isinstance(_versions_tf(), str)

    def test_required_version_present(self):
        assert 'required_version = ">= 1.3"' in _versions_tf()

    def test_fastly_provider_present(self):
        content = _versions_tf()
        assert "fastly/fastly" in content

    def test_fastly_version_constraint(self):
        assert '~> 5.0' in _versions_tf()

    def test_terraform_block_present(self):
        assert "terraform {" in _versions_tf()


class TestVariablesTf:
    def test_returns_string(self):
        assert isinstance(_variables_tf(), str)

    def test_fastly_api_key_variable(self):
        assert 'variable "fastly_api_key"' in _variables_tf()

    def test_sensitive_true(self):
        assert "sensitive   = true" in _variables_tf()

    def test_type_string(self):
        assert "type        = string" in _variables_tf()


class TestOutputsTf:
    def test_returns_string(self):
        assert isinstance(_outputs_tf(), str)

    def test_service_id_output(self):
        content = _outputs_tf()
        assert 'output "service_id"' in content

    def test_active_version_output(self):
        content = _outputs_tf()
        assert 'output "active_version"' in content

    def test_service_id_value(self):
        assert "fastly_service_vcl.service.id" in _outputs_tf()

    def test_active_version_value(self):
        assert "fastly_service_vcl.service.active_version" in _outputs_tf()


# ---------------------------------------------------------------------------
# Backend / healthcheck block generators
# ---------------------------------------------------------------------------

class TestBackendBlock:
    def setup_method(self):
        self.backend = BackendConfig(
            name="origin_1",
            host="example.com",
            port=443,
            use_ssl=True,
            ssl_check_cert=True,
        )
        self.block = _backend_block(self.backend)

    def test_returns_string(self):
        assert isinstance(self.block, str)

    def test_backend_keyword(self):
        assert "backend {" in self.block

    def test_name_present(self):
        assert 'name    = "origin_1"' in self.block

    def test_address_present(self):
        assert 'address = "example.com"' in self.block

    def test_port_present(self):
        assert "port    = 443" in self.block

    def test_use_ssl_true(self):
        assert "use_ssl = true" in self.block

    def test_ssl_check_cert_present_when_ssl_enabled(self):
        assert "ssl_check_cert = true" in self.block

    def test_ssl_check_cert_absent_when_ssl_disabled(self):
        b = BackendConfig(name="b", host="h.example.com", use_ssl=False)
        block = _backend_block(b)
        assert "ssl_check_cert" not in block

    def test_healthcheck_ref_absent_without_hc(self):
        assert "healthcheck" not in self.block

    def test_healthcheck_ref_present_with_hc(self):
        b = BackendConfig(name="b", host="h.example.com", health_check=HealthCheck("/ping"))
        block = _backend_block(b)
        assert 'healthcheck    = "b_hc"' in block

    def test_ssl_check_cert_false(self):
        b = BackendConfig(name="b", host="h.example.com", use_ssl=True, ssl_check_cert=False)
        block = _backend_block(b)
        assert "ssl_check_cert = false" in block


class TestHealthcheckBlock:
    def setup_method(self):
        self.backend = BackendConfig(
            name="origin_1",
            host="example.com",
            health_check=HealthCheck(path="/healthcheck"),
        )
        self.block = _healthcheck_block(self.backend)

    def test_returns_string(self):
        assert isinstance(self.block, str)

    def test_healthcheck_keyword(self):
        assert "healthcheck {" in self.block

    def test_name_uses_backend_name_suffix(self):
        assert 'name           = "origin_1_hc"' in self.block

    def test_host_present(self):
        assert 'host           = "example.com"' in self.block

    def test_path_present(self):
        assert 'path           = "/healthcheck"' in self.block

    def test_check_interval(self):
        assert "check_interval = 5000" in self.block

    def test_timeout(self):
        assert "timeout        = 2000" in self.block

    def test_window(self):
        assert "window         = 5" in self.block

    def test_threshold(self):
        assert "threshold      = 3" in self.block

    def test_custom_path(self):
        b = BackendConfig(name="b", host="h.com", health_check=HealthCheck(path="/ping"))
        block = _healthcheck_block(b)
        assert 'path           = "/ping"' in block


# ---------------------------------------------------------------------------
# _main_tf generator
# ---------------------------------------------------------------------------

class TestMainTf:
    def _make_backends_mod(self, **kwargs):
        defaults = dict(name="origin_1", host="example.com")
        defaults.update(kwargs)
        return BackendsModule(backends=[BackendConfig(**defaults)])

    def test_provider_block_present(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert 'provider "fastly"' in content

    def test_api_key_var_reference(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert "var.fastly_api_key" in content

    def test_service_name_embedded(self):
        config = VCLConfig(service_name="my-service", modules=[])
        content = _main_tf(config, None, None)
        assert '"my-service"' in content

    def test_vcl_block_present(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert 'vcl {' in content
        assert 'main_vcl' in content
        assert 'main    = true' in content

    def test_force_destroy_present(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert "force_destroy = true" in content

    def test_lifecycle_block_present(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert "lifecycle {" in content
        assert "create_before_destroy = true" in content

    def test_placeholder_backend_when_no_backends_mod(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert "# TODO: add backend block(s)" in content

    def test_backend_block_included_when_backends_mod_present(self):
        backends_mod = self._make_backends_mod()
        config = VCLConfig(service_name="svc", modules=[backends_mod])
        content = _main_tf(config, backends_mod, None)
        assert 'address = "example.com"' in content

    def test_no_placeholder_when_backends_mod_present(self):
        backends_mod = self._make_backends_mod()
        config = VCLConfig(service_name="svc", modules=[backends_mod])
        content = _main_tf(config, backends_mod, None)
        assert "# TODO: add backend block(s)" not in content

    def test_healthcheck_block_included_when_hc_present(self):
        backend = BackendConfig("b", "b.example.com", health_check=HealthCheck("/ping"))
        backends_mod = BackendsModule(backends=[backend])
        config = VCLConfig(service_name="svc", modules=[backends_mod])
        content = _main_tf(config, backends_mod, None)
        assert "healthcheck {" in content
        assert 'path           = "/ping"' in content

    def test_log_endpoint_comment_included_when_log_mod_present(self):
        backends_mod = self._make_backends_mod()
        log_mod = LogStreamingModule(endpoint_name="my-endpoint")
        config = VCLConfig(service_name="svc", modules=[backends_mod, log_mod])
        content = _main_tf(config, backends_mod, log_mod)
        assert "my-endpoint" in content
        assert "logging" in content

    def test_no_log_comment_when_no_log_mod(self):
        backends_mod = self._make_backends_mod()
        config = VCLConfig(service_name="svc", modules=[backends_mod])
        content = _main_tf(config, backends_mod, None)
        assert "logging" not in content

    def test_domain_placeholder_present(self):
        config = VCLConfig(service_name="svc", modules=[])
        content = _main_tf(config, None, None)
        assert "example.com" in content


# ---------------------------------------------------------------------------
# render_terraform integration
# ---------------------------------------------------------------------------

class TestRenderTerraform:
    def setup_method(self, tmp_path_factory=None):
        import tempfile
        self._tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _run(self, config: VCLConfig, vcl_content: str = "# VCL content"):
        render_terraform(config, vcl_content, self._tmpdir)
        return self._tmpdir

    def _make_config(self, service_name="test-svc"):
        backends_mod = BackendsModule(
            backends=[BackendConfig(name="origin_1", host="example.com")]
        )
        return VCLConfig(service_name=service_name, modules=[backends_mod])

    def test_creates_output_directory(self):
        out = self._tmpdir / "subdir"
        config = self._make_config()
        render_terraform(config, "# vcl", out)
        assert out.is_dir()

    def test_main_vcl_written(self):
        config = self._make_config()
        self._run(config, "# my vcl")
        assert (self._tmpdir / "main.vcl").read_text() == "# my vcl"

    def test_versions_tf_written(self):
        config = self._make_config()
        self._run(config)
        content = (self._tmpdir / "versions.tf").read_text()
        assert "fastly/fastly" in content

    def test_variables_tf_written(self):
        config = self._make_config()
        self._run(config)
        content = (self._tmpdir / "variables.tf").read_text()
        assert "fastly_api_key" in content

    def test_outputs_tf_written(self):
        config = self._make_config()
        self._run(config)
        content = (self._tmpdir / "outputs.tf").read_text()
        assert "service_id" in content
        assert "active_version" in content

    def test_main_tf_written(self):
        config = self._make_config()
        self._run(config)
        content = (self._tmpdir / "main.tf").read_text()
        assert "fastly_service_vcl" in content

    def test_main_tf_contains_service_name(self):
        config = self._make_config(service_name="my-cdn")
        self._run(config)
        content = (self._tmpdir / "main.tf").read_text()
        assert "my-cdn" in content

    def test_all_five_files_created(self):
        config = self._make_config()
        self._run(config)
        expected = {"main.vcl", "versions.tf", "variables.tf", "main.tf", "outputs.tf"}
        actual = {f.name for f in self._tmpdir.iterdir()}
        assert expected == actual

    def test_with_log_module(self):
        backends_mod = BackendsModule(
            backends=[BackendConfig(name="origin_1", host="example.com")]
        )
        log_mod = LogStreamingModule(endpoint_name="access-logs")
        config = VCLConfig(service_name="logged-svc", modules=[backends_mod, log_mod])
        self._run(config)
        content = (self._tmpdir / "main.tf").read_text()
        assert "access-logs" in content

    def test_with_health_check(self):
        backend = BackendConfig(
            "origin_1", "example.com",
            health_check=HealthCheck(path="/health")
        )
        backends_mod = BackendsModule(backends=[backend])
        config = VCLConfig(service_name="hc-svc", modules=[backends_mod])
        self._run(config)
        content = (self._tmpdir / "main.tf").read_text()
        assert "healthcheck {" in content
        assert "/health" in content
