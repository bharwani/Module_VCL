"""Unit tests for VideoStreamingModule."""
import pytest

from vcl_builder.modules.video_streaming import VideoStreamingModule


def _recv(module: VideoStreamingModule) -> str:
    return "\n".join(module.get_snippets().vcl_recv)


def _fetch(module: VideoStreamingModule) -> str:
    return "\n".join(module.get_snippets().vcl_fetch)


def _deliver(module: VideoStreamingModule) -> str:
    return "\n".join(module.get_snippets().vcl_deliver)


class TestVideoStreamingModuleName:
    def test_name(self):
        assert VideoStreamingModule().name == "video_streaming"


class TestSegmentedCaching:
    def test_enabled_by_default(self):
        recv = _recv(VideoStreamingModule())
        assert "req.enable_segmented_caching = true" in recv

    def test_present_when_explicitly_enabled(self):
        recv = _recv(VideoStreamingModule(enable_segmented_caching=True))
        assert "req.enable_segmented_caching = true" in recv

    def test_absent_when_disabled(self):
        recv = _recv(VideoStreamingModule(enable_segmented_caching=False))
        assert "req.enable_segmented_caching" not in recv

    def test_no_recv_snippets_when_disabled(self):
        snippets = VideoStreamingModule(enable_segmented_caching=False).get_snippets()
        assert snippets.vcl_recv == []


class TestManifestTTL:
    def test_live_default_manifest_ttl(self):
        fetch = _fetch(VideoStreamingModule(mode="live"))
        assert "beresp.ttl = 2s" in fetch

    def test_vod_default_manifest_ttl(self):
        fetch = _fetch(VideoStreamingModule(mode="vod"))
        assert "beresp.ttl = 60s" in fetch

    def test_custom_manifest_ttl(self):
        fetch = _fetch(VideoStreamingModule(manifest_ttl=10))
        assert "beresp.ttl = 10s" in fetch

    def test_m3u8_pattern_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert "m3u8" in fetch

    def test_mpd_pattern_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert "mpd" in fetch

    def test_manifest_cacheable_true(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.cacheable = true" in fetch


class TestSegmentTTL:
    def test_default_segment_ttl(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.ttl = 86400s" in fetch

    def test_custom_segment_ttl(self):
        fetch = _fetch(VideoStreamingModule(segment_ttl=3600))
        assert "beresp.ttl = 3600s" in fetch

    def test_ts_pattern_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert ".ts" in fetch

    def test_m4s_pattern_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert ".m4s" in fetch

    def test_mp4_pattern_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert ".mp4" in fetch


class TestErrorRecovery:
    def test_error_ttl_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.ttl = 1s" in fetch

    def test_grace_present(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.grace = 5s" in fetch

    def test_status_500_condition(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.status >= 500" in fetch

    def test_status_600_condition(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.status < 600" in fetch


class TestStreamingMiss:
    def test_do_stream_enabled_by_default(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.do_stream = true" in fetch

    def test_gzip_disabled_with_streaming_miss(self):
        fetch = _fetch(VideoStreamingModule())
        assert "beresp.gzip = false" in fetch

    def test_no_do_stream_when_disabled(self):
        fetch = _fetch(VideoStreamingModule(enable_streaming_miss=False))
        assert "beresp.do_stream" not in fetch

    def test_no_gzip_directive_when_streaming_miss_disabled(self):
        fetch = _fetch(VideoStreamingModule(enable_streaming_miss=False))
        assert "beresp.gzip" not in fetch


class TestStripCookies:
    def test_set_cookie_unset_by_default(self):
        deliver = _deliver(VideoStreamingModule())
        assert "unset resp.http.Set-Cookie" in deliver

    def test_vary_unset_by_default(self):
        deliver = _deliver(VideoStreamingModule())
        assert "unset resp.http.Vary" in deliver

    def test_all_media_extensions_in_deliver_pattern(self):
        deliver = _deliver(VideoStreamingModule())
        for ext in ("m3u8", "mpd", "ts", "m4s", "mp4"):
            assert ext in deliver

    def test_no_deliver_snippet_when_strip_cookies_disabled(self):
        snippets = VideoStreamingModule(strip_cookies=False).get_snippets()
        assert snippets.vcl_deliver == []


class TestDisableFeatures:
    def test_no_recv_when_segmented_caching_off(self):
        snippets = VideoStreamingModule(enable_segmented_caching=False).get_snippets()
        assert snippets.vcl_recv == []

    def test_fetch_still_present_when_segmented_caching_off(self):
        # fetch snippets are independent of segmented caching flag
        fetch = _fetch(VideoStreamingModule(enable_segmented_caching=False))
        assert "beresp.ttl" in fetch

    def test_no_do_stream_when_streaming_miss_off(self):
        fetch = _fetch(VideoStreamingModule(enable_streaming_miss=False))
        assert "beresp.do_stream" not in fetch

    def test_all_features_disabled(self):
        snippets = VideoStreamingModule(
            enable_segmented_caching=False,
            enable_streaming_miss=False,
            strip_cookies=False,
        ).get_snippets()
        assert snippets.vcl_recv == []
        assert snippets.vcl_deliver == []
        # fetch still has TTL + error recovery
        assert snippets.vcl_fetch != []
