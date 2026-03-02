from vcl_builder.modules.redirects import RedirectRule, RedirectsModule, RewriteRule


class TestRedirectsModuleName:
    def test_name(self):
        assert RedirectsModule().name == "redirects"


class TestEmptyModule:
    def test_no_snippets_when_empty(self):
        m = RedirectsModule()
        snippets = m.get_snippets()
        assert snippets.vcl_recv == []
        assert snippets.vcl_error == []


class TestRedirectRules:
    def setup_method(self):
        rules = [
            RedirectRule(from_path="^/old", to_url="https://example.com/new", status_code=301),
            RedirectRule(from_path="^/temp", to_url="https://example.com/temp-new", status_code=302),
        ]
        self.module = RedirectsModule(redirects=rules)
        self.snippets = self.module.get_snippets()

    def test_recv_has_error_signal_for_301(self):
        joined = "\n".join(self.snippets.vcl_recv)
        assert 'error 700' in joined
        assert '^/old' in joined

    def test_recv_has_error_signal_for_302(self):
        joined = "\n".join(self.snippets.vcl_recv)
        assert 'error 701' in joined
        assert '^/temp' in joined

    def test_vcl_error_handles_700(self):
        joined = "\n".join(self.snippets.vcl_error)
        assert 'obj.status == 700' in joined
        assert 'obj.http.Location' in joined
        assert '301' in joined

    def test_vcl_error_handles_701(self):
        joined = "\n".join(self.snippets.vcl_error)
        assert 'obj.status == 701' in joined
        assert '302' in joined

    def test_destination_carried_via_obj_response(self):
        joined = "\n".join(self.snippets.vcl_recv)
        # destination URL is passed as the error message string
        assert 'https://example.com/new' in joined

    def test_error_block_uses_obj_response_for_location(self):
        joined = "\n".join(self.snippets.vcl_error)
        assert 'obj.response' in joined


class TestRewriteRules:
    def test_rewrite_uses_regsuball(self):
        rules = [RewriteRule(from_pattern=r"^/api/v1/(.*)", to_path=r"/api/v2/\1")]
        m = RedirectsModule(rewrites=rules)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'regsuball' in joined
        assert r'^/api/v1/' in joined

    def test_rewrite_before_redirects(self):
        rewrites = [RewriteRule(from_pattern="^/x", to_path="/y")]
        redirects = [RedirectRule(from_path="^/old", to_url="https://new.example.com")]
        m = RedirectsModule(redirects=redirects, rewrites=rewrites)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        rewrite_pos = joined.find('regsuball')
        redirect_pos = joined.find('error 700')
        assert rewrite_pos < redirect_pos, "Rewrites should appear before redirects in vcl_recv"


class TestDeduplicatedErrorBlocks:
    def test_two_301_redirects_produce_one_error_block(self):
        rules = [
            RedirectRule("^/a", "https://example.com/a", 301),
            RedirectRule("^/b", "https://example.com/b", 301),
        ]
        m = RedirectsModule(redirects=rules)
        snippets = m.get_snippets()
        # Should have only one block for error code 700
        error_joined = "\n".join(snippets.vcl_error)
        assert error_joined.count("obj.status == 700") == 1
