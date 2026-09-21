"""Isolate actual VK upload helpers without app, database, or provider access."""

from __future__ import annotations

import ast
from contextlib import ExitStack
import ipaddress
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]
MEDIA_SOURCE = ROOT / "src/services/social_posts/media_delivery.py"
JSON_SOURCE = ROOT / "src/services/social_posts/recommendations_handoff.py"
NETWORK_SOURCE = ROOT / "src/core/outbound_network.py"
PHOTO_BYTES = b"synthetic-approved-photo"


def _load_helpers():
    namespace = {"json": json, "sys": sys, "urllib": urllib, "uuid": uuid}
    network = types.ModuleType("vk_upload_test_network")
    sys.modules[network.__name__] = network
    exec(compile(NETWORK_SOURCE.read_text(), str(NETWORK_SOURCE), "exec"), network.__dict__)
    namespace["outbound_network"] = network
    requested = {
        "_multipart_form_data", "_vk_api_request", "_upload_vk_wall_photos",
        "_vk_upload_request",
    }
    nodes = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    tree = ast.parse(MEDIA_SOURCE.read_text())
    nodes.extend(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in requested)
    json_tree = ast.parse(JSON_SOURCE.read_text())
    nodes.extend(node for node in json_tree.body if isinstance(node, ast.FunctionDef) and node.name == "_json_dict")
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, str(MEDIA_SOURCE), "exec"), namespace)
    return namespace


class _Response:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()
        self.closed = False
        self.status = 200
        self.headers = {}
        self.read_limits = []
        self.released = False
        self.read_error = None

    def read(self, limit=None):
        self.read_limits.append(limit)
        if self.read_error is not None:
            raise self.read_error
        return self.body if limit is None else self.body[:limit]

    def close(self):
        self.closed = True

    def release_conn(self):
        self.released = True


class VkUploadDestinationTests(unittest.TestCase):
    def _upload(self, upload_url, *, dns_answers=None, proxy_url="", upload_status=200,
                response_bytes=None, request_error=None, read_error=None):
        namespace = _load_helpers()
        calls = []
        responses = []
        observed = {"dns": [], "managers": [], "requests": [], "cleared": 0}
        self.observed = observed

        def transport(request, timeout):
            calls.append({"url": request.full_url, "body": request.data, "timeout": timeout})
            if request.full_url.startswith("https://api.vk.com/method/photos.getWallUploadServer?"):
                payload = {"response": {"upload_url": upload_url}}
            elif request.full_url == "https://api.vk.com/method/photos.saveWallPhoto":
                payload = {"response": [{"owner_id": -17, "id": 23}]}
            else:
                payload = {"server": 17, "photo": "x" * 1200, "hash": "synthetic-photo-hash"}
            response = _Response(payload)
            responses.append(response)
            return response

        namespace["outbound_urlopen"] = transport
        namespace["_media_asset_file"] = lambda _asset: {
            "content": PHOTO_BYTES, "mime_type": "image/jpeg", "filename": "test.jpg",
        }
        network = namespace["outbound_network"]

        class Manager:
            def __init__(self, *args, **options):
                self.options = options
                observed["managers"].append({"args": args, "options": options})

            def urlopen(self, method, url, **kwargs):
                observed["requests"].append({"method": method, "url": url, **kwargs})
                if request_error is not None:
                    raise request_error
                parsed = urllib.parse.urlsplit(url)
                logical_url = urllib.parse.urlunsplit(("https", kwargs["headers"]["Host"], parsed.path, parsed.query, ""))
                request = urllib.request.Request(logical_url, data=kwargs["body"], method=method)
                response = transport(request, self.options["timeout"].total)
                response.status = upload_status
                response.read_error = read_error
                if response_bytes is not None:
                    response.body = response_bytes
                return response

            def clear(self):
                observed["cleared"] += 1

        answers = list(dns_answers) if dns_answers is not None else None

        def resolving(hostname, port, **_kwargs):
            observed["dns"].append((hostname, port))
            if answers is not None:
                values = answers.pop(0)
                if isinstance(values, Exception):
                    raise values
            else:
                try:
                    values = [str(ipaddress.ip_address(hostname))]
                except ValueError:
                    values = ["93.184.216.34"]
            return [(10 if ":" in value else 2, 1, 6, "", (value, port)) for value in values]

        guards = ExitStack()
        guards.enter_context(patch.object(network, "resolve_outbound_http_proxy", return_value=proxy_url))
        guards.enter_context(patch.object(network.socket, "getaddrinfo", side_effect=resolving))
        guards.enter_context(patch.object(network.urllib3, "PoolManager", Manager))
        guards.enter_context(patch.object(network.urllib3, "ProxyManager", Manager))
        try:
            result = namespace["_upload_vk_wall_photos"](
                token="synthetic-token", owner_id="-17", api_version="5.199",
                media_assets=[{"id": "synthetic-photo"}],
            )
        finally:
            guards.close()
        return result, calls, responses

    def _assert_rejected_before_upload(self, upload_url):
        result, calls, responses = self._upload(upload_url)
        sent_photo = [call for call in calls if call["body"] and PHOTO_BYTES in call["body"]]
        self.assertEqual(sent_photo, [], "provider-issued non-public destination received photo bytes")
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1, "must not upload or save after invalid destination")
        self.assertTrue(all(response.closed for response in responses))

    def test_rejects_loopback_upload(self):
        self._assert_rejected_before_upload("http://127.0.0.1/internal")

    def test_rejects_metadata_upload(self):
        self._assert_rejected_before_upload("http://169.254.169.254/latest/meta-data")

    def test_rejects_private_upload(self):
        self._assert_rejected_before_upload("http://10.0.0.8/internal")

    def test_rejects_localhost_upload(self):
        self._assert_rejected_before_upload("http://localhost/internal")

    def test_rejects_file_scheme_upload(self):
        self._assert_rejected_before_upload("file:///synthetic-local-file")

    def test_preserves_approved_public_upload_and_full_provider_json(self):
        result, calls, responses = self._upload("https://upload.example.invalid/photo")
        self.assertEqual(result, {"success": True, "attachments": ["photo-17_23"]})
        self.assertEqual(len(calls), 3)
        self.assertIn(PHOTO_BYTES, calls[1]["body"])
        self.assertEqual(calls[1]["url"], "https://upload.example.invalid/photo")
        saved = urllib.parse.parse_qs(calls[2]["body"].decode())
        self.assertEqual(saved["photo"], ["x" * 1200])
        self.assertTrue(all(call["timeout"] == 20 for call in calls))
        self.assertTrue(all(response.closed for response in responses))

    def test_rejects_https_loopback_before_connection(self):
        self._assert_rejected_before_upload("https://127.0.0.1/private")
        self.assertEqual(self.observed["managers"], [])

    def test_rejects_private_dns_answer(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", dns_answers=[["10.0.0.8"]])
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.observed["managers"], [])

    def test_rejects_mixed_public_private_dns_answers(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", dns_answers=[["93.184.216.34", "127.0.0.1"]])
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.observed["managers"], [])

    def test_rejects_rebinding_before_connection(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", dns_answers=[["93.184.216.34"], ["10.0.0.8"]])
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.observed["dns"]), 2)
        self.assertEqual(self.observed["managers"], [])

    def test_rejects_embedded_upload_credentials(self):
        self._assert_rejected_before_upload("https://synthetic-user:synthetic-pass@upload.example.invalid/photo")
        self.assertEqual(self.observed["dns"], [])

    def test_rejects_plain_http_public_upload(self):
        self._assert_rejected_before_upload("http://upload.example.invalid/photo")
        self.assertEqual(self.observed["dns"], [])

    def test_pins_public_ip_and_preserves_hostname_tls_query_and_port(self):
        result, _calls, responses = self._upload("https://upload.example.invalid:8443/photo?part=2")
        self.assertTrue(result["success"])
        request = self.observed["requests"][0]
        self.assertEqual(request["url"], "https://93.184.216.34:8443/photo?part=2")
        self.assertEqual(request["headers"]["Host"], "upload.example.invalid:8443")
        self.assertFalse(request["redirect"])
        self.assertFalse(request["retries"])
        self.assertFalse(request["preload_content"])
        self.assertFalse(request["decode_content"])
        options = self.observed["managers"][0]["options"]
        self.assertEqual(options["server_hostname"], "upload.example.invalid")
        self.assertEqual(options["assert_hostname"], "upload.example.invalid")
        self.assertEqual(options["cert_reqs"], "CERT_REQUIRED")
        self.assertEqual(responses[1].read_limits, [1_000_001])
        self.assertTrue(responses[1].released)
        self.assertEqual(self.observed["cleared"], 1)

    def test_preserves_explicit_proxy_with_pinned_tunnel_target(self):
        result, _calls, _responses = self._upload("https://upload.example.invalid/photo", proxy_url="http://synthetic%2Duser:synthetic%2Dpass@proxy.example.invalid:10809")
        self.assertTrue(result["success"])
        manager = self.observed["managers"][0]
        self.assertEqual(manager["args"], ("http://proxy.example.invalid:10809",))
        self.assertFalse(manager["options"]["use_forwarding_for_https"])
        self.assertEqual(manager["options"]["proxy_headers"], {"proxy-authorization": "Basic c3ludGhldGljLXVzZXI6c3ludGhldGljLXBhc3M="})
        self.assertEqual(self.observed["requests"][0]["url"], "https://93.184.216.34:443/photo")
        self.assertNotIn("Proxy-Authorization", self.observed["requests"][0]["headers"])
        self.assertEqual(manager["options"]["server_hostname"], "upload.example.invalid")

    def test_proxy_failure_has_no_direct_retry_or_private_error_text(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", proxy_url="http://proxy.example.invalid:10809", request_error=TimeoutError("synthetic-private-detail"))
        self.assertFalse(result["success"])
        self.assertNotIn("synthetic-private-detail", str(result))
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.observed["managers"]), 1)
        self.assertEqual(len(self.observed["requests"]), 1)
        self.assertEqual(self.observed["cleared"], 1)

    def test_rejects_redirect_without_followup_or_save(self):
        result, calls, responses = self._upload("https://upload.example.invalid/photo", upload_status=302)
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(self.observed["requests"]), 1)
        self.assertFalse(self.observed["requests"][0]["redirect"])
        self.assertTrue(responses[1].closed and responses[1].released)

    def test_rejects_oversize_response_without_save(self):
        result, calls, responses = self._upload("https://upload.example.invalid/photo", response_bytes=b"x" * 1_000_002)
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(responses[1].read_limits, [1_000_001])
        self.assertTrue(responses[1].closed and responses[1].released)

    def test_rejects_malformed_json_without_save(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", response_bytes=b"not-json")
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 2)

    def test_read_timeout_closes_response_and_manager(self):
        result, calls, responses = self._upload("https://upload.example.invalid/photo", read_error=TimeoutError("synthetic-private-detail"))
        self.assertFalse(result["success"])
        self.assertNotIn("synthetic-private-detail", str(result))
        self.assertEqual(len(calls), 2)
        self.assertTrue(responses[1].closed and responses[1].released)
        self.assertEqual(self.observed["cleared"], 1)

    def test_dns_error_fails_closed_without_connection(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", dns_answers=[OSError("synthetic-private-detail")])
        self.assertFalse(result["success"])
        self.assertNotIn("synthetic-private-detail", str(result))
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.observed["managers"], [])

    def test_invalid_proxy_does_not_fall_back_to_direct(self):
        result, calls, _responses = self._upload("https://upload.example.invalid/photo", proxy_url="socks5://proxy.example.invalid:10808")
        self.assertFalse(result["success"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.observed["managers"], [])

    def test_pins_ipv6_target_and_host_header(self):
        result, _calls, _responses = self._upload("https://[2001:4860:4860::8888]/photo")
        self.assertTrue(result["success"])
        self.assertEqual(self.observed["requests"][0]["url"], "https://[2001:4860:4860::8888]:443/photo")
        self.assertEqual(self.observed["requests"][0]["headers"]["Host"], "[2001:4860:4860::8888]")

    def _assert_real_pool_construction(self, proxy_url):
        network = _load_helpers()["outbound_network"]
        observed = {}
        response = _Response({"synthetic": "response"})

        def no_socket_connect(connection):
            observed["tunnel_host"] = connection._tunnel_host
            observed["tunnel_port"] = connection._tunnel_port
            observed["tunnel_scheme"] = connection._tunnel_scheme

        def intercept_pool_request(pool, method, path, **kwargs):
            observed["pool_host"] = pool.host
            observed["proxy"] = pool.proxy
            observed["method"] = method
            observed["path"] = path
            observed["request"] = kwargs
            connection = pool._new_conn()
            try:
                observed["connection_host"] = connection.host
                observed["sni"] = connection.server_hostname
                observed["certificate_hostname"] = connection.assert_hostname
                observed["certificate_policy"] = connection.cert_reqs
                if pool.proxy:
                    pool._prepare_proxy(connection)
            finally:
                connection.close()
            return response

        guards = ExitStack()
        guards.enter_context(patch.object(network, "resolve_outbound_http_proxy", return_value=proxy_url))
        guards.enter_context(patch.object(network.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]))
        guards.enter_context(patch.object(network.urllib3.connectionpool.HTTPSConnectionPool, "urlopen", intercept_pool_request))
        guards.enter_context(patch.object(network.urllib3.connection.HTTPSConnection, "connect", no_socket_connect))
        try:
            result = network.public_pinned_https_post(
                "https://upload.example.invalid/photo?part=2", PHOTO_BYTES,
                {"Content-Type": "application/octet-stream"},
            )
        finally:
            guards.close()
        self.assertEqual(result.body, response.body)
        self.assertEqual(observed["pool_host"], "93.184.216.34")
        self.assertEqual(observed["sni"], "upload.example.invalid")
        self.assertEqual(observed["certificate_hostname"], "upload.example.invalid")
        self.assertEqual(observed["certificate_policy"], "CERT_REQUIRED")
        self.assertEqual(observed["method"], "POST")
        self.assertEqual(observed["path"], "/photo?part=2")
        self.assertEqual(observed["request"]["headers"]["Host"], "upload.example.invalid")
        self.assertFalse(observed["request"]["redirect"])
        self.assertTrue(response.closed and response.released)
        if proxy_url:
            self.assertEqual(observed["connection_host"], "proxy.example.invalid")
            self.assertEqual(observed["tunnel_host"], "93.184.216.34")
            self.assertEqual(observed["tunnel_port"], 443)
            self.assertEqual(observed["tunnel_scheme"], urllib.parse.urlsplit(proxy_url).scheme)
        else:
            self.assertIsNone(observed["proxy"])
            self.assertEqual(observed["connection_host"], "93.184.216.34")
            self.assertNotIn("tunnel_host", observed)

    def test_actual_urllib3_direct_pool_uses_pinned_ip(self):
        self._assert_real_pool_construction("")

    def test_actual_urllib3_http_proxy_builds_pinned_connect_tunnel(self):
        self._assert_real_pool_construction("http://proxy.example.invalid:10809")

    def test_actual_urllib3_https_proxy_builds_pinned_connect_tunnel(self):
        self._assert_real_pool_construction("https://proxy.example.invalid:10809")


if __name__ == "__main__":
    unittest.main()
