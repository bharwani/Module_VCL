"""Unit tests for LogStreamingModule."""
import pytest

from vcl_builder.modules.log_streaming import LogStreamingModule


class TestLogStreamingModuleName:
    def test_name(self):
        m = LogStreamingModule(endpoint_name="my-logs")
        assert m.name == "log_streaming"


class TestCombinedFormat:
    def setup_method(self):
        m = LogStreamingModule(endpoint_name="access-logs", format="combined")
        self.snippets = m.get_snippets()
        self.vcl_log = "\n".join(self.snippets.vcl_log)

    def test_log_statement_present(self):
        assert "log " in self.vcl_log

    def test_endpoint_name_present(self):
        assert "access-logs" in self.vcl_log

    def test_ip_field_present(self):
        assert "Fastly-Client-IP" in self.vcl_log

    def test_url_field_present(self):
        assert "req.url" in self.vcl_log

    def test_status_field_present(self):
        assert "resp.status" in self.vcl_log


class TestJsonFormat:
    def setup_method(self):
        m = LogStreamingModule(endpoint_name="json-logs", format="json")
        self.snippets = m.get_snippets()
        self.vcl_log = "\n".join(self.snippets.vcl_log)

    def test_host_key_present(self):
        assert "host" in self.vcl_log

    def test_method_key_present(self):
        assert "method" in self.vcl_log

    def test_url_key_present(self):
        assert "url" in self.vcl_log

    def test_status_key_present(self):
        assert "status" in self.vcl_log

    def test_ip_key_present(self):
        assert "ip" in self.vcl_log


class TestCustomFormat:
    def test_custom_expression_verbatim(self):
        custom = 'req.http.X-Custom-Field + " " + resp.status'
        m = LogStreamingModule(endpoint_name="custom-logs", format="custom", custom_format=custom)
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert custom in vcl_log


class TestErrorsOnly:
    def test_errors_only_wraps_with_condition(self):
        m = LogStreamingModule(endpoint_name="error-logs", errors_only=True)
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert "resp.status >= 400" in vcl_log

    def test_errors_only_false_no_condition(self):
        m = LogStreamingModule(endpoint_name="all-logs", errors_only=False)
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert "resp.status >= 400" not in vcl_log


class TestNoErrorsOnlyDefault:
    def test_default_errors_only_is_false(self):
        m = LogStreamingModule(endpoint_name="logs")
        assert m.errors_only is False
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert "resp.status >= 400" not in vcl_log


class TestSyslogPrefix:
    @pytest.mark.parametrize("fmt", ["combined", "json"])
    def test_log_starts_with_syslog(self, fmt):
        m = LogStreamingModule(endpoint_name="ep", format=fmt)
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert '"syslog "' in vcl_log

    def test_log_includes_service_id(self):
        m = LogStreamingModule(endpoint_name="ep")
        vcl_log = "\n".join(m.get_snippets().vcl_log)
        assert "req.service_id" in vcl_log


class TestNoVclRecvOrFetchSnippets:
    def setup_method(self):
        self.snippets = LogStreamingModule(endpoint_name="ep").get_snippets()

    def test_vcl_recv_empty(self):
        assert self.snippets.vcl_recv == []

    def test_vcl_fetch_empty(self):
        assert self.snippets.vcl_fetch == []

    def test_vcl_deliver_empty(self):
        assert self.snippets.vcl_deliver == []

    def test_vcl_log_not_empty(self):
        assert len(self.snippets.vcl_log) > 0
