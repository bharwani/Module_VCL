from vcl_builder.modules.caching import CachingModule, PathRule


class TestCachingModuleName:
    def test_name(self):
        assert CachingModule().name == "caching"


class TestDefaults:
    def setup_method(self):
        self.module = CachingModule()
        self.snippets = self.module.get_snippets()

    def test_no_recv_snippets_by_default(self):
        # No cookie bypass, no QS stripping → recv should be empty
        assert self.snippets.vcl_recv == []

    def test_default_ttl_in_fetch(self):
        joined = "\n".join(self.snippets.vcl_fetch)
        assert 'beresp.ttl = 3600s' in joined

    def test_unset_set_cookie_in_fetch(self):
        joined = "\n".join(self.snippets.vcl_fetch)
        assert 'unset beresp.http.Set-Cookie' in joined


class TestCookieBypass:
    def test_cookie_bypass_adds_recv_snippet(self):
        m = CachingModule(cookie_bypass=True)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'req.http.Cookie' in joined
        assert 'return(pass)' in joined


class TestQueryStringHandling:
    def test_strip_all(self):
        m = CachingModule(query_string_handling="strip_all")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'req.url.path' in joined

    def test_keep_specific(self):
        m = CachingModule(query_string_handling="keep_specific", keep_params=["page", "sort"])
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_recv)
        assert 'regsuball' in joined
        assert 'page' in joined
        assert 'sort' in joined

    def test_keep_all_no_recv(self):
        m = CachingModule(query_string_handling="keep_all")
        snippets = m.get_snippets()
        # keep_all with no cookie bypass → no recv snippets
        assert snippets.vcl_recv == []


class TestPathRules:
    def test_path_rule_in_fetch(self):
        rules = [PathRule(pattern="/api/", ttl=30), PathRule(pattern="/static/", ttl=86400)]
        m = CachingModule(path_rules=rules)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_fetch)
        assert 'beresp.ttl = 30s' in joined
        assert 'beresp.ttl = 86400s' in joined
        assert '/api/' in joined
        assert '/static/' in joined

    def test_path_rules_before_default(self):
        rules = [PathRule(pattern="/api/", ttl=30)]
        m = CachingModule(default_ttl=3600, path_rules=rules)
        snippets = m.get_snippets()
        joined = "\n".join(snippets.vcl_fetch)
        api_pos = joined.find('beresp.ttl = 30s')
        default_pos = joined.find('beresp.ttl = 3600s')
        assert api_pos < default_pos, "Path rules should appear before the default TTL"
