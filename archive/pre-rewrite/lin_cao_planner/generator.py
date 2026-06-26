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


def generate_draft_skip_llm(
    outline_id: str,
    title_path: str,
    target_words: int,
    requirements: list[str],
    evidence_types: list[str],
    constraints: list[str],
    evidence_chunks: list[EvidenceChunk],
    skip_llm: bool = False,
) -> GenerationResult:
    """Generate a chapter draft, with option to skip LLM for testing."""
    warnings: list[str] = []

    if skip_llm:
        warnings.append("LLM 已跳过（skip_llm=true），返回模拟草稿")
        # 生成模拟草稿：基于大纲信息生成模板内容
        simulated = _build_simulated_draft(title_path, target_words, requirements, evidence_types, evidence_chunks)
        word_count = len(simulated)
        evidence_ids = [f"{chunk.document_name}_{i}" for i, chunk in enumerate(evidence_chunks)]
        return GenerationResult(
            outline_id=outline_id,
            title=title_path,
            content=simulated,
            evidence_ids=evidence_ids,
            word_count=word_count,
            status="draft",
            warnings=warnings,
        )

    # 正常 LLM 调用
    return generate_chapter_draft(
        outline_id=outline_id,
        title_path=title_path,
        target_words=target_words,
        requirements=requirements,
        evidence_types=evidence_types,
        constraints=constraints,
        evidence_chunks=evidence_chunks,
    )


def _build_simulated_draft(
    title_path: str,
    target_words: int,
    requirements: list[str],
    evidence_types: list[str],
    evidence_chunks: list[EvidenceChunk],
) -> str:
    """Build a simulated draft for testing without LLM."""
    lines = [
        f"<!-- 模拟草稿（skip_llm=true）: {title_path} -->",
        "",
        f"<!-- 目标字数: {target_words} 字 -->",
        "",
    ]

    if evidence_chunks:
        lines.append("## 参考资料摘要")
        lines.append("")
        for i, chunk in enumerate(evidence_chunks, 1):
            lines.append(f"{i}. **[来源: {chunk.document_name}]**")
            lines.append(f"   {chunk.content[:200]}...")
            lines.append("")
    else:
        lines.append("> **[缺资料提示: 本章节未检索到相关参考资料，请先上传以下类型资料：]**")
        evidence_types_str = "、".join(evidence_types) if evidence_types else "政策文件、统计数据、案例"
        lines.append(f"> **{evidence_types_str}]**")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"<!-- 此处将生成约 {target_words} 字的正文内容 -->")
    lines.append(f"<!-- 写作要求：-->")
    for req in requirements:
        lines.append(f"<!-- - {req} -->")

    return "\n".join(lines)


# ── Draft Modification Functions (Phase 2) ──────────────

EXPAND_SYSTEM_PROMPT = """你是一位资深林草规划编制专家。你的任务是基于已有的草稿内容进行扩写。

## 扩写原则
1. 保留现有草稿的核心内容和结构
2. 根据目标字数，补充更多细节、数据、案例
3. 补充的内容必须基于提供的参考资料
4. 不编造数据，缺少依据时标注"待补充"
5. 保持与现有内容的风格一致
6. 新增内容标注来源 [来源: 文件名]
"""

COMPRESS_SYSTEM_PROMPT = """你是一位资深林草规划编制专家。你的任务是基于已有的草稿内容进行压缩。

## 压缩原则
1. 保留核心观点、关键数据和重要政策
2. 删除重复表述、冗余过渡句
3. 保持逻辑结构完整
4. 数据精度不降低
5. 压缩后内容应独立可读
"""

REWRITE_SYSTEM_PROMPT = """你是一位资深林草规划编制专家。你的任务根据用户的修改指令重写草稿。

## 改写原则
1. 理解用户的修改意图
2. 保留草稿中不需要修改的部分
3. 对需要修改的部分按指令进行调整
4. 改写后内容连贯、完整
5. 保持专业规范
"""


def expand_draft(
    draft_content: str,
    target_words: int,
    evidence_chunks: list[EvidenceChunk],
    llm_client: LLMClient | None = None,
) -> GenerationResult:
    """基于现有草稿进行扩写，增加字数到 target_words。"""
    warnings: list[str] = []
    evidence_text = "\n\n".join(chunk.format_for_prompt() for chunk in evidence_chunks)
    if not evidence_text:
        evidence_text = "（暂无检索到的参考资料）"

    user_prompt = f"""请对以下草稿进行扩写，目标字数 {target_words} 字。

## 当前草稿（{len(draft_content)} 字）

{draft_content}

## 参考资料

{evidence_text}

## 扩写要求
1. 保留现有核心内容
2. 补充细节、案例、数据
3. 不编造，缺依据时标注"待补充"
4. 新增内容标注来源

请输出扩写后的完整内容："""

    client = llm_client or LLMClient()
    if client.config.api_key:
        try:
            content = client.complete(EXPAND_SYSTEM_PROMPT, user_prompt, temperature=0.3, max_tokens=min(target_words * 2, 8000))
        except RuntimeError as exc:
            warnings.append(f"扩写失败: {exc}")
            content = draft_content
    else:
        warnings.append("未配置 LLM API Key，返回原草稿")
        content = draft_content

    return GenerationResult(
        outline_id="expand",
        title="扩写结果",
        content=content,
        word_count=len(content),
        status="draft",
        warnings=warnings,
    )


def compress_draft(
    draft_content: str,
    target_words: int,
    llm_client: LLMClient | None = None,
) -> GenerationResult:
    """压缩草稿，减少字数到 target_words。"""
    warnings: list[str] = []

    user_prompt = f"""请对以下草稿进行压缩，目标字数 {target_words} 字。

## 当前草稿（{len(draft_content)} 字）

{draft_content}

## 压缩要求
1. 保留核心观点、关键数据
2. 删除冗余表述
3. 保持逻辑完整
4. 数据精度不降低

请输出压缩后的完整内容："""

    client = llm_client or LLMClient()
    if client.config.api_key:
        try:
            content = client.complete(COMPRESS_SYSTEM_PROMPT, user_prompt, temperature=0.3, max_tokens=min(target_words * 2, 8000))
        except RuntimeError as exc:
            warnings.append(f"压缩失败: {exc}")
            content = draft_content
    else:
        warnings.append("未配置 LLM API Key，返回原草稿")
        content = draft_content

    return GenerationResult(
        outline_id="compress",
        title="压缩结果",
        content=content,
        word_count=len(content),
        status="draft",
        warnings=warnings,
    )


def rewrite_draft(
    draft_content: str,
    instruction: str,
    llm_client: LLMClient | None = None,
) -> GenerationResult:
    """根据用户指令重写草稿。"""
    warnings: list[str] = []

    user_prompt = f"""请根据以下修改指令重写草稿。

## 当前草稿

{draft_content}

## 修改指令

{instruction}

## 要求
1. 按指令修改相应内容
2. 未涉及的部分保持原样
3. 保持专业规范和风格一致

请输出重写后的完整内容："""

    client = llm_client or LLMClient()
    if client.config.api_key:
        try:
            content = client.complete(REWRITE_SYSTEM_PROMPT, user_prompt, temperature=0.3, max_tokens=8000)
        except RuntimeError as exc:
            warnings.append(f"改写失败: {exc}")
            content = draft_content
    else:
        warnings.append("未配置 LLM API Key，返回原草稿")
        content = draft_content

    return GenerationResult(
        outline_id="rewrite",
        title="改写结果",
        content=content,
        word_count=len(content),
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



# ── Multi-Model Router (Phase 3 P3-4) ────────────────────

@dataclass(slots=True)
class ModelConfig:
    """Model configuration with pricing."""
    name: str
    provider: str  # openai, openrouter, deepseek
    base_url: str
    api_key: str
    input_price_per_1k: float   # $/1K input tokens
    output_price_per_1k: float  # $/1K output tokens
    max_tokens: int = 8000
    is_free: bool = False

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        if self.is_free:
            return 0.0
        return (input_tokens / 1000) * self.input_price_per_1k + (output_tokens / 1000) * self.output_price_per_1k


# 可用模型列表（按能力从高到低）
AVAILABLE_MODELS: list[ModelConfig] = [
    ModelConfig(
        name="gpt-5.5",
        provider="openai",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        input_price_per_1k=0.0,
        output_price_per_1k=0.0,
        is_free=True,  # 通过 Codex CLI 免费调用
    ),
    ModelConfig(
        name="deepseek-chat",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key=os.environ.get("LINCAO_LLM_API_KEY", ""),
        input_price_per_1k=0.001,
        output_price_per_1k=0.002,
        is_free=True,
    ),
    ModelConfig(
        name="qwen/qwen3-coder:free",
        provider="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        input_price_per_1k=0.0,
        output_price_per_1k=0.0,
        is_free=True,
    ),
]


def select_model(
    task_type: str = "generation",
    prefer_free: bool = True,
) -> tuple[LLMClient | None, ModelConfig | None]:
    """Select the best available model for the task.
    
    Task types:
        - "outline": 大纲生成（结构化，中等推理）
        - "generation": 章节起草（需要最强能力）
        - "expansion": 扩写（需要创造力）
        - "compression": 压缩（中等推理）
        - "rewrite": 改写（需要指令遵循）
        - "review": 质检（需要强推理）
    Returns: (LLMClient, ModelConfig) or (None, None)
    """
    # 按优先级排序：generation 用最强，其他用免费够用
    generation_priority = ["gpt-5.5", "deepseek-chat", "qwen/qwen3-coder:free"]
    
    if task_type == "generation":
        priority = generation_priority
    else:
        # 非核心生成任务：优先免费模型
        priority = ["deepseek-chat", "qwen/qwen3-coder:free", "gpt-5.5"]

    for model_name in priority:
        model = next((m for m in AVAILABLE_MODELS if m.name == model_name), None)
        if model and (model.api_key or model.provider == "openai"):
            # 创建配置的 LLMClient
            config = LLMConfig(
                api_key=model.api_key,
                base_url=model.base_url,
                model=model.name,
                max_tokens=model.max_tokens,
            )
            client = LLMClient(config)
            return client, model

    return None, None


# ── Cost Tracker ─────────────────────────────────────────

_cost_stats: dict[str, float] = {"input_tokens": 0, "output_tokens": 0, "usd": 0.0}


def track_cost(input_tokens: int, output_tokens: int, model: ModelConfig | None = None) -> None:
    """Track token usage and cost for monitoring."""
    _cost_stats["input_tokens"] += input_tokens
    _cost_stats["output_tokens"] += output_tokens
    if model:
        _cost_stats["usd"] += model.estimate_cost(input_tokens, output_tokens)


def get_cost_stats() -> dict[str, float]:
    """Get accumulated cost statistics."""
    return dict(_cost_stats)


def reset_cost_stats() -> None:
    """Reset cost tracking."""
    _cost_stats.update({"input_tokens": 0, "output_tokens": 0, "usd": 0.0})
