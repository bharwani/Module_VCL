from vcl_builder.modules.rate_limit import RateLimitModule


class TestRateLimitModuleName:
    def test_name(self):
        assert RateLimitModule().name == "rate_limit"


class TestTopLevelDeclarations:
    def setup_method(self):
        self.module = RateLimitModule()
        self.snippets = self.module.get_snippets()

    def test_ratecounter_declared(self):
        joined = "\n".join(self.snippets.backends)
        assert 'ratecounter' in joined

    def test_penaltybox_declared(self):
        joined = "\n".join(self.snippets.backends)
        assert 'penaltybox' in joined


class TestRecvSnippet:
    def test_check_rate_call_in_recv(self):
        m = RateLimitModule(requests_per_second=5)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'ratelimit.check_rate' in joined

    def test_rps_value_in_recv(self):
        m = RateLimitModule(requests_per_second=20)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert '20' in joined

    def test_429_action(self):
        m = RateLimitModule(action="429")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert '429' in joined

    def test_redirect_action_uses_750(self):
        m = RateLimitModule(action="redirect", redirect_url="https://example.com/limited")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert '750' in joined


class TestScopePerIpPath:
    def test_per_ip_path_uses_url_path(self):
        m = RateLimitModule(scope="per_ip_path")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'req.url.path' in joined

    def test_per_ip_uses_client_ip(self):
        m = RateLimitModule(scope="per_ip")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'Fastly-Client-IP' in joined


class TestErrorSnippets:
    def test_429_error_snippet(self):
        m = RateLimitModule(action="429")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_error)
        assert 'obj.status == 429' in joined
        assert 'application/json' in joined

    def test_redirect_error_snippet(self):
        m = RateLimitModule(action="redirect", redirect_url="https://example.com/limited")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_error)
        assert 'obj.status == 750' in joined
        assert 'obj.http.Location' in joined
