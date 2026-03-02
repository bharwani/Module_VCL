"""Integration tests for the renderer + template."""
import re

import pytest

from vcl_builder.modules.backends import BackendConfig, BackendsModule
from vcl_builder.modules.caching import CachingModule, PathRule
from vcl_builder.modules.rate_limit import RateLimitModule
from vcl_builder.modules.redirects import RedirectRule, RedirectsModule, RewriteRule
from vcl_builder.modules.log_streaming import LogStreamingModule
from vcl_builder.modules.video_streaming import VideoStreamingModule
from vcl_builder.renderer import VCLConfig, render_vcl


REQUIRED_SUBS = [
    "sub vcl_recv",
    "sub vcl_hash",
    "sub vcl_hit",
    "sub vcl_miss",
    "sub vcl_pass",
    "sub vcl_fetch",
    "sub vcl_deliver",
    "sub vcl_error",
    "sub vcl_log",
]

REQUIRED_FASTLY_MACROS = [
    "#FASTLY recv",
    "#FASTLY hash",
    "#FASTLY hit",
    "#FASTLY miss",
    "#FASTLY pass",
    "#FASTLY fetch",
    "#FASTLY deliver",
    "#FASTLY error",
    "#FASTLY log",
]


def _make_minimal_config(service_name: str = "test-service") -> VCLConfig:
    backends = BackendsModule(
        backends=[BackendConfig(name="origin_1", host="example.com")]
    )
    return VCLConfig(service_name=service_name, modules=[backends])


class TestMinimalRender:
    def setup_method(self):
        self.vcl = render_vcl(_make_minimal_config())

    def test_output_is_string(self):
        assert isinstance(self.vcl, str)

    def test_output_not_empty(self):
        assert len(self.vcl) > 0

    def test_service_name_in_header(self):
        assert "test-service" in self.vcl

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_required_subroutines_present(self, sub):
        assert sub in self.vcl

    @pytest.mark.parametrize("macro", REQUIRED_FASTLY_MACROS)
    def test_fastly_macros_present(self, macro):
        assert macro in self.vcl

    def test_backend_block_in_output(self):
        assert "backend origin_1" in self.vcl

    def test_balanced_braces(self):
        assert self.vcl.count("{") == self.vcl.count("}")


class TestFullRender:
    """Full integration: all modules enabled."""

    def setup_method(self):
        backends = BackendsModule(
            backends=[
                BackendConfig("b1", "b1.example.com"),
                BackendConfig("b2", "b2.example.com"),
            ],
            director_type="random",
        )
        caching = CachingModule(
            default_ttl=600,
            cookie_bypass=True,
            path_rules=[PathRule("/api/", 30)],
        )
        rate_limit = RateLimitModule(requests_per_second=5, action="429")
        redirects = RedirectsModule(
            redirects=[RedirectRule("^/old", "https://example.com/new", 301)],
            rewrites=[RewriteRule(r"^/api/v1/(.*)", r"/api/v2/\1")],
        )
        config = VCLConfig(
            service_name="full-test",
            modules=[backends, caching, rate_limit, redirects],
        )
        self.vcl = render_vcl(config)

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_required_subs(self, sub):
        assert sub in self.vcl

    @pytest.mark.parametrize("macro", REQUIRED_FASTLY_MACROS)
    def test_fastly_macros(self, macro):
        assert macro in self.vcl

    def test_backend_blocks(self):
        assert "backend b1" in self.vcl
        assert "backend b2" in self.vcl

    def test_director_block(self):
        assert "director vcl_director random" in self.vcl

    def test_cookie_bypass(self):
        assert "return(pass)" in self.vcl

    def test_ttl_in_fetch(self):
        assert "beresp.ttl = 600s" in self.vcl

    def test_rate_limit_declarations(self):
        assert "ratecounter" in self.vcl
        assert "penaltybox" in self.vcl

    def test_rate_limit_check_in_recv(self):
        assert "ratelimit.check_rate" in self.vcl

    def test_redirect_signal_in_recv(self):
        assert "error 700" in self.vcl

    def test_url_rewrite_in_recv(self):
        assert "regsuball" in self.vcl

    def test_balanced_braces(self):
        assert self.vcl.count("{") == self.vcl.count("}")

    def test_recv_macro_is_first_in_sub(self):
        """#FASTLY recv must appear before any injected snippets in vcl_recv."""
        recv_start = self.vcl.find("sub vcl_recv")
        recv_end = self.vcl.find("sub vcl_hash")
        recv_body = self.vcl[recv_start:recv_end]
        macro_pos = recv_body.find("#FASTLY recv")
        # There should be content after the macro
        assert macro_pos != -1
        # Verify no backend/module snippets appear before #FASTLY recv
        first_snippet_pos = recv_body.find("req.backend")
        assert macro_pos < first_snippet_pos, "#FASTLY recv must precede req.backend"


class TestServiceNameEmbedded:
    def test_service_name_in_comment(self):
        config = VCLConfig(
            service_name="my-api",
            modules=[BackendsModule(backends=[BackendConfig("o1", "origin.example.com")])],
        )
        vcl = render_vcl(config)
        assert "my-api" in vcl


class TestBoilerplateDefaults:
    """Verify that the Fastly boilerplate defaults are present in all renders."""

    def setup_method(self):
        self.minimal_vcl = render_vcl(_make_minimal_config())
        self.boilerplate_vcl = render_vcl(VCLConfig(service_name="bp-test", modules=[]))

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_all_subroutines_present_minimal(self, sub):
        assert sub in self.minimal_vcl

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_all_subroutines_present_boilerplate(self, sub):
        assert sub in self.boilerplate_vcl

    def test_recv_method_check_present(self):
        assert 'req.request != "HEAD"' in self.minimal_vcl
        assert 'req.request != "HEAD"' in self.boilerplate_vcl

    def test_boilerplate_fetch_defaults_when_no_snippets(self):
        """Full boilerplate fetch logic appears when no caching module is configured."""
        assert "Fastly-Restarts" in self.boilerplate_vcl
        assert "Fastly-Cachetype" in self.boilerplate_vcl
        assert "beresp.ttl = 3600s" in self.boilerplate_vcl

    def test_boilerplate_fetch_replaced_by_module_snippets(self):
        """When a caching module is present, its TTL replaces the boilerplate default."""
        caching = CachingModule(default_ttl=7200)
        config = VCLConfig(
            service_name="cached",
            modules=[
                BackendsModule(backends=[BackendConfig("o1", "origin.example.com")]),
                caching,
            ],
        )
        vcl = render_vcl(config)
        assert "beresp.ttl = 7200s" in vcl
        # Boilerplate default TTL should not appear when module provides its own
        assert "beresp.ttl = 3600s" not in vcl

    def test_boilerplate_balanced_braces(self):
        assert self.boilerplate_vcl.count("{") == self.boilerplate_vcl.count("}")


class TestVideoStreamingIntegration:
    """Full render with VideoStreamingModule alongside backends."""

    def setup_method(self):
        backends = BackendsModule(
            backends=[BackendConfig(name="origin_1", host="cdn.example.com")]
        )
        video = VideoStreamingModule(mode="live")
        config = VCLConfig(
            service_name="video-test",
            modules=[backends, video],
        )
        self.vcl = render_vcl(config)

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_required_subs_present(self, sub):
        assert sub in self.vcl

    @pytest.mark.parametrize("macro", REQUIRED_FASTLY_MACROS)
    def test_fastly_macros_present(self, macro):
        assert macro in self.vcl

    def test_balanced_braces(self):
        assert self.vcl.count("{") == self.vcl.count("}")

    def test_segmented_caching_in_recv(self):
        assert "req.enable_segmented_caching = true" in self.vcl

    def test_manifest_ttl_in_fetch(self):
        # live mode default: 2s
        assert "beresp.ttl = 2s" in self.vcl

    def test_segment_ttl_in_fetch(self):
        assert "beresp.ttl = 86400s" in self.vcl

    def test_streaming_miss_in_fetch(self):
        assert "beresp.do_stream = true" in self.vcl

    def test_gzip_disabled_in_fetch(self):
        assert "beresp.gzip = false" in self.vcl

    def test_cookie_stripping_in_deliver(self):
        assert "unset resp.http.Set-Cookie" in self.vcl

    def test_vary_stripping_in_deliver(self):
        assert "unset resp.http.Vary" in self.vcl

    def test_error_recovery_in_fetch(self):
        assert "beresp.status >= 500" in self.vcl
        assert "beresp.ttl = 1s" in self.vcl


class TestLogStreamingIntegration:
    """Full render with LogStreamingModule alongside backends."""

    def setup_method(self):
        backends = BackendsModule(
            backends=[BackendConfig(name="origin_1", host="cdn.example.com")]
        )
        log_streaming = LogStreamingModule(endpoint_name="my-logs", format="json")
        config = VCLConfig(
            service_name="log-test",
            modules=[backends, log_streaming],
        )
        self.vcl = render_vcl(config)

    @pytest.mark.parametrize("sub", REQUIRED_SUBS)
    def test_required_subs_present(self, sub):
        assert sub in self.vcl

    @pytest.mark.parametrize("macro", REQUIRED_FASTLY_MACROS)
    def test_fastly_macros_present(self, macro):
        assert macro in self.vcl

    def test_balanced_braces(self):
        assert self.vcl.count("{") == self.vcl.count("}")

    def test_syslog_prefix_in_output(self):
        assert 'log "syslog "' in self.vcl

    def test_endpoint_name_in_output(self):
        assert "my-logs" in self.vcl

    def test_json_host_key_in_output(self):
        assert "host" in self.vcl

    def test_json_method_key_in_output(self):
        assert "method" in self.vcl

    def test_json_url_key_in_output(self):
        assert "url" in self.vcl
