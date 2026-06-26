from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RagflowError(RuntimeError):
    pass


@dataclass(slots=True)
class RagflowClient:
    """RAGFlow REST API 客户端适配层。

    覆盖数据集管理、文档上传、解析触发、检索和对话生成。
    所有方法在出错时统一抛出 RagflowError。
    """

    base_url: str
    api_key: str
    timeout_seconds: int = 60

    # -- 数据集管理 --

    def create_dataset(
        self,
        name: str,
        description: str = "",
        chunk_method: str = "naive",
        parser_id: str = "naive",
    ) -> dict[str, Any]:
        payload = {
            "name": name,
            "description": description,
            "chunk_method": chunk_method,
            "parser_id": parser_id,
        }
        return self._request("POST", "/api/v1/datasets", payload)

    def list_datasets(self, page: int = 1, page_size: int = 30) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/datasets?page={page}&page_size={page_size}")

    def delete_datasets(self, dataset_ids: list[str]) -> dict[str, Any]:
        return self._request("DELETE", "/api/v1/datasets", {"ids": dataset_ids})

    # -- 文档管理 --

    def upload_document(self, dataset_id: str, file_path: str) -> dict[str, Any]:
        return self._upload_request(dataset_id, file_path)

    def upload_documents(self, dataset_id: str, file_paths: list[str]) -> dict[str, Any]:
        return self._upload_request(dataset_id, file_paths)

    def _upload_request(self, dataset_id: str, file_paths: str | list[str]) -> dict[str, Any]:
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        boundary = "----LinCaoBoundary7MA4YWxkTrZu0gW"
        body_parts: list[bytes] = []
        for fp in file_paths:
            fname = fp.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
            content_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"
            with open(fp, "rb") as fh:
                file_data = fh.read()
            body_parts.append(f"--{boundary}\r\n".encode())
            body_parts.append(
                f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode()
            )
            body_parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
            body_parts.append(file_data)
            body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        url = f"{self.base_url.rstrip('/')}/api/v1/datasets/{dataset_id}/documents"
        request = Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        return self._send(request)

    def list_documents(self, dataset_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/datasets/{dataset_id}/documents")

    def delete_documents(self, dataset_id: str, document_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "DELETE", f"/api/v1/datasets/{dataset_id}/documents", {"ids": document_ids}
        )

    # -- 解析 --

    def parse_documents(self, dataset_id: str, document_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "POST", f"/api/v1/datasets/{dataset_id}/chunks", {"document_ids": document_ids}
        )

    def stop_parsing(self, dataset_id: str, document_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "DELETE", f"/api/v1/datasets/{dataset_id}/chunks", {"document_ids": document_ids}
        )

    # -- 检索 --

    def retrieve_chunks(
        self,
        question: str,
        dataset_ids: list[str],
        page_size: int = 8,
        similarity_threshold: float = 0.2,
        vector_similarity_weight: float = 0.3,
        metadata_condition: dict[str, Any] | None = None,
        keyword: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": question,
            "dataset_ids": dataset_ids,
            "page": 1,
            "page_size": page_size,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight,
            "keyword": keyword,
            "highlight": False,
        }
        if metadata_condition:
            payload["metadata_condition"] = metadata_condition
        return self._request("POST", "/api/v1/retrieval", payload)

    # -- 对话 / 生成 --

    def create_chat_assistant(
        self, name: str, dataset_ids: list[str], llm_model: str = ""
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "dataset_ids": dataset_ids}
        if llm_model:
            payload["llm_id"] = llm_model
        return self._request("POST", "/api/v1/chats", payload)

    def chat_completion(
        self,
        chat_id: str,
        messages: list[dict[str, str]],
        model: str = "model",
        stream: bool = False,
        reference: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "extra_body": {"reference": reference},
        }
        return self._request("POST", f"/api/v1/openai/{chat_id}/chat/completions", payload)

    # -- HTTP 底层 --

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        return self._send(request)

    def _send(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RagflowError(f"RAGFlow HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RagflowError(f"Cannot reach RAGFlow: {exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RagflowError(f"RAGFlow returned non-JSON response: {raw[:200]}") from exc

        if isinstance(parsed, dict) and parsed.get("code") not in (None, 0):
            raise RagflowError(str(parsed.get("message", parsed)))
        return parsed
