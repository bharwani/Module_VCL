import pytest

from vcl_builder.modules.backends import BackendConfig, BackendsModule, HealthCheck


def make_single_backend(**kwargs) -> BackendConfig:
    defaults = dict(name="origin_1", host="example.com", port=443, use_ssl=True, ssl_check_cert=True)
    defaults.update(kwargs)
    return BackendConfig(**defaults)


class TestBackendsModuleName:
    def test_name(self):
        m = BackendsModule(backends=[make_single_backend()])
        assert m.name == "backends"


class TestSingleBackend:
    def setup_method(self):
        self.module = BackendsModule(backends=[make_single_backend()])
        self.snippets = self.module.get_snippets()

    def test_backend_block_in_backends(self):
        assert len(self.snippets.backends) == 1

    def test_backend_block_has_host(self):
        assert 'example.com' in self.snippets.backends[0]

    def test_backend_block_has_port(self):
        assert '"443"' in self.snippets.backends[0]

    def test_backend_block_has_ssl(self):
        assert '.ssl = true' in self.snippets.backends[0]

    def test_vcl_recv_sets_backend(self):
        assert len(self.snippets.vcl_recv) == 1
        assert 'req.backend' in self.snippets.vcl_recv[0]
        assert 'origin_1' in self.snippets.vcl_recv[0]

    def test_no_director_block(self):
        # Single backend: no director
        joined = "\n".join(self.snippets.backends)
        assert 'director' not in joined


class TestSSLOptions:
    def test_no_ssl(self):
        m = BackendsModule(backends=[make_single_backend(use_ssl=False)])
        snippets = m.get_snippets()
        assert '.ssl' not in snippets.backends[0]

    def test_ssl_no_cert_check(self):
        m = BackendsModule(backends=[make_single_backend(use_ssl=True, ssl_check_cert=False)])
        snippets = m.get_snippets()
        assert '.ssl_check_cert = false' in snippets.backends[0]


class TestHealthCheck:
    def test_health_check_probe_in_block(self):
        hc = HealthCheck(path="/ping")
        m = BackendsModule(backends=[make_single_backend(health_check=hc)])
        snippets = m.get_snippets()
        assert '.probe' in snippets.backends[0]
        assert '/ping' in snippets.backends[0]


class TestMultipleBackendsWithDirector:
    def setup_method(self):
        backends = [
            BackendConfig("b1", "b1.example.com"),
            BackendConfig("b2", "b2.example.com"),
        ]
        self.module = BackendsModule(backends=backends, director_type="random")
        self.snippets = self.module.get_snippets()

    def test_two_backend_blocks(self):
        # Two backend blocks + one director block
        assert len(self.snippets.backends) == 3

    def test_director_block_type(self):
        director_block = self.snippets.backends[-1]
        assert 'director vcl_director random' in director_block

    def test_director_references_backends(self):
        director_block = self.snippets.backends[-1]
        assert 'b1' in director_block
        assert 'b2' in director_block

    def test_recv_sets_director(self):
        assert 'vcl_director' in self.snippets.vcl_recv[0]


class TestDirectorNone:
    def test_no_director_block_when_type_none(self):
        backends = [
            BackendConfig("b1", "b1.example.com"),
            BackendConfig("b2", "b2.example.com"),
        ]
        m = BackendsModule(backends=backends, director_type="none")
        snippets = m.get_snippets()
        joined = "\n".join(snippets.backends)
        assert 'director' not in joined

    def test_recv_uses_first_backend(self):
        backends = [BackendConfig("b1", "b1.example.com"), BackendConfig("b2", "b2.example.com")]
        m = BackendsModule(backends=backends, director_type="none")
        snippets = m.get_snippets()
        assert 'b1' in snippets.vcl_recv[0]


class TestEmptyBackendsRaises:
    def test_raises(self):
        with pytest.raises(ValueError):
            BackendsModule(backends=[])
