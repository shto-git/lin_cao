from __future__ import annotations

import re
from collections import defaultdict

from .domain import ChapterDraft, OutlineNode, QualityFinding


FORBIDDEN_PHRASES: dict[str, str] = {
    "据说": "改为可核验来源，例如文件名、统计年鉴或主管部门材料。",
    "大概": "改为明确数字，或标注为待补充数据。",
    "有关部门": "写明具体部门或责任单位。",
    "相关政策": "写明政策文件全称。",
}

METRIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "森林覆盖率": re.compile(r"森林覆盖率[^\d%]{0,16}(\d+(?:\.\d+)?)\s*%"),
    "草原综合植被盖度": re.compile(r"草原综合植被盖度[^\d%]{0,16}(\d+(?:\.\d+)?)\s*%"),
    "湿地保护率": re.compile(r"湿地保护率[^\d%]{0,16}(\d+(?:\.\d+)?)\s*%"),
}

FACT_MARKERS = ("根据", "依据", "按照", "统计", "监测", "调查", "年鉴", "数据显示")
NUMBER_WITH_UNIT = re.compile(r"\d+(?:\.\d+)?\s*(?:%|公顷|亩|万亩|平方公里|万元|亿元|年)")


def validate_document(outline: OutlineNode, drafts: list[ChapterDraft]) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    findings.extend(_validate_outline_coverage(outline, drafts))
    findings.extend(_validate_forbidden_phrases(drafts))
    findings.extend(_validate_evidence_required(drafts))
    findings.extend(_validate_metric_consistency(drafts))
    findings.extend(_validate_word_count(outline, drafts))
    findings.extend(_validate_figure_references(drafts))
    return findings


def _validate_outline_coverage(outline: OutlineNode, drafts: list[ChapterDraft]) -> list[QualityFinding]:
    draft_ids = {draft.outline_id for draft in drafts}
    findings: list[QualityFinding] = []
    for leaf in outline.leaves():
        if leaf.id not in draft_ids:
            findings.append(
                QualityFinding(
                    severity="warning",
                    code="missing_section",
                    message=f"缺少章节草稿：{leaf.title}",
                    location=leaf.id,
                    suggestion="生成或补录该章节后再做全文质检。",
                )
            )
    return findings


def _validate_forbidden_phrases(drafts: list[ChapterDraft]) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for draft in drafts:
        for phrase, suggestion in FORBIDDEN_PHRASES.items():
            if phrase in draft.content:
                findings.append(
                    QualityFinding(
                        severity="warning",
                        code="forbidden_phrase",
                        message=f"发现不规范表述：{phrase}",
                        location=draft.outline_id,
                        suggestion=suggestion,
                    )
                )
    return findings


def _validate_evidence_required(drafts: list[ChapterDraft]) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    for draft in drafts:
        has_fact = any(marker in draft.content for marker in FACT_MARKERS)
        has_number = NUMBER_WITH_UNIT.search(draft.content) is not None
        if (has_fact or has_number) and not draft.evidence_ids:
            findings.append(
                QualityFinding(
                    severity="error",
                    code="missing_evidence",
                    message="章节包含事实、数据或政策语气，但没有绑定来源。",
                    location=draft.outline_id,
                    suggestion="先从资料库检索依据，绑定 evidence_id 后再进入正式草稿。",
                )
            )
    return findings


def _validate_metric_consistency(drafts: list[ChapterDraft]) -> list[QualityFinding]:
    values: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for draft in drafts:
        for metric, pattern in METRIC_PATTERNS.items():
            for match in pattern.finditer(draft.content):
                values[metric].append((draft.outline_id, match.group(1)))

    findings: list[QualityFinding] = []
    for metric, hits in values.items():
        distinct = sorted({value for _, value in hits})
        if len(distinct) > 1:
            locations = ", ".join(f"{outline_id}={value}%" for outline_id, value in hits)
            findings.append(
                QualityFinding(
                    severity="error",
                    code="metric_conflict",
                    message=f"{metric} 出现多个数值：{locations}",
                    location="full_document",
                    suggestion="确认是否为不同年份或不同范围；若不是，应统一指标口径。",
                )
            )
    return findings



def _validate_word_count(outline: OutlineNode, drafts: list[ChapterDraft]) -> list[QualityFinding]:
    """Check if chapter word count deviates more than 30% from target."""
    findings: list[QualityFinding] = []
    # Build a map of outline_id -> target_words
    target_map: dict[str, int] = {}
    for leaf in outline.leaves():
        target_map[leaf.id] = leaf.target_words

    for draft in drafts:
        target = target_map.get(draft.outline_id, 0)
        if target <= 0:
            continue
        actual = len(draft.content)
        ratio = actual / target if target > 0 else 0
        if ratio < 0.7:
            findings.append(
                QualityFinding(
                    severity="warning",
                    code="word_count_low",
                    message=f"「{draft.title}」字数 {actual}，低于目标 {target} 的 70%",
                    location=draft.outline_id,
                    suggestion=f"建议扩写至 {int(target * 0.7)} 字以上，或调整字数分配。",
                )
            )
        elif ratio > 1.3:
            findings.append(
                QualityFinding(
                    severity="warning",
                    code="word_count_high",
                    message=f"「{draft.title}」字数 {actual}，超过目标 {target} 的 130%",
                    location=draft.outline_id,
                    suggestion=f"建议压缩至 {int(target * 1.3)} 字以内，或调整字数分配。",
                )
            )
    return findings


def _validate_figure_references(drafts: list[ChapterDraft]) -> list[QualityFinding]:
    """Check if chapters mention figures/tables but lack references."""
    findings: list[QualityFinding] = []
    figure_keywords = ["图", "表", "图表", "示意图", "统计表"]
    for draft in drafts:
        for kw in figure_keywords:
            if kw in draft.content:
                # Check if there's a proper figure reference like "图1-1" or "表3-2"
                ref_pattern = re.compile(rf"{kw}\s*\d+[-─‑]\d+")
                if not ref_pattern.search(draft.content):
                    findings.append(
                        QualityFinding(
                            severity="info",
                            code="missing_figure_ref",
                            message=f"「{draft.title}」提到「{kw}」但缺少规范编号（如{kw}1-1）",
                            location=draft.outline_id,
                            suggestion=f"请为{kw}添加规范编号，格式：{kw}X-Y（章节-序号）",
                        )
                    )
                    break  # One finding per chapter for this check
    return findings
