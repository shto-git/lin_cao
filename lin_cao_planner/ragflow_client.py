from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RagflowError(RuntimeError):
    pass


@dataclass(slots=True)
class RagflowClient:
    base_url: str
    api_key: str
    timeout_seconds: int = 60

    def create_dataset(self, name: str, description: str = "", chunk_method: str = "naive") -> dict[str, Any]:
        payload = {
            "name": name,
            "description": description,
            "chunk_method": chunk_method,
        }
        return self._request("POST", "/api/v1/datasets", payload)

    def parse_documents(self, dataset_id: str, document_ids: list[str]) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/datasets/{dataset_id}/chunks", {"document_ids": document_ids})

    def retrieve_chunks(
        self,
        question: str,
        dataset_ids: list[str],
        page_size: int = 8,
        similarity_threshold: float = 0.2,
        vector_similarity_weight: float = 0.3,
        metadata_condition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "question": question,
            "dataset_ids": dataset_ids,
            "page": 1,
            "page_size": page_size,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight,
            "keyword": True,
            "highlight": False,
        }
        if metadata_condition:
            payload["metadata_condition"] = metadata_condition
        return self._request("POST", "/api/v1/retrieval", payload)

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
