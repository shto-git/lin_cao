"""Chapter draft generation with RAG-enhanced prompting.

Supports any OpenAI-compatible API (DeepSeek, Qwen, OpenAI, etc.)
or RAGFlow\'s built-in chat completion.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# ── LLM Client ──────────────────────────────────────────────


@dataclass(slots=True)
class LLMConfig:
    """LLM connection configuration.

    Priority: environment variables > explicit config.
    Environment variables:
        LINCAO_LLM_API_KEY    — API key
        LINCAO_LLM_BASE_URL   — API base URL (default: https://api.deepseek.com/v1)
        LINCAO_LLM_MODEL      — model name (default: deepseek-chat)
    """

    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"
    temperature: float = 0.3
    max_tokens: int = 4096
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            api_key=os.environ.get("LINCAO_LLM_API_KEY", ""),
            base_url=os.environ.get("LINCAO_LLM_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.environ.get("LINCAO_LLM_MODEL", "deepseek-chat"),
        )


class LLMClient:
    """Minimal OpenAI-compatible chat completion client (no external deps)."""

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant response text."""
        if not self.config.api_key:
            raise RuntimeError(
                "LLM API key not configured. Set LINCAO_LLM_API_KEY environment variable."
            )

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature if temperature is not None else self.config.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
            "stream": False,
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Cannot reach LLM API: {exc.reason}") from exc

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            raise RuntimeError(f"LLM API returned non-JSON: {raw[:200]}")

        try:
            return parsed["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LLM response format: {parsed}") from exc


# ── Prompt Templates ────────────────────────────────────────

SYSTEM_PROMPT = """你是一位资深的林草规划编制专家。你的任务是根据提供的参考资料，撰写专业、准确、有据可查的规划章节文本。

## 写作原则

1. **以资料为依据**：所有数据、政策引用、工程名称必须来自提供的参考资料。
2. **不编造**：如果参考资料中没有相关信息，明确标注"待补充"，不要编造看似合理的内容。
3. **口径一致**：同一指标在全文中保持单位、年份和统计范围一致。
4. **专业规范**：使用林草行业规范术语，避免模糊表述（如"据说""大概""有关部门"）。
5. **引用标注**：在关键数据和政策表述后标注来源，格式为 [来源: 文件名]。

## 写作风格

- 语言正式、严谨，符合政府规划文件风格
- 数据准确，有明确的年份和单位
- 政策引用写明文件全称
- 结构清晰，段落之间有逻辑衔接
- 避免空话套话，内容要具体可操作
"""

CHAPTER_USER_PROMPT = """请根据以下参考资料，撰写规划章节。

## 章节信息

- **章节路径**：{title_path}
- **目标字数**：约 {target_words} 字
- **写作要求**：{requirements}

## 必须引用的资料类型

{evidence_types}

## 写作约束

{constraints}

## 参考资料

{evidence_text}

## 输出要求

1. 直接输出章节正文，不要加章节标题（标题已确定）
2. 字数控制在目标字数的 90%-110%
3. 在关键数据后标注来源 [来源: xxx]
4. 如果某项内容在参考资料中找不到依据，写"（该内容待补充，建议参考xxx资料）"
5. 使用 Markdown 格式，段落之间空行分隔

请开始撰写：
"""


# ── Generator ───────────────────────────────────────────────


@dataclass(slots=True)
class EvidenceChunk:
    """A piece of evidence retrieved from the knowledge base."""

    content: str
    document_name: str = ""
    similarity: float = 0.0
    page_number: int = 0

    def format_for_prompt(self) -> str:
        parts = [f"### 来源: {self.document_name or '未知'}"]
        if self.page_number:
            parts.append(f"页码: {self.page_number}")
        parts.append(self.content)
        return "\n".join(parts)


@dataclass(slots=True)
class GenerationResult:
    """Result of chapter draft generation."""

    outline_id: str
    title: str
    content: str
    evidence_ids: list[str] = field(default_factory=list)
    word_count: int = 0
    status: str = "draft"
    warnings: list[str] = field(default_factory=list)


def generate_chapter_draft(
    outline_id: str,
    title_path: str,
    target_words: int,
    requirements: list[str],
    evidence_types: list[str],
    constraints: list[str],
    evidence_chunks: list[EvidenceChunk],
    llm_client: LLMClient | None = None,
) -> GenerationResult:
    """Generate a chapter draft using RAG-enhanced prompting.

    If llm_client is None or no API key is configured, returns a placeholder
    draft with the evidence summary for manual review.
    """
    # Build the user prompt
    evidence_text = "\n\n".join(chunk.format_for_prompt() for chunk in evidence_chunks)
    if not evidence_text:
        evidence_text = "（暂无检索到的参考资料，请先上传资料并执行检索）"

    user_prompt = CHAPTER_USER_PROMPT.format(
        title_path=title_path,
        target_words=target_words,
        requirements="\n".join(f"- {r}" for r in requirements) if requirements else "无特殊要求",
        evidence_types="、".join(evidence_types) if evidence_types else "不限",
        constraints="\n".join(f"- {c}" for c in constraints),
        evidence_text=evidence_text,
    )

    warnings: list[str] = []
    content = ""

    # Try LLM generation
    client = llm_client or LLMClient()
    if client.config.api_key:
        try:
            content = client.complete(SYSTEM_PROMPT, user_prompt, temperature=0.3, max_tokens=min(target_words * 2, 8000))
        except RuntimeError as exc:
            warnings.append(f"LLM 调用失败: {exc}，返回占位草稿")
            content = _build_placeholder_draft(title_path, evidence_chunks, warnings)
    else:
        warnings.append("未配置 LLM API Key（LINCAO_LLM_API_KEY），返回占位草稿")
        content = _build_placeholder_draft(title_path, evidence_chunks, warnings)

    word_count = len(content)
    evidence_ids = [
        f"{chunk.document_name}_{i}" for i, chunk in enumerate(evidence_chunks)
    ]

    return GenerationResult(
        outline_id=outline_id,
        title=title_path,
        content=content,
        evidence_ids=evidence_ids,
        word_count=word_count,
        status="draft",
        warnings=warnings,
    )


def _build_placeholder_draft(
    title_path: str,
    evidence_chunks: list[EvidenceChunk],
    warnings: list[str],
) -> str:
    """Build a placeholder draft when LLM is unavailable.

    This provides a structured template for manual writing,
    with all retrieved evidence summarized.
    """
    lines = [
        f"<!-- 占位草稿：{title_path} -->",
        "",
        "<!-- 以下是检索到的参考资料摘要，请基于此撰写正文： -->",
        "",
    ]
    for i, chunk in enumerate(evidence_chunks, 1):
        lines.append(f"**资料 {i}** [{chunk.document_name}] (相似度: {chunk.similarity:.2f})")
        lines.append(f"> {chunk.content[:300]}")
        lines.append("")
    lines.append("<!-- 请在此处撰写章节正文 -->")
    return "\n".join(lines)
