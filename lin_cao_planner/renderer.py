from __future__ import annotations

from .domain import OutlineNode, QualityFinding, SectionBrief


def render_outline(outline: OutlineNode) -> str:
    lines = [f"# {outline.title}", "", f"目标字数：{outline.target_words}", ""]
    for chapter in outline.children:
        lines.append(f"## {chapter.title}（约 {chapter.target_words} 字）")
        for requirement in chapter.requirements:
            lines.append(f"- {requirement}")
        lines.append("")
        for section in chapter.children:
            lines.append(f"### {section.title}（约 {section.target_words} 字）")
            lines.append(f"- 依据类型：{', '.join(section.required_evidence_types)}")
            for requirement in section.requirements:
                lines.append(f"- {requirement}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_retrieval_plan(briefs: list[SectionBrief]) -> str:
    lines = ["# 章节检索计划", ""]
    for brief in briefs:
        lines.append(f"## {brief.outline_id} {' / '.join(brief.title_path)}")
        lines.append(f"- 目标字数：{brief.target_words}")
        lines.append(f"- 依据类型：{', '.join(brief.required_evidence_types)}")
        lines.append("- 检索问题：")
        for query in brief.retrieval_queries:
            lines.append(f"  - {query}")
        lines.append("- 写作约束：")
        for constraint in brief.writing_constraints:
            lines.append(f"  - {constraint}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_quality_report(findings: list[QualityFinding]) -> str:
    lines = ["# 质检报告", ""]
    if not findings:
        lines.append("未发现问题。")
        return "\n".join(lines) + "\n"
    for index, finding in enumerate(findings, start=1):
        lines.append(f"## {index}. {finding.code} [{finding.severity}]")
        lines.append(f"- 位置：{finding.location}")
        lines.append(f"- 问题：{finding.message}")
        lines.append(f"- 建议：{finding.suggestion}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
