from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

import httpx

from semantic_toolkit_sdk import SemanticToolkitClient, SemanticToolkitError


class SdkClientTests(unittest.TestCase):
    def test_json_and_file_calls_keep_public_fields(self):
        captured = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"code": 0, "data": {"ok": True}})

        transport = httpx.MockTransport(handler)
        http = httpx.Client(base_url="http://testserver", transport=transport)
        client = SemanticToolkitClient("http://testserver", client=http)
        client.invoke_text("/api/v1/research-question/text", {"scientific_document_fragment": "研究文本"})
        self.assertEqual(json.loads(captured[-1].content)["scientific_document_fragment"], "研究文本")

        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "paper.txt"
            file_path.write_text("科技文本", encoding="utf-8")
            client.invoke_file("/api/v1/classify/clc/zh/file", file_path, {
                "clc_labeled_data": {"source": "database", "resource_id": "RES-BUNDLED-CLC-ZH"},
            })
        content_type = captured[-1].headers.get("content-type", "")
        self.assertIn("multipart/form-data", content_type)
        body = captured[-1].content
        self.assertIn(b'name="chinese_scientific_document_text"', body)
        self.assertIn(b'name="clc_labeled_data"', body)

    def test_api_error_is_raised_as_sdk_error(self):
        transport = httpx.MockTransport(lambda _: httpx.Response(422, json={"code": 42201, "message": "字段缺失"}))
        client = SemanticToolkitClient("http://testserver", client=httpx.Client(base_url="http://testserver", transport=transport))
        with self.assertRaisesRegex(SemanticToolkitError, "字段缺失"):
            client.invoke_text("/api/v1/research-question/text", {})


if __name__ == "__main__":
    unittest.main()

