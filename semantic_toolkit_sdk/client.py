from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import httpx


class SemanticToolkitError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


_PRIMARY_FILE_FIELDS = {
    "/move/abstract/zh/": "chinese_scientific_abstract",
    "/move/abstract/en/": "english_scientific_abstract",
    "/move/fund/zh/": "project_document_text",
    "/classify/clc/zh/": "chinese_scientific_document_text",
    "/classify/clc/en/": "english_scientific_document_text",
    "/classify/domain/": "domain_scientific_literature_data",
    "/keywords/zh/": "chinese_scientific_abstract",
    "/keywords/en/": "english_scientific_abstract",
    "/research-question/": "scientific_document_fragment",
    "/citation-sentiment/": "scientific_document_full_text",
    "/citation/intent/": "citation_sentence_and_context",
    "/citation-intent/": "citation_sentence_and_context",
    "/concept-definition/": "scientific_document_fragment_or_batch_text",
    "/ner/general/": "bilingual_scientific_document_text",
    "/ner/research/": "academic_abstract_or_technical_report_text",
    "/ner/domain/": "domain_scientific_document_text",
    "/cluster/deep/": "scientific_document_texts",
    "/cluster-labels/": "cluster_phrase_sets",
    "/review/structured/": "document_set",
}


def _primary_field(endpoint: str) -> str:
    return next((field for marker, field in _PRIMARY_FILE_FIELDS.items() if marker in endpoint), "file")


def _form_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class SemanticToolkitClient:
    """Thin SDK: field names and response objects are identical to REST API."""

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        *,
        timeout: float = 300.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._owns_client = client is None
        self.client = client or httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> "SemanticToolkitClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @staticmethod
    def _check(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise SemanticToolkitError(
                f"服务返回非 JSON 响应（HTTP {response.status_code}）",
                status_code=response.status_code,
                response=response.text,
            ) from exc
        if response.is_error or int(body.get("code", 0) or 0) != 0:
            detail = body.get("detail") or body.get("message") or f"HTTP {response.status_code}"
            raise SemanticToolkitError(str(detail), status_code=response.status_code, response=body)
        return body

    def invoke_text(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._check(self.client.post(endpoint, json=dict(payload)))

    def invoke_texts(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.invoke_text(endpoint, payload)

    def invoke_history(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.invoke_text(endpoint, payload)

    def invoke_collection(self, endpoint: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.invoke_text(endpoint, payload)

    def invoke_file(
        self,
        endpoint: str,
        file_path: str | Path,
        payload: Optional[Mapping[str, Any]] = None,
        *,
        file_field: Optional[str] = None,
    ) -> dict[str, Any]:
        return self.invoke_files(endpoint, [file_path], payload or {}, file_field=file_field)

    def invoke_files(
        self,
        endpoint: str,
        file_paths: Iterable[str | Path],
        payload: Optional[Mapping[str, Any]] = None,
        *,
        file_field: Optional[str] = None,
    ) -> dict[str, Any]:
        paths = [Path(path) for path in file_paths]
        if not paths:
            raise ValueError("file_paths 不能为空")
        field = file_field or _primary_field(endpoint)
        streams = []
        try:
            files = []
            for path in paths:
                stream = path.open("rb")
                streams.append(stream)
                files.append((field, (path.name, stream, mimetypes.guess_type(path.name)[0] or "application/octet-stream")))
            data = {key: _form_value(value) for key, value in dict(payload or {}).items() if value is not None}
            return self._check(self.client.post(endpoint, files=files, data=data))
        finally:
            for stream in streams:
                stream.close()

    def evaluate_deep_cluster(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self.invoke_text("/api/v1/cluster/deep/evaluate", payload)

