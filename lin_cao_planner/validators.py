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
